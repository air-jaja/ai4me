"""The monthly operational list for the account managers, from the model in service.

    uv run python tools/liste_operationnelle.py                       # whole portfolio
    uv run python tools/liste_operationnelle.py --entree data/raw/churn_saas_echantillon.csv

Loads the champion by alias (its file's hash checked), prepares the accounts with the shared
chain, and writes `sorties/liste_operationnelle_<date>.csv` (UTF-8 with BOM, opens in Excel)
with business labels. Lists name real accounts: `sorties/` is never versioned.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def executer(entree: Path, sortie_dossier: Path = RACINE / "sorties"):
    sys.path.insert(0, str(RACINE / "src"))
    import pandas as pd

    from churn_saas import config
    from churn_saas.donnees import typer_pour_modele
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.industrialisation.liste import construire_liste
    from churn_saas.industrialisation.scoring import preparer
    from churn_saas.packaging import charger_champion, lire_aliases

    modele, _ = charger_champion()
    champion = lire_aliases()["champion"]
    brut = pd.read_csv(entree, dtype=str, encoding="utf-8-sig")
    catalogue = pd.read_csv(config.FICHIER_CATALOGUE, dtype=str, encoding="utf-8-sig")
    X = typer_pour_modele(
        preparer(brut, catalogue=catalogue).drop(columns=["churn"], errors="ignore")
    )
    valeur = pd.to_numeric(brut["valeur_vie_client_eur"], errors="coerce").set_axis(X.index)
    mrr = pd.to_numeric(
        brut["revenu_mensuel_recurrent_eur"].str.replace(",", "."), errors="coerce"
    ).set_axis(X.index)
    fond = parties_du_decoupage(
        executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    ).X_entrainement
    capacite = (
        round(config.CAPACITE_MENSUELLE * len(X) / 5000)
        if len(X) < 5000
        else config.CAPACITE_MENSUELLE
    )
    liste = construire_liste(
        modele,
        X,
        brut["client_id"].set_axis(X.index),
        valeur,
        mrr,
        fond,
        f"{champion['nom']} {champion['version']}",
        capacite,
    )
    sortie_dossier.mkdir(parents=True, exist_ok=True)
    sortie = sortie_dossier / f"liste_operationnelle_{time.strftime('%Y%m%d')}.csv"
    liste.to_csv(sortie, index=False, encoding="utf-8-sig", sep=";")
    return liste, sortie


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Liste opérationnelle du mois.")
    analyseur.add_argument(
        "--entree", default=str(RACINE / "data" / "raw" / "churn_saas_complet.csv")
    )
    arguments = analyseur.parse_args(argv)
    liste, sortie = executer(Path(arguments.entree))
    a_contacter = liste[liste["Action recommandée"] == "À contacter ce mois"]
    print(f"{len(liste)} comptes, {len(a_contacter)} à contacter ce mois")
    print(f"-> {sortie.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
