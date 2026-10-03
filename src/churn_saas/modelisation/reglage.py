"""Tuning and calibration of the candidate models (phase 7, rules B2 and B3).

`regler` searches a bounded grid on stratified folds, scored on PR-AUC, with ONE parallel
layer, inside the model and by threads: combinations are evaluated one after the other,
each model using N_JOBS threads. Worker processes would each receive a pickled copy of the
task, which broke on Windows (MemoryError, BrokenProcessPool); threads share memory.

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
    # Only models that use threads: a logistic regression's n_jobs is ignored since
    # scikit-learn 1.8, and setting it raises a FutureWarning.
    if modele.get_params().get("modele__n_jobs") is not None:
        modele.set_params(modele__n_jobs=N_JOBS)
    recherche = GridSearchCV(
        modele,
        grille,
        scoring="average_precision",
        cv=StratifiedKFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE),
        n_jobs=1,
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


# --- Phase 8: tuning the retained model, with overfitting watched (rules S1-S3, P1, P3) ------
def explorer_grille(
    construire_modele: Callable, grille: dict, X: pd.DataFrame, y: pd.Series, plis
) -> pd.DataFrame:
    """Every combination of the grid on the given folds: validation AND training PR-AUC.

    The training score is what S1 needs: a combination much better on the rows it learnt
    than on the others memorises them. One row per combination, the folds' validation
    scores kept for the paired comparisons.
    """
    from sklearn.model_selection import ParameterGrid, cross_validate

    lignes = []
    for parametres in ParameterGrid(grille):
        modele = construire_modele(X).set_params(**parametres)
        scores = cross_validate(
            modele,
            X,
            pd.Series(y).astype(int),
            cv=plis,
            scoring="average_precision",
            return_train_score=True,
            n_jobs=1,
        )
        lignes.append(
            {
                **{k.removeprefix("modele__"): v for k, v in parametres.items()},
                "PR-AUC validation": float(scores["test_score"].mean()),
                "écart-type": float(scores["test_score"].std()),
                "PR-AUC entraînement": float(scores["train_score"].mean()),
                "écart entraînement - validation": float(
                    scores["train_score"].mean() - scores["test_score"].mean()
                ),
                "par_pli": [float(v) for v in scores["test_score"]],
            }
        )
    return pd.DataFrame(lignes)


def regle_un_ecart_type(table: pd.DataFrame, seuil_ecart: float) -> int:
    """Rules P3 then P1: the index of the retained combination.

    Combinations whose training-validation gap exceeds `seuil_ecart` are discarded (P3).
    Among the others, those within one standard deviation of the best are equivalent, and
    the most regularised one - the smallest C - is retained; on a tie, the better score.
    """
    admissibles = table[table["écart entraînement - validation"] <= seuil_ecart]
    meilleur = admissibles["PR-AUC validation"].idxmax()
    plancher = (
        admissibles.loc[meilleur, "PR-AUC validation"] - admissibles.loc[meilleur, "écart-type"]
    )
    equivalents = admissibles[admissibles["PR-AUC validation"] >= plancher]
    return int(
        equivalents.sort_values(["C", "PR-AUC validation"], ascending=[True, False]).index[0]
    )


def _refit_un_ecart_type(seuil_ecart: float) -> Callable:
    """Rule P1 (and P3) as a `refit` callable, for the inner searches of a nested CV."""

    def choisir(resultats: dict) -> int:
        table = pd.DataFrame(
            {
                "C": [float(c) for c in resultats["param_modele__C"]],
                "PR-AUC validation": resultats["mean_test_score"],
                "écart-type": resultats["std_test_score"],
                "écart entraînement - validation": resultats["mean_train_score"]
                - resultats["mean_test_score"],
            }
        )
        return regle_un_ecart_type(table, seuil_ecart)

    return choisir


def optimisme_imbrique(
    construire_modele: Callable, grille: dict, X: pd.DataFrame, y: pd.Series, seuil_ecart: float
) -> dict:
    """Rule S3: how much choosing the best combination flatters its own score.

    Each of 5 outer folds runs the whole tuning - grid, rules P3 and P1 - on its training
    part only, then scores the chosen model on the outer fold it never saw. The gap
    between the inner (selected) scores and the outer scores is the selection optimism.
    """
    import numpy as np

    y = pd.Series(y).astype(int)
    externes = StratifiedKFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE)
    internes, exterieurs, choix = [], [], []
    for entrainement, validation in externes.split(X, y):
        Xa, ya = X.iloc[entrainement], y.iloc[entrainement]
        recherche = GridSearchCV(
            construire_modele(Xa),
            grille,
            scoring="average_precision",
            cv=StratifiedKFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE + 1),
            refit=_refit_un_ecart_type(seuil_ecart),
            return_train_score=True,
            n_jobs=1,
        ).fit(Xa, ya)
        indice = recherche.best_index_
        internes.append(float(recherche.cv_results_["mean_test_score"][indice]))
        from sklearn.metrics import average_precision_score

        score = recherche.predict_proba(X.iloc[validation])[:, 1]
        exterieurs.append(float(average_precision_score(y.iloc[validation], score)))
        choix.append(
            {
                k.removeprefix("modele__"): (str(v) if v is None else v)
                for k, v in recherche.best_params_.items()
            }
        )
    return {
        "score_interne": float(np.mean(internes)),
        "score_externe": float(np.mean(exterieurs)),
        "optimisme": float(np.mean(internes) - np.mean(exterieurs)),
        "scores_externes": exterieurs,
        "choix_par_pli": choix,
    }
