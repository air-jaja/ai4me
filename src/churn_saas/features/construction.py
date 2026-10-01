"""Derived variables.

A ratio speaks louder than a pair of raw values: "2 features used out of 10 available"
directly answers whether the customer exploits what they pay for, which neither number
does on its own.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _ratio(numerateur: pd.Series, denominateur: pd.Series) -> pd.Series:
    """Guarded division: a zero denominator yields NaN, never an error nor an infinity.

    Infinities are worse than missing values here: they propagate silently through the
    pipeline and only surface as absurd model coefficients.
    """
    num = pd.to_numeric(numerateur, errors="coerce")
    den = pd.to_numeric(denominateur, errors="coerce")
    return (num / den.replace(0, np.nan)).astype(float)


# Ratios divided by the number of active users, hence undefined when it is zero.
RATIOS_PAR_ACTIF = ("usage_par_actif", "tickets_par_actif")


def ajouter_ratios_usage(df: pd.DataFrame) -> pd.DataFrame:
    """Add usage ratios, and the indicator their denominator hides.

    Ratios built here:

    - `taux_activation`      share of purchased seats actually used
    - `taux_couverture_fonc` share of plan features actually used
    - `usage_par_actif`      usage intensity per active user
    - `tickets_par_actif`    support pressure relative to account size

    **Plus one indicator that is not a ratio, and matters more than all of them.**
    Dividing by the number of active users yields NaN when that number is zero. Those NaN
    are not missing data: they encode a precise business situation - an account still
    being paid for that nobody uses.

    On this portfolio the situation covers 5.9% of accounts, which churn at 86.5% against
    24.3% for the rest. Leaving the signal inside a NaN would mean losing it at the first
    imputation, since a median would replace it with the value of an ordinary account.
    `compte_sans_utilisateur_actif` therefore states it explicitly (notebook 03, § 3).
    The NaN themselves stay here, where the exploration reads them; they are set to 0 on
    the way to gold by `combler_ratios_structurels` (phase 4).
    """
    out = df.copy()
    if "utilisateurs_actifs" in out.columns:
        # Declared before the ratios: the indicator explains the NaN they are about to
        # produce, and a reader meets the cause before the consequence.
        actifs = pd.to_numeric(out["utilisateurs_actifs"], errors="coerce")
        out["compte_sans_utilisateur_actif"] = (actifs == 0).astype("Int8")
    if {"utilisateurs_actifs", "sieges_souscrits"} <= set(out.columns):
        out["taux_activation"] = _ratio(out["utilisateurs_actifs"], out["sieges_souscrits"])
    if {"fonctionnalites_utilisees", "fonctionnalites_total"} <= set(out.columns):
        out["taux_couverture_fonc"] = _ratio(
            out["fonctionnalites_utilisees"], out["fonctionnalites_total"]
        )
    if {"heures_usage_30j", "utilisateurs_actifs"} <= set(out.columns):
        out["usage_par_actif"] = _ratio(out["heures_usage_30j"], out["utilisateurs_actifs"])
    if {"tickets_support_90j", "utilisateurs_actifs"} <= set(out.columns):
        out["tickets_par_actif"] = _ratio(out["tickets_support_90j"], out["utilisateurs_actifs"])

    return out


def combler_ratios_structurels(df: pd.DataFrame) -> pd.DataFrame:
    """Set the per-user ratios to 0 where there is no active user (phase 4).

    With no active user, a per-user ratio is undefined, not unknown. The value 0 is a
    convention; the indicator `compte_sans_utilisateur_actif` carries the meaning. For
    usage the convention matches the data (hours are always 0 or missing there); for
    tickets it does not - 210 such accounts still open tickets - which is why the model
    must read the indicator, not the ratio.

    Filling them here separates the two causes of NaN. What remains is genuinely unknown
    (hours missing on an account that has users) and goes to the median imputation of the
    model pipeline. Applied on the way to gold only: silver keeps the NaN the exploration
    reads, so the phase 3 demonstration stays reproducible.
    """
    out = df.copy()
    if "compte_sans_utilisateur_actif" not in out.columns:
        return out
    sans_actif = pd.to_numeric(out["compte_sans_utilisateur_actif"], errors="coerce").eq(1)
    for ratio in RATIOS_PAR_ACTIF:
        if ratio in out.columns:
            out.loc[sans_actif, ratio] = 0.0
    return out
