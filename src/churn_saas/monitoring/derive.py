"""Détection de dérive des données.

Le PSI (*Population Stability Index*) compare la distribution courante d'une variable à
une distribution de référence. Lecture usuelle : < 0,10 stable · 0,10–0,25 à surveiller ·
> 0,25 dérive significative.

Point de vigilance (notebook § 13) : la distribution de référence doit être versionnée et
mise à jour à chaque réentraînement. Sans cela, le dispositif compare indéfiniment le
présent à un état ancien — il signale une dérive déjà absorbée, ou cesse d'en détecter.
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
    """Indice de stabilité entre deux distributions d'une même variable numérique."""
    reference = pd.to_numeric(pd.Series(reference), errors="coerce").dropna()
    courant = pd.to_numeric(pd.Series(courant), errors="coerce").dropna()
    if reference.empty or courant.empty:
        return float("nan")

    bornes = np.unique(np.quantile(reference, np.linspace(0, 1, n_quantiles + 1)))
    if len(bornes) < 2:
        return float("nan")
    bornes[0], bornes[-1] = -np.inf, np.inf

    part_ref = np.clip(np.histogram(reference, bins=bornes)[0] / len(reference), epsilon, None)
    part_cur = np.clip(np.histogram(courant, bins=bornes)[0] / len(courant), epsilon, None)
    return float(np.sum((part_cur - part_ref) * np.log(part_cur / part_ref)))


def ks_deux_echantillons(reference: pd.Series, courant: pd.Series) -> tuple[float, float]:
    """Test de Kolmogorov-Smirnov : statistique et p-valeur.

    Complémentaire du PSI. Sur de gros échantillons il devient très sensible et signale
    des écarts sans portée pratique : à lire avec le PSI, pas à sa place.
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
    """Tableau PSI et KS par variable, avec le verdict associé au seuil retenu."""
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
