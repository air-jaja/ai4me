"""Niveau GOLD — jeu prêt pour l'apprentissage.

C'est ici qu'est appliquée la règle d'exclusion la plus importante du projet : aucune
colonne postérieure à la décision ne peut servir de variable explicative. Cette règle est
générale, elle ne vise pas une colonne en particulier (notebook § 8, itération 1).
"""

from __future__ import annotations

import pandas as pd

from ..config import (
    CIBLE,
    EXCLUES_ARTEFACT,
    EXCLUES_CIBLE_SECONDAIRE,
    EXCLUES_FUITE,
    EXCLUES_IDENTIFIANT,
    EXCLUES_RGPD,
)

MOTIFS_EXCLUSION: dict[str, str] = {
    **{c: "fuite temporelle — information postérieure à la décision" for c in EXCLUES_FUITE},
    **{
        c: "identifiant — aucun pouvoir prédictif, risque de mémorisation"
        for c in EXCLUES_IDENTIFIANT
    },
    **{
        c: "RGPD — texte libre susceptible de contenir des données personnelles"
        for c in EXCLUES_RGPD
    },
    **{c: "artefact de process interne — pas une variable métier" for c in EXCLUES_ARTEFACT},
    **{
        c: "cible secondaire — pondération de décision, jamais variable explicative"
        for c in EXCLUES_CIBLE_SECONDAIRE
    },
}


def table_exclusions() -> pd.DataFrame:
    """Tableau colonne → motif, à afficher dans le notebook pour rendre la règle lisible."""
    return pd.DataFrame(sorted(MOTIFS_EXCLUSION.items()), columns=["colonne", "motif d'exclusion"])


def construire_gold(
    silver: pd.DataFrame, colonnes_supplementaires: list[str] | None = None
) -> pd.DataFrame:
    """Retire les colonnes interdites et renvoie le jeu modélisable, cible incluse."""
    a_retirer = [c for c in MOTIFS_EXCLUSION if c in silver.columns]
    a_retirer += [c for c in (colonnes_supplementaires or []) if c in silver.columns]
    return silver.drop(columns=sorted(set(a_retirer)))


def separer_cible(gold: pd.DataFrame, cible: str = CIBLE) -> tuple[pd.DataFrame, pd.Series]:
    """Sépare les variables explicatives de la cible."""
    if cible not in gold.columns:
        raise KeyError(f"Colonne cible `{cible}` absente du jeu gold.")
    y = pd.to_numeric(gold[cible], errors="coerce").astype("Int64")
    X = gold.drop(columns=[cible])
    return X, y
