"""Activity 2 - feature construction and control."""

import pandas as pd

from churn_saas.features.construction import ajouter_ratios_usage
from churn_saas.features.controle import (
    controler_schema,
    detecter_fuite_suspecte,
    verifier_leurres,
)


def test_ratio_protege_contre_la_division_par_zero():
    """A zero denominator must yield NaN, never an infinity.

    An infinity propagates silently through the pipeline and only surfaces as an absurd
    model coefficient, far from its cause."""
    df = pd.DataFrame({"utilisateurs_actifs": [5, 0], "sieges_souscrits": [10, 0]})
    resultat = ajouter_ratios_usage(df)
    assert resultat["taux_activation"].iloc[0] == 0.5
    assert pd.isna(resultat["taux_activation"].iloc[1])  # neither error nor infinity


def test_controle_de_schema_signale_une_colonne_absente():
    """A missing expected column must be reported as non-compliant.

    This is step 2 of the CI chain: it blocks a batch rather than scoring out-of-domain
    data, which would produce plausible but wrong probabilities."""
    df = pd.DataFrame({"a": [1, 2]})
    rapport = controler_schema(df, ["a", "b"])
    assert bool(rapport.loc[rapport["colonne"] == "b", "conforme"].iloc[0]) is False


def test_detection_generique_de_fuite():
    """The check targets no named column: it spots the abnormal correlation."""
    y = pd.Series([0, 1] * 50)
    X = pd.DataFrame({"fuite": y * 100, "bruit": range(100)})
    suspects = detecter_fuite_suspecte(X, y)
    assert "fuite" in set(suspects["variable"])
    assert "bruit" not in set(suspects["variable"])


def test_confirmation_empirique_des_leurres():
    """Decoy variables must be confirmed as useless by measurement, not by assumption.

    Dropping them upfront would forfeit the interpretability demonstration the brief asks
    for; keeping them without checking would be an unverified claim."""
    importances = pd.Series(
        {"anciennete_mois": 0.40, "csat": 0.30, "couleur_theme_interface_bleu": 0.001}
    )
    resultat = verifier_leurres(importances, leurres_attendus=("couleur_theme_interface",))
    assert bool(resultat["confirme"].iloc[0]) is True
