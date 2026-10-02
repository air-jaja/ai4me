"""Does the customer lifetime value carry the outcome it is used to weigh?

The decision rule ranks accounts by expected value = probability x lifetime value. If that
value had been computed knowing how long each account actually stayed, evaluating the rule
with it would reward the model for information it never had: the impact measured on the
test set would be inflated (C8).

The raw signal looked suspicious: expressed in months of revenue, the value is 18.9 months
for accounts that stay and 15.6 for those that leave. The question is whether churn
explains it, or whether something known before the decision does.

The test is direct. Predict the value from the pre-decision variables only, then add the
outcome. If the outcome carries information the other variables lack, the explained share
of variance rises and its coefficient is large. If it does not, the gap was a composition
effect - churners are simply younger accounts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_score

from ..config import GRAINE

# Below both thresholds, the outcome adds nothing measurable to the value: the observed
# value can be used to evaluate the rule. Fixed before running the diagnostic (rule 8).
GAIN_R2_MAXIMAL = 0.01
EFFET_ISSUE_MAXIMAL = 0.10


def diagnostiquer_valeur_vie(
    explicatives: pd.DataFrame,
    valeur: pd.Series,
    revenu: pd.Series,
    issue: pd.Series,
    anciennete: pd.Series,
    plis: int = 5,
) -> pd.DataFrame:
    """Explained variance of log(value) without, then with, the outcome.

    `explicatives` holds the numeric pre-decision variables; gaps are filled with the
    median, which is enough for a diagnostic. Rows without revenue are dropped: the value
    is read as a number of months of revenue.
    """
    garder = revenu.notna() & valeur.notna() & (revenu > 0) & (valeur > 0)
    X = explicatives.loc[garder].astype(float)
    X = X.fillna(X.median())
    X["log_revenu"] = np.log(revenu.loc[garder].astype(float))
    y = np.log(valeur.loc[garder].astype(float))
    resultat_issue = issue.loc[garder].astype(int)

    validation = KFold(plis, shuffle=True, random_state=GRAINE)
    r2_sans = cross_val_score(LinearRegression(), X, y, cv=validation, scoring="r2").mean()
    avec = X.assign(issue=resultat_issue)
    r2_avec = cross_val_score(LinearRegression(), avec, y, cv=validation, scoring="r2").mean()
    effet = float(np.exp(LinearRegression().fit(avec, y).coef_[-1]) - 1)

    mois = valeur.loc[garder].astype(float) / revenu.loc[garder].astype(float)
    duree = anciennete.loc[garder].astype(float)
    encode = (r2_avec - r2_sans) >= GAIN_R2_MAXIMAL or abs(effet) >= EFFET_ISSUE_MAXIMAL
    lignes = [
        ("Comptes analysés", float(garder.sum())),
        ("Mois de revenu, comptes qui restent (médiane)", mois[resultat_issue == 0].median()),
        ("Mois de revenu, comptes qui partent (médiane)", mois[resultat_issue == 1].median()),
        ("Ancienneté, comptes qui restent (mois, médiane)", duree[resultat_issue == 0].median()),
        ("Ancienneté, comptes qui partent (mois, médiane)", duree[resultat_issue == 1].median()),
        ("Variance expliquée sans l'issue (R², validation croisée)", r2_sans),
        ("Variance expliquée avec l'issue (R², validation croisée)", r2_avec),
        ("Gain de R² apporté par l'issue", r2_avec - r2_sans),
        ("Effet de l'issue sur la valeur, à variables égales (%)", effet * 100),
        ("La valeur encode-t-elle l'issue ?", 1.0 if encode else 0.0),
    ]
    return pd.DataFrame(lignes, columns=["indicateur", "valeur"])


def valeur_encode_l_issue(diagnostic: pd.DataFrame) -> bool:
    """Reading of the diagnostic: True if the value must not be used to evaluate the rule."""
    ligne = diagnostic.loc[diagnostic["indicateur"] == "La valeur encode-t-elle l'issue ?"]
    return bool(ligne["valeur"].iloc[0])
