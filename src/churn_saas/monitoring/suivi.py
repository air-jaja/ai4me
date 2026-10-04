"""Monthly monitoring: a batch against the reference profile, rule by rule (phase 11, A2-A4).

    M5  combined drift: PSI over the key-variable threshold on one key variable, or over the
        moderate threshold on three model variables, or on the score;
    M8  missing values: a variable's share above twice its training share, as received;
    M9  flagged accounts: a gap over 30 % against the previous month.

Each function returns the evidence (a table or a dict) and the verdict; `mesures_du_mois`
turns the verdicts into the {indicator: triggered} mapping `evaluer_alertes` reads. A
verdict warns, it never blocks the scoring (M6).
"""

from __future__ import annotations

import pandas as pd

from .alertes import (
    ECART_VOLUME_SIGNALES,
    FACTEUR_MANQUANTS,
    NB_VARIABLES_PSI_MODERE,
    SEUIL_PSI_MODERE,
    SEUIL_PSI_SCORE,
    SEUIL_PSI_VARIABLE_CLE,
)
from .derive import psi_contre_profil

INDICATEUR_DERIVE = "Dérive des entrées et du score (PSI)"
INDICATEUR_MANQUANTS = "Taux de manquants à l'entrée"
INDICATEUR_VOLUME = "Volume de comptes signalés"


def derive_combinee(profil: dict, lot: pd.DataFrame, score: pd.Series) -> tuple[pd.DataFrame, dict]:
    """M5: per-variable PSI against the profile, the score's PSI, and the combined verdict."""
    cles = set(profil["variables_cles"])
    lignes = [
        {
            "variable": colonne,
            "variable clé": colonne in cles,
            "psi": round(psi_contre_profil(reference, lot[colonne]), 4),
        }
        for colonne, reference in profil["variables"].items()
        if colonne in lot.columns
    ]
    table = pd.DataFrame(lignes).sort_values("psi", ascending=False).reset_index(drop=True)
    psi_score = round(psi_contre_profil(profil["score"], score), 4)
    cles_hautes = table.loc[table["variable clé"] & (table["psi"] > SEUIL_PSI_VARIABLE_CLE)]
    moderees = table.loc[table["psi"] > SEUIL_PSI_MODERE]
    verdict = {
        "variables clés au-dessus de 0,25": cles_hautes["variable"].tolist(),
        "variables au-dessus de 0,10": moderees["variable"].tolist(),
        "psi du score": psi_score,
        "déclenchée": bool(
            len(cles_hautes)
            or len(moderees) >= NB_VARIABLES_PSI_MODERE
            or psi_score > SEUIL_PSI_SCORE
        ),
    }
    return table, verdict


def manquants_relatifs(profil: dict, lot_recu: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """M8: missing share of each variable as received, against twice its training share.

    A variable never missing in training alerts on its first missing value: twice zero is
    zero, and a value that used to arrive and no longer does is a collection change.
    """
    lignes = []
    for colonne, part_reference in profil["manquants_a_l_entree"].items():
        if colonne not in lot_recu.columns:
            continue
        part = float(lot_recu[colonne].isna().mean())
        seuil = FACTEUR_MANQUANTS * part_reference
        lignes.append(
            {
                "variable": colonne,
                "part à l'entraînement": round(part_reference, 4),
                "part du lot": round(part, 4),
                "seuil": round(seuil, 4),
                "alerte": part > seuil,
            }
        )
    table = pd.DataFrame(lignes).sort_values("part du lot", ascending=False).reset_index(drop=True)
    verdict = {
        "variables en alerte": table.loc[table["alerte"], "variable"].tolist(),
        "déclenchée": bool(table["alerte"].any()),
    }
    return table, verdict


def ecart_volume(signales: int, signales_precedent: int | None) -> dict:
    """M9: gap in flagged accounts against the previous month; none without a previous one."""
    if not signales_precedent:
        return {
            "comptes signalés": signales,
            "mois précédent": None,
            "écart": None,
            "déclenchée": False,
        }
    ecart = abs(signales - signales_precedent) / signales_precedent
    return {
        "comptes signalés": int(signales),
        "mois précédent": int(signales_precedent),
        "écart": round(ecart, 4),
        "déclenchée": ecart > ECART_VOLUME_SIGNALES,
    }


def mesures_du_mois(derive: dict, manquants: dict, volume: dict) -> dict[str, bool]:
    """The verdicts as `evaluer_alertes` reads them: indicator -> triggered."""
    return {
        INDICATEUR_DERIVE: derive["déclenchée"],
        INDICATEUR_MANQUANTS: manquants["déclenchée"],
        INDICATEUR_VOLUME: volume["déclenchée"],
    }


# --- Quarterly review (phase 11, part B) ----------------------------------------------------
INDICATEUR_COUVERTURE = "Couverture du revenu à risque"
INDICATEUR_SUISSE = "Rappel sur le segment Suisse"
INDICATEUR_RETENTION = "Rétention des comptes traités"
INDICATEUR_PR_AUC = "PR-AUC en production"


def _intervalle_bootstrap(valeurs, tirages: int, generateur) -> list[float]:
    import numpy as np

    valeurs = np.asarray(valeurs, dtype=float)
    moyennes = [
        valeurs[generateur.integers(0, len(valeurs), len(valeurs))].mean() for _ in range(tirages)
    ]
    return [round(float(np.quantile(moyennes, q)), 4) for q in (0.025, 0.975)]


def couverture_revenu(issues: pd.DataFrame) -> dict:
    """M1: MRR of the departed accounts the list flagged, over the MRR of all departed (R8)."""
    from .alertes import CIBLE_COUVERTURE_REVENU

    partis = issues[issues["parti"]]
    expose = float(partis["mrr"].sum())
    couvert = float(partis.loc[partis["signale"], "mrr"].sum())
    part = couvert / expose if expose else None
    return {
        "MRR exposé (€)": round(expose, 0),
        "MRR couvert (€)": round(couvert, 0),
        "part couverte": round(part, 4) if part is not None else None,
        "déclenchée": bool(part is not None and part < CIBLE_COUVERTURE_REVENU),
    }


def rappel_segment(
    issues: pd.DataFrame,
    colonne: str,
    modalite: str,
    ratio: float,
    taille_min: int,
    departs_min: int,
    generateur,
    tirages: int = 1000,
) -> dict:
    """M7: recall of the flagged list on one segment, against the R9 criterion.

    Triggered when the segment is conclusive, its recall under `ratio` x the global recall,
    and its bootstrap interval excludes the global recall.
    """
    partis = issues[issues["parti"]]
    rappel_global = float(partis["signale"].mean()) if len(partis) else float("nan")
    segment = issues[issues[colonne] == modalite]
    partis_segment = segment[segment["parti"]]
    concluant = len(segment) >= taille_min and len(partis_segment) >= departs_min
    if not len(partis_segment):
        return {"comptes": int(len(segment)), "départs": 0, "concluant": False, "déclenchée": False}
    rappel = float(partis_segment["signale"].mean())
    intervalle = _intervalle_bootstrap(partis_segment["signale"], tirages, generateur)
    sous_le_ratio = rappel < ratio * rappel_global
    exclut = not intervalle[0] <= rappel_global <= intervalle[1]
    return {
        "comptes": int(len(segment)),
        "départs": int(len(partis_segment)),
        "rappel": round(rappel, 4),
        "intervalle du rappel": intervalle,
        "rappel global": round(rappel_global, 4),
        "concluant": bool(concluant),
        "déclenchée": bool(concluant and sous_le_ratio and exclut),
    }


def retention_contre_temoin(issues: pd.DataFrame, generateur, tirages: int = 1000) -> dict:
    """Efficacy = relative churn reduction of the contacted accounts against the control
    group; the rule triggers when its interval reaches zero (not significant)."""
    import numpy as np

    contact = issues.loc[issues["groupe"] == "contact", "parti"].to_numpy(dtype=float)
    temoin = issues.loc[issues["groupe"] == "temoin", "parti"].to_numpy(dtype=float)
    if not len(contact) or not len(temoin) or not temoin.mean():
        return {
            "comptes contactés": int(len(contact)),
            "comptes témoins": int(len(temoin)),
            "efficacité mesurée": None,
            "déclenchée": True,
        }

    def mesure(c, t):
        return (t.mean() - c.mean()) / t.mean() if t.mean() else np.nan

    valeurs = [
        mesure(generateur.choice(contact, len(contact)), generateur.choice(temoin, len(temoin)))
        for _ in range(tirages)
    ]
    intervalle = [round(float(np.nanquantile(valeurs, q)), 4) for q in (0.025, 0.975)]
    return {
        "comptes contactés": int(len(contact)),
        "comptes témoins": int(len(temoin)),
        "départs, contactés": round(float(contact.mean()), 4),
        "départs, témoins": round(float(temoin.mean()), 4),
        "efficacité mesurée": round(float(mesure(contact, temoin)), 4),
        "intervalle 95 %": intervalle,
        "déclenchée": bool(intervalle[0] <= 0),
    }


def pr_auc_en_production(issues: pd.DataFrame, reference: float) -> dict:
    """PR-AUC on the accounts NOT contacted - a contact changes the outcome it would score -
    against the reference; triggered beyond the relative drop of the configuration."""
    from sklearn.metrics import average_precision_score

    from ..config import SEUIL_DEGRADATION_PR_AUC

    non_contactes = issues[issues["groupe"] != "contact"]
    valeur = float(average_precision_score(non_contactes["parti"], non_contactes["score"]))
    baisse = (reference - valeur) / reference
    return {
        "comptes": int(len(non_contactes)),
        "PR-AUC": round(valeur, 4),
        "référence": reference,
        "baisse relative": round(baisse, 4),
        "déclenchée": bool(baisse > SEUIL_DEGRADATION_PR_AUC),
    }


def mesures_du_trimestre(couverture: dict, suisse: dict, retention: dict, pr_auc: dict) -> dict:
    """The quarterly verdicts as `evaluer_alertes` reads them."""
    return {
        INDICATEUR_COUVERTURE: couverture["déclenchée"],
        INDICATEUR_SUISSE: suisse["déclenchée"],
        INDICATEUR_RETENTION: retention["déclenchée"],
        INDICATEUR_PR_AUC: pr_auc["déclenchée"],
    }
