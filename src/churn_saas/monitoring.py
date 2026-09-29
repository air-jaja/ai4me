"""Surveillance de la dérive des données (notebook § 13).

Le PSI (Population Stability Index) compare la distribution courante d'une variable à
une distribution de référence. Lecture usuelle : < 0,10 stable · 0,10–0,25 à surveiller ·
> 0,25 dérive significative.

Point de vigilance : la distribution de référence doit être versionnée et mise à jour à
chaque réentraînement, faute de quoi le dispositif compare indéfiniment le présent à un
état ancien.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def psi(
    reference: pd.Series,
    courant: pd.Series,
    n_quantiles: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """Indice de stabilité entre deux distributions d'une même variable numérique."""
    reference = pd.Series(reference).dropna()
    courant = pd.Series(courant).dropna()
    if reference.empty or courant.empty:
        return float("nan")

    bornes = np.unique(np.quantile(reference, np.linspace(0, 1, n_quantiles + 1)))
    bornes[0], bornes[-1] = -np.inf, np.inf

    part_ref = np.histogram(reference, bins=bornes)[0] / len(reference)
    part_cur = np.histogram(courant, bins=bornes)[0] / len(courant)
    part_ref = np.clip(part_ref, epsilon, None)
    part_cur = np.clip(part_cur, epsilon, None)

    return float(np.sum((part_cur - part_ref) * np.log(part_cur / part_ref)))


def rapport_derive(
    reference: pd.DataFrame,
    courant: pd.DataFrame,
    colonnes: list[str],
    seuil: float = 0.25,
) -> pd.DataFrame:
    """Tableau PSI par variable, avec le verdict associé au seuil retenu."""
    lignes = [
        {"variable": col, "psi": psi(reference[col], courant[col])}
        for col in colonnes
        if col in reference.columns and col in courant.columns
    ]
    rapport = pd.DataFrame(lignes)
    if not rapport.empty:
        rapport["alerte"] = rapport["psi"] > seuil
        rapport = rapport.sort_values("psi", ascending=False)
    return rapport
