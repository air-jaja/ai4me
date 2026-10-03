"""Monthly scoring batch - the only place where the decision is taken.

Replays **exactly** the training preparation chain by reusing the functions from
`donnees.silver` and `features.construction`. No transformation is rewritten here: that is
the condition for the model to receive production data prepared the way it learned from.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import CAPACITE_MENSUELLE, EFFICACITE_RETENTION
from ..donnees import (
    colonnes_attendues_au_scoring,
    exiger_contrat,
    typer_pour_modele,
    verifier_contrat,
)
from ..evaluation import prioriser
from ..features import (
    COLONNES_DATES,
    COLONNES_DECIMALES,
    COLONNES_ENTIERES,
    construire_silver_standard,
    preparer_gold,
)


def preparer(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    **options_silver: Any,
) -> pd.DataFrame:
    """Single preparation chain, shared between training and scoring.

    Since phase 4 it calls exactly what `executer_pipeline` calls - same column lists,
    same structural zeros, same reconstruction, same exclusions. Before, it built silver
    without the column lists and skipped nothing visible: the batch would have been
    prepared differently from the training set, without any error.
    """
    silver = construire_silver_standard(brut, catalogue=catalogue, **options_silver)
    return preparer_gold(silver).gold


def controler_lot(brut: pd.DataFrame, catalogue: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run the data contract on a monthly batch, as on the training set.

    Not part of `preparer`, which the API also calls on a single account: a missing rate
    computed on one row means nothing. Silver is built with `strict=False` so that a
    conversion loss is reported by the contract, with every other check, instead of
    stopping at the first exception.
    """
    silver = construire_silver_standard(brut, catalogue=catalogue, strict=False)
    return verifier_contrat(
        silver,
        brut=brut,
        colonnes_numeriques=list(COLONNES_DECIMALES) + list(COLONNES_ENTIERES),
        colonnes_dates=list(COLONNES_DATES),
        colonnes_attendues=colonnes_attendues_au_scoring(),
    )


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
    """Produce the prioritised shortlist for the Customer Success teams.

    `valeur_vie_client` is supplied when known, otherwise estimated by the secondary
    model. This is the use the brief intends: a decision weight, never an explanatory
    variable of the churn model.
    """
    # Identifiers are captured before preparation, since construire_gold drops them.
    identifiants = brut[identifiant] if identifiant in brut.columns else pd.Series(brut.index)
    exiger_contrat(controler_lot(brut, catalogue=catalogue))
    X = preparer(brut, catalogue=catalogue, **options_silver)
    X = typer_pour_modele(X.drop(columns=[c for c in ("churn",) if c in X.columns]))

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
