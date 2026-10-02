"""Activity 2 - feature construction and control."""

import numpy as np
import pandas as pd
import pytest

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


# --- Phase 4 · Structural gaps -----------------------------------------------------------
def _ratios() -> pd.DataFrame:
    from churn_saas.features import combler_ratios_structurels

    return combler_ratios_structurels(
        ajouter_ratios_usage(
            pd.DataFrame(
                {
                    "utilisateurs_actifs": [0, 0, 4, 4],
                    "sieges_souscrits": [5, 5, 5, 5],
                    "heures_usage_30j": [0.0, None, 8.0, None],
                    "tickets_support_90j": [3, 0, 2, 2],
                }
            )
        )
    )


def test_les_ratios_structurels_valent_zero():
    """No active user: the per-user ratios are undefined, set to 0 by convention.

    The indicator carries the meaning. Without the zero, these 297 accounts would be
    imputed with the median of ordinary accounts - mixed with genuinely unknown values.
    """
    resultat = _ratios()
    assert resultat.loc[:1, "usage_par_actif"].tolist() == [0.0, 0.0]
    assert resultat.loc[:1, "tickets_par_actif"].tolist() == [0.0, 0.0]
    assert resultat.loc[:1, "compte_sans_utilisateur_actif"].tolist() == [1, 1]


def test_un_vrai_manquant_de_ratio_reste_manquant():
    """Users present, hours unknown: that gap is genuine and must reach the median imputation."""
    resultat = _ratios()
    assert resultat.loc[2, "usage_par_actif"] == 2.0
    assert pd.isna(resultat.loc[3, "usage_par_actif"])


def test_la_chaine_partagee_produit_le_meme_gold_que_le_pipeline():
    """Training and monthly batch go through `preparer_gold`; it must match the pipeline.

    The batch used to rebuild silver without the column lists and to skip what the
    pipeline did. This compares on a small frame; the non-regression suite compares on
    the full dataset.
    """
    from churn_saas.features import construire_silver_standard, preparer_gold

    brut = pd.DataFrame(
        {
            "client_id": ["A", "B"],
            "utilisateurs_actifs": ["0", "4"],
            "sieges_souscrits": ["5", "5"],
            "heures_usage_30j": ["0", "8,5"],
            "tickets_support_90j": ["1", "2"],
            "churn": ["1", "0"],
        }
    )
    gold = preparer_gold(construire_silver_standard(brut)).gold
    assert gold["usage_par_actif"].tolist() == [0.0, pytest.approx(2.125)]
    assert "taux_activation" not in gold.columns


def test_le_silver_garde_les_nan_que_l_exploration_lit():
    """The zeros apply on the way to gold; silver keeps the phase 3 NaN as they were."""
    brut = pd.DataFrame({"utilisateurs_actifs": [0], "tickets_support_90j": [3]})
    assert ajouter_ratios_usage(brut)["tickets_par_actif"].isna().all()


# --- Phase 4 · Figures of the certification notebook ------------------------------------
def test_les_graphiques_se_tracent_a_partir_des_seules_donnees_recues():
    """Each drawing function works on its arguments alone: no global, no file written.

    They were inline closures in the phase notebooks, reading notebook variables. Moved
    here so the certification notebook calls them instead of holding a second copy.
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    from churn_saas.features import graphiques

    df = pd.DataFrame(
        {
            "revenu": [100.0, 50.0, 10.0, 5.0, 1.0, 1.0],
            "churn": [1, 0, 1, 0, 0, 1],
            "utilisateurs_actifs": [0, 3, 2, 0, 1, 4],
            "secteur": ["A", "B", "A", "B", "A", "B"],
        }
    )
    profil = pd.DataFrame({"colonne": ["x", "y"], "manquants_pct": [4.0, 12.0]})
    tranches = pd.DataFrame({"taux (%)": [50.0, 20.0, 15.0]})
    figures = [
        graphiques.tracer_concentration(df["revenu"], df["churn"]),
        graphiques.tracer_completude(profil, 10, 50),
        graphiques.tracer_compte_abandonne(df),
        graphiques.tracer_fragmentation(
            pd.DataFrame({"colonne": ["secteur"], "avant": [3], "après": [2]})
        ),
        graphiques.tracer_risque_par_segment(df, ["secteur"]),
        graphiques.tracer_tendances({"x": tranches}, taux_global=28.0),
        graphiques.tracer_psi(pd.DataFrame({"variable": ["a", "b"], "psi": [0.01, 0.2]}), 0.1),
        graphiques.tracer_validation_adverse(np.array([0, 0.5, 1]), np.array([0, 0.5, 1]), 0.5),
        graphiques.tracer_permutation(np.array([0.27, 0.28, 0.3]), 0.79, 0.28),
        graphiques.tracer_valeur_vie_par_anciennete(
            pd.DataFrame(
                {
                    "valeur_vie_client_eur": [1000.0, 1200, 1500, 1800, 2000, 1100, 1300, 1600],
                    "revenu_mensuel_recurrent_eur": [100.0] * 8,
                    "anciennete_mois": [1, 2, 5, 8, 12, 1, 3, 9],
                    "churn": [1, 0, 1, 0, 1, 0, 1, 0],
                }
            ),
            tranches=2,
        ),
        graphiques.tracer_charge_calcul(
            pd.DataFrame({"étape": ["a", "b"], "secondes": [60.0, 30.0]})
        ),
        graphiques.tracer_courbes_apprentissage(
            {
                "m": pd.DataFrame(
                    {
                        "comptes d'entraînement": [100, 200],
                        "PR-AUC entraînement": [0.9, 0.85],
                        "PR-AUC validation": [0.7, 0.75],
                        "écart-type validation": [0.02, 0.02],
                    }
                )
            }
        ),
    ]
    assert all(isinstance(f, Figure) for f in figures)
    assert all(f.axes and (f.axes[0].get_title() or f._suptitle) for f in figures)
