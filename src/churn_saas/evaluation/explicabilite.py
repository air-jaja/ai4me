"""Explicabilité locale par valeurs de Shapley.

L'importance globale des variables répond à « qu'est-ce qui compte en général ? ».
Le CSM a besoin d'une autre réponse : « pourquoi CE compte-ci est-il signalé ? ».
Les deux lectures sont complémentaires et ne se remplacent pas.

Usage responsable : une valeur de Shapley est une **attribution**, pas une cause. Elle
indique la contribution d'une variable à l'écart entre cette prédiction et la prédiction
moyenne, pas ce qui ferait rester le client.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def expliquer_compte(
    modele: Any,
    X: pd.DataFrame,
    index_compte: int,
    n_facteurs: int = 5,
    taille_fond: int = 100,
) -> pd.DataFrame:
    """Principaux facteurs du score d'un compte, du plus contributif au moins.

    `taille_fond` borne l'échantillon de référence : le coût de calcul des valeurs de
    Shapley croît avec lui, sans gain d'interprétation au-delà de quelques dizaines
    d'observations.
    """
    import shap

    fond = shap.utils.sample(X, min(taille_fond, len(X)), random_state=0)
    explicateur = shap.Explainer(modele.predict_proba, fond)
    valeurs = explicateur(X.iloc[[index_compte]])

    # Classe positive (churn) pour un modèle binaire.
    contributions = valeurs.values[0]
    if contributions.ndim > 1:
        contributions = contributions[:, 1]

    table = pd.DataFrame(
        {
            "variable": X.columns,
            "valeur": X.iloc[index_compte].to_numpy(),
            "contribution": contributions,
        }
    )
    table["sens"] = table["contribution"].apply(
        lambda c: "augmente le risque" if c > 0 else "diminue le risque"
    )
    return (
        table.reindex(table["contribution"].abs().sort_values(ascending=False).index)
        .head(n_facteurs)
        .reset_index(drop=True)
    )


def motif_lisible(explication: pd.DataFrame, n: int = 3) -> str:
    """Phrase destinée à la fiche CRM du compte, lisible par un conseiller."""
    principaux = explication.head(n)
    morceaux = [
        f"{ligne.variable} ({ligne.valeur}) {ligne.sens}" for ligne in principaux.itertuples()
    ]
    return "Facteurs principaux : " + " ; ".join(morceaux) + "."
