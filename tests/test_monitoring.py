"""Activity 7 - drift detection and alert rules."""

import numpy as np
import pandas as pd

from churn_saas.monitoring.alertes import evaluer_alertes, table_regles
from churn_saas.monitoring.derive import ks_deux_echantillons, psi, rapport_derive


def test_psi_nul_sur_distributions_identiques():
    serie = pd.Series(np.random.default_rng(0).normal(size=5_000))
    assert psi(serie, serie) < 0.01


def test_psi_detecte_un_decalage_franc():
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(0, size=5_000)), pd.Series(rng.normal(2, size=5_000))) > 0.25


def test_ks_coherent_avec_le_psi():
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
    rng = np.random.default_rng(2)
    ref = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(size=2_000)})
    cur = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(3, size=2_000)})
    rapport = rapport_derive(ref, cur, ["a", "b"])
    assert bool(rapport.loc[rapport["variable"] == "b", "alerte"].iloc[0]) is True


def test_chaque_regle_porte_une_action_et_un_responsable():
    regles = table_regles()
    assert (regles["action"].str.len() > 0).all()
    assert (regles["responsable"].str.len() > 0).all()


def test_alerte_declenchee_expose_son_action():
    resultat = evaluer_alertes({"PSI sur variables clés": True})
    ligne = resultat.loc[resultat["indicateur"] == "PSI sur variables clés"].iloc[0]
    assert ligne["declenchee"]
    assert ligne["responsable"] != "—"
