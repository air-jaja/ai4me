"""Export the API contract (OpenAPI) to docs/openapi.json - versioned, checked up to date.

uv run python tools/exporter_openapi.py
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
    analyseur = argparse.ArgumentParser(description="Exporte le contrat OpenAPI de l'API.")
    analyseur.add_argument("--sortie", default=str(RACINE / "docs" / "openapi.json"))
    arguments = analyseur.parse_args(argv)
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.industrialisation.api import app

    texte = json.dumps(app.openapi(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    Path(arguments.sortie).write_text(texte, encoding="utf-8", newline="\n")
    print(f"Contrat OpenAPI : {arguments.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
