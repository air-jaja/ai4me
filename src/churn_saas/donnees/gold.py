"""GOLD level - dataset ready for learning.

This is where the most important exclusion rule of the project is enforced: no column
known only after the decision may be used as an explanatory variable. The rule is
general; it does not target one named column (notebook section 8, iteration 1).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split

from ..config import (
    CIBLE,
    ECART_STRATIFICATION_MAX_PTS,
    EXCLUES_ARTEFACT,
    EXCLUES_ATTRIBUT_FORMULE,
    EXCLUES_CIBLE_SECONDAIRE,
    EXCLUES_DATE_BRUTE,
    EXCLUES_DOUBLON,
    EXCLUES_FUITE,
    EXCLUES_IDENTIFIANT,
    EXCLUES_LEURRES,
    EXCLUES_RGPD,
    EXCLUES_SANS_APPORT,
    EXCLUES_SOUS_LE_PLANCHER,
    GRAINE,
    PART_TEST,
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
    **{c: f"doublon — même information que {source}" for c, source in EXCLUES_DOUBLON.items()},
    **{
        c: "date brute — encodée telle quelle, une catégorie par jour ; "
        "anciennete_mois porte déjà l'information"
        for c in EXCLUES_DATE_BRUTE
    },
    **{
        c: "attribut de la formule — une seule valeur par plan, information portée par `plan`"
        for c in EXCLUES_ATTRIBUT_FORMULE
    },
    **{
        c: "variable construite — apport non significatif mesuré (phase 5, bloc B)"
        for c in EXCLUES_SANS_APPORT
    },
    **{
        c: "sous le plancher des leurres (deux modèles), retrait sans perte (phase 5, bloc C)"
        for c in EXCLUES_SOUS_LE_PLANCHER
    },
    **{
        c: "leurre — étalon du bruit pendant la sélection, retiré du modèle final (phase 5)"
        for c in EXCLUES_LEURRES
    },
}


def table_exclusions() -> pd.DataFrame:
    """Column-to-rationale table, displayed in the notebook to make the rule readable."""
    return pd.DataFrame(sorted(MOTIFS_EXCLUSION.items()), columns=["colonne", "motif d'exclusion"])


def construire_gold(
    silver: pd.DataFrame,
    colonnes_supplementaires: list[str] | None = None,
    garder: list[str] | None = None,
) -> pd.DataFrame:
    """Drop forbidden columns and return the modellable dataset, target included.

    `garder` exempts excluded columns from removal: the selection notebook rebuilds the
    candidate set it decided on, with the variables it later removed.
    """
    exemptees = set(garder or [])
    a_retirer = [c for c in MOTIFS_EXCLUSION if c in silver.columns and c not in exemptees]
    a_retirer += [c for c in (colonnes_supplementaires or []) if c in silver.columns]
    return silver.drop(columns=sorted(set(a_retirer)))


def separer_cible(gold: pd.DataFrame, cible: str = CIBLE) -> tuple[pd.DataFrame, pd.Series]:
    """Split explanatory variables from the target."""
    if cible not in gold.columns:
        raise KeyError(f"Colonne cible `{cible}` absente du jeu gold.")
    y = pd.to_numeric(gold[cible], errors="coerce").astype("Int64")
    X = gold.drop(columns=[cible])
    return X, y


@dataclass(frozen=True)
class Decoupage:
    """Training and test parts of the gold dataset, with the parameters that produced them."""

    X_entrainement: pd.DataFrame
    X_test: pd.DataFrame
    y_entrainement: pd.Series
    y_test: pd.Series
    part_test: float
    graine: int


def decouper_entrainement_test(
    X: pd.DataFrame, y: pd.Series, part_test: float = PART_TEST, graine: int = GRAINE
) -> Decoupage:
    """Stratified split: the test part is set aside once and used once (arbitrage 1).

    Stratified on the target so both parts keep the 28 % churn rate; seeded so the very
    same accounts land in the test part on every machine. Validation happens inside the
    training part, by cross-validation - there is no fixed validation set (choix § 7 bis).
    """
    X_a, X_t, y_a, y_t = train_test_split(
        X, y, test_size=part_test, stratify=y, random_state=graine
    )
    return Decoupage(X_a, X_t, y_a, y_t, part_test, graine)


def resume_decoupage(decoupage: Decoupage) -> pd.DataFrame:
    """Sizes and churn rate of each part, and the stratification verdict."""
    taux_a = float(pd.to_numeric(decoupage.y_entrainement).mean() * 100)
    taux_t = float(pd.to_numeric(decoupage.y_test).mean() * 100)
    ecart = abs(taux_a - taux_t)
    return pd.DataFrame(
        [
            {
                "partie": "entraînement",
                "comptes": len(decoupage.y_entrainement),
                "taux de churn (%)": round(taux_a, 2),
            },
            {
                "partie": "test",
                "comptes": len(decoupage.y_test),
                "taux de churn (%)": round(taux_t, 2),
            },
            {
                "partie": "écart (points)",
                "comptes": None,
                "taux de churn (%)": round(ecart, 2),
                "conforme": ecart < ECART_STRATIFICATION_MAX_PTS,
            },
        ]
    )
