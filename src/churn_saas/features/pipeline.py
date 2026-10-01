"""Bronze -> silver -> gold pipeline, assembled in one place.

**Why activity 2 and not activity 1.** The pipeline ends with the gold dataset, derived
variables included - which is activity 2's deliverable, not activity 1's. Placing it under
data management would make activity 1 import activity 2 and invert the lifecycle order;
the structure test rejects exactly that.

The three levels already existed as separate functions. This module composes them and
returns, alongside the datasets, a **report** of what each step did: rows dropped, columns
added, columns removed. Without that report the pipeline is a black box, and a
transformation nobody can quantify is a transformation nobody can defend.

    BRONZE  raw data exactly as received. Everything is text: letting pandas infer types
            would hide the very defects the preparation must handle.
    SILVER  cleaned, typed, joined, human-readable. Faithful to the business.
    GOLD    ready for learning: derived variables added, forbidden columns removed,
            target separated.

**Where imputation belongs.** Statistical imputation is *not* performed here. It is fitted
inside the model pipeline, on training folds only. Filling values before the split would
let the test set influence the values the model learns from - a quiet form of leakage.
`silver_lisible()` exists for the other consumer, a human reading the data, and is never
fed to the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CIBLE
from ..donnees import (
    MOTIFS_EXCLUSION,
    charger_bronze,
    construire_gold,
    construire_silver,
    separer_cible,
)
from .construction import ajouter_ratios_usage

# Columns whose numbers arrive as text, and dates in mixed formats. Declared once: the
# notebooks and the monthly batch must not each hold their own copy of this list.
COLONNES_DECIMALES = (
    "taux_adoption_pct",
    "heures_usage_30j",
    "delai_reponse_support_h",
    "revenu_mensuel_recurrent_eur",
    "valeur_vie_client_eur",
)
COLONNES_ENTIERES = (
    "anciennete_mois",
    "sieges_souscrits",
    "utilisateurs_actifs",
    "connexions_30j",
    "fonctionnalites_total",
    "fonctionnalites_utilisees",
    "nb_integrations",
    "derniere_connexion_jours",
    "tickets_support_90j",
    "csat",
    "retards_paiement_12m",
    "sante_compte_fin_periode",
    "churn",
)
COLONNES_DATES = ("date_souscription",)


@dataclass
class ResultatPipeline:
    """Datasets produced, and the report of what produced them."""

    bronze: pd.DataFrame
    silver: pd.DataFrame
    gold: pd.DataFrame
    X: pd.DataFrame
    y: pd.Series
    journal: pd.DataFrame = field(default_factory=pd.DataFrame)


def _journal(etapes: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(etapes)


def executer_pipeline(
    chemin_donnees: Path | str,
    chemin_catalogue: Path | str | None = None,
    enrichir: bool = True,
    cible: str = CIBLE,
) -> ResultatPipeline:
    """Run the three levels and record what each one changed.

    `enrichir` adds the usage ratios. It is a parameter rather than a constant because
    the evaluation -> features loop compares the model with and without them: measuring
    the contribution of feature engineering requires being able to switch it off.
    """
    etapes: list[dict[str, Any]] = []

    bronze = charger_bronze(chemin_donnees)
    etapes.append(
        {
            "niveau": "bronze",
            "opération": "Lecture brute, tout en texte",
            "lignes": len(bronze),
            "colonnes": bronze.shape[1],
            "effet": "Aucune transformation : les défauts restent visibles",
        }
    )

    catalogue = charger_bronze(chemin_catalogue) if chemin_catalogue else None
    silver = construire_silver(
        bronze,
        catalogue=catalogue,
        colonnes_decimales=list(COLONNES_DECIMALES),
        colonnes_dates=list(COLONNES_DATES),
        colonnes_entieres=list(COLONNES_ENTIERES),
    )
    etapes.append(
        {
            "niveau": "silver",
            "opération": "Doublons, typage, normalisation, jointure catalogue",
            "lignes": len(silver),
            "colonnes": silver.shape[1],
            "effet": (
                f"{len(bronze) - len(silver)} doublons retirés, "
                f"{silver.shape[1] - bronze.shape[1]} colonnes issues du catalogue"
            ),
        }
    )

    avant_enrichissement = silver.shape[1]
    if enrichir:
        silver = ajouter_ratios_usage(silver)
        etapes.append(
            {
                "niveau": "silver+",
                "opération": "Variables dérivées (ratios d'usage)",
                "lignes": len(silver),
                "colonnes": silver.shape[1],
                "effet": f"{silver.shape[1] - avant_enrichissement} ratios ajoutés",
            }
        )

    gold = construire_gold(silver)
    retirees = sorted(set(silver.columns) - set(gold.columns))
    etapes.append(
        {
            "niveau": "gold",
            "opération": "Retrait des colonnes interdites",
            "lignes": len(gold),
            "colonnes": gold.shape[1],
            "effet": f"{len(retirees)} colonnes retirées : {', '.join(retirees)}",
        }
    )

    X, y = separer_cible(gold, cible=cible)
    etapes.append(
        {
            "niveau": "X / y",
            "opération": "Séparation de la cible",
            "lignes": len(X),
            "colonnes": X.shape[1],
            "effet": f"Cible `{cible}` isolée, taux : {y.astype(float).mean():.1%}",
        }
    )

    return ResultatPipeline(
        bronze=bronze, silver=silver, gold=gold, X=X, y=y, journal=_journal(etapes)
    )


def table_transformations(resultat: ResultatPipeline) -> pd.DataFrame:
    """Column-level view: where each column comes from, and where it stops."""
    lignes = []
    for colonne in resultat.silver.columns:
        origine = "source" if colonne in resultat.bronze.columns else "construite"
        if colonne in MOTIFS_EXCLUSION:
            devenir = "retirée au gold"
            motif = MOTIFS_EXCLUSION[colonne]
        elif colonne in resultat.X.columns:
            devenir = "variable explicative"
            motif = "—"
        elif colonne == CIBLE:
            devenir = "cible"
            motif = "—"
        else:
            devenir = "absente du gold"
            motif = "—"
        lignes.append({"colonne": colonne, "origine": origine, "devenir": devenir, "motif": motif})
    return pd.DataFrame(lignes)
