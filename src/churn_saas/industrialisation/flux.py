"""Monthly batch orchestration with Prefect.

The flow materialises the chain described in notebook section 10:

    ingestion -> data contract -> scoring -> prioritisation -> persistence -> publication
    -> monitoring (phase 11: drift, missing values, flagged volume against the reference profile)

Each step is a separate task: on failure the log says **which** one gave way, and a rerun
does not replay what already succeeded. A monolithic script offers neither.

The data quality gate runs before scoring and **blocks** on failure: scoring
out-of-domain data yields plausible but wrong probabilities - the worst case, since
nothing signals it. The monitoring step, on the contrary, **warns** and never blocks (M6).

Until 04/10/2026 the flow could not run: its gate was an ad hoc 30 % completeness check that
rejected the free-text comment column (55 % empty in the source itself), and scoring got
neither the accounts' value nor the plan catalogue. A test now runs the whole flow.
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


from ..config import CAPACITE_MENSUELLE, RACINE
from ..donnees import charger_bronze, exiger_contrat
from ..packaging import charger_modele
from .scoring import controler_lot, scorer_lot_mensuel

PROFIL_REFERENCE = RACINE / "resultats" / "profil_reference.json"


@task(name="ingestion", retries=2, retry_delay_seconds=30)
def etape_ingestion(chemin: str) -> pd.DataFrame:
    """Read this month's data.

    Retries because a networked source can be momentarily unavailable without the whole
    batch needing a restart.
    """
    return charger_bronze(chemin)


@task(name="controle_qualite")
def etape_controle(brut: pd.DataFrame, catalogue: pd.DataFrame | None) -> pd.DataFrame:
    """Blocking data contract - the very one the training data passed (donnees.qualite)."""
    contrat = controler_lot(brut, catalogue=catalogue)
    exiger_contrat(contrat)
    return contrat


@task(name="scoring")
def etape_scoring(
    chemin_modele: str, brut: pd.DataFrame, catalogue: pd.DataFrame | None, capacite: int
) -> tuple[pd.DataFrame, str]:
    """Score and prioritise by expected value, with the accounts' recorded value."""
    modele, fiche = charger_modele(chemin_modele)
    table = scorer_lot_mensuel(
        modele,
        brut,
        valeur_vie_client="valeur_vie_client_eur",
        catalogue=catalogue,
        capacite=capacite,
    )
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


@task(name="suivi")
def etape_suivi(
    brut: pd.DataFrame,
    table: pd.DataFrame,
    catalogue: pd.DataFrame | None,
    chemin_profil: str,
    signales_precedents: int | None,
) -> dict:
    """Phase 11 monthly verdicts against the reference profile (M5, M8, M9) and the alerts
    they raise, published to Prometheus. Warns, never blocks (M6)."""
    import json
    from pathlib import Path

    from ..donnees import typer_pour_modele
    from ..features import construire_silver_standard, preparer_gold
    from ..monitoring import (
        derive_combinee,
        ecart_volume,
        evaluer_alertes,
        manquants_relatifs,
        mesures_du_mois,
        publier_suivi,
    )

    profil = json.loads(Path(chemin_profil).read_text(encoding="utf-8"))
    silver = construire_silver_standard(brut, catalogue=catalogue)
    X = typer_pour_modele(preparer_gold(silver).gold.drop(columns=["churn"], errors="ignore"))
    _, derive = derive_combinee(profil, X, table["proba_churn"].reindex(X.index))
    _, manquants = manquants_relatifs(profil, silver)
    volume = ecart_volume(int(table["a_traiter"].sum()), signales_precedents)
    alertes = evaluer_alertes(mesures_du_mois(derive, manquants, volume))
    publier_suivi(derive, manquants, volume, alertes)
    return {
        "M5_derive": derive,
        "M8_manquants": manquants,
        "M9_volume": volume,
        "alertes": alertes.to_dict(orient="records"),
    }


@flow(name="lot-mensuel-churn")
def lot_mensuel(
    chemin_donnees: str,
    chemin_modele: str,
    chemin_catalogue: str | None = None,
    url_base: str | None = None,
    capacite: int = CAPACITE_MENSUELLE,
    chemin_profil: str = str(PROFIL_REFERENCE),
    signales_precedents: int | None = None,
) -> pd.DataFrame:
    """Full monthly batch flow. Returns the prioritised shortlist; the monitoring verdicts
    ride along in `table.attrs["suivi"]`."""
    brut = etape_ingestion(chemin_donnees)
    catalogue = (
        pd.read_csv(chemin_catalogue, dtype=str, encoding="utf-8-sig") if chemin_catalogue else None
    )
    etape_controle(brut, catalogue)
    table, version = etape_scoring(chemin_modele, brut, catalogue, capacite)
    etape_ecriture(table, version, url_base)
    etape_publication(table)
    table.attrs["suivi"] = etape_suivi(brut, table, catalogue, chemin_profil, signales_precedents)
    return table


def main(argv: list[str] | None = None) -> int:
    """`make lot-mensuel`: the flow on one batch, with the champion named by its alias."""
    import argparse
    import os
    import sys
    from pathlib import Path

    from ..config import FICHIER_CATALOGUE, FICHIER_COMPLET, MODELES
    from ..packaging import charger_champion, lire_aliases

    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Lot mensuel : contrôle, score, suivi.")
    analyseur.add_argument("--donnees", default=str(FICHIER_COMPLET), help="lot du mois (CSV)")
    analyseur.add_argument("--catalogue", default=str(FICHIER_CATALOGUE))
    analyseur.add_argument("--precedent", type=int, help="comptes signalés le mois précédent")
    arguments = analyseur.parse_args(argv)

    # Same resolution as the API: the alias names the file, its hash is checked first.
    aliases = Path(os.environ.get("CHURN_ALIASES", RACINE / "resultats" / "aliases_modeles.json"))
    dossier = Path(os.environ.get("CHURN_MODELES", MODELES))
    charger_champion(aliases, dossier)
    modele = dossier / lire_aliases(aliases)["champion"]["fichier"]

    table = lot_mensuel(
        arguments.donnees,
        str(modele),
        chemin_catalogue=arguments.catalogue,
        url_base=os.environ.get("CHURN_DB_URL"),
        signales_precedents=arguments.precedent,
    )
    alertes = [a["indicateur"] for a in table.attrs["suivi"]["alertes"] if a["declenchee"]]
    print(f"{len(table)} comptes scorés, {int(table['a_traiter'].sum())} à traiter ce mois")
    print("Alertes du suivi : " + (", ".join(alertes) if alertes else "aucune"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
