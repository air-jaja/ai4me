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


@pytest.mark.phase11
def test_chaque_regle_porte_une_action_et_un_responsable():
    """No rule may exist without a triggered action and a named owner.

    A dashboard with no action owner produces no decision - it produces meetings."""
    regles = table_regles()
    assert (regles["action"].str.len() > 0).all()
    assert (regles["responsable"].str.len() > 0).all()


@pytest.mark.phase11
def test_alerte_declenchee_expose_son_action():
    """A triggered alert must surface what to do and who does it."""
    resultat = evaluer_alertes({"Dérive des entrées et du score (PSI)": True})
    ligne = resultat.loc[resultat["indicateur"] == "Dérive des entrées et du score (PSI)"].iloc[0]
    assert ligne["declenchee"]
    assert ligne["responsable"] != "—"


# --- Phase 11 · Defaults validated before any implementation ----------------------------
@pytest.mark.phase11
def test_les_valeurs_par_defaut_de_la_phase_11_sont_figees():
    """M1 to M9, validated by the project owner on 04/10/2026 (rule 8): changing one is a new
    decision, committed alone - not an edit slipped into an implementation commit."""
    from churn_saas.monitoring import alertes

    assert alertes.CIBLE_COUVERTURE_REVENU == 0.50
    assert alertes.FREQUENCE_REENTRAINEMENT_MOIS == 3
    assert alertes.FENETRE_REENTRAINEMENT_MOIS == 12
    assert (alertes.SEUIL_PSI_VARIABLE_CLE, alertes.SEUIL_PSI_MODERE) == (0.25, 0.10)
    assert (alertes.NB_VARIABLES_PSI_MODERE, alertes.SEUIL_PSI_SCORE) == (3, 0.10)
    assert alertes.FACTEUR_MANQUANTS == 2.0
    assert alertes.ECART_VOLUME_SIGNALES == 0.30
    assert alertes.SEGMENTS_SURVEILLES == (("pays", "Suisse"),)


@pytest.mark.phase11
def test_le_tableau_des_regles_reprend_les_valeurs_validees():
    """The rule table is what people read; the constants are what the code will use. Each
    validated value must appear in its rule, so the two cannot tell different stories."""
    from churn_saas.monitoring import alertes

    seuils = dict(zip(table_regles()["indicateur"], table_regles()["seuil"], strict=True))
    assert (
        f"{alertes.CIBLE_COUVERTURE_REVENU:.0%}".replace("%", " %")
        in seuils["Couverture du revenu à risque"]
    )
    derive = seuils["Dérive des entrées et du score (PSI)"]
    assert "0,25" in derive and derive.count("0,10") == 2 and "trois" in derive
    assert f"{alertes.FACTEUR_MANQUANTS:.0f} ×" in seuils["Taux de manquants à l'entrée"]
    assert (
        f"{alertes.ECART_VOLUME_SIGNALES:.0%}".replace("%", " %")
        in seuils["Volume de comptes signalés"]
    )
    assert "Rappel sur le segment Suisse" in seuils


@pytest.mark.phase11
def test_les_variables_cles_sont_les_quatre_premieres_de_la_phase_9():
    """M5 names the key variables after the recorded permutation importance (R10), so the
    list cannot silently drift from the result it claims to follow."""
    import json
    from pathlib import Path

    from churn_saas.monitoring import alertes

    restitution = json.loads(
        (Path(__file__).resolve().parents[1] / "resultats" / "restitution_test.json").read_text(
            encoding="utf-8"
        )
    )
    premieres = tuple(i["variable"] for i in restitution["importance_permutation"][:4])
    assert alertes.VARIABLES_CLES == premieres


# --- Phase 5 · Categorical stability ------------------------------------------------------
@pytest.mark.phase5
def test_le_psi_categoriel_est_nul_sans_changement_et_positif_sinon():
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a"] * 50 + ["b"] * 50)
    assert psi_categoriel(reference, reference) == pytest.approx(0, abs=1e-9)
    assert psi_categoriel(reference, pd.Series(["a"] * 90 + ["b"] * 10)) > 0.25


@pytest.mark.phase5
def test_une_hausse_des_manquants_categoriels_est_une_derive():
    """Missing values form their own category: more of them is a drift."""
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a", "b"] * 50)
    courant = pd.Series(["a", "b"] * 25 + [None] * 50)
    assert psi_categoriel(reference, courant) > 0.25


@pytest.mark.phase5
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
