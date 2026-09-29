"""Baseline : régression logistique régularisée, dans un pipeline complet.

Le préprocesseur est inclus **dans** le pipeline, non appliqué avant. Cela garantit que
l'imputation et la mise à l'échelle sont apprises sur les seuls plis d'entraînement lors
de la validation croisée. Les appliquer avant reviendrait à laisser fuiter de
l'information du jeu de test vers l'entraînement — une fuite discrète et fréquente.
"""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import GRAINE


def construire_preprocesseur(X: pd.DataFrame) -> ColumnTransformer:
    """Chaîne de préparation : imputation puis encodage, par type de colonne.

    `OneHotEncoder` et non `LabelEncoder` : `secteur`, `pays` et `plan` sont nominales.
    Un encodage ordinal introduirait un ordre arbitraire qu'un modèle linéaire
    interpréterait comme une relation de grandeur.
    """
    numeriques = X.select_dtypes(include="number").columns.tolist()
    categorielles = [c for c in X.columns if c not in numeriques]

    return ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        # Médiane et non moyenne : le MRR est très asymétrique
                        # (médiane 682 EUR, moyenne 3 543 EUR).
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
                        ("imputation", SimpleImputer(strategy="most_frequent")),
                        (
                            "encodage",
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
    """Pipeline complet de la baseline."""
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
