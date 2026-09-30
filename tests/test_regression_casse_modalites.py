"""The category-case defect: what it produced, and what the fix produces.

Found in phase 3 while plotting churn rate per segment: the chart showed eight company
sizes where the business has four, and twenty-one sectors where it has seven. Case
normalisation was applied to the join key only, through a temporary column - the join
worked while the stored values kept every spelling.

**Why two sets of tests rather than one.** The first set reproduces the defect with
normalisation switched off and pins what it produced. It documents that the problem was
real, measured, and how far it reached - a corrected bug with no trace is a bug the next
person reintroduces. The second set pins the corrected behaviour.

The defect also invalidated three published figures in the framing notebook, which is what
makes it worth this much attention: the segment spreads were overstated by a factor of two,
and the framing conclusion rested on them.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from churn_saas.donnees import charger_bronze
from churn_saas.donnees.silver import construire_silver

RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "data" / "raw"

SEGMENTS = ("taille_entreprise", "secteur", "plan")


@pytest.fixture(scope="module")
def brut() -> pd.DataFrame:
    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    return charger_bronze(fichier)


def _amplitude(df: pd.DataFrame, colonne: str, effectif_minimal: int = 30) -> float:
    """Spread in points between the highest and lowest churn rate across modalities."""
    churn = pd.to_numeric(df["churn"], errors="coerce")
    groupes = churn.groupby(df[colonne]).agg(["mean", "size"])
    retenus = groupes.loc[groupes["size"] >= effectif_minimal, "mean"]
    return float((retenus.max() - retenus.min()) * 100)


# =====================================================================================
# 1. The defect, reproduced and measured
# =====================================================================================
@pytest.mark.parametrize(
    ("colonne", "modalites_fragmentees", "modalites_reelles"),
    [("taille_entreprise", 8, 4), ("secteur", 21, 7), ("plan", 12, 4)],
)
def test_sans_normalisation_les_categories_sont_fragmentees(
    brut: pd.DataFrame, colonne: str, modalites_fragmentees: int, modalites_reelles: int
):
    """Without value normalisation, each spelling counts as its own category.

    One-hot encoding would then produce a column per spelling: the model sees several rare
    categories where the business has one, splits the signal between them, and every
    importance reading becomes misleading.
    """
    silver = construire_silver(brut, colonnes_categorielles=[])
    assert silver[colonne].nunique() == modalites_fragmentees
    assert silver[colonne].astype(str).str.casefold().nunique() == modalites_reelles


def test_sans_normalisation_des_modalites_deviennent_trop_petites(brut: pd.DataFrame):
    """Fragmentation creates modalities too small for their rate to mean anything.

    `tpe` carried 49 accounts against 1 435 for `TPE`. The small one, statistically
    unstable, then set the extreme of the segment table published in the framing notebook.
    """
    silver = construire_silver(brut, colonnes_categorielles=[])
    effectifs = silver["taille_entreprise"].value_counts()
    assert effectifs.min() < 60
    assert effectifs.max() / effectifs.min() > 20


@pytest.mark.parametrize(
    ("colonne", "amplitude_surestimee"),
    [("taille_entreprise", 13.2), ("secteur", 16.9), ("plan", 24.4)],
)
def test_sans_normalisation_les_ecarts_entre_segments_sont_surestimes(
    brut: pd.DataFrame, colonne: str, amplitude_surestimee: float
):
    """The fragmented spread is what the framing notebook published, and it was wrong.

    Pinned here so the erroneous figures stay traceable: a reader of the git history must
    be able to tell which numbers were corrected, and by how much.
    """
    silver = construire_silver(brut, colonnes_categorielles=[])
    assert _amplitude(silver, colonne) == pytest.approx(amplitude_surestimee, abs=0.3)


# =====================================================================================
# 2. The fix, confirmed
# =====================================================================================
@pytest.mark.parametrize(
    ("colonne", "modalites"), [("taille_entreprise", 4), ("secteur", 7), ("plan", 4)]
)
def test_apres_normalisation_une_seule_etiquette_par_categorie(
    brut: pd.DataFrame, colonne: str, modalites: int
):
    """One label per business category, and it is the most frequent spelling.

    A deliverable read by a jury should show `TPE`, not `tpe`.
    """
    silver = construire_silver(brut)
    assert silver[colonne].nunique() == modalites
    valeurs = silver[colonne].dropna().astype(str)
    assert valeurs.nunique() == valeurs.str.strip().str.casefold().nunique()


@pytest.mark.parametrize(
    ("colonne", "amplitude_reelle"),
    [("taille_entreprise", 8.3), ("secteur", 7.0), ("plan", 17.5)],
)
def test_apres_normalisation_les_ecarts_refletent_le_metier(
    brut: pd.DataFrame, colonne: str, amplitude_reelle: float
):
    """The corrected spreads are those the framing notebook now publishes.

    They are roughly half the previous ones - which **strengthens** the framing
    conclusion: no segment concentrates the risk, so a model is justified over a business
    rule. The argument held; the figure supporting it did not.
    """
    silver = construire_silver(brut)
    assert _amplitude(silver, colonne) == pytest.approx(amplitude_reelle, abs=0.3)


def test_apres_normalisation_aucune_modalite_n_est_marginale(brut: pd.DataFrame):
    """Every modality now carries enough accounts for its rate to be readable.

    This is what makes grouping unnecessary, a decision stated in the exploration notebook.
    """
    silver = construire_silver(brut)
    for colonne in SEGMENTS:
        assert int(silver[colonne].value_counts().min()) >= 50


def test_la_normalisation_est_desactivable_explicitement(brut: pd.DataFrame):
    """An empty list means "normalise nothing", it does not fall back to the default.

    Written with `or` instead of `is None`, the parameter silently ignored an empty list -
    and the defect tests above would have measured the corrected behaviour while claiming
    to measure the broken one.
    """
    assert construire_silver(brut, colonnes_categorielles=[])["secteur"].nunique() == 21
    assert construire_silver(brut, colonnes_categorielles=["secteur"])["secteur"].nunique() == 7
    assert construire_silver(brut)["secteur"].nunique() == 7


# =====================================================================================
# 3. The quality audit now reports both consequences
# =====================================================================================
def test_l_audit_chiffre_les_modalites_en_trop(brut: pd.DataFrame):
    """The audit counts the surplus modalities instead of naming the columns.

    Phase 2 reported "case and whitespace inconsistent" on three columns and stopped
    there. A defect stated without its scope cannot be arbitrated: 26 surplus modalities
    is a number a reader can act on, "inconsistent" is not.
    """
    from churn_saas.donnees import auditer_qualite

    ligne = auditer_qualite(brut)
    ligne = ligne.loc[ligne["défaut"].str.contains("Casse")].iloc[0]
    assert "26 modalités en trop" in ligne["portée"]
    assert "21 au lieu de 7" in ligne["portée"]


def test_l_audit_signale_les_deux_consequences_de_la_casse(brut: pd.DataFrame):
    """Both effects are reported, not just the join failure.

    Phase 2 mentioned only the silent join. The second - category fragmentation at
    encoding time - is the more damaging, and it is the one that actually invalidated
    published figures.
    """
    from churn_saas.donnees import auditer_qualite

    audit = auditer_qualite(brut)
    consequence = audit.loc[audit["défaut"].str.contains("Casse"), "conséquence si non traité"]
    texte = consequence.iloc[0]
    assert "jointure" in texte.lower()
    assert "encodage" in texte.lower()
