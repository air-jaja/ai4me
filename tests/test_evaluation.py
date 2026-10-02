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
