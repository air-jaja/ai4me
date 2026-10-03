"""Activity 4 - metrics, decision rule and business impact."""

import pandas as pd
import pytest

from churn_saas.evaluation.decision import prioriser, sensibilite_classement, seuil_par_compte
from churn_saas.evaluation.impact import resume_impact
from churn_saas.evaluation.metriques import intervalle_confiance_rappel


def test_seuil_decroit_avec_la_valeur_du_compte():
    """The rational action threshold must fall as account value rises.

    This monotonicity is the whole justification for abandoning a single global threshold:
    if it broke, the decision rule would lose its rationale."""
    seuils = seuil_par_compte(pd.Series([800, 11_200, 177_300]))
    assert seuils.is_monotonic_decreasing
    assert seuils.iloc[0] > 0.30  # small account: high risk needed before acting
    assert seuils.iloc[-1] < 0.01  # large account: act on even a tiny risk


def test_classement_insensible_a_l_efficacite_de_retention():
    """Core argument of section 9: u is a common factor, it does not change the order."""
    proba = pd.Series([0.10, 0.50, 0.30])
    clv = pd.Series([100_000, 2_000, 20_000])
    assert list(prioriser(proba, clv, efficacite_retention=0.25).index) == list(
        prioriser(proba, clv, efficacite_retention=0.15).index
    )


def test_sensibilite_confirme_la_stabilite_de_la_liste():
    """The handled shortlist must stay identical across retention-effectiveness values.

    Produces the evidence behind the sensitivity analysis promised in section 9 - an
    analysis announced in the deliverable but never run would be worse than none."""
    proba = pd.Series([0.1 * (i % 9 + 1) for i in range(500)])
    clv = pd.Series(range(1, 501))
    rapport = sensibilite_classement(proba, clv, capacite=140)
    assert (rapport["part_commune_pct"] == 100.0).all()


def test_la_capacite_borne_le_nombre_de_comptes_traites():
    """The shortlist must never exceed team capacity.

    A model flagging more accounts than the team can handle produces no additional action:
    the constraint is operational, not statistical."""
    table = prioriser(pd.Series([0.4] * 500), pd.Series(range(1, 501)), capacite=140)
    assert table["a_traiter"].sum() == 140


def test_les_trois_niveaux_d_impact_sont_decroissants():
    """Exposed, covered and preserved revenue must decrease in that order.

    An inversion would mean claiming to save more than what is at risk - the kind of figure
    that discredits an entire presentation."""
    mrr = pd.Series([1000, 2000, 3000, 4000])
    churn = pd.Series([1, 1, 0, 1])
    traite = pd.Series([True, False, True, True])
    resume = resume_impact(mrr, churn, traite, efficacite_retention=0.25)
    montants = list(resume["montant_eur"])
    assert montants[0] >= montants[1] >= montants[2]


def test_intervalle_de_confiance_sur_le_rappel():
    """The stated uncertainty on recall must remain around five points.

    Section 9 tells the jury that two operating points at 70% and 74% are statistically
    indistinguishable. That statement must stay true."""
    # ~280 positives, recall 0.70 -> about +/- 5.4 points (notebook section 9)
    assert intervalle_confiance_rappel(0.70, 280) == __import__("pytest").approx(0.054, abs=0.002)


# --- Phase 5 · Does the lifetime value carry the outcome? ------------------------------
def _comptes_synthetiques(encoder_l_issue: bool):
    import numpy as np

    generateur = np.random.default_rng(0)
    n = 2000
    anciennete = generateur.integers(1, 48, n).astype(float)
    revenu = generateur.lognormal(7, 0.8, n)
    issue = (generateur.random(n) < 1 / (1 + np.exp(0.08 * (anciennete - 10)))).astype(int)
    mois = 10 + 0.3 * anciennete + generateur.normal(0, 1.5, n)
    if encoder_l_issue:
        # The value shortened by the actual departure: knowledge of the outcome.
        mois = mois * np.where(issue == 1, 0.6, 1.0)
    explicatives = pd.DataFrame({"anciennete": anciennete})
    return (
        explicatives,
        pd.Series(revenu * mois),
        pd.Series(revenu),
        pd.Series(issue),
        pd.Series(anciennete),
    )


@pytest.mark.phase5
def test_une_valeur_construite_sans_l_issue_n_est_pas_signalee():
    """Leavers are younger here, so their value is lower - but the outcome adds nothing."""
    from churn_saas.evaluation import diagnostiquer_valeur_vie, valeur_encode_l_issue

    assert not valeur_encode_l_issue(diagnostiquer_valeur_vie(*_comptes_synthetiques(False)))


@pytest.mark.phase5
def test_une_valeur_qui_encode_l_issue_est_signalee():
    """A value cut short by the actual departure is caught: the outcome explains it."""
    from churn_saas.evaluation import diagnostiquer_valeur_vie, valeur_encode_l_issue

    assert valeur_encode_l_issue(diagnostiquer_valeur_vie(*_comptes_synthetiques(True)))


# --- Phase 6 · Evaluation protocol ------------------------------------------------------------
@pytest.mark.phase6
def test_le_rappel_et_la_precision_du_haut_du_classement():
    """Top 20 % of ten accounts = two accounts; one of the two churners is among them."""
    from churn_saas.evaluation import rappel_precision_haut

    y = pd.Series([1, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    score = [0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.2]
    assert rappel_precision_haut(y, score, part=0.2) == (0.5, 0.5)


@pytest.mark.phase6
def test_l_erreur_de_calibration_distingue_une_probabilite_juste_d_une_biaisee():
    import numpy as np

    from churn_saas.evaluation import erreur_calibration

    generateur = np.random.default_rng(0)
    proba = generateur.uniform(size=20_000)
    y = (generateur.uniform(size=20_000) < proba).astype(int)
    assert erreur_calibration(y, proba) < 0.02
    assert erreur_calibration(y, np.clip(proba + 0.2, 0, 1)) > 0.15


@pytest.mark.phase6
def test_un_classement_n_a_ni_brier_ni_calibration():
    """A ranking rule is not a probability: its calibration is reported missing, not computed."""
    from churn_saas.evaluation import mesurer

    mesures = mesurer(pd.Series([0, 1, 0, 1]), [0.1, 0.9, 0.2, 0.7], probabiliste=False)
    assert pd.isna(mesures["Brier"]) and pd.isna(mesures["erreur de calibration"])
    assert mesures["PR-AUC"] == 1.0


@pytest.mark.phase6
def test_le_protocole_couvre_25_plis_et_chaque_compte_une_fois_hors_pli():
    import numpy as np
    from sklearn.dummy import DummyClassifier

    from churn_saas.evaluation import evaluer_selon_protocole

    generateur = np.random.default_rng(1)
    X = pd.DataFrame({"a": generateur.normal(size=200)})
    y = pd.Series((generateur.random(200) < 0.3).astype(int))
    resultat = evaluer_selon_protocole(lambda X: DummyClassifier(strategy="prior"), X, y)
    assert len(resultat.par_pli) == 25
    assert resultat.hors_pli.notna().all()


@pytest.mark.phase6
def test_le_protocole_et_la_selection_utilisent_les_memes_plis():
    """The baselines are measured on the very folds the phase 5 selection used."""
    import numpy as np

    from churn_saas.evaluation import plis_du_protocole
    from churn_saas.features.selection import plis_repetes

    X = np.zeros((100, 1))
    y = np.r_[np.zeros(70), np.ones(30)]
    a = [tuple(v) for _, v in plis_du_protocole().split(X, y)]
    b = [tuple(v) for _, v in plis_repetes().split(X, y)]
    assert a == b


# --- Phase 7 · Rule B1: selecting the final model ---------------------------------------------
def _scores(gain: float, bruit: float = 0.02, n: int = 25):
    import numpy as np

    generateur = np.random.default_rng(0)
    base = 0.79 + generateur.normal(0, bruit, n)
    return base.tolist(), (base + gain + generateur.normal(0, 0.001, n)).tolist()


@pytest.mark.phase7
def test_un_gain_sous_un_ecart_type_garde_la_reference():
    from churn_saas.evaluation import comparer_a_la_reference, selectionner

    reference, candidat = _scores(gain=0.005)
    table = comparer_a_la_reference({"rl": reference, "foret": candidat}, "rl")
    assert selectionner(table, "rl", ("rl", "foret")) == "rl"


@pytest.mark.phase7
def test_un_gain_significatif_remplace_la_reference():
    from churn_saas.evaluation import comparer_a_la_reference, selectionner

    reference, candidat = _scores(gain=0.05)
    table = comparer_a_la_reference({"rl": reference, "foret": candidat}, "rl")
    assert selectionner(table, "rl", ("rl", "foret")) == "foret"


@pytest.mark.phase7
def test_a_egalite_le_plus_simple_l_emporte():
    from churn_saas.evaluation import comparer_a_la_reference, selectionner

    reference, candidat = _scores(gain=0.05)
    table = comparer_a_la_reference({"rl": reference, "foret": candidat, "xgb": candidat}, "rl")
    assert selectionner(table, "rl", ("rl", "foret", "xgb")) == "foret"


# --- B6, option C: exact linear contributions --------------------------------------------------
def _modele_lineaire():
    import numpy as np

    from churn_saas.modelisation import construire_baseline, construire_calibre

    generateur = np.random.default_rng(0)
    X = pd.DataFrame(
        {
            "a": generateur.normal(size=300),
            "b": generateur.choice(["x", "y", "z"], 300),
            "c": generateur.normal(size=300),
        }
    )
    y = ((X["a"] + (X["b"] == "z") + generateur.normal(scale=0.5, size=300)) > 0.5).astype(int)
    return X, y, construire_baseline, construire_calibre


@pytest.mark.phase7
def test_les_contributions_reconstituent_exactement_le_score():
    """Base + sum of contributions = the model's log-odds, to the floating-point digit -
    for a plain regression and for the calibrated average of its copies."""
    import numpy as np

    from churn_saas.evaluation import contributions_lineaires

    X, y, construire_baseline, construire_calibre = _modele_lineaire()
    simple = construire_baseline(X).fit(X, y)
    contributions, base = contributions_lineaires(simple, X)
    assert np.allclose(base + contributions.sum(axis=1), simple.decision_function(X))
    assert list(contributions.columns) == ["a", "b", "c"]  # one-hot summed back into "b"

    calibre = construire_calibre(construire_baseline, "sigmoid")(X).fit(X, y)
    contributions, base = contributions_lineaires(calibre, X)
    logit = np.mean(
        [c.estimator.decision_function(X) for c in calibre.calibrated_classifiers_], axis=0
    )
    assert np.allclose(base + contributions.sum(axis=1), logit)


@pytest.mark.phase7
def test_le_motif_du_conseiller_vient_des_contributions():
    from churn_saas.evaluation import expliquer_par_contributions, motif_lisible

    X, y, construire_baseline, _ = _modele_lineaire()
    modele = construire_baseline(X).fit(X, y)
    explication = expliquer_par_contributions(modele, X, X.index[0], n_facteurs=2)
    assert len(explication) == 2 and explication["contribution"].abs().is_monotonic_decreasing
    assert motif_lisible(explication, n=2).startswith("Facteurs principaux : ")
