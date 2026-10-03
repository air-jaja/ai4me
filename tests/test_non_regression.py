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

import importlib.util
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


def _part_tukey(silver: pd.DataFrame) -> tuple[float, float]:
    """Share of accounts (%) above Tukey's upper fence on revenue, and their revenue share."""
    from churn_saas.donnees import bornes_valeurs_extremes

    mrr = pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce")
    _, haute = bornes_valeurs_extremes(mrr)
    au_dela = mrr > haute
    return float(au_dela.mean() * 100), float(mrr[au_dela].sum() / mrr.sum() * 100)


def _diagnostic_valeur_vie(silver: pd.DataFrame) -> dict[str, float]:
    """Diagnostic of arbitrage 3, on the gold variables of the reference data."""
    from churn_saas.evaluation import diagnostiquer_valeur_vie
    from churn_saas.features import preparer_gold

    gold = preparer_gold(silver).gold
    explicatives = gold.drop(columns=["churn"]).select_dtypes("number")
    diagnostic = diagnostiquer_valeur_vie(
        explicatives,
        silver["valeur_vie_client_eur"],
        silver["revenu_mensuel_recurrent_eur"],
        silver["churn"],
        silver["anciennete_mois"],
    )
    return dict(zip(diagnostic["indicateur"], diagnostic["valeur"], strict=True))


def _gold_candidat(silver: pd.DataFrame) -> pd.DataFrame:
    """Gold with the variables the phase 5 selection removed: the chain still builds them."""
    from churn_saas.config import EXCLUES_PAR_SELECTION
    from churn_saas.features import preparer_gold

    return preparer_gold(silver, garder=EXCLUES_PAR_SELECTION).gold


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
        # 34 until phase 4, 31 until the catalogue was reduced to plan, 26 until the
        # selection (phase 5, blocs B and C) removed seven variables.
        cite_dans="03_exploration § 3.6 (34 avant la phase 4) · notebook § 7, § 8.C · fiche modèle",
        attendu=19,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver).shape[1]),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Variables explicatives après séparation de la cible",
        cite_dans="03_exploration § 3.6 (33 avant la phase 4) · notebook § 1, 5, 7, 8.C · suivi",
        attendu=18,
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
        calcul=lambda brut, silver: float(_gold_candidat(silver)["usage_par_actif"].isna().sum()),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Comptes au-delà de la borne haute de Tukey sur le revenu (%)",
        # Phase 3 printed "one account in eight, nearly half the revenue" next to a computed
        # 76 %: the sentence was wrong, the computation right. Corrected in phase 4.
        cite_dans="notebook § 6.2 · 03.EXPLORATION_explications · suivi · registre E-301",
        attendu=13.6,
        tolerance=0.1,
        calcul=lambda brut, silver: _part_tukey(silver)[0],
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Part du revenu portée par ces comptes (%)",
        cite_dans="notebook § 6.2 · 03.EXPLORATION_explications · suivi · registre E-301",
        attendu=76.0,
        tolerance=0.5,
        calcul=lambda brut, silver: _part_tukey(silver)[1],
    ),
    # --- Phase 5 · Feature engineering --------------------------------------------------
    ChiffrePublie(
        phase="5 · Features",
        libelle="Variance de la valeur vie client expliquée sans l'issue (R²)",
        cite_dans="00.README_choix_methodologiques § 7 bis · registre E-508 · notebook § 12",
        attendu=0.895,
        tolerance=0.01,
        calcul=lambda brut, silver: _diagnostic_valeur_vie(silver)[
            "Variance expliquée sans l'issue (R², validation croisée)"
        ],
    ),
    ChiffrePublie(
        phase="5 · Features",
        libelle="Gain de R² apporté par l'issue",
        cite_dans="00.README_choix_methodologiques § 7 bis · registre E-508",
        attendu=0.0,
        tolerance=0.005,
        calcul=lambda brut, silver: _diagnostic_valeur_vie(silver)[
            "Gain de R² apporté par l'issue"
        ],
    ),
    ChiffrePublie(
        phase="5 · Features",
        libelle="Ancienneté médiane des comptes qui partent (mois)",
        cite_dans="00.README_choix_methodologiques § 7 bis",
        attendu=6,
        tolerance=0,
        calcul=lambda brut, silver: _diagnostic_valeur_vie(silver)[
            "Ancienneté, comptes qui partent (mois, médiane)"
        ],
    ),
    ChiffrePublie(
        phase="5 · Features",
        libelle="Ancienneté médiane des comptes qui restent (mois)",
        cite_dans="00.README_choix_methodologiques § 7 bis",
        attendu=12,
        tolerance=0,
        calcul=lambda brut, silver: _diagnostic_valeur_vie(silver)[
            "Ancienneté, comptes qui restent (mois, médiane)"
        ],
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
    gold = _gold_candidat(silver)
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


def test_la_valeur_vie_client_n_encode_pas_l_issue(silver: pd.DataFrame):
    """Arbitrage 3 settled by measurement: the observed value may evaluate the rule.

    The 18.9 against 15.6 months gap is a composition effect - leavers are younger accounts.
    Were the value to start encoding the outcome, the impact measured in phase 9 would be
    inflated, and this test would say so before the jury does.
    """
    from churn_saas.evaluation import diagnostiquer_valeur_vie, valeur_encode_l_issue
    from churn_saas.features import preparer_gold

    gold = preparer_gold(silver).gold
    diagnostic = diagnostiquer_valeur_vie(
        gold.drop(columns=["churn"]).select_dtypes("number"),
        silver["valeur_vie_client_eur"],
        silver["revenu_mensuel_recurrent_eur"],
        silver["churn"],
        silver["anciennete_mois"],
    )
    assert not valeur_encode_l_issue(diagnostic), diagnostic.to_string()


def test_les_attributs_de_formule_ne_prennent_qu_une_valeur_par_plan(silver: pd.DataFrame):
    """The premise of arbitrage 2: if a plan ever had two prices, `plan` alone would lose it."""
    from churn_saas.config import EXCLUES_ATTRIBUT_FORMULE

    valeurs = silver.groupby("plan")[EXCLUES_ATTRIBUT_FORMULE].nunique()
    assert (valeurs <= 1).all().all(), valeurs.to_string()


# --- Phase 5 · Bloc A: the split and the dataset are valid --------------------------------
@pytest.fixture(scope="module")
def parties(chaine):
    from churn_saas.features import parties_du_decoupage

    return parties_du_decoupage(chaine)


def test_le_decoupage_reste_celui_qui_a_ete_publie(parties):
    """4,000 / 1,000 accounts, the same 28 % churn rate in both parts."""
    from churn_saas.config import ECART_STRATIFICATION_MAX_PTS

    assert (len(parties.y_entrainement), len(parties.y_test)) == (4000, 1000)
    ecart = abs(parties.y_entrainement.mean() - parties.y_test.mean()) * 100
    assert ecart < ECART_STRATIFICATION_MAX_PTS


def test_chaque_variable_est_stable_entre_entrainement_et_test(chaine, parties):
    """Largest PSI published at 0.033 (utilisateurs_actifs), rule: below 0.10 everywhere."""
    from churn_saas.config import SEUIL_PSI_DECOUPAGE
    from churn_saas.monitoring import rapport_derive

    rapport = rapport_derive(
        parties.X_entrainement, parties.X_test, list(chaine.X.columns), SEUIL_PSI_DECOUPAGE
    )
    assert len(rapport) == chaine.X.shape[1], "Une variable manque au rapport de dérive."
    assert rapport["psi"].max() == pytest.approx(0.033, abs=0.01)
    assert not rapport["alerte"].any(), rapport.head().to_string()


def test_l_entrainement_et_le_test_sont_indiscernables(chaine, parties):
    """Adversarial validation, published at 0.52 with the forest; checked here with the
    logistic regression, which reaches the same verdict in a second instead of fifteen."""
    from churn_saas.modelisation import construire_baseline, validation_adverse

    resultat = validation_adverse(
        construire_baseline(chaine.X), parties.X_entrainement, parties.X_test
    )
    assert resultat["conforme"] and resultat["auc"] == pytest.approx(0.516, abs=0.03)


def test_le_modele_bat_les_etiquettes_melangees(chaine, parties):
    """Published with 100 shuffles: 0.789 against 0.285, p = 0.01. Twenty shuffles here,
    the fewest that can reach p < 0.05, to keep the suite fast."""
    from churn_saas.modelisation import construire_baseline, tester_permutation

    resultat = tester_permutation(
        construire_baseline(chaine.X), parties.X_entrainement, parties.y_entrainement, 20
    )
    assert resultat["conforme"]
    assert resultat["score"] == pytest.approx(0.789, abs=0.01)
    assert resultat["moyenne_permutee"] == pytest.approx(0.28, abs=0.03)


def test_la_regression_logistique_a_converge(chaine, parties):
    """Learning curve: validation PR-AUC 0.789 at full size, 0.016 from the training score."""
    from churn_saas.modelisation import construire_baseline, courbe_apprentissage

    courbe = courbe_apprentissage(
        construire_baseline(chaine.X), parties.X_entrainement, parties.y_entrainement
    )
    finale = courbe.iloc[-1]
    assert finale["PR-AUC validation"] == pytest.approx(0.789, abs=0.01)
    assert finale["écart entraînement - validation"] < 0.05


def test_le_manifeste_decrit_le_decoupage_produit_par_le_code(chaine):
    """The test part recorded is the one the code sets aside today.

    When it fails after a deliberate change: re-run the materialisation (carnet 03), then
    commit the manifest with the code. Until then, no result on the test part is comparable.
    """
    from churn_saas.features import verifier_decoupage

    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    if "decoupage" not in manifeste:
        pytest.fail("Le manifeste n'enregistre pas le découpage : re-matérialiser (carnet 03).")
    controle = verifier_decoupage(chaine, manifeste)
    assert controle["conforme"].all(), controle.to_string()


# --- Phase 5 · Blocs B and C: the selection holds, and integrates ---------------------------
VARIABLES_RETENUES = [
    "jour_souscription",
    "secteur",
    "taille_entreprise",
    "plan",
    "anciennete_mois",
    "sieges_souscrits",
    "utilisateurs_actifs",
    "taux_adoption_pct",
    "connexions_30j",
    "heures_usage_30j",
    "fonctionnalites_utilisees",
    "nb_integrations",
    "derniere_connexion_jours",
    "tickets_support_90j",
    "delai_reponse_support_h",
    "csat",
    "retards_paiement_12m",
    "revenu_mensuel_recurrent_eur",
]


def test_les_variables_retenues_sont_celles_de_la_selection(chaine):
    """The 18 variables the selection kept, and only them; no decoy reaches the model."""
    from churn_saas.features import LEURRES

    assert list(chaine.X.columns) == VARIABLES_RETENUES
    assert not set(LEURRES) & set(chaine.X.columns)


def test_les_familles_couvrent_exactement_le_jeu_candidat(chaine):
    """Every candidate variable belongs to one family, so the ablation misses none."""
    from churn_saas.features import GROUPES_DE_VARIABLES, parties_avant_selection

    candidats = parties_avant_selection(chaine).X_entrainement.columns
    membres = [v for groupe in GROUPES_DE_VARIABLES.values() for v in groupe]
    assert sorted(membres) == sorted(candidats) and len(membres) == len(set(membres))


def test_les_variables_construites_n_apportent_toujours_rien(chaine):
    """Bloc B, logistic regression: gain -0.001, under one std between folds (0.020)."""
    from churn_saas.features import (
        VARIABLES_CONSTRUITES,
        comparer_jeux,
        parties_avant_selection,
        resumer_apport,
    )
    from churn_saas.modelisation import construire_baseline

    parties = parties_avant_selection(chaine)
    X, y = parties.X_entrainement, parties.y_entrainement
    brutes = [c for c in X.columns if c not in VARIABLES_CONSTRUITES]
    scores = comparer_jeux(construire_baseline, X, y, {"brutes": brutes, "toutes": list(X.columns)})
    apport = resumer_apport(scores, "brutes", "toutes")
    assert not apport["gain significatif"]
    assert apport["gain moyen"] == pytest.approx(-0.001, abs=0.005)


def test_les_retraits_combines_ne_coutent_rien(chaine):
    """Removals were confirmed one by one; together, the 18 variables lose nothing either
    (logistic regression: +0.003 over the 25 candidates, better on 23 folds out of 25)."""
    from churn_saas.features import comparer_jeux, parties_avant_selection, resumer_apport
    from churn_saas.modelisation import construire_baseline

    parties = parties_avant_selection(chaine)
    X, y = parties.X_entrainement, parties.y_entrainement
    scores = comparer_jeux(
        construire_baseline, X, y, {"candidats": list(X.columns), "retenues": VARIABLES_RETENUES}
    )
    apport = resumer_apport(scores, "candidats", "retenues")
    assert apport["gain moyen"] > -apport["écart-type entre plis"]
    assert apport["PR-AUC candidat"] == pytest.approx(0.793, abs=0.01)


def test_la_fuite_de_la_sante_du_compte_reste_demontree(chaine):
    """Bloc D: the same logistic regression goes from 0.891 to 0.999 AUC with the
    end-of-period health score - the leak the notebook narrates, now measured."""
    from churn_saas.features import parties_du_decoupage
    from churn_saas.modelisation import construire_baseline, demontrer_fuite

    parties = parties_du_decoupage(chaine)
    sante = pd.to_numeric(chaine.silver["sante_compte_fin_periode"], errors="coerce")
    table = demontrer_fuite(
        construire_baseline, parties.X_entrainement, parties.y_entrainement, sante
    ).set_index("jeu")
    assert table.loc["sans la variable", "AUC"] == pytest.approx(0.891, abs=0.01)
    assert table.loc["avec `sante_compte_fin_periode`", "AUC"] > 0.99


# --- Phase 6 · Baselines and reference results ------------------------------------------------
def _reference() -> dict:
    return json.loads(
        (RACINE / "resultats" / "reference_baseline.json").read_text(encoding="utf-8")
    )


def test_les_resultats_de_reference_sont_reproduits():
    """The code still yields, fold by fold, the baselines' results phase 7 must beat.

    When it fails after a deliberate change to the data or the protocol: rerun
    `tools/resultats_reference.py`, then commit the file with the change.
    """
    import importlib.util

    specification = importlib.util.spec_from_file_location(
        "resultats_reference", RACINE / "tools" / "resultats_reference.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    differences = outil.ecarts(_reference(), outil.calculer())
    assert not differences, "\n".join(differences)


def test_le_modele_bat_la_regle_metier_qui_bat_le_hasard():
    """PR-AUC 0.793 > 0.530 > 0.280: the model is worth more than what a CSM would do alone."""
    moyennes = {n: b["moyenne"]["PR-AUC"] for n, b in _reference()["baselines"].items()}
    assert moyennes["régression logistique"] > moyennes["règle métier"] > moyennes["naïve"]
    assert moyennes["régression logistique"] == pytest.approx(0.793, abs=0.01)
    assert moyennes["règle métier"] == pytest.approx(0.530, abs=0.01)


def test_la_regression_doit_etre_calibree_en_phase_7():
    """Calibration error 0.11, over the 0.05 threshold fixed beforehand: phase 7 calibrates.
    The class weighting that helps ranking pushes the probabilities up."""
    from churn_saas.config import SEUIL_ERREUR_CALIBRATION

    erreur = _reference()["baselines"]["régression logistique"]["moyenne"]["erreur de calibration"]
    assert erreur > SEUIL_ERREUR_CALIBRATION
    assert erreur == pytest.approx(0.114, abs=0.02)


# --- Phase 7 · Bloc 7.0: MLflow agrees with the sources of truth -----------------------------
@pytest.mark.skipif(
    importlib.util.find_spec("mlflow") is None, reason="MLflow absent (groupe suivi)"
)
def test_le_jeu_vu_par_mlflow_est_celui_du_manifeste(chaine):
    """The data run attaches the gold with the manifest's own fingerprint as digest."""
    mlflow = pytest.importorskip("mlflow")

    from churn_saas.packaging import tracer_donnees

    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    run_id = tracer_donnees(chaine.gold, chaine.journal, manifeste)
    run = mlflow.get_run(run_id)
    empreinte = manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"]
    assert run.inputs.dataset_inputs[0].dataset.digest == empreinte[:32]
    assert run.data.tags["empreinte_gold"] == empreinte


@pytest.mark.skipif(
    importlib.util.find_spec("mlflow") is None, reason="MLflow absent (groupe suivi)"
)
def test_les_baselines_retracees_sont_les_references_figees():
    """Phase 6 replayed into MLflow gives back, to the digit, the recorded reference."""
    from churn_saas.packaging import configurer_suivi

    specification = importlib.util.spec_from_file_location(
        "retracer_mlflow", RACINE / "tools" / "retracer_mlflow.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    retrace = outil.retracer_phase6(configurer_suivi(), {"phase": "6"})
    for nom, baseline in _reference()["baselines"].items():
        assert retrace[nom] == pytest.approx(baseline["moyenne"]["PR-AUC"], abs=1e-9)


# --- Phase 7 · The decision rules validated before any comparison (rule 8) ---------------------
def test_les_regles_de_la_phase_7_n_ont_pas_bouge_depuis_leur_validation():
    """B1 to B5 were validated on 02/10/2026, before tuning, comparison, calibration and the
    test evaluation. Changing one after the results is precisely what rule 8 forbids: it
    must go through this test, hence through a reviewed, dated change."""
    from churn_saas import config
    from churn_saas.modelisation import grille_hyperparametres

    assert config.ORDRE_DE_SIMPLICITE == ("régression logistique", "forêt aléatoire", "xgboost")
    assert config.METHODES_CALIBRATION == ("sigmoid", "isotonic")
    assert config.SEUIL_ERREUR_CALIBRATION == 0.05
    assert (config.TIRAGES_BOOTSTRAP, config.NIVEAU_CONFIANCE) == (1000, 0.95)
    assert config.MODELES_VALEUR_VIE == ("régression linéaire", "forêt de régression")
    grille = grille_hyperparametres()["xgboost"]
    combinaisons = 1
    for valeurs in grille.values():
        combinaisons *= len(valeurs)
    assert combinaisons == 24


# --- Phase 7 · The recorded selection follows the rules ------------------------------------------
def _selection() -> dict:
    chemin = RACINE / "resultats" / "selection_modele.json"
    if not chemin.exists():
        pytest.skip("Sélection pas encore enregistrée (tools/selection_modele.py).")
    return json.loads(chemin.read_text(encoding="utf-8"))


def test_la_selection_applique_la_regle_b1_a_ses_propres_chiffres():
    """Recomputing rule B1 from the recorded per-fold scores gives the recorded decision,
    and the regression's folds are those of the frozen reference."""
    from churn_saas.config import ORDRE_DE_SIMPLICITE
    from churn_saas.evaluation import comparer_a_la_reference, selectionner

    selection = _selection()
    regression = "régression logistique"
    reference = _reference()["baselines"][regression]["par_pli"]["PR-AUC"]
    assert selection["par_pli"][regression] == pytest.approx(reference, abs=1e-9)
    table = comparer_a_la_reference(selection["par_pli"], regression)
    assert selectionner(table, regression, ORDRE_DE_SIMPLICITE) == selection["modele_retenu"]


def test_la_calibration_retenue_est_celle_de_moindre_erreur():
    calibration = _selection()["calibration"]
    erreurs = {m: v["erreur de calibration"] for m, v in calibration["methodes"].items()}
    assert calibration["methode_retenue"] == min(erreurs, key=erreurs.get)


# --- Phase 7 · The single evaluation on the test part (rule B4) -----------------------------------
def _evaluation_finale() -> dict:
    chemin = RACINE / "resultats" / "evaluation_finale.json"
    if not chemin.exists():
        pytest.skip("Évaluation finale pas encore faite (tools/evaluation_finale.py).")
    return json.loads(chemin.read_text(encoding="utf-8"))


def test_l_evaluation_finale_porte_sur_le_jeu_de_test_enregistre():
    """The test part evaluated is the one the manifest set aside in phase 5."""
    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    evaluation = _evaluation_finale()
    assert evaluation["empreinte_comptes_test"] == manifeste["decoupage"]["empreinte_comptes_test"]
    assert evaluation["comptes_test"] == 1000


def test_le_resultat_sur_le_test_est_coherent_avec_la_validation_croisee():
    """PR-AUC 0.761 on the test part, interval [0.712, 0.806]: the cross-validated 0.793 lies
    inside it - the model generalises as the protocol predicted."""
    evaluation = _evaluation_finale()
    bas, haut = evaluation["intervalles_95"]["PR-AUC"]
    assert bas <= evaluation["validation_croisee_pr_auc"] <= haut
    assert bas <= evaluation["metriques"]["PR-AUC"] <= haut


def test_le_jeu_de_test_ne_peut_pas_etre_relu_en_silence(tmp_path):
    """A second evaluation is refused unless a motive is given and kept (rule B4)."""
    import shutil
    import subprocess
    import sys

    copie = tmp_path / "evaluation_finale.json"
    if not (RACINE / "resultats" / "evaluation_finale.json").exists():
        pytest.skip("Évaluation finale pas encore faite.")
    shutil.copy(RACINE / "resultats" / "evaluation_finale.json", copie)
    sortie = subprocess.run(
        [sys.executable, str(RACINE / "tools" / "evaluation_finale.py"), "--sortie", str(copie)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RACINE,
        timeout=120,
    )
    assert sortie.returncode != 0 and "ne sert qu'une fois" in sortie.stderr


def test_le_modele_de_valeur_retenu_suit_la_regle_b5():
    """Recorded: forest R² 0.888 against 0.805 on log(value), gain far above one standard
    deviation (0.004): the forest is kept, by the rule validated beforehand."""
    chemin = RACINE / "resultats" / "modele_valeur_vie.json"
    if not chemin.exists():
        pytest.skip("Modèle de valeur pas encore comparé (tools/modele_valeur_vie.py).")
    from churn_saas.modelisation import choisir_modele_valeur

    bilan = json.loads(chemin.read_text(encoding="utf-8"))
    assert choisir_modele_valeur(pd.DataFrame(bilan["r2_log_par_pli"])) == bilan["modele_retenu"]


# --- Optimisation B1 · The recorded phase 5 results say what the frozen figures say -------------
def test_les_resultats_enregistres_de_la_phase_5_concordent_avec_les_chiffres_figes():
    """The notebook now READS phase 5's computations from resultats/selection_variables.json.
    Whatever identity they were recorded under, they must agree with the figures frozen
    above - otherwise the notebook would show stale results."""
    chemin = RACINE / "resultats" / "selection_variables.json"
    if not chemin.exists():
        pytest.skip("Calculs de la phase 5 pas encore enregistrés (tools/selection_variables.py).")
    bilan = json.loads(chemin.read_text(encoding="utf-8"))
    assert bilan["permutation"]["score"] == pytest.approx(0.789, abs=0.01)
    assert bilan["permutation"]["p_valeur"] < 0.05
    assert bilan["adverse"]["auc"] < 0.6
    apport = pd.DataFrame(bilan["apports"]["Régression logistique"])
    assert (apport["brutes + construites"] - apport["brutes"]).mean() == pytest.approx(
        -0.001, abs=0.005
    )
    final = pd.DataFrame(bilan["final"]["Régression logistique"])
    assert final.filter(like="retenues").iloc[:, 0].mean() == pytest.approx(0.793, abs=0.01)
    assert sorted(bilan["candidates_au_retrait"]) == ["pays", "usage_par_actif"]


def test_les_trois_modeles_s_appuient_sur_des_facteurs_communs():
    """B6, option C: recorded SHAP comparison - integrations, seniority and support tickets
    are among the five main factors of all three models; the two tree models agree almost
    perfectly (rank correlation 0.96)."""
    chemin = RACINE / "resultats" / "explicabilite_comparee.json"
    if not chemin.exists():
        pytest.skip("Comparaison des explications pas encore enregistrée.")
    bilan = json.loads(chemin.read_text(encoding="utf-8"))
    assert {"nb_integrations", "anciennete_mois", "tickets_support_90j"} <= set(
        bilan["top_5_commun_aux_trois"]
    )
    for parts in bilan["parts"].values():
        assert sum(parts.values()) == pytest.approx(1.0, abs=1e-3)


def test_les_regles_de_la_phase_8_n_ont_pas_bouge_depuis_leur_validation():
    """Validated on 03/10/2026 before any tuning computation (rule 8)."""
    from churn_saas import config
    from churn_saas.modelisation import grille_hyperparametres

    assert (
        config.SEUIL_ECART_SURAPPRENTISSAGE,
        config.SEUIL_OPTIMISME_SELECTION,
        config.SEUIL_ECART_APPRENTISSAGE,
    ) == (0.05, 0.01, 0.02)
    assert (config.BUDGET_LOT_MENSUEL_S, config.BUDGET_COMPTE_MS) == (60.0, 50.0)
    grille = grille_hyperparametres()["regression"]
    assert grille["modele__C"] == [0.01, 0.03, 0.1, 0.3, 1, 3, 10]
    assert grille["modele__class_weight"] == [None, "balanced"]


# --- Phase 8 · The recorded tuning follows the rules validated beforehand ------------------------
def _reglage() -> dict:
    chemin = RACINE / "resultats" / "reglage_modele.json"
    if not chemin.exists():
        pytest.skip("Réglage pas encore enregistré (tools/reglage_modele.py).")
    return json.loads(chemin.read_text(encoding="utf-8"))


def test_le_reglage_retenu_suit_la_regle_d_un_ecart_type():
    """P3 then P1, recomputed from the recorded grid: C=0.01 without weighting, the most
    regularised combination within one standard deviation of the best (C=0.03)."""
    from churn_saas.config import SEUIL_ECART_SURAPPRENTISSAGE
    from churn_saas.modelisation import regle_un_ecart_type

    reglage = _reglage()
    table = pd.DataFrame(reglage["grille"])
    assert regle_un_ecart_type(table, SEUIL_ECART_SURAPPRENTISSAGE) == reglage["indice_retenu"]


def test_aucun_signe_de_surapprentissage_dans_le_reglage():
    """S1: every gap under 0.011 (threshold 0.05); S3: no selection optimism (-0.001);
    S4: final learning-curve gap 0.005; S5: calibration error 0.032."""
    s = _reglage()["surapprentissage"]
    assert s["S1_combinaisons_ecartees"] == 0 and s["S1_ecart_max_grille"] < 0.05
    assert s["S3_conforme"] and s["S4_conforme"] and s["S5_conforme"]


def test_le_reglage_ne_remplace_pas_le_champion():
    """P2: +0.0003 of paired PR-AUC (14 folds of 25), far under one standard deviation
    (0.019): the champion of phase 7 stays - and the test part need not be read again."""

    reglage = _reglage()
    table = pd.DataFrame(reglage["P2_comparaison"])
    assert not table["gain significatif"].any()
    assert reglage["P2_remplacer_le_champion"] is False


# --- Phase 8 · Decision c: the served model is equivalent to the evaluated champion -----------
def test_le_modele_servi_est_equivalent_au_champion_evalue():
    """One calibrated copy instead of five (decision c, option i - the test part is not read
    again): same PR-AUC (paired gain -0.0001, threshold 0.019), same calibration, same
    rankings (rank correlation 0.9999), within the per-account budget, about 5 times faster."""
    chemin = RACINE / "resultats" / "modele_servi.json"
    if not chemin.exists():
        pytest.skip("Modèle servi pas encore construit (tools/modele_servi.py).")
    bilan = json.loads(chemin.read_text(encoding="utf-8"))
    equivalence = bilan["equivalence"]
    assert equivalence["équivalent en performance"] and equivalence["calibration conforme"]
    assert equivalence["corrélation de rang des probabilités"] > 0.999
    assert equivalence["budget d'un compte respecté"] and equivalence["budget du lot respecté"]
    assert equivalence["accélération d'un compte"] > 3
    hyper = bilan["hyperparametres"]
    assert (hyper["C"], hyper["class_weight"], hyper["calibration"], hyper["copies calibrées"]) == (
        1.0,
        "balanced",
        "sigmoid",
        1,
    )
