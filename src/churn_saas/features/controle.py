"""Guardrails applied to features before modelling.

These checks are executable and tested: they form step 2 of the CI chain described in
notebook section 10 (input data validation).
"""

from __future__ import annotations

import pandas as pd

from ..donnees.gold import MOTIFS_EXCLUSION


def controler_schema(
    df: pd.DataFrame,
    colonnes_attendues: list[str],
    taux_manquants_max: float = 0.30,
) -> pd.DataFrame:
    """Check column presence and completeness. Returns findings, never raises.

    Returning a table rather than raising lets the notebook display the full diagnosis.
    The caller decides whether to block.
    """
    lignes = []
    for col in colonnes_attendues:
        presente = col in df.columns
        taux = float(df[col].isna().mean()) if presente else 1.0
        lignes.append(
            {
                "colonne": col,
                "presente": presente,
                "manquants_pct": round(taux * 100, 2),
                "conforme": presente and taux <= taux_manquants_max,
            }
        )
    return pd.DataFrame(lignes)


def detecter_fuite_suspecte(
    X: pd.DataFrame,
    y: pd.Series,
    seuil_correlation: float = 0.80,
) -> pd.DataFrame:
    """Flag variables too strongly correlated with the target to be honest.

    On a churn problem a correlation above 0.80 with the target is almost never a business
    signal: it is the symptom of information known after the fact. The check is generic -
    it targets no named column, so it would also catch a future, unanticipated leak.
    """
    cible = pd.to_numeric(y, errors="coerce")
    lignes = []
    for col in X.select_dtypes(include="number").columns:
        correlation = pd.to_numeric(X[col], errors="coerce").corr(cible)
        if pd.notna(correlation) and abs(correlation) >= seuil_correlation:
            lignes.append(
                {
                    "variable": col,
                    "correlation_cible": round(float(correlation), 3),
                    "motif_connu": MOTIFS_EXCLUSION.get(col, "à investiguer"),
                }
            )
    return pd.DataFrame(lignes)


def verifier_leurres(
    importances: pd.Series,
    leurres_attendus: tuple[str, ...] = ("couleur_theme_interface", "code_datacenter"),
    quantile_max: float = 0.25,
) -> pd.DataFrame:
    """Check that decoy variables do sit at the bottom of the importance ranking.

    Decoys are deliberately **kept** in the model: dropping them upfront would forfeit the
    demonstration. So we verify afterwards that they contribute nothing, rather than
    assuming it (notebook section 7).
    """
    seuil = importances.quantile(quantile_max)
    lignes = []
    for nom in leurres_attendus:
        # One-hot encoding turns a categorical decoy into several columns sharing its
        # prefix: take the strongest of them, otherwise the check could be fooled.
        correspondances = [i for i in importances.index if str(i).startswith(nom)]
        if not correspondances:
            lignes.append({"leurre": nom, "importance_max": None, "confirme": None})
            continue
        importance_max = float(importances[correspondances].max())
        lignes.append(
            {
                "leurre": nom,
                "importance_max": round(importance_max, 5),
                "confirme": bool(importance_max <= seuil),
            }
        )
    return pd.DataFrame(lignes)
