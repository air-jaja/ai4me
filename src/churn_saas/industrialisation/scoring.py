"""Lot mensuel de scoring — le seul endroit où la décision est prise.

Rejoue **exactement** la chaîne de préparation de l'entraînement en réutilisant les
fonctions de `donnees.silver` et `features.construction`. Aucune transformation n'est
réécrite ici : c'est la condition pour que le modèle reçoive en production des données
préparées comme à l'apprentissage.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import CAPACITE_MENSUELLE, EFFICACITE_RETENTION
from ..donnees.gold import construire_gold
from ..donnees.silver import construire_silver
from ..evaluation.decision import prioriser
from ..features.construction import ajouter_ratios_usage


def preparer(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    **options_silver: Any,
) -> pd.DataFrame:
    """Chaîne de préparation unique, partagée entre entraînement et scoring."""
    silver = construire_silver(brut, catalogue=catalogue, **options_silver)
    silver = ajouter_ratios_usage(silver)
    return construire_gold(silver)


def scorer_lot_mensuel(
    modele_churn: Any,
    brut: pd.DataFrame,
    valeur_vie_client: pd.Series | None = None,
    modele_clv: Any | None = None,
    catalogue: pd.DataFrame | None = None,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
    identifiant: str = "client_id",
    **options_silver: Any,
) -> pd.DataFrame:
    """Produit la liste priorisée destinée aux équipes Customer Success.

    `valeur_vie_client` est fournie si elle est connue ; sinon elle est estimée par le
    modèle secondaire. C'est l'usage prévu par l'énoncé : pondération de la décision,
    jamais variable explicative du modèle de churn.
    """
    identifiants = brut[identifiant] if identifiant in brut.columns else pd.Series(brut.index)
    X = preparer(brut, catalogue=catalogue, **options_silver)
    X = X.drop(columns=[c for c in ("churn",) if c in X.columns])

    proba = pd.Series(modele_churn.predict_proba(X)[:, 1], index=X.index)

    if valeur_vie_client is None:
        if modele_clv is None:
            raise ValueError(
                "Fournir `valeur_vie_client` ou `modele_clv` : la priorisation par valeur "
                "espérée ne peut pas être calculée sans la valeur du compte."
            )
        valeur_vie_client = pd.Series(modele_clv.predict(X), index=X.index)

    table = prioriser(
        proba, valeur_vie_client, capacite=capacite, efficacite_retention=efficacite_retention
    )
    table.insert(0, identifiant, identifiants.reindex(table.index).to_numpy())
    return table
