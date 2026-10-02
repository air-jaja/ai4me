"""Validating the prepared dataset and its split, before any model is chosen.

Three questions, each answered by a measurement and a threshold fixed beforehand
(choix § 7 bis):

- Can a model tell the training part from the test part? It must not: if it can, the
  test part does not represent what the model was trained on (adversarial validation).
- Does the model beat shuffled labels? It must, clearly: a model scoring as well on
  shuffled labels as on real ones learns from the chain, not from the data - a leak
  (label permutation test).
- Does more data still help, and does the model overfit? The learning curve says whether
  5,000 accounts are enough, and how far training and validation scores stay apart.

Every function takes the model as an argument: the same checks apply to the baseline and
to the candidate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_predict,
    learning_curve,
    permutation_test_score,
)

from ..config import GRAINE, SEUIL_AUC_ADVERSE, SEUIL_P_PERMUTATION


def validation_adverse(
    modele, X_entrainement: pd.DataFrame, X_test: pd.DataFrame, plis: int = 5
) -> dict[str, object]:
    """Out-of-fold AUC of a classifier asked to tell the two parts apart.

    0.5 means it cannot: both parts come from the same distribution. Out-of-fold
    predictions are used, so the classifier never scores rows it was trained on.
    """
    X = pd.concat([X_entrainement, X_test], ignore_index=True)
    origine = np.r_[np.zeros(len(X_entrainement)), np.ones(len(X_test))].astype(int)
    validation = StratifiedKFold(plis, shuffle=True, random_state=GRAINE)
    probabilites = cross_val_predict(
        clone(modele), X, origine, cv=validation, method="predict_proba"
    )[:, 1]
    auc = float(roc_auc_score(origine, probabilites))
    taux_faux, taux_vrais, _ = roc_curve(origine, probabilites)
    return {
        "auc": auc,
        "conforme": auc < SEUIL_AUC_ADVERSE,
        "taux_faux_positifs": taux_faux,
        "taux_vrais_positifs": taux_vrais,
    }


def tester_permutation(
    modele,
    X: pd.DataFrame,
    y: pd.Series,
    n_permutations: int = 100,
    plis: int = 5,
) -> dict[str, object]:
    """Real PR-AUC against the PR-AUC obtained on shuffled labels.

    The p-value is the share of shuffles that do at least as well as the real labels; its
    floor is 1 / (n_permutations + 1), so at least 20 shuffles are needed to reach 0.05.
    """
    validation = StratifiedKFold(plis, shuffle=True, random_state=GRAINE)
    score, permutes, p_valeur = permutation_test_score(
        clone(modele),
        X,
        pd.Series(y).astype(int),
        scoring="average_precision",
        cv=validation,
        n_permutations=n_permutations,
        random_state=GRAINE,
    )
    return {
        "score": float(score),
        "scores_permutes": np.asarray(permutes),
        "moyenne_permutee": float(np.mean(permutes)),
        "p_valeur": float(p_valeur),
        "conforme": float(p_valeur) < SEUIL_P_PERMUTATION,
    }


def courbe_apprentissage(
    modele,
    X: pd.DataFrame,
    y: pd.Series,
    tailles: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 1.0),
    plis: int = 5,
) -> pd.DataFrame:
    """PR-AUC on the training folds and on the validation folds, by training size."""
    validation = StratifiedKFold(plis, shuffle=True, random_state=GRAINE)
    effectifs, entrainement, test = learning_curve(
        clone(modele),
        X,
        pd.Series(y).astype(int),
        train_sizes=np.asarray(tailles),
        cv=validation,
        scoring="average_precision",
        shuffle=True,
        random_state=GRAINE,
    )
    return pd.DataFrame(
        {
            "comptes d'entraînement": effectifs,
            "PR-AUC entraînement": entrainement.mean(axis=1),
            "PR-AUC validation": test.mean(axis=1),
            "écart-type validation": test.std(axis=1),
            "écart entraînement - validation": entrainement.mean(axis=1) - test.mean(axis=1),
        }
    )
