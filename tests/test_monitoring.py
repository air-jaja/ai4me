"""Activity 7 - drift detection and alert rules."""

import numpy as np
import pandas as pd
import pytest

from churn_saas.monitoring.alertes import evaluer_alertes, table_regles
from churn_saas.monitoring.derive import ks_deux_echantillons, psi, rapport_derive


def test_psi_nul_sur_distributions_identiques():
    """Identical distributions must score near zero.

    A drift indicator raising alerts on stable data would be switched off within a month."""
    serie = pd.Series(np.random.default_rng(0).normal(size=5_000))
    assert psi(serie, serie) < 0.01


def test_psi_detecte_un_decalage_franc():
    """A clear distribution shift must cross the alert threshold."""
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(0, size=5_000)), pd.Series(rng.normal(2, size=5_000))) > 0.25


def test_ks_coherent_avec_le_psi():
    """The Kolmogorov-Smirnov test must agree with PSI on obvious cases.

    The two indicators are read together: a disagreement on a clear-cut case would mean one
    of them is misconfigured."""
    rng = np.random.default_rng(1)
    _, p_identique = ks_deux_echantillons(
        pd.Series(rng.normal(size=2_000)), pd.Series(rng.normal(size=2_000))
    )
    _, p_decale = ks_deux_echantillons(
        pd.Series(rng.normal(0, size=2_000)), pd.Series(rng.normal(2, size=2_000))
    )
    assert p_identique > 0.01
    assert p_decale < 0.01


def test_rapport_derive_marque_les_alertes():
    """The drift report must flag the drifting variable and only that one."""
    rng = np.random.default_rng(2)
    ref = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(size=2_000)})
    cur = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(3, size=2_000)})
    rapport = rapport_derive(ref, cur, ["a", "b"])
    assert bool(rapport.loc[rapport["variable"] == "b", "alerte"].iloc[0]) is True


def test_chaque_regle_porte_une_action_et_un_responsable():
    """No rule may exist without a triggered action and a named owner.

    A dashboard with no action owner produces no decision - it produces meetings."""
    regles = table_regles()
    assert (regles["action"].str.len() > 0).all()
    assert (regles["responsable"].str.len() > 0).all()


def test_alerte_declenchee_expose_son_action():
    """A triggered alert must surface what to do and who does it."""
    resultat = evaluer_alertes({"PSI sur variables clés": True})
    ligne = resultat.loc[resultat["indicateur"] == "PSI sur variables clés"].iloc[0]
    assert ligne["declenchee"]
    assert ligne["responsable"] != "—"


# --- Phase 5 · Categorical stability ------------------------------------------------------
def test_le_psi_categoriel_est_nul_sans_changement_et_positif_sinon():
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a"] * 50 + ["b"] * 50)
    assert psi_categoriel(reference, reference) == pytest.approx(0, abs=1e-9)
    assert psi_categoriel(reference, pd.Series(["a"] * 90 + ["b"] * 10)) > 0.25


def test_une_hausse_des_manquants_categoriels_est_une_derive():
    """Missing values form their own category: more of them is a drift."""
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a", "b"] * 50)
    courant = pd.Series(["a", "b"] * 25 + [None] * 50)
    assert psi_categoriel(reference, courant) > 0.25


def test_une_derive_categorielle_declenche_une_alerte():
    """A sector mix moving from 50/50 to 95/5 must raise an alert.

    Until phase 5 the numeric index was applied to every column: on text it returned NaN,
    and NaN compared to the threshold gave "no alert". The largest possible drift on a
    categorical variable was reported as none, without any error.
    """
    from churn_saas.monitoring import rapport_derive

    reference = pd.DataFrame({"x": range(100), "c": ["a", "b"] * 50})
    courant = pd.DataFrame({"x": range(100), "c": ["a"] * 95 + ["b"] * 5})
    rapport = rapport_derive(reference, courant, ["x", "c"]).set_index("variable")
    assert rapport.loc["c", "alerte"] and not pd.isna(rapport.loc["c", "psi"])
    assert not rapport.loc["x", "alerte"]
