"""Modèle candidat et protocole de comparaison.

La comparaison se fait sur le PR-AUC, pas sur l'exactitude : 72 % des comptes restent, un
modèle prédisant toujours « pas de churn » obtiendrait 72 % d'exactitude sans aucune
valeur.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline

from ..config import GRAINE
from .baseline import construire_preprocesseur


def construire_candidat(X: pd.DataFrame, equilibrer: bool = True) -> Pipeline:
    """Pipeline du modèle candidat : forêt aléatoire."""
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
                    n_jobs=-1,
                ),
            ),
        ]
    )


def grille_hyperparametres() -> dict[str, dict[str, list]]:
    """Grille volontairement restreinte (éco-conception, notebook § 8).

    Une recherche exhaustive multiplierait le coût de calcul pour un gain marginal non
    démontré. L'étendue de la grille est elle-même un arbitrage documenté.
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
    """Validation croisée stratifiée. Renvoie moyenne **et** écart-type.

    L'écart-type n'est pas décoratif : un gain de PR-AUC inférieur à la variabilité entre
    plis n'est pas un gain. C'est le critère qui tranche la boucle évaluation → features
    (notebook § 9).
    """
    plis = StratifiedKFold(n_splits=n_plis, shuffle=True, random_state=GRAINE)
    lignes = []
    for nom, modele in modeles.items():
        scores = cross_validate(
            modele, X, y, cv=plis, scoring=["average_precision", "roc_auc"], n_jobs=-1
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
