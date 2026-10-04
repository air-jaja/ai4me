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


def preparer_lot(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    **options_silver: Any,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A batch's silver table and model matrix, on the same index.

    Silver drops the duplicate rows and renumbers the accounts: from then on, a row of `brut`
    is no longer the row of the same rank in the matrix. The account's identifier and value
    must be read from silver - read from `brut` by position, they shift after the first
    duplicate and every account carries its neighbour's score.
    """
    silver = construire_silver_standard(brut, catalogue=catalogue, **options_silver)
    X = preparer_gold(silver).gold
    X = typer_pour_modele(X.drop(columns=[c for c in ("churn",) if c in X.columns]))
    return silver.loc[X.index], X


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
    valeur_vie_client: str | pd.Series | None = None,
    modele_clv: Any | None = None,
    catalogue: pd.DataFrame | None = None,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
    identifiant: str = "client_id",
    **options_silver: Any,
) -> pd.DataFrame:
    """Produce the prioritised shortlist for the Customer Success teams.

    `valeur_vie_client` is supplied when known - the name of a batch column, or a series
    indexed by account identifier - otherwise estimated by the secondary model. This is the
    use the brief intends: a decision weight, never an explanatory variable of the churn
    model. Never by position: the batch may hold duplicates, which silver drops.
    """
    exiger_contrat(controler_lot(brut, catalogue=catalogue))
    silver, X = preparer_lot(brut, catalogue=catalogue, **options_silver)
    # Identifiers come from silver, aligned with X: construire_gold drops them.
    identifiants = silver[identifiant] if identifiant in silver.columns else pd.Series(X.index)

    proba = pd.Series(modele_churn.predict_proba(X)[:, 1], index=X.index)

    if valeur_vie_client is None:
        if modele_clv is None:
            raise ValueError(
                "Fournir `valeur_vie_client` ou `modele_clv` : la priorisation par valeur "
                "espérée ne peut pas être calculée sans la valeur du compte."
            )
        valeur = pd.Series(modele_clv.predict(X), index=X.index)
    elif isinstance(valeur_vie_client, str):
        valeur = pd.to_numeric(silver[valeur_vie_client], errors="coerce")
    else:
        absents = ~identifiants.isin(valeur_vie_client.index)
        if not valeur_vie_client.index.is_unique or absents.any():
            raise ValueError(
                f"`valeur_vie_client` doit être indexée par `{identifiant}`, une valeur par "
                f"compte : {int(absents.sum())} compte(s) du lot n'y figurent pas."
            )
        valeur = pd.Series(valeur_vie_client.reindex(identifiants).to_numpy(), index=X.index)

    table = prioriser(proba, valeur, capacite=capacite, efficacite_retention=efficacite_retention)
    table.insert(0, identifiant, identifiants.reindex(table.index).to_numpy())
    return table
