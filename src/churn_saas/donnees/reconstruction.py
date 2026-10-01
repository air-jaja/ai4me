"""Deterministic reconstruction - filling a gap from the row itself, never from the dataset.

Some missing values are not unknown: the same row holds what is needed to recompute them.
Recomputing them is not a statistical estimate, it is a business rule applied row by row.
Nothing is learnt from other rows, so nothing can leak from a test set into a training
set: the reconstruction may run before the split, unlike the median imputation.

Each rule was checked against the rows where the true value is known (phase 4):

    revenu_mensuel_recurrent_eur = sieges_souscrits x prix_mensuel_par_siege_eur
        median relative error 9.0 % on 4,850 observed accounts, against 91.4 % for the
        global median - which is what the model would otherwise receive.
    taux_adoption_pct = utilisateurs_actifs / sieges_souscrits x 100, one decimal
        zero gap on the observed rows: the source column is exactly this ratio.

A value already present is never replaced. A row missing one ingredient keeps its gap,
which the median imputation of the model pipeline then handles.

This step runs **after** the data contract. Placed before, it would make the contract
measure 0 % missing revenue where the source has 3 %, and the monthly monitoring of
incoming data quality would go blind.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RegleReconstruction:
    """One reconstruction rule, declared as data so the notebook can display it."""

    colonne: str
    formule: str
    ingredients: tuple[str, ...]
    calcul: Callable[[pd.DataFrame], pd.Series]


def _num(df: pd.DataFrame, colonne: str) -> pd.Series:
    return pd.to_numeric(df[colonne], errors="coerce").astype(float)


REGLES_RECONSTRUCTION: tuple[RegleReconstruction, ...] = (
    RegleReconstruction(
        colonne="revenu_mensuel_recurrent_eur",
        formule="sièges souscrits × prix mensuel par siège",
        ingredients=("sieges_souscrits", "prix_mensuel_par_siege_eur"),
        calcul=lambda df: (
            _num(df, "sieges_souscrits") * _num(df, "prix_mensuel_par_siege_eur")
        ).round(2),
    ),
    RegleReconstruction(
        colonne="taux_adoption_pct",
        formule="utilisateurs actifs ÷ sièges souscrits × 100, une décimale",
        ingredients=("utilisateurs_actifs", "sieges_souscrits"),
        calcul=lambda df: (
            _num(df, "utilisateurs_actifs")
            / _num(df, "sieges_souscrits").where(_num(df, "sieges_souscrits") > 0)
            * 100
        ).round(1),
    ),
)


def reconstruire_valeurs_deterministes(
    df: pd.DataFrame, regles: tuple[RegleReconstruction, ...] = REGLES_RECONSTRUCTION
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill the gaps each rule can recompute; return the data and what was done.

    The report has one row per rule: how many gaps it found, filled, and left. A rule whose
    column or ingredients are absent is reported as not applicable rather than skipped in
    silence.
    """
    out = df.copy()
    bilan = []
    for regle in regles:
        if regle.colonne not in out.columns or not set(regle.ingredients) <= set(out.columns):
            bilan.append(
                {
                    "colonne": regle.colonne,
                    "règle": regle.formule,
                    "manquants avant": None,
                    "reconstruits": 0,
                    "manquants après": None,
                    "statut": "non applicable (colonne ou ingrédient absent)",
                }
            )
            continue
        manquant = out[regle.colonne].isna()
        valeurs = regle.calcul(out)
        comblables = manquant & valeurs.notna()
        out[regle.colonne] = out[regle.colonne].astype(float).where(~comblables, valeurs)
        bilan.append(
            {
                "colonne": regle.colonne,
                "règle": regle.formule,
                "manquants avant": int(manquant.sum()),
                "reconstruits": int(comblables.sum()),
                "manquants après": int(out[regle.colonne].isna().sum()),
                "statut": "appliquée",
            }
        )
    return out, pd.DataFrame(bilan)
