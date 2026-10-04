"""Put a model into service, or roll back - in one command.

    uv run python tools/promouvoir.py --nom churn_saas_servi --version 1.1   # promote
    uv run python tools/promouvoir.py --retour-arriere                        # roll back
    uv run python tools/promouvoir.py --etat                                  # show aliases

Promotion takes the model from `resultats/registre_modeles.json` and makes it `champion`;
the former champion becomes `precedent`. Rollback swaps them after checking the previous
file is present and intact. Rules: `src/churn_saas/packaging/versions.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Promotion et retour arrière du modèle.")
    analyseur.add_argument("--nom")
    analyseur.add_argument("--version")
    analyseur.add_argument("--changement-de-contrat", action="store_true")
    analyseur.add_argument("--retour-arriere", action="store_true")
    analyseur.add_argument("--etat", action="store_true")
    arguments = analyseur.parse_args(argv)
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.packaging.versions import lire_aliases, promouvoir, retour_arriere

    if arguments.retour_arriere:
        aliases = retour_arriere()
    elif arguments.nom and arguments.version:
        registre = json.loads(
            (RACINE / "resultats" / "registre_modeles.json").read_text(encoding="utf-8")
        )
        candidats = [
            e for e in registre if e["nom"] == arguments.nom and e["version"] == arguments.version
        ]
        if not candidats:
            print(f"Absent du registre : {arguments.nom} {arguments.version}", file=sys.stderr)
            return 1
        aliases = promouvoir(candidats[-1], changement_de_contrat=arguments.changement_de_contrat)
    else:
        aliases = lire_aliases()
    for alias in ("champion", "precedent"):
        e = aliases.get(alias)
        print(
            f"{alias:10s} : {e['nom']} {e['version']} ({e['fichier']})" if e else f"{alias:10s} : —"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
