"""Bayesian hyperparameter optimisation with pruning.

**Why Optuna rather than an exhaustive grid.** The eco-design argument in notebook
section 8 was about search *breadth*, not about the tool. An exhaustive grid evaluates
every combination, including those whose early folds already show they will not pay off.
Optuna samples (TPE) and **prunes** hopeless trials: at equal compute budget it covers
more space, at equal coverage it consumes less. The budget stays bounded by `n_essais`,
which remains the documented trade-off.

Compute footprint is measurable with CodeCarbon (`mesurer_empreinte`), turning the
eco-design argument from a claim into a measurement.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from ..config import GRAINE


def espace_baseline(essai: Any) -> dict[str, Any]:
    """Search space for logistic regression."""
    return {
        # log scale: regularisation strength matters by order of magnitude, not linearly.
        "modele__C": essai.suggest_float("C", 1e-3, 1e2, log=True),
        "modele__class_weight": essai.suggest_categorical("class_weight", [None, "balanced"]),
    }


def espace_candidat(essai: Any) -> dict[str, Any]:
    """Search space for the random forest."""
    return {
        "modele__n_estimators": essai.suggest_int("n_estimators", 100, 400, step=100),
        "modele__max_depth": essai.suggest_categorical("max_depth", [None, 10, 20, 30]),
        "modele__min_samples_leaf": essai.suggest_int("min_samples_leaf", 1, 20),
        "modele__class_weight": essai.suggest_categorical("class_weight", [None, "balanced"]),
    }


def optimiser(
    modele: Pipeline,
    espace: Callable[[Any], dict[str, Any]],
    X: pd.DataFrame,
    y: pd.Series,
    n_essais: int = 30,
    n_plis: int = 5,
) -> Any:
    """Search the hyperparameters maximising cross-validated PR-AUC.

    `n_essais` is deliberately modest: the marginal gain of a wider search is not
    demonstrated at this data volume, and it would be paid in compute.
    """
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    plis = StratifiedKFold(n_splits=n_plis, shuffle=True, random_state=GRAINE)

    def objectif(essai: Any) -> float:
        candidat = modele.set_params(**espace(essai))
        scores = cross_val_score(candidat, X, y, cv=plis, scoring="average_precision", n_jobs=-1)
        return float(scores.mean())

    etude = optuna.create_study(
        direction="maximize",
        # Fixed seed: two runs of the same commit must yield the same study.
        sampler=optuna.samplers.TPESampler(seed=GRAINE),
        pruner=optuna.pruners.MedianPruner(),
    )
    etude.optimize(objectif, n_trials=n_essais, show_progress_bar=False)
    return etude


def resume_etude(etude: Any) -> pd.DataFrame:
    """Trial table, reported in the notebook (hyperparameters described, C5)."""
    return (
        etude.trials_dataframe(attrs=("number", "value", "params", "state"))
        .sort_values("value", ascending=False)
        .reset_index(drop=True)
    )


@contextmanager
def mesurer_empreinte(nom: str = "optimisation", dossier: str = "reports"):
    """Measure the carbon footprint of the enclosed block, if CodeCarbon is installed.

    Silent when absent: the notebook stays runnable without the full stack.
    """
    try:
        from codecarbon import EmissionsTracker
    except ImportError:
        yield None
        return

    traceur = EmissionsTracker(project_name=nom, output_dir=dossier, log_level="error")
    traceur.start()
    try:
        yield traceur
    finally:
        emissions = traceur.stop()
        print(f"Empreinte mesurée pour « {nom} » : {emissions:.6f} kg eqCO2")
