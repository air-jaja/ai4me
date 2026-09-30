"""Technical metrics and their uncertainty.

Reporting recall to two decimals on 280 positives conveys false precision. Every recall
figure therefore ships with its confidence interval.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)


def intervalle_confiance_rappel(rappel: float, n_positifs: int, z: float = 1.96) -> float:
    """Half-width of the 95% confidence interval around a recall value.

    Normal approximation, adequate here: with ~280 positives and recall around 0.7 the
    validity conditions are comfortably met.
    """
    if n_positifs <= 0:
        return float("nan")
    return float(z * np.sqrt(rappel * (1 - rappel) / n_positifs))


def evaluer(y_vrai: pd.Series, proba: pd.Series, seuil: float = 0.5) -> dict[str, float]:
    """Metric set at the given threshold, including recall uncertainty."""
    y_vrai = pd.Series(y_vrai).astype(int)
    y_pred = (pd.Series(proba) >= seuil).astype(int)
    # labels=[0, 1] keeps the unpacking valid even if a class is absent from a fold.
    vn, fp, fn, vp = confusion_matrix(y_vrai, y_pred, labels=[0, 1]).ravel()
    rappel = float(recall_score(y_vrai, y_pred, zero_division=0))
    n_positifs = int(y_vrai.sum())
    return {
        "roc_auc": float(roc_auc_score(y_vrai, proba)),
        "pr_auc": float(average_precision_score(y_vrai, proba)),
        "precision": float(precision_score(y_vrai, y_pred, zero_division=0)),
        "rappel": rappel,
        "rappel_ic95": intervalle_confiance_rappel(rappel, n_positifs),
        "vrais_positifs": int(vp),
        "faux_positifs": int(fp),
        "faux_negatifs": int(fn),
        "vrais_negatifs": int(vn),
        "n_positifs": n_positifs,
    }
