"""Activité 4 — métriques, règle de décision et impact métier."""

import pandas as pd

from churn_saas.evaluation.decision import prioriser, sensibilite_classement, seuil_par_compte
from churn_saas.evaluation.impact import resume_impact
from churn_saas.evaluation.metriques import intervalle_confiance_rappel


def test_seuil_decroit_avec_la_valeur_du_compte():
    seuils = seuil_par_compte(pd.Series([800, 11_200, 177_300]))
    assert seuils.is_monotonic_decreasing
    assert seuils.iloc[0] > 0.30  # petit compte : il faut un risque élevé pour agir
    assert seuils.iloc[-1] < 0.01  # gros compte : agir dès un risque très faible


def test_classement_insensible_a_l_efficacite_de_retention():
    """Argument central du § 9 : u est un facteur commun, il ne change pas l'ordre."""
    proba = pd.Series([0.10, 0.50, 0.30])
    clv = pd.Series([100_000, 2_000, 20_000])
    assert list(prioriser(proba, clv, efficacite_retention=0.25).index) == list(
        prioriser(proba, clv, efficacite_retention=0.15).index
    )


def test_sensibilite_confirme_la_stabilite_de_la_liste():
    proba = pd.Series([0.1 * (i % 9 + 1) for i in range(500)])
    clv = pd.Series(range(1, 501))
    rapport = sensibilite_classement(proba, clv, capacite=140)
    assert (rapport["part_commune_pct"] == 100.0).all()


def test_la_capacite_borne_le_nombre_de_comptes_traites():
    table = prioriser(pd.Series([0.4] * 500), pd.Series(range(1, 501)), capacite=140)
    assert table["a_traiter"].sum() == 140


def test_les_trois_niveaux_d_impact_sont_decroissants():
    mrr = pd.Series([1000, 2000, 3000, 4000])
    churn = pd.Series([1, 1, 0, 1])
    traite = pd.Series([True, False, True, True])
    resume = resume_impact(mrr, churn, traite, efficacite_retention=0.25)
    montants = list(resume["montant_eur"])
    assert montants[0] >= montants[1] >= montants[2]


def test_intervalle_de_confiance_sur_le_rappel():
    # ~280 positifs, rappel 0,70 -> environ +/- 5,4 points (notebook § 9)
    assert intervalle_confiance_rappel(0.70, 280) == __import__("pytest").approx(0.054, abs=0.002)
