"""Empty the project's MLflow store, so it can be rebuilt from the sources of truth.

    uv run python tools/nettoyer_mlflow.py              # show what would be deleted
    uv run python tools/nettoyer_mlflow.py --confirmer  # delete it

MLflow is a journal, not an authority: everything it holds is rebuilt by
`tools/materialiser.py`, `tools/retracer_mlflow.py` and `tools/pipeline_mlflow.py`. The
command also removes the `notebooks/mlruns/` folders left by the scattered-artefacts defect
fixed in bloc 7.0 bis. A tracking server (MLFLOW_TRACKING_URI over http) is never touched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOSSIERS = [RACINE / "mlruns", RACINE / "notebooks" / "mlruns", RACINE / "mlartifacts"]


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Vide le magasin MLflow local du projet.")
    analyseur.add_argument("--confirmer", action="store_true", help="supprimer réellement")
    arguments = analyseur.parse_args(argv)
    presents = [d for d in DOSSIERS if d.exists()]
    if not presents:
        print("Rien à supprimer : le magasin MLflow local est déjà vide.")
        return 0
    for dossier in presents:
        taille = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file()) / 1e6
        action = "supprimé" if arguments.confirmer else "serait supprimé"
        print(f"{dossier.relative_to(RACINE)} ({taille:.0f} Mo) : {action}")
        if arguments.confirmer:
            shutil.rmtree(dossier)
    if not arguments.confirmer:
        print("Relancer avec --confirmer pour supprimer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
