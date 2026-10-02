"""Baseline: regularised logistic regression, wrapped in a full pipeline.

The preprocessor lives **inside** the pipeline rather than being applied beforehand. This
guarantees imputation and scaling are fitted on training folds only during
cross-validation. Applying them upfront would leak information from the test fold into
training - a subtle and very common form of leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import GRAINE, VARIABLE_REGLE_METIER

# Label given to a missing category (phase 4), instead of the most frequent one.
MODALITE_MANQUANTE = "Non renseigné"


def construire_preprocesseur(X: pd.DataFrame) -> ColumnTransformer:
    """Preparation chain: impute then encode, per column type.

    `OneHotEncoder` rather than `LabelEncoder`: `secteur`, `pays` and `plan` are nominal.
    Ordinal encoding would introduce an arbitrary ordering that a linear model would read
    as a magnitude relation.
    """
    numeriques = X.select_dtypes(include="number").columns.tolist()
    categorielles = [c for c in X.columns if c not in numeriques]

    return ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        # Median rather than mean: MRR is heavily skewed
                        # (median 682 EUR, mean 3,543 EUR). The mean would import that
                        # skew into every imputed value.
                        ("imputation", SimpleImputer(strategy="median")),
                        ("echelle", StandardScaler()),
                    ]
                ),
                numeriques,
            ),
            (
                "cat",
                Pipeline(
                    [
                        # An explicit category rather than the most frequent one
                        # (phase 4): the mode would inflate the dominant sector or country
                        # and bias the per-segment fairness analysis; an explicit
                        # "missing" label keeps the gap visible, and usable by the model.
                        (
                            "imputation",
                            SimpleImputer(strategy="constant", fill_value=MODALITE_MANQUANTE),
                        ),
                        (
                            "encodage",
                            # min_frequency groups rare categories: without it a category
                            # seen twice would get its own column and invite overfitting.
                            OneHotEncoder(handle_unknown="ignore", min_frequency=0.01),
                        ),
                    ]
                ),
                categorielles,
            ),
        ],
        remainder="drop",
    )


def construire_baseline(X: pd.DataFrame, equilibrer: bool = True) -> Pipeline:
    """Full baseline pipeline."""
    return Pipeline(
        [
            ("preparation", construire_preprocesseur(X)),
            (
                "modele",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced" if equilibrer else None,
                    random_state=GRAINE,
                ),
            ),
        ]
    )


# --- Phase 6: the two simpler references the logistic regression must beat ----------------
class RegleMetier(ClassifierMixin, BaseEstimator):
    """Rank accounts by one variable, as a CSM would without a model.

    No learning: `fit` only records the variable's range, so the score lies in [0, 1].
    It is a ranking, not a probability - the protocol reports no calibration for it.
    """

    def __init__(self, colonne: str = "derniere_connexion_jours", croissant: bool = True):
        self.colonne = colonne
        self.croissant = croissant

    def fit(self, X: pd.DataFrame, y: pd.Series) -> RegleMetier:
        valeurs = pd.to_numeric(X[self.colonne], errors="coerce")
        self.minimum_, self.maximum_ = float(valeurs.min()), float(valeurs.max())
        self.mediane_ = float(valeurs.median())
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        valeurs = pd.to_numeric(X[self.colonne], errors="coerce").fillna(self.mediane_)
        etendue = max(self.maximum_ - self.minimum_, 1e-12)
        score = ((valeurs - self.minimum_) / etendue).clip(0, 1).to_numpy()
        score = score if self.croissant else 1 - score
        return np.column_stack([1 - score, score])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def construire_baseline_naive(X: pd.DataFrame | None = None) -> DummyClassifier:
    """The floor: the base rate for every account (PR-AUC equal to the churn rate)."""
    return DummyClassifier(strategy="prior")


def construire_baseline_metier(X: pd.DataFrame | None = None) -> RegleMetier:
    """The business rule: the longer since the last login, the riskier."""
    return RegleMetier(VARIABLE_REGLE_METIER, croissant=True)
