"""Non-regression tests for every completed phase.

**What this file pins, and what it does not.** Other test files check *behaviour*: a
function does what its contract says. This one pins *published figures* - the numbers
quoted in the phase notebooks, in the explanatory documents and in the oral presentation.

The distinction matters. A cleaning function can keep working perfectly while returning
different numbers, because a source changed or a rule was adjusted. Nothing would fail,
and three deliverables would silently become wrong at once.

**How to extend it.** One section per completed phase. Numeric figures go into
`CHIFFRES_PUBLIES`, which a single parametrised test walks through: adding a phase means
adding entries, not writing new tests. Structural guarantees that are not a number - a
join losing no row, a fingerprint matching - keep their own test.

Tolerances are deliberately loose. The aim is to catch a chain that broke, not to forbid a
rounding difference.

    Phase 1 - Framing                        notebooks/01_cadrage.ipynb
    Phase 2 - Ingestion and governance       notebooks/02_donnees.ipynb
    Phase 3 - Exploration and profiling      notebooks/03_exploration.ipynb
              materialisation                data/processed/*.parquet + manifest
    Phase 4 - Preparation and cleaning       certification notebook § 7 (rule 4 amended)
              data contract                  src/churn_saas/donnees/qualite.py
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn_saas.config import COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION
from churn_saas.donnees import (
    charger_bronze,
    construire_silver,
    controler_jointure,
    decrire_schema,
    verifier_manifeste,
)
from churn_saas.evaluation.decision import seuil_par_compte

RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "data" / "raw"

COLONNES_DECIMALES = [
    "taux_adoption_pct",
    "heures_usage_30j",
    "delai_reponse_support_h",
    "revenu_mensuel_recurrent_eur",
    "valeur_vie_client_eur",
]
COLONNES_ENTIERES = [
    "anciennete_mois",
    "sieges_souscrits",
    "utilisateurs_actifs",
    "connexions_30j",
    "fonctionnalites_total",
    "fonctionnalites_utilisees",
    "nb_integrations",
    "derniere_connexion_jours",
    "tickets_support_90j",
    "csat",
    "retards_paiement_12m",
    "sante_compte_fin_periode",
    "churn",
]


# --- Fixtures shared by every phase ---------------------------------------------------
@pytest.fixture(scope="module")
def brut() -> pd.DataFrame:
    """Raw dataset, read exactly as the notebooks read it."""
    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip(
            "Jeu de données absent ou réduit à un pointeur Git-LFS. "
            "Exécuter `git lfs pull` ou replacer les CSV dans data/raw/."
        )
    return charger_bronze(fichier)


@pytest.fixture(scope="module")
def silver(brut: pd.DataFrame) -> pd.DataFrame:
    """Cleaned dataset, built exactly as the notebooks build it."""
    catalogue = charger_bronze(DONNEES / "catalogue_plans.csv")
    return construire_silver(
        brut,
        catalogue=catalogue,
        colonnes_decimales=COLONNES_DECIMALES,
        colonnes_dates=["date_souscription"],
        colonnes_entieres=COLONNES_ENTIERES,
    )


def _pertes_totales(brut: pd.DataFrame) -> float:
    """Values present in the source and lost on conversion, every converted column."""
    from churn_saas.donnees import (
        nettoyer_decimal_texte,
        parser_dates_multiformat,
        pertes_de_conversion,
    )

    source = brut.drop_duplicates()
    total = sum(
        int(pertes_de_conversion(source[c], nettoyer_decimal_texte(source[c])).sum())
        for c in COLONNES_DECIMALES + COLONNES_ENTIERES
    )
    dates = source["date_souscription"]
    return float(total + pertes_de_conversion(dates, parser_dates_multiformat(dates)).sum())


def _dates_ambigues(brut: pd.DataFrame) -> pd.Series:
    """Slash dates whose first two fields could both be a month (day <= 12)."""
    texte = brut.drop_duplicates()["date_souscription"].astype(str)
    return texte.str.match(r"^(0?[1-9]|1[0-2])/(0?[1-9]|1[0-2])/")


JOURS_SEMAINE = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _accord_jour_semaine(brut: pd.DataFrame, masque: str, format_: str | None = None) -> float:
    """Share of dates (%) falling on the weekday the source states in `jour_souscription`.

    The weekday is an independent witness of the date parsing: a date read with day and
    month swapped almost never lands on it. `masque` selects the rows ("toutes", "iso",
    "ambigues"); `format_` forces one reading, to measure the alternative that was rejected
    ("ancienne lecture" being the `format="mixed", dayfirst=True` used until phase 4).
    """
    from churn_saas.donnees import parser_dates_multiformat

    source = brut.drop_duplicates().reset_index(drop=True)
    texte = source["date_souscription"].astype(str)
    selection = {
        "toutes": pd.Series(True, index=texte.index),
        "iso": texte.str.match(r"^\d{4}-\d{2}-\d{2}$"),
        "ambigues": _dates_ambigues(brut).reset_index(drop=True),
    }[masque]
    if format_ == "ancienne lecture":
        lues = pd.to_datetime(texte[selection], format="mixed", dayfirst=True)
    elif format_:
        lues = pd.to_datetime(texte[selection], format=format_)
    else:
        lues = parser_dates_multiformat(texte[selection])
    jour = lues.dt.dayofweek.map(dict(enumerate(JOURS_SEMAINE)))
    declare = source.loc[selection, "jour_souscription"].str.strip().str.casefold()
    return float((jour == declare).mean() * 100)


def _iso_inversees_par_l_ancienne_lecture(brut: pd.DataFrame) -> float:
    """ISO dates that `format="mixed", dayfirst=True` - the reading used until phase 4 -
    returns with day and month swapped. Pinned to keep the size of the defect on record."""
    texte = brut.drop_duplicates()["date_souscription"].astype(str)
    iso = texte[texte.str.match(r"^\d{4}-\d{2}-\d{2}$")]
    ancienne = pd.to_datetime(iso, format="mixed", dayfirst=True)
    return float((ancienne != pd.to_datetime(iso, format="%Y-%m-%d")).sum())


def _bilan_reconstruction(silver: pd.DataFrame) -> dict[str, int]:
    """Values filled by each deterministic rule on the reference data."""
    from churn_saas.features import preparer_gold

    bilan = preparer_gold(silver).reconstructions
    return dict(zip(bilan["colonne"], bilan["reconstruits"], strict=True))


def _erreur_revenu(silver: pd.DataFrame, methode: str) -> float:
    """Median relative error (%) on accounts whose revenue is known.

    The rule is applied where the truth is known, and compared to it. `mediane` measures
    what the model would receive without the rule: the global median revenue.
    """
    connu = pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").dropna()
    if methode == "regle":
        sieges = pd.to_numeric(silver["sieges_souscrits"], errors="coerce").astype(float)
        prix = pd.to_numeric(silver["prix_mensuel_par_siege_eur"], errors="coerce")
        estime = (sieges * prix).loc[connu.index]
    else:
        estime = pd.Series(connu.median(), index=connu.index)
    return float(((estime - connu).abs() / connu).median() * 100)


def _ecart_taux_adoption(silver: pd.DataFrame) -> float:
    """Largest gap between the observed adoption rate and the rule, in points."""
    taux = pd.to_numeric(silver["taux_adoption_pct"], errors="coerce")
    actifs = pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce").astype(float)
    sieges = pd.to_numeric(silver["sieges_souscrits"], errors="coerce").astype(float)
    recalcule = (actifs / sieges * 100).round(1)
    return float((taux - recalcule).abs().max())


# --- Published figures, declared once -------------------------------------------------
@dataclass(frozen=True)
class ChiffrePublie:
    """One figure quoted in a deliverable, with how to recompute it.

    `cite_dans` is not decoration: it is what turns a failure into an action. Knowing a
    number moved is useless without knowing which documents now contradict the code.
    """

    phase: str
    libelle: str
    cite_dans: str
    attendu: float
    tolerance: float
    calcul: Callable[[pd.DataFrame, pd.DataFrame], float]


def _part_concentree(serie: pd.Series, part: float = 0.10) -> float:
    """Share of the total carried by the largest `part` of the values."""
    valeurs = pd.to_numeric(serie, errors="coerce").dropna().sort_values(ascending=False)
    return float(valeurs.head(int(len(valeurs) * part)).sum() / valeurs.sum())


def _gold(silver: pd.DataFrame) -> pd.DataFrame:
    """Gold dataset rebuilt from the cleaned data, target included."""
    from churn_saas.features import preparer_gold

    return preparer_gold(silver).gold


def _amplitude_segment(silver: pd.DataFrame, colonne: str, effectif_minimal: int = 30) -> float:
    """Spread in points between the highest and lowest churn rate across modalities.

    These three figures were published wrong until phase 3: computed on un-normalised
    modalities, they were overstated by roughly a factor of two, a marginal spelling
    variant setting the extreme.
    """
    churn = pd.to_numeric(silver["churn"], errors="coerce")
    groupes = churn.groupby(silver[colonne]).agg(["mean", "size"])
    retenus = groupes.loc[groupes["size"] >= effectif_minimal, "mean"]
    return float((retenus.max() - retenus.min()) * 100)


def _ecart_churn_selon_manquant(brut: pd.DataFrame, colonne: str) -> float:
    """Gap in churn rate between rows where a column is present and where it is missing."""
    cible = pd.to_numeric(brut["churn"], errors="coerce")
    absent = brut[colonne].isna()
    return float(abs(cible[absent].mean() - cible[~absent].mean()) * 100)


CHIFFRES_PUBLIES: tuple[ChiffrePublie, ...] = (
    # ---------------------------------------------------------------- Phase 1 - Cadrage
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Lignes du fichier source",
        cite_dans="01_cadrage § 1.1 · 02_donnees § 1.1 · suivi_projet_ia",
        attendu=5035,
        tolerance=0,
        calcul=lambda brut, silver: float(len(brut)),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Comptes uniques après retrait des doublons",
        cite_dans="01_cadrage § 1.1 · 02_donnees § 1.3 · README",
        attendu=5000,
        tolerance=0,
        calcul=lambda brut, silver: float(len(silver)),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Taux de résiliation",
        cite_dans="01_cadrage § 1.1 · notebook § 8 (déséquilibre modéré) · soutenance",
        attendu=0.28,
        tolerance=0.005,
        calcul=lambda brut, silver: float(silver["churn"].astype(float).mean()),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="MRR mensuel total du portefeuille (M€)",
        cite_dans="01_cadrage § 1.1 · notebook § 12 (assiette de référence)",
        attendu=17.2,
        tolerance=0.9,
        calcul=lambda brut, silver: float(
            pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").sum() / 1e6
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR portée par 10 % des comptes",
        cite_dans="01_cadrage § 1.2 · figure de concentration",
        attendu=0.68,
        tolerance=0.03,
        calcul=lambda brut, silver: _part_concentree(silver["revenu_mensuel_recurrent_eur"]),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR perdu portée par 10 % des churners",
        cite_dans="01_cadrage § 1.2 · 02.DONNEES_explications · README · soutenance",
        attendu=0.72,
        tolerance=0.03,
        calcul=lambda brut, silver: _part_concentree(
            silver.loc[silver["churn"].astype(float) == 1, "revenu_mensuel_recurrent_eur"]
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR exposée au départ",
        cite_dans="01_cadrage § 1.1 · notebook § 12",
        attendu=0.23,
        tolerance=0.02,
        calcul=lambda brut, silver: float(
            pd.to_numeric(
                silver.loc[silver["churn"].astype(float) == 1, "revenu_mensuel_recurrent_eur"],
                errors="coerce",
            ).sum()
            / pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").sum()
        ),
    ),
    # ------------------------------------------- Phase 2 - Ingestion et gouvernance
    ChiffrePublie(
        phase="2 · Données",
        libelle="Colonnes du fichier source",
        cite_dans="02_donnees § 1.2 · dictionnaire de données",
        attendu=29,
        tolerance=0,
        calcul=lambda brut, silver: float(brut.shape[1]),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Doublons stricts retirés",
        cite_dans="02_donnees § 1.3 · 02.DONNEES_explications · suivi_projet_ia",
        attendu=35,
        tolerance=0,
        calcul=lambda brut, silver: float(len(brut) - len(silver)),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Manquants sur `commentaire_csm` (%)",
        cite_dans="02_donnees § 1.3 · notebook § 5 (valeurs de référence)",
        attendu=55.4,
        tolerance=0.5,
        calcul=lambda brut, silver: float(brut["commentaire_csm"].isna().mean() * 100),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Manquants les plus élevés hors texte libre (%)",
        cite_dans="02_donnees § 1.3 · notebook § 5 (seuil d'alerte à 10 %)",
        attendu=10.0,
        tolerance=0.5,
        calcul=lambda brut, silver: float(
            (brut.drop(columns=["commentaire_csm"]).isna().mean() * 100).max()
        ),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Écart de churn selon l'absence d'une valeur — colonnes SOURCE (points)",
        cite_dans="02_donnees § 1.3 · 02.DONNEES_explications · suivi_projet_ia",
        attendu=4.5,
        tolerance=1.0,
        calcul=lambda brut, silver: max(
            _ecart_churn_selon_manquant(brut, colonne)
            for colonne in brut.columns
            if colonne not in ("churn", "commentaire_csm") and brut[colonne].isna().sum() >= 30
        ),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Champs `commentaire_csm` renseignés (%)",
        cite_dans="02_donnees § 4.2",
        attendu=44.6,
        tolerance=0.5,
        calcul=lambda brut, silver: float(brut["commentaire_csm"].notna().mean() * 100),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Modalités en trop dues à la casse, avant correction",
        cite_dans="02_donnees § 1.3 (audit qualité) · 03_exploration § 4.2",
        attendu=26,
        tolerance=0,
        calcul=lambda brut, silver: float(
            sum(
                brut[c].dropna().astype(str).str.strip().nunique()
                - brut[c].dropna().astype(str).str.strip().str.casefold().nunique()
                for c in ("secteur", "plan", "taille_entreprise", "pays", "code_datacenter")
            )
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre tailles d'entreprise (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=8.3,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "taille_entreprise"),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre secteurs (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=7.0,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "secteur"),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre pays (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=6.1,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "pays"),
    ),
    # ----------------------------------------- Phase 3 - Exploration et profilage
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Comptes sans aucun utilisateur actif",
        cite_dans="03_exploration § 3.4 · 03.EXPLORATION_explications · soutenance",
        attendu=297,
        tolerance=0,
        calcul=lambda brut, silver: float(
            (pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0).sum()
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Taux de churn des comptes abandonnés",
        cite_dans="03_exploration § 3.4 · figure « signal de 62 points »",
        attendu=0.865,
        tolerance=0.02,
        calcul=lambda brut, silver: float(
            silver.loc[pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0, "churn"]
            .astype(float)
            .mean()
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Écart de risque porté par l'abandon (points)",
        cite_dans="03_exploration § 3.4 · titre de figure · soutenance",
        attendu=62.2,
        tolerance=3.0,
        calcul=lambda brut, silver: float(
            (
                silver.loc[
                    pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0, "churn"
                ]
                .astype(float)
                .mean()
                - silver.loc[
                    pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") != 0, "churn"
                ]
                .astype(float)
                .mean()
            )
            * 100
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Modalités de `taille_entreprise` après normalisation",
        cite_dans="03_exploration § 4.2 (8 orthographes pour 4 catégories)",
        attendu=4,
        tolerance=0,
        calcul=lambda brut, silver: float(silver["taille_entreprise"].dropna().nunique()),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Colonnes du jeu gold livré au modèle",
        # 34 until phase 4, which excluded the raw date and two duplicates.
        cite_dans="03_exploration § 3.6 (34 avant la phase 4) · notebook § 7 · fiche modèle",
        attendu=31,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver).shape[1]),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Variables explicatives après séparation de la cible",
        cite_dans="03_exploration § 3.6 (33 avant la phase 4) · notebook § 7 · suivi_projet_ia",
        attendu=30,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver).shape[1] - 1),
    ),
    # --- Phase 4 · Preparation and cleaning -----------------------------------------------
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Valeurs présentes perdues à la conversion",
        cite_dans="notebook § 7 · suivi_projet_ia § 4 · 04.SOUTENANCE",
        attendu=0,
        tolerance=0,
        calcul=lambda brut, silver: _pertes_totales(brut),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Délais de support écrits avec l'unité « h »",
        cite_dans="notebook § 7 · suivi_projet_ia § 4 · 04.SOUTENANCE",
        attendu=570,
        tolerance=0,
        calcul=lambda brut, silver: float(
            brut.drop_duplicates()["delai_reponse_support_h"]
            .astype(str)
            .str.contains(r"\d\s*h$")
            .sum()
        ),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Manquants réels sur `delai_reponse_support_h` (%)",
        # 21.4 % in 03_exploration § 2.2: 570 of those 1,070 were conversion losses.
        cite_dans="notebook § 7 · 03_exploration § 2.2 (21,4 % avant correction) · suivi",
        attendu=10.0,
        tolerance=0.1,
        calcul=lambda brut, silver: float(silver["delai_reponse_support_h"].isna().mean() * 100),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Manquants du délai avec l'ancienne conversion (%)",
        # Real gaps plus the values written "3.1 h", which the old conversion turned to NaN.
        cite_dans="03_exploration § 2.2 (avant ré-exécution) · suivi § 4 · 04.SOUTENANCE",
        attendu=21.4,
        tolerance=0.1,
        calcul=lambda brut, silver: float(
            (
                silver["delai_reponse_support_h"].isna().sum()
                + brut.drop_duplicates()["delai_reponse_support_h"]
                .astype(str)
                .str.contains(r"\d\s*h$")
                .sum()
            )
            / len(silver)
            * 100
        ),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Dates ambiguës (jour <= 12, format JJ/MM)",
        cite_dans="notebook § 7 · docstring de parser_dates_multiformat",
        attendu=955,
        tolerance=0,
        calcul=lambda brut, silver: float(_dates_ambigues(brut).sum()),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Dates ISO lues jour et mois inversés avant correction",
        cite_dans="notebook § 7 · suivi_projet_ia § 4 · 04.SOUTENANCE · FORMATS_DATE",
        attendu=960,
        tolerance=0,
        calcul=lambda brut, silver: _iso_inversees_par_l_ancienne_lecture(brut),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Dates ISO d'accord avec le jour de semaine, ancienne lecture (%)",
        cite_dans="04.SOUTENANCE (encadré « un témoin dans les données »)",
        attendu=48.2,
        tolerance=0.5,
        calcul=lambda brut, silver: _accord_jour_semaine(brut, "iso", "ancienne lecture"),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Dates d'accord avec le jour de semaine déclaré (%)",
        cite_dans="notebook § 7 · docstring de parser_dates_multiformat",
        attendu=100.0,
        tolerance=0,
        calcul=lambda brut, silver: _accord_jour_semaine(brut, "toutes"),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Dates ambiguës d'accord si lues mois en premier (%)",
        cite_dans="notebook § 7 · docstring de parser_dates_multiformat",
        attendu=15.1,
        tolerance=0.5,
        calcul=lambda brut, silver: _accord_jour_semaine(brut, "ambigues", "%m/%d/%Y"),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Revenus mensuels reconstruits (sièges × prix)",
        cite_dans="notebook § 7 · suivi § 4 · 04.SOUTENANCE · registre",
        attendu=150,
        tolerance=0,
        calcul=lambda brut, silver: float(
            _bilan_reconstruction(silver)["revenu_mensuel_recurrent_eur"]
        ),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Taux d'adoption reconstruits (actifs ÷ sièges)",
        cite_dans="notebook § 7 · suivi § 4 · 04.SOUTENANCE",
        attendu=250,
        tolerance=0,
        calcul=lambda brut, silver: float(_bilan_reconstruction(silver)["taux_adoption_pct"]),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Erreur relative médiane du revenu reconstruit, valeurs connues (%)",
        cite_dans="docstring de donnees/reconstruction.py · 04.SOUTENANCE · registre",
        attendu=9.0,
        tolerance=0.3,
        calcul=lambda brut, silver: _erreur_revenu(silver, "regle"),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Erreur relative médiane si l'on imputait la médiane globale (%)",
        cite_dans="docstring de donnees/reconstruction.py · 04.SOUTENANCE · registre",
        attendu=91.4,
        tolerance=0.5,
        calcul=lambda brut, silver: _erreur_revenu(silver, "mediane"),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Écart maximal du taux d'adoption recalculé, valeurs connues (points)",
        cite_dans="docstring de donnees/reconstruction.py",
        attendu=0.0,
        tolerance=0.0,
        calcul=lambda brut, silver: _ecart_taux_adoption(silver),
    ),
    ChiffrePublie(
        phase="4 · Préparation",
        libelle="Vrais manquants restants sur `usage_par_actif`",
        cite_dans="notebook § 7 · suivi § 4",
        attendu=284,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver)["usage_par_actif"].isna().sum()),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Modalités de `secteur` après normalisation",
        cite_dans="03_exploration § 4.2 (21 orthographes pour 7 catégories)",
        attendu=7,
        tolerance=0,
        calcul=lambda brut, silver: float(silver["secteur"].dropna().nunique()),
    ),
)


@pytest.mark.parametrize(
    "chiffre",
    CHIFFRES_PUBLIES,
    ids=lambda c: f"{c.phase.split(' ')[0]}-{c.libelle[:45]}",
)
def test_les_chiffres_publies_sont_inchanges(
    chiffre: ChiffrePublie, brut: pd.DataFrame, silver: pd.DataFrame
):
    """A published figure must still be reproducible by the code that produced it.

    When this fails, the code is not necessarily wrong: a source may legitimately have
    changed. What is certain is that the documents listed in `cite_dans` now contradict
    it, and must be updated in the same commit.
    """
    obtenu = chiffre.calcul(brut, silver)
    assert obtenu == pytest.approx(chiffre.attendu, abs=chiffre.tolerance), (
        f"\n  Phase      : {chiffre.phase}"
        f"\n  Chiffre    : {chiffre.libelle}"
        f"\n  Publié     : {chiffre.attendu}"
        f"\n  Recalculé  : {obtenu:.4f}"
        f"\n  Cité dans  : {chiffre.cite_dans}"
        f"\n  → Corriger le code, ou mettre à jour ces documents dans le même commit."
    )


# --- Phase 1 · Cadrage : guarantees that are not a single figure -----------------------
def test_l_ecart_de_seuil_entre_deciles_reste_superieur_a_cent(silver: pd.DataFrame):
    """The "factor over 100" argument justifies rejecting a single global threshold.

    It is the central argument of the decision rule, quoted in the framing notebook, in
    the explanatory document and in the oral pitch. If the spread narrowed, a global
    threshold would become defensible and the whole design would need rethinking.
    """
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    seuils = seuil_par_compte(clv.quantile([0.10, 0.90]))
    facteur = float(seuils.iloc[0] / seuils.iloc[1])
    assert facteur > 100, (
        f"Écart tombé à {facteur:.0f} : l'argument central de la règle de décision ne tient plus"
    )


def test_le_seuil_du_dernier_decile_reste_tres_bas(silver: pd.DataFrame):
    """Acting on a top-decile account stays rational below 1% risk.

    The 0.3% figure is the striking end of the argument presented to the jury.
    """
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    assert float(seuil_par_compte(pd.Series([clv.quantile(0.90)])).iloc[0]) < 0.01


def test_les_hypotheses_de_cadrage_sont_inchangees():
    """These values are quoted verbatim in the documents and in the oral pitch."""
    assert EFFICACITE_RETENTION == 0.25
    assert COUT_CONTACT_CSM_EUR == 135.0


def test_la_precision_statistique_du_rappel_reste_autour_de_cinq_points(silver: pd.DataFrame):
    """The "±5 points" caveat stated in section 9 must remain true.

    Saying it before the jury does is worth more than being told; but only while it holds.
    """
    n_positifs = int(silver["churn"].astype(float).sum() * 0.20)
    demi_largeur = 1.96 * np.sqrt(0.70 * 0.30 / n_positifs)
    assert demi_largeur == pytest.approx(0.054, abs=0.01)


# --- Phase 2 · Ingestion et gouvernance : guarantees that are not a single figure -------
def test_la_jointure_catalogue_apparie_tous_les_comptes(silver: pd.DataFrame):
    """A silent join failure would corrupt every downstream figure."""
    assert "prix_mensuel_par_siege_eur" in silver.columns
    assert silver["prix_mensuel_par_siege_eur"].notna().all()


def test_la_normalisation_de_la_cle_reste_indispensable(brut: pd.DataFrame):
    """Without normalisation the join matches nothing, and raises nothing.

    This measurement is the one quoted to justify the normalisation step. Should the
    sources become consistent on their own, the argument would need rewording - the code
    would still be right, the document would be misleading.
    """
    catalogue = charger_bronze(DONNEES / "catalogue_plans.csv")
    controle = controler_jointure(brut, catalogue, cle="plan")
    assert controle.iloc[0]["taux d'appariement"] == "54.3%"
    assert controle.iloc[1]["taux d'appariement"] == "100.0%"


def test_chaque_colonne_source_porte_toujours_un_role(brut: pd.DataFrame):
    """A new column arriving undocumented is a column nobody decided what to do with."""
    schema = decrire_schema(brut)
    sans_role = sorted(schema.loc[schema["role"] == "non documenté", "colonne"])
    assert not sans_role, (
        f"Colonnes sans rôle déclaré : {sans_role}. "
        "Compléter ROLES_COLONNES avant de les laisser entrer dans la chaîne."
    )


def test_six_colonnes_restent_hors_du_modele(brut: pd.DataFrame):
    """Six columns cannot be explanatory variables, for six distinct reasons.

    The count is quoted in the phase 2 notebook and in the explanatory document. The
    motives are not interchangeable: the grid separates the ethical exclusion from the
    technical one.
    """
    non_modelisables = {
        "identifiant",
        "cible principale",
        "cible secondaire",
        "postérieur à la décision",
        "texte libre",
        "artefact de process",
    }
    schema = decrire_schema(brut)
    exclues = schema.loc[schema["role"].isin(non_modelisables)]
    assert len(exclues) == 6
    assert exclues["role"].nunique() == 6


def test_les_sources_correspondent_toujours_au_manifeste():
    """The recorded fingerprints still match the files on disk.

    This is the strongest non-regression guarantee of the project: it states that the data
    themselves have not moved. Every other figure here is computed from them, so a failure
    on this test explains all the others at once.
    """
    chemin = RACINE / "data" / "manifeste_v1.0.json"
    if not chemin.exists():
        pytest.skip("Manifeste absent : exécuter notebooks/02_donnees.ipynb.")

    manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    controle = verifier_manifeste(manifeste)
    non_conformes = controle.loc[~controle["conforme"], "source"].tolist()
    assert not non_conformes, (
        f"Sources modifiées depuis l'écriture du manifeste : {non_conformes}. "
        "Les chiffres publiés ne décrivent plus ces données."
    )


# --- Phase 3 · Exploration : guarantees that are not a single figure --------------------
def test_les_modalites_ne_comportent_plus_de_variante_de_casse(silver: pd.DataFrame):
    """One label per business category, across every categorical column.

    Normalising the join key alone left `TPE` and `tpe` as two categories in the dataset.
    One-hot encoding then produced a column per spelling: the model saw several rare
    categories where the business has one, split the signal between them, and every
    importance reading became misleading.
    """
    for colonne in ("secteur", "pays", "taille_entreprise", "plan", "code_datacenter"):
        valeurs = silver[colonne].dropna().astype(str)
        assert valeurs.nunique() == valeurs.str.strip().str.casefold().nunique(), (
            f"`{colonne}` conserve des variantes de casse : {sorted(valeurs.unique())[:6]}"
        )


def test_les_nan_des_ratios_ont_une_cause_unique_et_connue(silver: pd.DataFrame):
    """Every NaN in `tickets_par_actif` comes from a zero denominator, nothing else.

    The claim made in section 3.4 - that these NaN encode an abandoned account - only
    holds while this is true. Another cause appearing would make the explanatory indicator
    partly wrong without any metric saying so.
    """
    from churn_saas.features import ajouter_ratios_usage

    enrichi = ajouter_ratios_usage(silver)
    actifs = pd.to_numeric(enrichi["utilisateurs_actifs"], errors="coerce")
    assert (enrichi["tickets_par_actif"].isna() == (actifs == 0)).all()
    assert (
        pd.to_numeric(enrichi["compte_sans_utilisateur_actif"], errors="coerce") == (actifs == 0)
    ).all()


def test_les_trous_structurels_sont_combles_sur_le_chemin_du_gold(silver: pd.DataFrame):
    """Phase 4: in gold, the per-user ratios are 0 on abandoned accounts, and the only NaN
    left in `usage_par_actif` are hours genuinely unknown on accounts that have users -
    the one kind of gap the median may fill."""
    gold = _gold(silver)
    actifs = pd.to_numeric(gold["utilisateurs_actifs"], errors="coerce")
    sans_actif = actifs == 0
    assert (gold.loc[sans_actif, ["usage_par_actif", "tickets_par_actif"]] == 0).all().all()
    assert gold["tickets_par_actif"].notna().all()
    attendu = gold["heures_usage_30j"].isna() & (actifs > 0)
    assert (gold["usage_par_actif"].isna() == attendu).all()


def test_aucun_segment_ne_concentre_le_risque(silver: pd.DataFrame):
    """No segment stands out enough for a business rule to replace the model.

    This is the framing conclusion of section 1.2: it justifies building a model rather
    than writing "watch sector X". It was published on overstated spreads - 13 to 17
    points instead of 7 to 8 - which made it look weaker than it is.

    The threshold is set at 15 points: beyond that, a simple segmentation would start to
    compete with the model and the framing would need revisiting.
    """
    for colonne in ("taille_entreprise", "secteur", "pays"):
        amplitude = _amplitude_segment(silver, colonne)
        assert amplitude < 15, (
            f"`{colonne}` sépare de {amplitude:.1f} points : une règle métier deviendrait "
            "compétitive et le cadrage serait à revoir."
        )


# --- Phase 3 · Materialisation: the chain stays reproducible --------------------------
def test_la_chaine_produit_deux_fois_le_meme_jeu_gold():
    """Two runs on the same sources must give the same gold dataset, byte for byte.

    This is the assumption the whole snapshot mechanism rests on. If it broke - a pandas
    upgrade, a change in join order - the fingerprint recorded in the manifest would no
    longer identify anything, and a model card would describe data the model never saw.

    The check is cheap: the chain runs in under a second on this volume.
    """
    from churn_saas.donnees import empreinte_donnees
    from churn_saas.features import executer_pipeline

    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")

    catalogue = DONNEES / "catalogue_plans.csv"
    premier = executer_pipeline(fichier, catalogue)
    second = executer_pipeline(fichier, catalogue)

    assert empreinte_donnees(premier.silver) == empreinte_donnees(second.silver)
    assert empreinte_donnees(premier.gold) == empreinte_donnees(second.gold)


def test_les_instantanes_derives_ne_sont_pas_versionnes():
    """Parquet snapshots stay out of Git; the manifest that describes them stays in.

    Versioning the snapshots would produce a binary diff at every change to the cleaning
    rules, for information already held by the sources plus the code. The manifest is
    small, textual, and it is the contract.
    """
    import subprocess

    resultat = subprocess.run(
        ["git", "check-ignore", "data/processed/gold_v1.0_20260101.parquet"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    if resultat.returncode == 128:
        pytest.skip("Hors copie de travail Git.")
    assert resultat.returncode == 0, (
        "Les instantanés Parquet doivent rester hors de Git : vérifier `.gitignore`."
    )

    suivis = subprocess.run(
        ["git", "ls-files", "data/manifeste_v1.0.json"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    assert suivis.stdout.strip(), "Le manifeste doit, lui, être versionné."


def test_les_figures_produites_ne_sont_pas_versionnees():
    """Figures are outputs: regenerable, and a binary diff at every retouch otherwise.

    The documents that reuse them get them by running the notebook, not from the history.
    """
    import subprocess

    resultat = subprocess.run(
        ["git", "check-ignore", "reports/figures/03_correlations.png"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    if resultat.returncode == 128:
        pytest.skip("Hors copie de travail Git.")
    assert resultat.returncode == 0, "Les figures doivent rester hors de Git."


def test_le_cache_des_figures_depend_du_code_de_trace():
    """The property the whole figure cache rests on, pinned here as well.

    If the key stopped covering the drawing code, every notebook would keep displaying
    figures from a previous version - and the deliverable would show pictures that no
    longer match the numbers beside them.
    """
    from churn_saas.figures import cle_cache

    def tracer():
        return None

    def tracer_modifie():
        return None  # commentaire ajouté : le source change, donc la clé aussi

    assert cle_cache("signature", tracer) != cle_cache("signature", tracer_modifie)


# --- Phase 4 · Preparation: guarantees that are not a single figure ---------------------
@pytest.fixture(scope="module")
def chaine():
    """The full chain, as the notebook and the monthly batch run it."""
    from churn_saas.features import executer_pipeline

    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    return executer_pipeline(fichier, DONNEES / "catalogue_plans.csv")


def test_le_contrat_de_donnees_est_respecte_sur_le_jeu_de_reference(chaine):
    """The reference data pass every check of the contract, without a single watch flag.

    If a check turned to "to watch" here, either the data moved (the manifest test says
    so) or a cleaning rule regressed.
    """
    from churn_saas.donnees import CONFORME

    assert (chaine.contrat["statut"] == CONFORME).all(), chaine.contrat.to_string()


def test_aucune_colonne_numerique_n_entre_dans_le_modele_comme_categorie(chaine):
    """Every non-numeric explanatory column is genuinely textual.

    Generic on purpose: it names no column. The catalogue prices reached the model as
    categories until phase 4; the next column read as text by mistake will fail here too.
    """
    from churn_saas.donnees import nettoyer_decimal_texte

    X = chaine.X
    textuelles = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    deguisees = [
        c
        for c in textuelles
        if nettoyer_decimal_texte(X[c].dropna()).notna().all() and X[c].notna().any()
    ]
    assert not deguisees, f"Colonnes numériques encodées comme catégories : {deguisees}"


def test_aucune_date_n_entre_dans_le_modele(chaine):
    """A raw date one-hot encoded is one category per day: noise, and unknown at scoring."""
    dates = [c for c in chaine.X.columns if pd.api.types.is_datetime64_any_dtype(chaine.X[c])]
    assert not dates, f"Dates brutes parmi les variables explicatives : {dates}"


def test_aucune_colonne_du_gold_n_est_le_doublon_d_une_autre(chaine):
    """Two identical columns give the model the same information twice, under two names.

    `fonctionnalites_incluses` was an exact copy of `fonctionnalites_total`, and
    `taux_activation` a rescaled copy of `taux_adoption_pct`, until phase 4. Generic:
    compares every pair, names none.
    """
    X = chaine.X
    colonnes = list(X.columns)
    doublons = [
        (a, b)
        for i, a in enumerate(colonnes)
        for b in colonnes[i + 1 :]
        if X[a].astype("string").fillna("<NA>").equals(X[b].astype("string").fillna("<NA>"))
    ]
    assert not doublons, f"Colonnes identiques dans le gold : {doublons}"

    # Strengthened in phase 4: a rescaled copy is a duplicate too. `taux_activation` was
    # `taux_adoption_pct` / 100 and escaped the equality check above.
    numeriques = X.select_dtypes(include="number").astype(float)
    correlations = numeriques.corr().abs()
    proportionnelles = [
        (a, b)
        for i, a in enumerate(correlations.columns)
        for b in correlations.columns[i + 1 :]
        if correlations.loc[a, b] > 0.999
    ]
    assert not proportionnelles, f"Colonnes proportionnelles dans le gold : {proportionnelles}"


def test_les_manquants_du_delai_restent_au_hasard_apres_correction(chaine):
    """The phase 3 conclusion still holds on the corrected column.

    Phase 3 concluded that support delays are missing at random, on a column where more
    than half the gaps were conversion losses. Corrected, the column must still show no
    structural cause (no ticket) and no churn signal - otherwise the imputation strategy
    built on that conclusion would rest on nothing.
    """
    silver = chaine.silver
    manquant = silver["delai_reponse_support_h"].isna()
    sans_ticket = pd.to_numeric(silver["tickets_support_90j"], errors="coerce") == 0
    churn = pd.to_numeric(silver["churn"], errors="coerce")
    assert abs(sans_ticket[manquant].mean() - sans_ticket.mean()) * 100 < 3
    assert abs(churn[manquant].mean() - churn[~manquant].mean()) * 100 < 3


def test_l_absence_d_une_valeur_source_n_est_toujours_pas_un_signal(chaine):
    """Phase 2 published a 4.5-point maximum churn gap on raw data; it holds after cleaning.

    Measured on silver now, since the cleaning is what phase 4 changed. A gap growing past
    the published figure plus its tolerance would mean the cleaning creates a signal.
    """
    silver = chaine.silver
    churn = pd.to_numeric(silver["churn"], errors="coerce")
    from churn_saas.donnees.schema import ROLES_COLONNES

    sources = [
        c
        for c, role in ROLES_COLONNES.items()
        if c in silver.columns and role not in {"texte libre", "cible principale"}
    ]
    ecarts = {
        c: abs(churn[silver[c].isna()].mean() - churn[silver[c].notna()].mean()) * 100
        for c in sources
        if silver[c].isna().any()
    }
    assert max(ecarts.values()) <= 4.5 + 1.0, ecarts


def test_le_manifeste_decrit_les_jeux_produits_par_le_code(chaine):
    """The derived datasets recorded in the manifest are the ones the code produces today.

    Changing a cleaning rule changes silver and gold. Without this test the manifest kept
    describing the phase 3 gold - 34 columns, misread dates - while the code produced
    another one, and a model card would have cited a fingerprint nobody can reproduce.

    When it fails after a deliberate change: re-run the materialisation (README of the
    phase 4 delivery), then commit the manifest with the code.
    """
    from churn_saas.donnees import empreinte_donnees

    chemin = RACINE / "data" / "manifeste_v1.0.json"
    manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    jeux = manifeste.get("jeux_derives", {}).get("jeux", {})
    if not jeux:
        pytest.skip("Aucun jeu dérivé matérialisé dans le manifeste.")
    for nom, df in (("silver", chaine.silver), ("gold", chaine.gold)):
        assert jeux[nom]["empreinte_contenu"] == empreinte_donnees(df), (
            f"Le manifeste décrit un {nom} que le code ne produit plus "
            f"({jeux[nom]['colonnes']} colonnes enregistrées, {df.shape[1]} produites). "
            "Re-matérialiser puis committer le manifeste avec le code."
        )


def test_le_contrat_mesure_les_manquants_de_la_source(chaine):
    """The reconstruction runs after the contract, so the contract still sees real gaps.

    Placed before, it would report 0 % missing revenue where the source has 3 %, and the
    monthly monitoring of incoming data quality would go blind.
    """
    assert chaine.silver["revenu_mensuel_recurrent_eur"].isna().sum() == 150
    assert chaine.gold["revenu_mensuel_recurrent_eur"].isna().sum() == 0
