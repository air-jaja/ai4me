"""Local explainability through Shapley values.

Global feature importance answers "what matters in general?". A CSM needs a different
answer: "why is THIS account flagged?". The two readings complement each other; neither
replaces the other.

Responsible use: a Shapley value is an **attribution**, not a cause. It reports a
variable's contribution to the gap between this prediction and the average prediction, not
what would make the customer stay.
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
    """Main drivers of one account's score, most to least contributive.

    `taille_fond` bounds the background sample: Shapley computation cost grows with it,
    with no interpretive gain beyond a few dozen observations.
    """
    import shap

    fond = shap.utils.sample(X, min(taille_fond, len(X)), random_state=0)
    explicateur = shap.Explainer(modele.predict_proba, fond)
    valeurs = explicateur(X.iloc[[index_compte]])

    # Positive class (churn) for a binary model.
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
    # Rank by absolute contribution: a strong negative driver matters as much as a
    # strong positive one when explaining a score.
    return (
        table.reindex(table["contribution"].abs().sort_values(ascending=False).index)
        .head(n_facteurs)
        .reset_index(drop=True)
    )


def motif_lisible(explication: pd.DataFrame, n: int = 3) -> str:
    """Sentence meant for the account's CRM record, readable by an advisor."""
    principaux = explication.head(n)
    morceaux = [
        f"{ligne.variable} ({ligne.valeur}) {ligne.sens}" for ligne in principaux.itertuples()
    ]
    return "Facteurs principaux : " + " ; ".join(morceaux) + "."
