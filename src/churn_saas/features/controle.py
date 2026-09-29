"""Garde-fous appliqués aux variables avant modélisation.

Ces contrôles sont exécutables et testés : ils constituent l'étape 2 de la chaîne CI
décrite au notebook § 10 (validation des données d'entrée).
"""

from __future__ import annotations

import pandas as pd

from ..donnees.gold import MOTIFS_EXCLUSION


def controler_schema(
    df: pd.DataFrame,
    colonnes_attendues: list[str],
    taux_manquants_max: float = 0.30,
) -> pd.DataFrame:
    """Vérifie présence et complétude des colonnes. Renvoie le constat, ne lève pas.

    Renvoyer un tableau plutôt que lever une exception permet d'afficher le diagnostic
    complet dans le notebook. C'est l'appelant qui décide de bloquer ou non.
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
    """Signale les variables trop corrélées à la cible pour être honnêtes.

    Une corrélation supérieure à 0,80 avec la cible sur un problème de churn n'est
    pratiquement jamais un signal métier : c'est le symptôme d'une information connue
    après coup. Le contrôle est générique, il ne cible aucune colonne nommée.
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
    """Vérifie que les variables leurres figurent bien en bas du classement d'importance.

    Le leurre est **conservé** dans le modèle à dessein : l'écarter a priori priverait de
    la démonstration. On vérifie donc a posteriori qu'il n'apporte rien, plutôt que de le
    supposer (notebook § 7).
    """
    seuil = importances.quantile(quantile_max)
    lignes = []
    for nom in leurres_attendus:
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
