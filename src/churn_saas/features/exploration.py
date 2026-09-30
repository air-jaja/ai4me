"""Exploration of the relationships a model could learn.

Profiling (activity 1) says what the data contain. This module says what they suggest:
which categories are imbalanced, which variables move with the target, which segments
behave differently.

It belongs to activity 2 rather than activity 1 because its output decides what becomes a
feature. Everything here is read **before** any model is fitted, and on the training data
only in a real setting - exploring the test set is a way of leaking it slowly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def desequilibre_cible(y: pd.Series) -> pd.DataFrame:
    """Class balance of the target, with what it implies for the metric.

    The imbalance level decides which metrics can be trusted. At 28% positives the
    imbalance is moderate: accuracy is already useless, PR-AUC is preferable to ROC-AUC,
    but neither is as dramatic as in a rare-event problem. Overstating the imbalance in a
    presentation invites a correction.
    """
    valeurs = pd.to_numeric(y, errors="coerce").dropna()
    positifs = int((valeurs == 1).sum())
    negatifs = int((valeurs == 0).sum())
    taux = positifs / len(valeurs) if len(valeurs) else float("nan")
    majoritaire = max(taux, 1 - taux)
    return pd.DataFrame(
        [
            {"mesure": "Positifs (churn)", "valeur": f"{positifs:,}".replace(",", " ")},
            {"mesure": "Négatifs", "valeur": f"{negatifs:,}".replace(",", " ")},
            {"mesure": "Taux de positifs", "valeur": f"{taux:.1%}"},
            {
                "mesure": "Ratio négatifs / positifs",
                "valeur": f"{negatifs / max(positifs, 1):.1f} : 1",
            },
            {
                "mesure": "Exactitude d'un modèle trivial",
                "valeur": f"{majoritaire:.1%} — d'où l'inutilité de cette métrique",
            },
            {
                "mesure": "Qualification",
                "valeur": (
                    "déséquilibre sévère"
                    if majoritaire > 0.90
                    else "déséquilibre modéré"
                    if majoritaire > 0.65
                    else "classes équilibrées"
                ),
            },
        ]
    )


def desequilibre_categories(
    df: pd.DataFrame, colonnes: list[str], effectif_minimal: int = 50
) -> pd.DataFrame:
    """Balance of every categorical variable, and the modalities too rare to be trusted.

    A modality carrying a handful of accounts produces an unstable estimate that one-hot
    encoding would turn into a column the model could memorise. Grouping them is a
    decision; knowing they exist is a prerequisite.
    """
    lignes = []
    for colonne in colonnes:
        if colonne not in df.columns:
            continue
        effectifs = df[colonne].value_counts(dropna=True)
        rares = effectifs[effectifs < effectif_minimal]
        lignes.append(
            {
                "variable": colonne,
                "modalités": int(effectifs.size),
                "plus fréquente": f"{effectifs.index[0]} ({effectifs.iloc[0]})",
                "plus rare": f"{effectifs.index[-1]} ({effectifs.iloc[-1]})",
                "rapport max/min": round(float(effectifs.iloc[0] / max(effectifs.iloc[-1], 1)), 1),
                f"modalités < {effectif_minimal}": int(rares.size),
            }
        )
    return pd.DataFrame(lignes)


def taux_cible_par_segment(
    df: pd.DataFrame, colonne: str, cible: str, effectif_minimal: int = 30
) -> pd.DataFrame:
    """Target rate per modality, with the gap to the overall rate.

    The gap is what matters, not the rate itself: it says whether the variable separates
    anything. A segment whose rate matches the average carries no information, however
    large it is.
    """
    valeurs = pd.to_numeric(df[cible], errors="coerce")
    taux_global = float(valeurs.mean())
    groupes = df.groupby(colonne, dropna=True)

    lignes = []
    for modalite, indices in groupes.groups.items():
        effectif = len(indices)
        if effectif < effectif_minimal:
            continue
        taux = float(valeurs.loc[indices].mean())
        lignes.append(
            {
                "modalité": modalite,
                "effectif": effectif,
                "taux cible (%)": round(taux * 100, 1),
                "écart au global (points)": round((taux - taux_global) * 100, 1),
            }
        )
    profil = pd.DataFrame(lignes)
    if not profil.empty:
        profil = profil.sort_values("taux cible (%)", ascending=False).reset_index(drop=True)
    return profil


def correlations_cible(X: pd.DataFrame, y: pd.Series, seuil_notable: float = 0.10) -> pd.DataFrame:
    """Correlation of every numeric variable with the target, strongest first.

    Two cautions belong with this table.

    A correlation is linear and bivariate: a variable that matters only in combination
    with another shows up near zero here. A low correlation is therefore not a reason to
    drop a variable.

    And a very high correlation on a churn problem is a symptom, not a success: it is
    what leakage looks like.
    """
    cible = pd.to_numeric(y, errors="coerce")
    lignes = []
    for colonne in X.select_dtypes(include="number").columns:
        valeurs = pd.to_numeric(X[colonne], errors="coerce")
        correlation = valeurs.corr(cible)
        if pd.isna(correlation):
            continue
        lignes.append(
            {
                "variable": colonne,
                "corrélation": round(float(correlation), 3),
                "sens": "augmente le risque" if correlation > 0 else "diminue le risque",
                "notable": bool(abs(correlation) >= seuil_notable),
            }
        )
    profil = pd.DataFrame(lignes)
    if profil.empty:
        return profil
    return profil.reindex(
        profil["corrélation"].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)


def correlations_entre_variables(X: pd.DataFrame, seuil: float = 0.80) -> pd.DataFrame:
    """Pairs of variables that say nearly the same thing.

    Redundancy is not fatal to a tree ensemble but it destabilises a linear model's
    coefficients and, above all, it makes any importance reading misleading: two
    equivalent variables share the credit and both look half as useful as they are.
    """
    numeriques = X.select_dtypes(include="number")
    matrice = numeriques.corr(numeric_only=True).abs()
    haut = matrice.where(np.triu(np.ones(matrice.shape), k=1).astype(bool))

    lignes = [
        {
            "variable A": ligne,
            "variable B": colonne,
            "corrélation": round(float(haut.loc[ligne, colonne]), 3),
        }
        for ligne in haut.index
        for colonne in haut.columns
        if pd.notna(haut.loc[ligne, colonne]) and haut.loc[ligne, colonne] >= seuil
    ]
    profil = pd.DataFrame(lignes)
    if not profil.empty:
        profil = profil.sort_values("corrélation", ascending=False).reset_index(drop=True)
    return profil


def tendance_par_tranche(
    df: pd.DataFrame, colonne: str, cible: str, n_tranches: int = 5
) -> pd.DataFrame:
    """Target rate per quantile of a numeric variable.

    Reveals what a correlation coefficient hides: a relationship can be strong and
    non-monotonic, in which case the single number underestimates it and a linear model
    will miss it entirely.
    """
    valeurs = pd.to_numeric(df[colonne], errors="coerce")
    cible_valeurs = pd.to_numeric(df[cible], errors="coerce")
    tranches = pd.qcut(valeurs, q=n_tranches, duplicates="drop")

    profil = (
        pd.DataFrame({"tranche": tranches, "cible": cible_valeurs})
        .dropna(subset=["tranche"])
        .groupby("tranche", observed=True)["cible"]
        .agg(effectif="size", taux="mean")
        .reset_index()
    )
    profil["taux (%)"] = (profil["taux"] * 100).round(1)
    profil["tranche"] = profil["tranche"].astype(str)
    return profil.drop(columns=["taux"])


def monotonie(profil_tranches: pd.DataFrame) -> str:
    """Say whether the trend across quantiles is monotonic, and in which direction."""
    taux = profil_tranches["taux (%)"].to_numpy()
    if len(taux) < 3:
        return "indéterminée"
    if all(np.diff(taux) <= 0):
        return "décroissante"
    if all(np.diff(taux) >= 0):
        return "croissante"
    return "non monotone"
