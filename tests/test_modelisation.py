"""Activity 3 - model preparation: what the statistical imputation learns, and from what.

The imputation is the one step of the preparation that learns from the data. That is
precisely what makes it a leakage risk: fitted on the whole table, it would let the test
set shape the values the model trains on. These tests pin where it learns.
"""

import numpy as np
import pandas as pd

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
