"""Monthly batch orchestration with Prefect.

The flow materialises the chain described in notebook section 10:

    ingestion -> preparation -> scoring -> prioritisation -> persistence -> publication

Each step is a separate task: on failure the log says **which** one gave way, and a rerun
does not replay what already succeeded. A monolithic script offers neither.

The data quality gate runs before scoring and **blocks** on failure: scoring
out-of-domain data yields plausible but wrong probabilities - the worst case, since
nothing signals it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

try:  # pragma: no cover - depends on the `orchestration` group being installed
    from prefect import flow, task
except ImportError:  # pragma: no cover
    # No-op decorators so the module stays importable without Prefect: the notebook must
    # run with base dependencies only.
    def task(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorateur(fonction):
            return fonction

        return decorateur(args[0]) if args and callable(args[0]) else decorateur

    def flow(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorateur(fonction):
            return fonction

        return decorateur(args[0]) if args and callable(args[0]) else decorateur


from ..config import CAPACITE_MENSUELLE
from ..donnees import charger_bronze
from ..features import controler_schema
from ..packaging import charger_modele
from .scoring import scorer_lot_mensuel


@task(name="ingestion", retries=2, retry_delay_seconds=30)
def etape_ingestion(chemin: str) -> pd.DataFrame:
    """Read this month's data.

    Retries because a networked source can be momentarily unavailable without the whole
    batch needing a restart.
    """
    return charger_bronze(chemin)


@task(name="controle_qualite")
def etape_controle(brut: pd.DataFrame, colonnes_attendues: list[str]) -> pd.DataFrame:
    """Blocking schema and completeness gate."""
    rapport = controler_schema(brut, colonnes_attendues)
    non_conformes = rapport.loc[~rapport["conforme"], "colonne"].tolist()
    if non_conformes:
        raise ValueError(
            f"Contrôle qualité en échec sur {non_conformes}. Lot interrompu : scorer des "
            "données hors domaine produirait des probabilités plausibles mais fausses."
        )
    return rapport


@task(name="scoring")
def etape_scoring(
    chemin_modele: str, brut: pd.DataFrame, capacite: int
) -> tuple[pd.DataFrame, str]:
    """Score and prioritise by expected value."""
    modele, fiche = charger_modele(chemin_modele)
    table = scorer_lot_mensuel(modele, brut, capacite=capacite)
    return table, fiche.get("version", "inconnue")


@task(name="ecriture")
def etape_ecriture(table: pd.DataFrame, version_modele: str, url_base: str | None) -> int:
    """Persist to the warehouse. Skipped when no URL is provided (local run)."""
    if not url_base:
        return 0
    from .entrepot import construire_moteur, creer_schema, ecrire_scores

    moteur = construire_moteur(url_base)
    creer_schema(moteur)
    return ecrire_scores(moteur, table, version_modele)


@task(name="publication_metriques")
def etape_publication(table: pd.DataFrame) -> None:
    """Publish indicators to Prometheus, when the exporter is available."""
    from ..monitoring import publier_lot

    publier_lot(table)


@flow(name="lot-mensuel-churn")
def lot_mensuel(
    chemin_donnees: str,
    chemin_modele: str,
    colonnes_attendues: list[str],
    url_base: str | None = None,
    capacite: int = CAPACITE_MENSUELLE,
) -> pd.DataFrame:
    """Full monthly batch flow. Returns the prioritised shortlist."""
    brut = etape_ingestion(chemin_donnees)
    etape_controle(brut, colonnes_attendues)
    table, version = etape_scoring(chemin_modele, brut, capacite)
    etape_ecriture(table, version, url_base)
    etape_publication(table)
    return table
