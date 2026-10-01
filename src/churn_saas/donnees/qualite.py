"""Data contract - the checks every batch must pass before it reaches a model.

Training and monthly scoring run the **same** contract. A batch that differs from what the
model learnt on - a new unit in a numeric column, an unknown category, a duplicated
account - produces wrong scores without raising anything. The contract turns those silent
differences into a status a person can read: conforming, to watch, or blocking.

The checks are declared as data (`PLAGES`, `COHERENCES`) rather than buried in code, so the
notebook can display the contract itself and the jury can read what is enforced.

Had it existed in phase 3, this contract would have blocked both silent defects found in
phase 4: 570 support delays lost on conversion (a 21.4 % missing rate against a 10 % watch
threshold), and 960 ISO dates read with day and month swapped (the calendar check).
"""

from __future__ import annotations

import pandas as pd

from .profilage import SEUIL_MANQUANTS_CRITIQUE, SEUIL_MANQUANTS_SURVEILLANCE
from .schema import ROLES_COLONNES
from .silver import (
    COLONNES_A_NORMALISER,
    nettoyer_decimal_texte,
    parser_dates_multiformat,
    pertes_de_conversion,
)

CONFORME = "conforme"
SURVEILLANCE = "à surveiller"
BLOQUANT = "bloquant"
_GRAVITE = {CONFORME: 0, SURVEILLANCE: 1, BLOQUANT: 2}

# Value ranges that hold by definition. A value outside is a defect, not an outlier:
# extreme but plausible values (a very large MRR) are real customers and stay.
PLAGES: dict[str, tuple[float | None, float | None]] = {
    "taux_adoption_pct": (0, 100),
    "csat": (1, 5),
    "anciennete_mois": (0, None),
    "sieges_souscrits": (0, None),
    "utilisateurs_actifs": (0, None),
    "connexions_30j": (0, None),
    "heures_usage_30j": (0, None),
    "fonctionnalites_total": (0, None),
    "fonctionnalites_utilisees": (0, None),
    "nb_integrations": (0, None),
    "derniere_connexion_jours": (0, None),
    "tickets_support_90j": (0, None),
    "delai_reponse_support_h": (0, None),
    "retards_paiement_12m": (0, None),
    "revenu_mensuel_recurrent_eur": (0, None),
    "valeur_vie_client_eur": (0, None),
}

# Business invariants between two columns: (left, right), meaning left <= right.
COHERENCES: tuple[tuple[str, str], ...] = (
    ("utilisateurs_actifs", "sieges_souscrits"),
    ("fonctionnalites_utilisees", "fonctionnalites_total"),
)

# The adoption rate is the active-to-seat ratio, rounded at the source. The relation is
# what makes an exact reconstruction possible later; it must therefore keep holding.
TOLERANCE_TAUX_ADOPTION_PTS = 0.5

ROLES_SANS_SEUIL_DE_MANQUANTS = {"texte libre"}

# The source states the weekday of each subscription. It is a free, independent witness
# of the date parsing: a date read with day and month swapped almost never falls on the
# stated weekday. This check is what exposed the ISO dates read as YYYY-DD-MM.
JOURS_SEMAINE = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _ligne(controle: str, attendu: str, observe: str, statut: str) -> dict[str, str]:
    return {"contrôle": controle, "attendu": attendu, "observé": observe, "statut": statut}


def _colonnes_attendues(silver: pd.DataFrame) -> dict[str, str]:
    absentes = sorted(set(ROLES_COLONNES) - set(silver.columns))
    return _ligne(
        "Colonnes attendues présentes",
        f"{len(ROLES_COLONNES)} colonnes documentées",
        f"absentes : {', '.join(absentes)}" if absentes else "toutes présentes",
        BLOQUANT if absentes else CONFORME,
    )


def _conversions(
    brut: pd.DataFrame, colonnes_numeriques: list[str], colonnes_dates: list[str]
) -> dict[str, str]:
    source = brut.drop_duplicates()
    pertes: dict[str, int] = {}
    for col in [c for c in colonnes_numeriques if c in source.columns]:
        n = int(pertes_de_conversion(source[col], nettoyer_decimal_texte(source[col])).sum())
        if n:
            pertes[col] = n
    for col in [c for c in colonnes_dates if c in source.columns]:
        n = int(pertes_de_conversion(source[col], parser_dates_multiformat(source[col])).sum())
        if n:
            pertes[col] = n
    return _ligne(
        "Aucune valeur perdue à la conversion",
        "0 valeur présente devenue manquante",
        ", ".join(f"{c} : {n}" for c, n in pertes.items()) if pertes else "0",
        BLOQUANT if pertes else CONFORME,
    )


def _unicite(silver: pd.DataFrame, cle: str) -> dict[str, str]:
    if cle not in silver.columns:
        return _ligne(f"`{cle}` unique", "1 ligne par compte", "colonne absente", BLOQUANT)
    doublons = int(silver[cle].dropna().duplicated().sum())
    return _ligne(
        f"`{cle}` unique",
        "1 ligne par compte",
        f"{doublons} compte(s) en double",
        BLOQUANT if doublons else CONFORME,
    )


def _plages(silver: pd.DataFrame) -> dict[str, str]:
    hors: list[str] = []
    for col, (bas, haut) in PLAGES.items():
        if col not in silver.columns:
            continue
        valeurs = pd.to_numeric(silver[col], errors="coerce")
        n = int((valeurs < bas).sum()) if bas is not None else 0
        if haut is not None:
            n += int((valeurs > haut).sum())
        if n:
            hors.append(f"{col} : {n}")
    return _ligne(
        "Valeurs dans leur plage de définition",
        f"{len(PLAGES)} plages (taux 0-100, CSAT 1-5, compteurs >= 0)",
        ", ".join(hors) if hors else "aucune valeur hors plage",
        BLOQUANT if hors else CONFORME,
    )


def _coherences(silver: pd.DataFrame) -> dict[str, str]:
    ecarts: list[str] = []
    for gauche, droite in COHERENCES:
        if {gauche, droite} <= set(silver.columns):
            g = pd.to_numeric(silver[gauche], errors="coerce")
            d = pd.to_numeric(silver[droite], errors="coerce")
            n = int((g > d).sum())
            if n:
                ecarts.append(f"{gauche} > {droite} : {n}")
    colonnes = {"taux_adoption_pct", "utilisateurs_actifs", "sieges_souscrits"}
    if colonnes <= set(silver.columns):
        taux = pd.to_numeric(silver["taux_adoption_pct"], errors="coerce")
        actifs = pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce").astype(float)
        sieges = pd.to_numeric(silver["sieges_souscrits"], errors="coerce").astype(float)
        attendu = actifs / sieges.where(sieges > 0) * 100
        n = int(((taux - attendu).abs() > TOLERANCE_TAUX_ADOPTION_PTS).sum())
        if n:
            ecarts.append(f"taux_adoption_pct ≠ actifs / sièges : {n}")
    return _ligne(
        "Invariants métier respectés",
        "actifs <= sièges, utilisées <= total, taux d'adoption = actifs / sièges",
        ", ".join(ecarts) if ecarts else "aucun écart",
        BLOQUANT if ecarts else CONFORME,
    )


def _calendrier(silver: pd.DataFrame) -> dict[str, str] | None:
    if not {"date_souscription", "jour_souscription"} <= set(silver.columns):
        return None
    dates = pd.to_datetime(silver["date_souscription"], errors="coerce")
    attendu = dates.dt.dayofweek.map(dict(enumerate(JOURS_SEMAINE)))
    declare = silver["jour_souscription"].astype("string").str.strip().str.casefold()
    comparables = attendu.notna() & declare.notna()
    ecarts = int((attendu[comparables] != declare[comparables]).sum())
    return _ligne(
        "Date cohérente avec le jour de semaine déclaré",
        "date_souscription tombe le jour indiqué par jour_souscription",
        f"{ecarts} date(s) en désaccord sur {int(comparables.sum())}",
        BLOQUANT if ecarts else CONFORME,
    )


def _modalites(
    silver: pd.DataFrame, reference: dict[str, list[str]] | None
) -> list[dict[str, str]]:
    colonnes = [c for c in COLONNES_A_NORMALISER if c in silver.columns]
    variantes = [
        c
        for c in colonnes
        if silver[c].dropna().astype(str).nunique()
        != silver[c].dropna().astype(str).str.strip().str.casefold().nunique()
    ]
    lignes = [
        _ligne(
            "Une seule orthographe par modalité",
            "aucune variante de casse ou d'espaces",
            f"variantes : {', '.join(variantes)}" if variantes else "aucune variante",
            BLOQUANT if variantes else CONFORME,
        )
    ]
    if reference is not None:
        inconnues = []
        for col in colonnes:
            nouvelles = sorted(set(silver[col].dropna().astype(str)) - set(reference.get(col, [])))
            if nouvelles:
                inconnues.append(f"{col} : {', '.join(nouvelles[:3])}")
        # To watch, not blocking: an unknown category is scored as "none of the known
        # ones" by the encoder. The batch remains usable; the drift must be looked at.
        lignes.append(
            _ligne(
                "Modalités connues à l'entraînement",
                "aucune modalité nouvelle",
                "; ".join(inconnues) if inconnues else "aucune modalité nouvelle",
                SURVEILLANCE if inconnues else CONFORME,
            )
        )
    return lignes


def _manquants(silver: pd.DataFrame, surveillance: float, critique: float) -> dict[str, str]:
    colonnes = [
        c
        for c, role in ROLES_COLONNES.items()
        if c in silver.columns and role not in ROLES_SANS_SEUIL_DE_MANQUANTS
    ]
    taux = (silver[colonnes].isna().mean() * 100).sort_values(ascending=False)
    critiques = taux[taux > critique]
    a_surveiller = taux[(taux > surveillance) & (taux <= critique)]
    if not critiques.empty:
        statut, offenders = BLOQUANT, critiques
    elif not a_surveiller.empty:
        statut, offenders = SURVEILLANCE, a_surveiller
    else:
        statut, offenders = CONFORME, taux.head(1)
    observe = ", ".join(f"{c} : {v:.1f} %" for c, v in offenders.items())
    return _ligne(
        "Taux de manquants par colonne",
        f"<= {surveillance:.0f} % (surveillance), <= {critique:.0f} % (blocage)",
        observe if statut != CONFORME else f"maximum {observe}",
        statut,
    )


def _cible(silver: pd.DataFrame, cible: str) -> dict[str, str] | None:
    if cible not in silver.columns:
        return None
    valeurs = set(pd.to_numeric(silver[cible], errors="coerce").dropna().unique())
    hors = sorted(valeurs - {0, 1})
    return _ligne(
        f"Cible `{cible}` binaire",
        "valeurs dans {0, 1}, aucune manquante",
        f"hors domaine : {hors}" if hors else f"{int(silver[cible].isna().sum())} manquante(s)",
        BLOQUANT if hors or silver[cible].isna().any() else CONFORME,
    )


def referentiel_modalites(silver: pd.DataFrame) -> dict[str, list[str]]:
    """Categories seen at training time, to compare each later batch against."""
    return {
        col: sorted(silver[col].dropna().astype(str).unique())
        for col in COLONNES_A_NORMALISER
        if col in silver.columns
    }


def verifier_contrat(
    silver: pd.DataFrame,
    brut: pd.DataFrame | None = None,
    colonnes_numeriques: list[str] | None = None,
    colonnes_dates: list[str] | None = None,
    modalites_reference: dict[str, list[str]] | None = None,
    cle_compte: str = "client_id",
    cible: str = "churn",
    seuil_surveillance: float = SEUIL_MANQUANTS_SURVEILLANCE,
    seuil_critique: float = SEUIL_MANQUANTS_CRITIQUE,
) -> pd.DataFrame:
    """Run every check and return one row per check: what is expected, what is observed.

    `brut` enables the conversion check, which compares the source with its typed form.
    It must be the raw text, before `construire_silver`: once converted, a lost value
    looks exactly like a missing one.
    """
    lignes = [_colonnes_attendues(silver)]
    if brut is not None:
        lignes.append(_conversions(brut, colonnes_numeriques or [], colonnes_dates or []))
    lignes += [
        _unicite(silver, cle_compte),
        _plages(silver),
        _coherences(silver),
        *[ligne for ligne in (_calendrier(silver),) if ligne is not None],
        *_modalites(silver, modalites_reference),
        _manquants(silver, seuil_surveillance, seuil_critique),
    ]
    ligne_cible = _cible(silver, cible)
    if ligne_cible is not None:
        lignes.append(ligne_cible)
    return pd.DataFrame(lignes)


def statut_global(contrat: pd.DataFrame) -> str:
    """The most severe status of the table."""
    return max(contrat["statut"], key=_GRAVITE.__getitem__)


def exiger_contrat(contrat: pd.DataFrame) -> None:
    """Stop the chain when a blocking check fails, naming every failing check."""
    bloquants = contrat.loc[contrat["statut"] == BLOQUANT]
    if bloquants.empty:
        return
    detail = "\n".join(
        f"  - {row['contrôle']} : {row['observé']}" for _, row in bloquants.iterrows()
    )
    raise ValueError(f"Contrat de données non respecté :\n{detail}")
