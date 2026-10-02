"""Candidate model and comparison protocol.

Comparison relies on PR-AUC, not accuracy: 72% of accounts stay, so a model always
predicting "no churn" would score 72% accuracy while being worthless.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline

from ..config import GRAINE, N_JOBS
from .baseline import construire_preprocesseur


def construire_candidat(X: pd.DataFrame, equilibrer: bool = True) -> Pipeline:
    """Candidate model pipeline: random forest."""
    return Pipeline(
        [
            ("preparation", construire_preprocesseur(X)),
            (
                "modele",
                RandomForestClassifier(
                    n_estimators=300,
                    min_samples_leaf=5,
                    class_weight="balanced" if equilibrer else None,
                    random_state=GRAINE,
                    n_jobs=N_JOBS,
                ),
            ),
        ]
    )


def grille_hyperparametres() -> dict[str, dict[str, list]]:
    """Deliberately narrow search grid (eco-design, notebook section 8).

    An exhaustive search would multiply compute cost for an undemonstrated marginal gain.
    The grid width is itself a documented trade-off.
    """
    return {
        "baseline": {
            "modele__C": [0.01, 0.1, 1, 10],
            "modele__class_weight": [None, "balanced"],
        },
        "candidat": {
            "modele__n_estimators": [100, 300],
            "modele__max_depth": [None, 10, 20],
            "modele__min_samples_leaf": [1, 5, 20],
            "modele__class_weight": [None, "balanced"],
        },
    }


def comparer(
    modeles: dict[str, Pipeline],
    X: pd.DataFrame,
    y: pd.Series,
    n_plis: int = 5,
) -> pd.DataFrame:
    """Stratified cross-validation. Returns mean **and** standard deviation.

    The standard deviation is not decorative: a PR-AUC gain smaller than fold-to-fold
    variability is not a gain. It is the criterion settling the evaluation -> features
    loop (notebook section 9).
    """
    plis = StratifiedKFold(n_splits=n_plis, shuffle=True, random_state=GRAINE)
    lignes = []
    for nom, modele in modeles.items():
        scores = cross_validate(
            modele, X, y, cv=plis, scoring=["average_precision", "roc_auc"], n_jobs=1
        )
        lignes.append(
            {
                "modele": nom,
                "pr_auc_moy": scores["test_average_precision"].mean().round(4),
                "pr_auc_ecart_type": scores["test_average_precision"].std().round(4),
                "roc_auc_moy": scores["test_roc_auc"].mean().round(4),
                "roc_auc_ecart_type": scores["test_roc_auc"].std().round(4),
            }
        )
    return pd.DataFrame(lignes).sort_values("pr_auc_moy", ascending=False)
