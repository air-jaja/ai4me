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


# --- Option C (B6, 03/10/2026): exact linear contributions in production ----------------------
def _variable_source(nom: str, categorielles: list[str]) -> str:
    """Original variable of a preprocessed column: `num__x` -> x, `cat__plan_pro` -> plan."""
    bloc, _, reste = nom.partition("__")
    if bloc != "cat":
        return reste
    candidates = [c for c in categorielles if reste == c or reste.startswith(f"{c}_")]
    return max(candidates, key=len) if candidates else reste


def _chaines_lineaires(modele: Any) -> list:
    """The fitted (preprocessing, logistic regression) pipelines behind a model.

    The retained model is calibrated by an inner cross-validation: it averages several
    calibrated copies of the regression. A plain pipeline is its own single chain.
    """
    if hasattr(modele, "calibrated_classifiers_"):
        return [c.estimator for c in modele.calibrated_classifiers_]
    return [modele]


def moyennes_de_reference(modele: Any, fond: pd.DataFrame) -> list:
    """The baseline of the explanations, computed once: the mean transformed account of
    `fond`, per calibrated copy. A service scoring one account at a time passes it to
    `contributions_lineaires` instead of re-transforming the whole training set per call."""
    import numpy as np

    return [
        np.asarray(chaine.named_steps["preparation"].transform(fond), dtype=float).mean(axis=0)
        for chaine in _chaines_lineaires(modele)
    ]


def contributions_lineaires(
    modele: Any, X: pd.DataFrame, fond: pd.DataFrame | None = None, moyennes: list | None = None
) -> tuple[pd.DataFrame, float]:
    """Each variable's contribution to each account's risk score, exactly (option C).

    For a logistic regression, a variable's contribution is coefficient x (its value -
    its average value), on the log-odds scale; the score is the base plus their sum,
    with no approximation. This is what linear SHAP computes, without SHAP: no dependency
    in production, and an explanation that is exact rather than estimated. One-hot columns
    are summed back into their variable - "the plan", not "plan_pro".

    The retained model averages calibrated copies of the regression: contributions and
    base are averaged over those copies. Calibration is monotone and does not reorder the
    accounts, so the explanation is that of the ranking the advisor sees.

    Returns the contributions (accounts x variables) and the base (average log-odds).
    """
    import numpy as np

    fond = X if fond is None else fond
    tables, bases = [], []
    for rang, chaine in enumerate(_chaines_lineaires(modele)):
        preparation, regression = chaine.named_steps["preparation"], chaine.steps[-1][1]
        categorielles = next(
            (list(cols) for nom, _, cols in preparation.transformers_ if nom == "cat"), []
        )
        noms = preparation.get_feature_names_out()
        Xt = np.asarray(preparation.transform(X), dtype=float)
        moyenne = (
            moyennes[rang]
            if moyennes is not None
            else np.asarray(preparation.transform(fond), dtype=float).mean(axis=0)
        )
        coefficients = regression.coef_.ravel()
        contributions = pd.DataFrame((Xt - moyenne) * coefficients, index=X.index, columns=noms)
        tables.append(
            contributions.T.groupby([_variable_source(n, categorielles) for n in noms]).sum().T
        )
        bases.append(float(regression.intercept_[0] + coefficients @ moyenne))
    moyenne_tables = sum(tables) / len(tables)
    return moyenne_tables[list(X.columns)], float(np.mean(bases))


def expliquer_par_contributions(
    modele: Any,
    X: pd.DataFrame,
    index_compte,
    n_facteurs: int = 5,
    fond: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Main drivers of one account's score, from the exact linear contributions.

    Same table as `expliquer_compte`, so `motif_lisible` writes the advisor's sentence
    from either; this one needs no SHAP and no background sampling.
    """
    contributions, _ = contributions_lineaires(modele, X.loc[[index_compte]], fond)
    ligne = contributions.iloc[0]
    table = pd.DataFrame(
        {
            "variable": ligne.index,
            "valeur": X.loc[index_compte, ligne.index].to_numpy(),
            "contribution": ligne.to_numpy(),
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
