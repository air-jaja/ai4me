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
    exiger_contrat,
    reconstruire_valeurs_deterministes,
    separer_cible,
    statut_global,
    verifier_contrat,
)
from .construction import ajouter_ratios_usage, combler_ratios_structurels

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


def construire_silver_standard(
    bronze: pd.DataFrame, catalogue: pd.DataFrame | None = None, **options: Any
) -> pd.DataFrame:
    """Silver built with the project's column lists - the one entry point for every caller.

    Until phase 4 the monthly batch called `construire_silver` without these lists: it
    would have scored on numbers left as text and unparsed dates, while training used
    converted ones. Same function, different preparation - the training-serving skew.
    """
    parametres: dict[str, Any] = {
        "colonnes_decimales": list(COLONNES_DECIMALES),
        "colonnes_dates": list(COLONNES_DATES),
        "colonnes_entieres": list(COLONNES_ENTIERES),
    }
    parametres.update(options)
    return construire_silver(bronze, catalogue=catalogue, **parametres)


@dataclass
class PreparationGold:
    """What `preparer_gold` produced: enriched silver, gold, and the reconstruction report."""

    silver_enrichi: pd.DataFrame
    gold: pd.DataFrame
    reconstructions: pd.DataFrame


def preparer_gold(silver: pd.DataFrame, enrichir: bool = True) -> PreparationGold:
    """Silver -> gold, identically for training and for the monthly batch.

    Order: usage ratios, structural zeros, deterministic reconstruction, exclusions. The
    statistical imputation is *not* here: it is learnt inside the model pipeline, on
    training folds only.

    Zeros and reconstruction apply to the gold path only. Silver stays faithful to the
    source - a reader sees a missing revenue as missing, the exploration still sees the
    NaN of abandoned accounts - and the data contract, run on silver, keeps measuring the
    real gaps of incoming data.
    """
    enrichi = ajouter_ratios_usage(silver) if enrichir else silver.copy()
    reconstruit, bilan = reconstruire_valeurs_deterministes(combler_ratios_structurels(enrichi))
    return PreparationGold(
        silver_enrichi=enrichi, gold=construire_gold(reconstruit), reconstructions=bilan
    )


@dataclass
class ResultatPipeline:
    """Datasets produced, and the report of what produced them."""

    bronze: pd.DataFrame
    silver: pd.DataFrame
    gold: pd.DataFrame
    X: pd.DataFrame
    y: pd.Series
    journal: pd.DataFrame = field(default_factory=pd.DataFrame)
    contrat: pd.DataFrame = field(default_factory=pd.DataFrame)
    reconstructions: pd.DataFrame = field(default_factory=pd.DataFrame)


def _journal(etapes: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(etapes)


def executer_pipeline(
    chemin_donnees: Path | str,
    chemin_catalogue: Path | str | None = None,
    enrichir: bool = True,
    cible: str = CIBLE,
    exiger: bool = True,
) -> ResultatPipeline:
    """Run the three levels and record what each one changed.

    `enrichir` adds the usage ratios. It is a parameter rather than a constant because
    the evaluation -> features loop compares the model with and without them: measuring
    the contribution of feature engineering requires being able to switch it off.

    The data contract runs right after silver, on the same terms as the monthly batch.
    With `exiger` (the default) a blocking check stops the chain; `exiger=False` lets a
    notebook display a failing contract instead of an exception.
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
    silver = construire_silver_standard(bronze, catalogue=catalogue)
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

    contrat = verifier_contrat(
        silver,
        brut=bronze,
        colonnes_numeriques=list(COLONNES_DECIMALES) + list(COLONNES_ENTIERES),
        colonnes_dates=list(COLONNES_DATES),
    )
    etapes.append(
        {
            "niveau": "contrat",
            "opération": "Contrat de données (mêmes contrôles qu'au lot mensuel)",
            "lignes": len(silver),
            "colonnes": silver.shape[1],
            "effet": (f"{len(contrat)} contrôles, statut global : {statut_global(contrat)}"),
        }
    )
    if exiger:
        exiger_contrat(contrat)

    avant_enrichissement = silver.shape[1]
    preparation = preparer_gold(silver, enrichir=enrichir)
    silver, gold = preparation.silver_enrichi, preparation.gold
    if enrichir:
        etapes.append(
            {
                "niveau": "silver+",
                "opération": "Variables dérivées (ratios d'usage)",
                "lignes": len(silver),
                "colonnes": silver.shape[1],
                "effet": f"{silver.shape[1] - avant_enrichissement} variables ajoutées",
            }
        )
    reconstruits = preparation.reconstructions
    etapes.append(
        {
            "niveau": "reconstruction",
            "opération": "Zéros structurels et valeurs recalculées ligne à ligne",
            "lignes": len(gold),
            "colonnes": silver.shape[1],
            "effet": ", ".join(
                f"{r['colonne']} : {r['reconstruits']}" for _, r in reconstruits.iterrows()
            ),
        }
    )

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
        bronze=bronze,
        silver=silver,
        gold=gold,
        X=X,
        y=y,
        journal=_journal(etapes),
        contrat=contrat,
        reconstructions=preparation.reconstructions,
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
