"""Activity 3 - model preparation: what the statistical imputation learns, and from what.

The imputation is the one step of the preparation that learns from the data. That is
precisely what makes it a leakage risk: fitted on the whole table, it would let the test
set shape the values the model trains on. These tests pin where it learns.
"""

import numpy as np
import pandas as pd
import pytest

from churn_saas.modelisation import construire_preprocesseur
from churn_saas.modelisation.baseline import MODALITE_MANQUANTE


def _jeu() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "heures": [1.0, 2.0, 3.0, None, 100.0, 200.0],
            "secteur": ["Tech", None, "Tech", "Retail", "Retail", "Retail"],
        }
    )


def _matrice(sortie) -> np.ndarray:
    return np.asarray(sortie.toarray() if hasattr(sortie, "toarray") else sortie, dtype=float)


def test_l_imputation_est_apprise_sur_le_pli_d_entrainement_seulement():
    """The median learnt is the training fold's, never the whole table's.

    Training fold: 1, 2, 3 -> median 2. Whole table: median 3. Fitted on everything, the
    test rows (100, 200) would have pulled the value imputed into training rows.
    """
    X = _jeu()
    entrainement = X.iloc[:4]
    preprocesseur = construire_preprocesseur(X).fit(entrainement)
    mediane = preprocesseur.named_transformers_["num"].named_steps["imputation"].statistics_
    assert mediane.tolist() == [2.0]


def test_aucune_valeur_manquante_ne_sort_du_preprocesseur():
    X = _jeu()
    sortie = construire_preprocesseur(X).fit_transform(X)
    assert not np.isnan(_matrice(sortie)).any()


def test_les_categories_manquantes_deviennent_non_renseigne():
    """An explicit category, not the most frequent one.

    The mode would have turned the unknown sector into "Retail" here, inflating the
    dominant segment and biasing the per-segment fairness analysis.
    """
    X = _jeu()
    preprocesseur = construire_preprocesseur(X).fit(X)
    imputeur = preprocesseur.named_transformers_["cat"].named_steps["imputation"]
    assert imputeur.transform(X[["secteur"]].iloc[[1]]).ravel().tolist() == [MODALITE_MANQUANTE]


def test_le_candidat_partage_le_preprocesseur_de_la_baseline():
    """One imputation strategy for both models: otherwise the comparison measures two."""
    from churn_saas.modelisation import construire_baseline, construire_candidat

    X = _jeu()
    baseline = construire_baseline(X).steps[0][1]
    candidat = construire_candidat(X).steps[0][1]
    assert repr(baseline) == repr(candidat)


# --- Compute footprint, measured and converted openly ------------------------------------
@pytest.mark.phase5
def test_la_conversion_en_energie_et_en_emissions_est_exacte():
    """One hour at 10 W is 10 Wh; at 30.2 g/kWh, 0.302 g. Ten runs, ten times as much."""
    from churn_saas.modelisation import convertir_empreinte

    une = convertir_empreinte(3600, puissance_w=10, intensite_g_kwh=30.2)
    assert une["énergie (Wh)"] == 10
    assert une["émissions (g CO₂e)"] == pytest.approx(0.302)
    dix = convertir_empreinte(3600, puissance_w=10, intensite_g_kwh=30.2, executions=10)
    assert dix["énergie (Wh)"] == 100


@pytest.mark.phase5
def test_la_charge_se_deduit_des_temps_elementaires():
    """The workload is declared as data: each step costs its operations times their time."""
    from churn_saas.modelisation import EtapeDeCalcul, estimer_charge

    temps = {
        "entrainement_lr_s": 0.1,
        "entrainement_foret_s": 1.0,
        "importance_lr_s": 2.0,
        "importance_foret_s": 5.0,
        "scoring_portefeuille_s": 0.5,
    }
    charge = (
        EtapeDeCalcul("a", entrainements_lr=10, entrainements_foret=2),
        EtapeDeCalcul("b", importances_foret=1, scorings=4),
    )
    resultat = estimer_charge(temps, charge)
    assert resultat["secondes"].tolist() == [3.0, 7.0]
    assert resultat["entraînements"].tolist() == [12, 0]


@pytest.mark.phase5
def test_la_mesure_des_temps_renvoie_chaque_operation():
    """Smoke test on a small frame: every elementary time the document needs is measured."""
    from churn_saas.modelisation import mesurer_temps

    generateur = np.random.default_rng(0)
    X = pd.DataFrame(
        {"a": generateur.normal(size=200), "b": generateur.choice(["x", "y"], size=200)}
    )
    y = pd.Series((X["a"] > 0).astype(int))
    temps = mesurer_temps(X, y, repetitions=1)
    attendus = {
        "entrainement_lr_s",
        "entrainement_foret_s",
        "scoring_portefeuille_s",
        "importance_lr_s",
        "importance_foret_s",
        "lignes_entrainement",
    }
    assert attendus <= set(temps)
    assert all(v > 0 for v in temps.values())


# --- Phase 5 · Validating the split and the dataset ---------------------------------------
def _donnees_informatives(n: int = 400, signal: bool = True):
    generateur = np.random.default_rng(1)
    X = pd.DataFrame({"a": generateur.normal(size=n), "b": generateur.normal(size=n)})
    bruit = generateur.normal(scale=0.5, size=n)
    y = pd.Series(((X["a"] + bruit > 0.6) if signal else (generateur.random(n) < 0.28)).astype(int))
    return X, y


@pytest.mark.phase5
def test_la_validation_adverse_ne_distingue_pas_deux_tirages_de_la_meme_source():
    from churn_saas.modelisation import construire_baseline, validation_adverse

    X, _ = _donnees_informatives()
    resultat = validation_adverse(construire_baseline(X), X.iloc[:300], X.iloc[300:])
    assert resultat["auc"] < 0.6 and resultat["conforme"]


@pytest.mark.phase5
def test_la_validation_adverse_detecte_un_decalage():
    """A test part drawn elsewhere is told apart.

    The check can fail, which is what gives its passing a meaning.
    """
    from churn_saas.modelisation import construire_baseline, validation_adverse

    X, _ = _donnees_informatives()
    decale = X.iloc[300:].assign(a=lambda d: d["a"] + 2)
    resultat = validation_adverse(construire_baseline(X), X.iloc[:300], decale)
    assert resultat["auc"] > 0.8 and not resultat["conforme"]


@pytest.mark.phase5
def test_le_test_de_permutation_separe_signal_et_bruit():
    """Real signal beats every shuffle; pure noise does not."""
    from churn_saas.modelisation import construire_baseline, tester_permutation

    X, y = _donnees_informatives(signal=True)
    avec = tester_permutation(construire_baseline(X), X, y, n_permutations=20)
    X, y = _donnees_informatives(signal=False)
    sans = tester_permutation(construire_baseline(X), X, y, n_permutations=20)
    assert avec["conforme"] and avec["p_valeur"] < 0.05
    assert not sans["conforme"]


@pytest.mark.phase5
def test_la_courbe_d_apprentissage_couvre_chaque_taille():
    from churn_saas.modelisation import construire_baseline, courbe_apprentissage

    X, y = _donnees_informatives()
    courbe = courbe_apprentissage(construire_baseline(X), X, y, tailles=(0.5, 1.0))
    assert len(courbe) == 2
    assert {"PR-AUC entraînement", "PR-AUC validation", "écart-type validation"} <= set(courbe)


@pytest.mark.phase5
def test_une_variable_connue_apres_l_issue_est_demontree_comme_fuite():
    """A variable built from the outcome lifts the AUC to near perfection: the symptom."""
    from churn_saas.modelisation import construire_baseline, demontrer_fuite

    X, y = _donnees_informatives()
    fuite = pd.Series(y + np.random.default_rng(4).normal(scale=0.05, size=len(y)), name="apres")
    table = demontrer_fuite(construire_baseline, X, y, fuite).set_index("jeu")
    assert table.loc["avec `apres`", "AUC"] > 0.98
    assert table.loc["sans la variable", "AUC"] < table.loc["avec `apres`", "AUC"]
