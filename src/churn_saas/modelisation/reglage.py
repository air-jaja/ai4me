"""Tuning and calibration of the candidate models (phase 7, rules B2 and B3).

`regler` searches a bounded grid on stratified folds, scored on PR-AUC, with ONE parallel
layer: the search runs N_JOBS fits at once, each model on a single core - a parallel
search over parallel models would oversubscribe the machine.

`construire_calibre` wraps a model factory in a calibration step (B2): the calibrator is
learnt inside each training fold by an inner cross-validation, never on the rows it is
then evaluated on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from ..config import GRAINE, N_JOBS, PLIS_VALIDATION


@dataclass
class ResultatReglage:
    """Best settings of a grid search, and every combination's score."""

    meilleurs_parametres: dict
    meilleur_score: float
    tableau: pd.DataFrame


def regler(
    construire_modele: Callable, grille: dict, X: pd.DataFrame, y: pd.Series
) -> ResultatReglage:
    """Grid search on PR-AUC over stratified folds; one parallel layer."""
    modele = construire_modele(X)
    if "modele__n_jobs" in modele.get_params():
        modele.set_params(modele__n_jobs=1)
    recherche = GridSearchCV(
        modele,
        grille,
        scoring="average_precision",
        cv=StratifiedKFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE),
        n_jobs=N_JOBS,
    ).fit(X, pd.Series(y).astype(int))
    colonnes = [f"param_{p}" for p in grille] + ["mean_test_score", "std_test_score"]
    tableau = (
        pd.DataFrame(recherche.cv_results_)[colonnes]
        .rename(columns=lambda c: c.removeprefix("param_modele__").replace("_test_score", ""))
        .sort_values("mean", ascending=False)
        .reset_index(drop=True)
    )
    return ResultatReglage(dict(recherche.best_params_), float(recherche.best_score_), tableau)


def construire_calibre(construire_modele: Callable, methode: str) -> Callable:
    """A factory whose models calibrate their probabilities (`sigmoid` or `isotonic`).

    The inner cross-validation fits the calibrator on held-out parts of the training
    fold only - the protocol's validation fold never sees it.
    """

    def fabrique(X: pd.DataFrame):
        return CalibratedClassifierCV(
            construire_modele(X),
            method=methode,
            cv=StratifiedKFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE),
        )

    return fabrique
