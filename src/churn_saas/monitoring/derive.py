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


def psi_categoriel(reference: pd.Series, courant: pd.Series, epsilon: float = 1e-6) -> float:
    """Stability index for a categorical variable: the same formula, on category shares.

    Missing values form their own category: a rise in missing values is a drift too.
    A category absent from the reference still counts, through the epsilon floor.
    """
    ref = pd.Series(reference).astype("string").fillna("<manquant>")
    cur = pd.Series(courant).astype("string").fillna("<manquant>")
    if ref.empty or cur.empty:
        return float("nan")
    modalites = sorted(set(ref) | set(cur))
    part_ref = np.clip(
        ref.value_counts(normalize=True).reindex(modalites, fill_value=0), epsilon, None
    )
    part_cur = np.clip(
        cur.value_counts(normalize=True).reindex(modalites, fill_value=0), epsilon, None
    )
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
        # Categorical variables get the categorical index and no KS test, which assumes an
        # ordered scale. Until phase 5 the numeric index returned NaN on them, and NaN
        # compared to the threshold reads as "no alert": any categorical drift went unseen.
        if pd.api.types.is_numeric_dtype(reference[col]):
            stat_ks, p_ks = ks_deux_echantillons(reference[col], courant[col])
            indice = psi(reference[col], courant[col])
        else:
            stat_ks, p_ks = float("nan"), float("nan")
            indice = psi_categoriel(reference[col], courant[col])
        lignes.append(
            {
                "variable": col,
                "psi": round(indice, 4),
                "ks_statistique": round(stat_ks, 4),
                "ks_p_valeur": round(p_ks, 4),
            }
        )
    rapport = pd.DataFrame(lignes)
    if not rapport.empty:
        rapport["alerte"] = rapport["psi"] > seuil
        rapport = rapport.sort_values("psi", ascending=False).reset_index(drop=True)
    return rapport


# --- Reference profile (phase 11, A1) -------------------------------------------------------
# The PSI needs the reference distribution. Keeping the training rows next to the service
# would carry account data into production; the profile keeps only what the index reads -
# bin edges and shares - versioned with the model it describes (notebook section 13).
MANQUANT = "<manquant>"


def profil_variable(reference: pd.Series, n_quantiles: int = 10) -> dict:
    """What `psi` or `psi_categoriel` reads from a reference series, and nothing more."""
    serie = pd.Series(reference)
    if pd.api.types.is_numeric_dtype(serie):
        valeurs = pd.to_numeric(serie, errors="coerce").dropna()
        bornes = np.unique(np.quantile(valeurs, np.linspace(0, 1, n_quantiles + 1)))
        if valeurs.empty or len(bornes) < 2:
            return {"type": "numérique", "bornes_internes": [], "parts": []}
        bornes[0], bornes[-1] = -np.inf, np.inf
        parts = np.histogram(valeurs, bins=bornes)[0] / len(valeurs)
        # Outer edges are open (+-inf): only the inner ones are stored, JSON has no infinity.
        return {
            "type": "numérique",
            "bornes_internes": [float(b) for b in bornes[1:-1]],
            "parts": [float(p) for p in parts],
        }
    parts = serie.astype("string").fillna(MANQUANT).value_counts(normalize=True)
    return {"type": "catégoriel", "parts": {str(k): float(v) for k, v in parts.items()}}


def psi_contre_profil(profil: dict, courant: pd.Series, epsilon: float = 1e-6) -> float:
    """The same index as `psi` / `psi_categoriel`, the reference read from its profile."""
    if profil["type"] == "numérique":
        courant = pd.to_numeric(pd.Series(courant), errors="coerce").dropna()
        if courant.empty or not profil["parts"]:
            return float("nan")
        bornes = np.array([-np.inf, *profil["bornes_internes"], np.inf])
        part_ref = np.clip(np.array(profil["parts"]), epsilon, None)
        part_cur = np.clip(np.histogram(courant, bins=bornes)[0] / len(courant), epsilon, None)
        return float(np.sum((part_cur - part_ref) * np.log(part_cur / part_ref)))
    cur = pd.Series(courant).astype("string").fillna(MANQUANT)
    if cur.empty:
        return float("nan")
    modalites = sorted(set(profil["parts"]) | set(cur))
    part_ref = np.clip(
        pd.Series(profil["parts"]).reindex(modalites, fill_value=0).to_numpy(), epsilon, None
    )
    part_cur = np.clip(
        cur.value_counts(normalize=True).reindex(modalites, fill_value=0).to_numpy(), epsilon, None
    )
    return float(np.sum((part_cur - part_ref) * np.log(part_cur / part_ref)))
