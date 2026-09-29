"""Métriques techniques et leur incertitude.

Annoncer un rappel au centième sur 280 positifs donne une fausse impression de précision.
Chaque métrique de rappel est donc accompagnée de son intervalle de confiance.
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
    """Demi-largeur de l'intervalle de confiance à 95 % sur un rappel.

    Approximation normale, suffisante ici : avec ~280 positifs et un rappel autour de 0,7,
    les conditions de validité sont largement remplies.
    """
    if n_positifs <= 0:
        return float("nan")
    return float(z * np.sqrt(rappel * (1 - rappel) / n_positifs))


def evaluer(y_vrai: pd.Series, proba: pd.Series, seuil: float = 0.5) -> dict[str, float]:
    """Jeu de métriques au seuil indiqué, avec l'incertitude sur le rappel."""
    y_vrai = pd.Series(y_vrai).astype(int)
    y_pred = (pd.Series(proba) >= seuil).astype(int)
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
