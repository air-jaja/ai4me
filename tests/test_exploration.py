"""Activity 1 profiling and activity 2 exploration (phase 3).

These functions decide the preparation: the imputation strategy, the choice of metric and
the handling of extreme values all follow from what they measure. A profiling function
that reports wrong sends the whole phase in the wrong direction, quietly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn_saas.donnees import (
    bornes_valeurs_extremes,
    manquants_structurels,
    mecanisme_manquants,
    profil_distributions,
    profil_doublons,
    profil_manquants,
    resume_profilage,
    silver_lisible,
)
from churn_saas.features import (
    correlations_cible,
    correlations_entre_variables,
    desequilibre_categories,
    desequilibre_cible,
    executer_pipeline,
    monotonie,
    table_transformations,
    taux_cible_par_segment,
    tendance_par_tranche,
)


# --- Profiling ------------------------------------------------------------------------
def test_le_profil_des_manquants_classe_par_gravite():
    """A column missing over half its values is not treated like one missing 3%."""
    df = pd.DataFrame(
        {
            "complete": list(range(20)),
            "un_peu": [None] + list(range(19)),  # 5 %
            "beaucoup": [None] * 15 + list(range(5)),  # 75 %
        }
    )
    profil = profil_manquants(df).set_index("colonne")
    assert profil.loc["complete", "verdict"] == "complète"
    assert profil.loc["un_peu", "verdict"] == "imputable"
    assert profil.loc["beaucoup", "verdict"] == "écarter ou traiter à part"


def test_le_profil_des_doublons_distingue_stricts_et_cle():
    """Two different questions: an export accident, or one account with two versions.

    A strict duplicate can be dropped. A duplicate on the key alone cannot: the two rows
    disagree, and no automatic rule can decide which is right.
    """
    df = pd.DataFrame({"id": ["a", "a", "b"], "valeur": [1, 2, 3]})
    profil = profil_doublons(df, cle="id")
    assert int(profil.iloc[0]["nombre"]) == 0  # no strictly identical row
    assert int(profil.iloc[1]["nombre"]) == 1  # but the key repeats


def test_le_profil_des_distributions_signale_l_asymetrie():
    """The mean-to-median ratio is what decides median imputation over mean imputation."""
    df = pd.DataFrame({"symetrique": list(range(1, 100)), "asymetrique": [1] * 98 + [10_000]})
    profil = profil_distributions(df).set_index("colonne")
    assert profil.loc["symetrique", "moyenne/médiane"] == pytest.approx(1.0, abs=0.05)
    assert profil.loc["asymetrique", "moyenne/médiane"] > 5


def test_le_mecanisme_des_manquants_mesure_l_ecart_a_la_cible():
    """An absence that predicts the target must be kept as a signal, not filled in."""
    df = pd.DataFrame(
        {
            "informatif": [None] * 50 + list(range(50)),
            "churn": [1] * 50 + [0] * 50,
        }
    )
    profil = mecanisme_manquants(df, cible="churn")
    assert abs(float(profil.iloc[0]["écart (points)"])) > 50


def test_un_manquant_structurel_se_distingue_d_un_manquant_aleatoire():
    """A delay missing only when no ticket exists is structural: imputing would invent it."""
    df = pd.DataFrame(
        {
            "delai": [None] * 40 + [2.0] * 60,
            "tickets": [0] * 40 + [3] * 60,
        }
    )
    profil = manquants_structurels(df, {"delai": "tickets"})
    assert bool(profil.iloc[0]["structurel"])

    aleatoire = pd.DataFrame({"delai": [None] * 40 + [2.0] * 60, "tickets": [3] * 100})
    assert not bool(manquants_structurels(aleatoire, {"delai": "tickets"}).iloc[0]["structurel"])


def test_les_bornes_de_tukey_sont_informatives_et_non_appliquees():
    """Bounds are given for reference: on this portfolio the extremes are real accounts.

    Removing them would drop exactly the customers the project exists to protect.
    """
    basse, haute = bornes_valeurs_extremes(pd.Series([1, 2, 3, 4, 5, 100]))
    assert basse < 1 < haute < 100


# --- Pipeline -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def resultat():
    """Full pipeline on the real data, skipped when the sources are unavailable."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    fichier = racine / "data" / "raw" / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    return executer_pipeline(fichier, racine / "data" / "raw" / "catalogue_plans.csv")


def test_le_pipeline_journalise_chacune_de_ses_etapes(resultat):
    """A transformation nobody can quantify is a transformation nobody can defend."""
    journal = resultat.journal
    # "contrat" since phase 4: the data contract runs between silver and the ratios.
    assert list(journal["niveau"]) == ["bronze", "silver", "contrat", "silver+", "gold", "X / y"]
    assert (journal["effet"].str.len() > 10).all()


def test_le_pipeline_retire_les_colonnes_interdites(resultat):
    """The gold dataset carries no identifier, no leak, no free text, no secondary target."""
    interdites = {
        "client_id",
        "commentaire_csm",
        "groupe_experimentation",
        "sante_compte_fin_periode",
        "valeur_vie_client_eur",
    }
    assert not interdites & set(resultat.X.columns)
    assert "churn" not in resultat.X.columns


def test_le_pipeline_peut_se_passer_des_variables_derivees(resultat):
    """Switching enrichment off is what makes the evaluation -> features loop measurable.

    Without this parameter, the contribution of feature engineering could only be
    asserted, never compared.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    sans = executer_pipeline(
        racine / "data" / "raw" / "churn_saas_complet.csv",
        racine / "data" / "raw" / "catalogue_plans.csv",
        enrichir=False,
    )
    assert sans.X.shape[1] < resultat.X.shape[1]
    assert "silver+" not in set(sans.journal["niveau"])


def test_la_table_des_transformations_trace_chaque_colonne(resultat):
    """Every column says where it comes from and where it stops."""
    table = table_transformations(resultat)
    assert set(table["origine"]) <= {"source", "construite"}
    assert (table.loc[table["devenir"] == "retirée au gold", "motif"] != "—").all()


def test_le_silver_lisible_ne_sert_jamais_au_modele(resultat):
    """Readable silver fills every hole, which is exactly why it must not train a model.

    The values are computed on the whole table: using them would let the test set
    influence what the model learns. The `_impute` flags make a reconstructed value
    distinguishable from an observed one.
    """
    lisible = silver_lisible(resultat.silver)
    assert int(lisible.isna().sum().sum()) == 0
    assert any(c.endswith("_impute") for c in lisible.columns)
    assert lisible.shape[1] > resultat.silver.shape[1]


# --- Exploration ----------------------------------------------------------------------
def test_le_desequilibre_est_qualifie_et_non_seulement_chiffre():
    """Overstating the imbalance in a presentation invites a correction."""
    modere = desequilibre_cible(pd.Series([1] * 28 + [0] * 72)).set_index("mesure")
    assert modere.loc["Qualification", "valeur"] == "déséquilibre modéré"

    severe = desequilibre_cible(pd.Series([1] * 2 + [0] * 98)).set_index("mesure")
    assert severe.loc["Qualification", "valeur"] == "déséquilibre sévère"


def test_le_desequilibre_des_categories_repere_les_modalites_rares():
    """A modality carrying a handful of rows produces an estimate nobody should trust."""
    df = pd.DataFrame({"secteur": ["A"] * 200 + ["B"] * 100 + ["C"] * 5})
    profil = desequilibre_categories(df, ["secteur"], effectif_minimal=50)
    assert int(profil.iloc[0]["modalités < 50"]) == 1


def test_le_taux_par_segment_expose_l_ecart_au_global():
    """The gap is what matters: a segment at the average carries no information."""
    df = pd.DataFrame({"segment": ["A"] * 100 + ["B"] * 100, "churn": [1] * 80 + [0] * 120})
    profil = taux_cible_par_segment(df, "segment", "churn")
    assert float(profil.iloc[0]["écart au global (points)"]) > 0
    assert float(profil.iloc[-1]["écart au global (points)"]) < 0


def test_les_correlations_sont_classees_par_force_absolue():
    """A strong negative driver matters as much as a strong positive one."""
    rng = np.random.default_rng(0)
    y = pd.Series(rng.integers(0, 2, 500))
    X = pd.DataFrame(
        {
            "protectrice": -y + rng.normal(0, 0.1, 500),
            "bruit": rng.normal(0, 1, 500),
            "aggravante": y + rng.normal(0, 0.5, 500),
        }
    )
    profil = correlations_cible(X, y)
    assert profil.iloc[0]["variable"] == "protectrice"
    assert profil.iloc[0]["sens"] == "diminue le risque"
    assert not bool(profil.loc[profil["variable"] == "bruit", "notable"].iloc[0])


def test_les_variables_redondantes_sont_signalees():
    """Two equivalent variables share the credit, and both look half as useful as they are."""
    X = pd.DataFrame({"a": range(100), "copie": [v * 2 for v in range(100)], "autre": [1] * 100})
    paires = correlations_entre_variables(X, seuil=0.80)
    assert {"a", "copie"} == {paires.iloc[0]["variable A"], paires.iloc[0]["variable B"]}


def test_la_tendance_par_tranche_revele_le_non_monotone():
    """A correlation coefficient hides a strong non-monotonic relationship."""
    df = pd.DataFrame({"x": list(range(100)), "churn": [1] * 25 + [0] * 50 + [1] * 25})
    profil = tendance_par_tranche(df, "x", "churn", n_tranches=4)
    assert monotonie(profil) == "non monotone"

    croissant = pd.DataFrame({"x": list(range(100)), "churn": [0] * 50 + [1] * 50})
    assert monotonie(tendance_par_tranche(croissant, "x", "churn", n_tranches=4)) == "croissante"


# --- Findings pinned on the real data -------------------------------------------------
def test_les_manquants_des_colonnes_SOURCE_sont_completement_aleatoires(resultat):
    """On source columns, neither the target nor a structural cause explains the holes.

    Two independent readings agree, which is what legitimises a statistical imputation
    fitted inside the model pipeline. Should either move, the strategy would have to be
    reconsidered.
    """
    colonnes_source = [c for c in resultat.bronze.columns if c in resultat.silver.columns]
    mecanisme = mecanisme_manquants(resultat.silver, cible="churn", colonnes=colonnes_source)
    assert mecanisme["écart (points)"].abs().max() < 6

    structurels = manquants_structurels(
        resultat.silver,
        {"delai_reponse_support_h": "tickets_support_90j", "csat": "tickets_support_90j"},
    )
    assert not structurels["structurel"].any()


def test_les_manquants_des_ratios_sont_structurels_et_porteurs_de_signal(resultat):
    """The conclusion drawn on source columns does not carry over to derived ones.

    Dividing by the number of active users yields NaN when that number is zero. Those NaN
    encode an abandoned account - still paid for, used by nobody - and separate the target
    more strongly than any other variable in the dataset.

    Imputing them with a median would replace the strongest available signal by the value
    of an ordinary account, and no metric would report the loss.
    """
    mecanisme = mecanisme_manquants(resultat.silver, cible="churn", colonnes=["tickets_par_actif"])
    assert float(mecanisme.iloc[0]["écart (points)"]) > 50

    actifs = pd.to_numeric(resultat.silver["utilisateurs_actifs"], errors="coerce")
    nan_ratio = resultat.silver["tickets_par_actif"].isna()
    assert (nan_ratio == (actifs == 0)).all(), "Les NaN du ratio ont une autre cause"


def test_l_indicateur_de_compte_abandonne_rend_le_signal_explicite(resultat):
    """The signal becomes a variable instead of a side effect of a division by zero.

    A NaN survives no imputation; a declared indicator does. It is also readable by a CSM,
    which a missing value is not.
    """
    assert "compte_sans_utilisateur_actif" in resultat.X.columns
    indicateur = pd.to_numeric(resultat.X["compte_sans_utilisateur_actif"], errors="coerce")
    cible = resultat.y.astype(float)
    assert float(cible[indicateur == 1].mean()) > 0.80
    assert float(cible[indicateur == 0].mean()) < 0.30


def test_le_resume_de_profilage_couvre_les_constats_cles(resultat):
    resume = resume_profilage(resultat.silver, cible="churn", cle="client_id")
    assert len(resume) >= 8
    assert (resume["valeur"].astype(str).str.len() > 0).all()
