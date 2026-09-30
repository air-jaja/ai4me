"""Non-regression tests for the framing step (notebook 01_cadrage).

**Why these tests exist.** The framing decisions rest on figures computed from the data:
the churn rate, the concentration of value, the spread of the rational action threshold.
Those figures are quoted in the notebook, in the explanatory documents and in the oral
presentation. If a change to the cleaning chain moved any of them, three deliverables
would become wrong at once - silently.

These tests pin the numbers the framing relies on. They are not about model quality: they
are about the arguments staying true.

Tolerances are deliberately loose. The point is to catch a chain that broke, not to forbid
a rounding difference.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn_saas.config import COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION
from churn_saas.donnees.ingestion import charger_bronze
from churn_saas.donnees.silver import construire_silver
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


@pytest.fixture(scope="module")
def silver() -> pd.DataFrame:
    """Cleaned dataset, built exactly as the framing notebook builds it."""
    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip(
            "Jeu de données absent ou réduit à un pointeur Git-LFS. "
            "Exécuter `git lfs pull` ou replacer les CSV dans data/raw/."
        )
    brut = charger_bronze(fichier)
    catalogue = charger_bronze(DONNEES / "catalogue_plans.csv")
    return construire_silver(
        brut,
        catalogue=catalogue,
        colonnes_decimales=COLONNES_DECIMALES,
        colonnes_dates=["date_souscription"],
        colonnes_entieres=COLONNES_ENTIERES,
    )


# --- Volumetry, quoted in sections 1.1 and 5 of the framing notebook -----------------
def test_volumetrie_de_reference(silver: pd.DataFrame):
    """The source file and its duplicate count must be the ones the framing used.

    Every figure downstream is computed on these 5,000 accounts: a changed source would
    invalidate the framing notebook, the explanatory document and the oral pitch at once."""
    brut = charger_bronze(DONNEES / "churn_saas_complet.csv")
    assert len(brut) == 5035, "Le fichier source n'est plus celui du cadrage"
    assert len(silver) == 5000, "Le nombre de doublons stricts a changé"


def test_la_jointure_catalogue_apparie_tous_les_comptes(silver: pd.DataFrame):
    """A silent join failure would corrupt every downstream figure."""
    assert "prix_mensuel_par_siege_eur" in silver.columns
    assert silver["prix_mensuel_par_siege_eur"].notna().all()


# --- Target, quoted in sections 1.1 and 8 --------------------------------------------
def test_taux_de_churn_de_reference(silver: pd.DataFrame):
    """The churn rate must stay at 28%.

    It underpins the 'moderate imbalance' argument of section 8 and the 72% accuracy a
    trivial model would reach - both quoted verbatim in the deliverables."""
    taux = float(silver["churn"].astype(float).mean())
    assert taux == pytest.approx(0.28, abs=0.005), (
        "Le taux de churn fonde l'argument « déséquilibre modéré » de la section 8"
    )


# --- Value concentration: the finding that changed the objective ----------------------
def test_concentration_de_la_valeur(silver: pd.DataFrame):
    """10% of accounts carry ~68% of revenue; 10% of churners carry ~72% of the loss.

    This is the observation that turned exhaustive detection into prioritisation.
    """
    mrr = pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").dropna()
    churn = silver["churn"].astype(float)

    part_top10 = mrr.sort_values(ascending=False).head(int(len(mrr) * 0.10)).sum() / mrr.sum()
    assert part_top10 == pytest.approx(0.68, abs=0.03)

    perdu = pd.to_numeric(
        silver.loc[churn == 1, "revenu_mensuel_recurrent_eur"], errors="coerce"
    ).dropna()
    part_churners = (
        perdu.sort_values(ascending=False).head(int(len(perdu) * 0.10)).sum() / perdu.sum()
    )
    assert part_churners == pytest.approx(0.72, abs=0.03), (
        "Le chiffre de 72 % est cité dans le cadrage, le README et la soutenance"
    )


def test_mrr_total_de_reference(silver: pd.DataFrame):
    """Portfolio revenue must stay around 17.2 million euros.

    This is the reference base against which exposed, covered and preserved revenue are
    expressed in section 12."""
    mrr = pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce")
    assert float(mrr.sum()) == pytest.approx(17.2e6, rel=0.05)


# --- Decision rule: the factor quoted in sections 3.3 and 9 ---------------------------
def test_l_ecart_de_seuil_entre_deciles_reste_superieur_a_cent(silver: pd.DataFrame):
    """The 'factor > 100' argument justifies rejecting a single global threshold."""
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    seuils = seuil_par_compte(clv.quantile([0.10, 0.90]))
    facteur = float(seuils.iloc[0] / seuils.iloc[1])
    assert facteur > 100, (
        f"Écart tombé à {facteur:.0f} : l'argument central de la règle de décision ne tient plus"
    )


def test_le_seuil_du_dernier_decile_reste_tres_bas(silver: pd.DataFrame):
    """Acting on a top-decile account must stay rational below 1% risk.

    The 0.3% figure is the striking end of the argument presented to the jury."""
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    assert float(seuil_par_compte(pd.Series([clv.quantile(0.90)])).iloc[0]) < 0.01


# --- Assumptions: pinned so a silent edit cannot invalidate the deliverables ----------
def test_les_hypotheses_de_cadrage_sont_inchangees():
    """These three values are quoted verbatim in the documents and the oral pitch."""
    assert EFFICACITE_RETENTION == 0.25
    assert COUT_CONTACT_CSM_EUR == 135.0


def test_precision_statistique_du_rappel_reste_autour_de_cinq_points(silver: pd.DataFrame):
    """The '+/- 5 points' caveat stated in section 9 must remain true."""
    n_positifs = int(silver["churn"].astype(float).sum() * 0.20)
    demi_largeur = 1.96 * np.sqrt(0.70 * 0.30 / n_positifs)
    assert demi_largeur == pytest.approx(0.054, abs=0.01)
