"""Secondary model: the customer lifetime value of an account (phase 7, rule B5).

The decision rule weighs each account by probability x lifetime value. The observed value
does not encode the outcome (phase 5 diagnostic), so it can be used as it is - but an
account too recent to have one needs an estimate. This model provides it, from the
variables known before the decision only.

The target is learnt on the log scale - values span two orders of magnitude, and the
diagnostic explained 89.5 % of the log variance linearly - and returned in euros.
Rule B5, validated before this code ran: a linear regression against a regression forest;
the forest is kept only if its R² gain over 5 folds exceeds one standard deviation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline

from ..config import GRAINE, N_JOBS, PLIS_VALIDATION
from .baseline import construire_preprocesseur


def _sur_echelle_log(regresseur) -> TransformedTargetRegressor:
    return TransformedTargetRegressor(regressor=regresseur, func=np.log, inverse_func=np.exp)


def construire_regression_valeur(X: pd.DataFrame) -> Pipeline:
    """Linear model of log(value). A tiny ridge penalty keeps one-hot columns stable."""
    return Pipeline(
        [("preparation", construire_preprocesseur(X)), ("modele", _sur_echelle_log(Ridge(1e-3)))]
    )


def construire_foret_valeur(X: pd.DataFrame) -> Pipeline:
    """Regression forest of log(value), the non-linear comparator of rule B5."""
    foret = RandomForestRegressor(
        n_estimators=300, min_samples_leaf=5, random_state=GRAINE, n_jobs=N_JOBS
    )
    return Pipeline(
        [("preparation", construire_preprocesseur(X)), ("modele", _sur_echelle_log(foret))]
    )


def comparer_modeles_valeur(X: pd.DataFrame, valeur: pd.Series) -> pd.DataFrame:
    """R² on log(value), per fold, for both models of rule B5 (same folds)."""
    garder = valeur.notna() & (valeur > 0)
    X, cible = X.loc[garder], np.log(valeur.loc[garder].astype(float))
    plis = KFold(PLIS_VALIDATION, shuffle=True, random_state=GRAINE)
    scores = {}
    for nom, fabrique in (
        ("régression linéaire", construire_regression_valeur),
        ("forêt de régression", construire_foret_valeur),
    ):
        # Score on the log scale: the models predict euros, so they are scored here as
        # plain regressors of log(value) - the same pipelines, without the transform.
        modele = fabrique(X)
        modele.set_params(modele__func=None, modele__inverse_func=None)
        scores[nom] = cross_val_score(modele, X, cible, cv=plis, scoring="r2")
    return pd.DataFrame(scores).rename_axis("pli")


def choisir_modele_valeur(scores: pd.DataFrame) -> str:
    """Rule B5: the forest only with an R² gain above one standard deviation, paired."""
    gain = scores["forêt de régression"] - scores["régression linéaire"]
    seuil = float(scores["régression linéaire"].std())
    return "forêt de régression" if float(gain.mean()) > seuil else "régression linéaire"
