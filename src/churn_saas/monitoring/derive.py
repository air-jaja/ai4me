"""Data drift detection.

PSI (Population Stability Index) compares a variable's current distribution to a reference
one. Usual reading: < 0.10 stable, 0.10-0.25 watch, > 0.25 significant drift.

Watch out (notebook section 13): the reference distribution must be versioned and refreshed
at every retraining. Otherwise the system keeps comparing the present to an old state - it
flags drift already absorbed, or stops detecting new drift altogether.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def psi(
    reference: pd.Series,
    courant: pd.Series,
    n_quantiles: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """Stability index between two distributions of the same numeric variable."""
    reference = pd.to_numeric(pd.Series(reference), errors="coerce").dropna()
    courant = pd.to_numeric(pd.Series(courant), errors="coerce").dropna()
    if reference.empty or courant.empty:
        return float("nan")

    # np.unique collapses duplicate quantiles: a highly concentrated variable would
    # otherwise produce empty bins and a meaningless index.
    bornes = np.unique(np.quantile(reference, np.linspace(0, 1, n_quantiles + 1)))
    if len(bornes) < 2:
        return float("nan")
    # Open the outer edges so current values beyond the reference range are still counted.
    bornes[0], bornes[-1] = -np.inf, np.inf

    # epsilon clipping avoids log(0) when a bin is empty on one side.
    part_ref = np.clip(np.histogram(reference, bins=bornes)[0] / len(reference), epsilon, None)
    part_cur = np.clip(np.histogram(courant, bins=bornes)[0] / len(courant), epsilon, None)
    return float(np.sum((part_cur - part_ref) * np.log(part_cur / part_ref)))


def ks_deux_echantillons(reference: pd.Series, courant: pd.Series) -> tuple[float, float]:
    """Kolmogorov-Smirnov test: statistic and p-value.

    Complements PSI. On large samples it becomes very sensitive and flags differences of
    no practical consequence: read it alongside PSI, not instead of it.
    """
    ref = pd.to_numeric(pd.Series(reference), errors="coerce").dropna()
    cur = pd.to_numeric(pd.Series(courant), errors="coerce").dropna()
    if ref.empty or cur.empty:
        return float("nan"), float("nan")
    resultat = stats.ks_2samp(ref, cur)
    return float(resultat.statistic), float(resultat.pvalue)


def rapport_derive(
    reference: pd.DataFrame,
    courant: pd.DataFrame,
    colonnes: list[str],
    seuil: float = 0.25,
) -> pd.DataFrame:
    """Per-variable PSI and KS table, with the verdict at the chosen threshold."""
    lignes = []
    for col in colonnes:
        if col not in reference.columns or col not in courant.columns:
            continue
        stat_ks, p_ks = ks_deux_echantillons(reference[col], courant[col])
        lignes.append(
            {
                "variable": col,
                "psi": round(psi(reference[col], courant[col]), 4),
                "ks_statistique": round(stat_ks, 4),
                "ks_p_valeur": round(p_ks, 4),
            }
        )
    rapport = pd.DataFrame(lignes)
    if not rapport.empty:
        rapport["alerte"] = rapport["psi"] > seuil
        rapport = rapport.sort_values("psi", ascending=False).reset_index(drop=True)
    return rapport
