"""Orchestration du lot mensuel avec Prefect.

Le flux matérialise la chaîne décrite au notebook § 10 :

    ingestion -> préparation -> scoring -> priorisation -> écriture -> publication

Chaque étape est une tâche distincte : en cas d'échec, le journal indique **laquelle** a
cédé, et la reprise ne rejoue pas ce qui avait abouti. Un script monolithique
n'offrirait ni l'un ni l'autre.

Le contrôle de qualité des données précède le scoring et **bloque** s'il échoue : scorer
sur des données hors domaine produit des probabilités plausibles mais fausses — le pire
des cas, car rien ne le signale.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

try:  # pragma: no cover - dépend de l'installation du groupe orchestration
    from prefect import flow, task
except ImportError:  # pragma: no cover

    def task(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorateur(fonction):
            return fonction

        return decorateur(args[0]) if args and callable(args[0]) else decorateur

    def flow(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorateur(fonction):
            return fonction

        return decorateur(args[0]) if args and callable(args[0]) else decorateur


from ..config import CAPACITE_MENSUELLE
from ..donnees.ingestion import charger_bronze
from ..features.controle import controler_schema
from ..industrialisation.scoring import scorer_lot_mensuel
from ..packaging.artefacts import charger_modele


@task(name="ingestion", retries=2, retry_delay_seconds=30)
def etape_ingestion(chemin: str) -> pd.DataFrame:
    """Lecture des données du mois. Réessaie : une source réseau peut être momentanément
    indisponible sans que le lot soit à reprendre entièrement."""
    return charger_bronze(chemin)


@task(name="controle_qualite")
def etape_controle(brut: pd.DataFrame, colonnes_attendues: list[str]) -> pd.DataFrame:
    """Contrôle bloquant du schéma et de la complétude."""
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
    """Scoring et priorisation par valeur espérée."""
    modele, fiche = charger_modele(chemin_modele)
    table = scorer_lot_mensuel(modele, brut, capacite=capacite)
    return table, fiche.get("version", "inconnue")


@task(name="ecriture")
def etape_ecriture(table: pd.DataFrame, version_modele: str, url_base: str | None) -> int:
    """Écriture en base. Sans URL fournie, l'étape est sautée (exécution locale)."""
    if not url_base:
        return 0
    from ..stockage.entrepot import construire_moteur, creer_schema, ecrire_scores

    moteur = construire_moteur(url_base)
    creer_schema(moteur)
    return ecrire_scores(moteur, table, version_modele)


@task(name="publication_metriques")
def etape_publication(table: pd.DataFrame) -> None:
    """Publication des indicateurs vers Prometheus, si l'exporteur est disponible."""
    from ..monitoring.exporteur import publier_lot

    publier_lot(table)


@flow(name="lot-mensuel-churn")
def lot_mensuel(
    chemin_donnees: str,
    chemin_modele: str,
    colonnes_attendues: list[str],
    url_base: str | None = None,
    capacite: int = CAPACITE_MENSUELLE,
) -> pd.DataFrame:
    """Flux complet du lot mensuel. Renvoie la liste priorisée."""
    brut = etape_ingestion(chemin_donnees)
    etape_controle(brut, colonnes_attendues)
    table, version = etape_scoring(chemin_modele, brut, capacite)
    etape_ecriture(table, version, url_base)
    etape_publication(table)
    return table
