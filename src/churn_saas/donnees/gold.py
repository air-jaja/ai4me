"""GOLD level - dataset ready for learning.

This is where the most important exclusion rule of the project is enforced: no column
known only after the decision may be used as an explanatory variable. The rule is
general; it does not target one named column (notebook section 8, iteration 1).
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

# Each exclusion carries its own rationale. The motives are NOT interchangeable: the
# certification grid separates ethics (C2) from technical preparation (C3), so a single
# blanket justification would not satisfy either.
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
    """Column-to-rationale table, displayed in the notebook to make the rule readable."""
    return pd.DataFrame(sorted(MOTIFS_EXCLUSION.items()), columns=["colonne", "motif d'exclusion"])


def construire_gold(
    silver: pd.DataFrame, colonnes_supplementaires: list[str] | None = None
) -> pd.DataFrame:
    """Drop forbidden columns and return the modellable dataset, target included."""
    a_retirer = [c for c in MOTIFS_EXCLUSION if c in silver.columns]
    a_retirer += [c for c in (colonnes_supplementaires or []) if c in silver.columns]
    return silver.drop(columns=sorted(set(a_retirer)))


def separer_cible(gold: pd.DataFrame, cible: str = CIBLE) -> tuple[pd.DataFrame, pd.Series]:
    """Split explanatory variables from the target."""
    if cible not in gold.columns:
        raise KeyError(f"Colonne cible `{cible}` absente du jeu gold.")
    y = pd.to_numeric(gold[cible], errors="coerce").astype("Int64")
    X = gold.drop(columns=[cible])
    return X, y
