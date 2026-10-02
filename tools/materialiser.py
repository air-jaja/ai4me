"""Re-materialise the derived datasets and the split, without running a notebook.

Until phase 5 the manifest was refreshed by re-executing the phase 3 notebook: an
exploratory document carried a production step, and the step failed whenever Jupyter did
(the `orjson` episode of 02/10). Materialising is a pipeline operation; it now has its own
command, and the notebook keeps calling the same function.

    uv run python tools/materialiser.py          # or: make materialiser

It runs the shared chain, writes silver and gold under `data/processed/`, records their
fingerprints and the training / test split in `data/manifeste_v1.0.json`, then re-reads the
manifest and checks that it matches what the code produces. Commit the manifest afterwards.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Re-matérialise les jeux dérivés.")
    analyseur.add_argument("--manifeste", help="chemin du manifeste (défaut : celui du dépôt)")
    analyseur.add_argument("--dossier", help="dossier des instantanés (défaut : data/processed)")
    arguments = analyseur.parse_args(argv)

    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.config import FICHIER_CATALOGUE, FICHIER_COMPLET
    from churn_saas.features import (
        executer_pipeline,
        materialiser,
        verifier_decoupage,
        verifier_jeux_derives,
    )

    resultat = executer_pipeline(FICHIER_COMPLET, FICHIER_CATALOGUE)
    manifeste = materialiser(
        resultat,
        version_donnees="v1.0",
        dossier=arguments.dossier,
        chemin_manifeste=arguments.manifeste,
    )
    jeux = verifier_jeux_derives(resultat, manifeste)
    decoupage = verifier_decoupage(resultat, manifeste)
    for nom, details in manifeste["jeux_derives"]["jeux"].items():
        print(f"{nom:7s} {details['colonnes']:>3} colonnes  {details['empreinte_contenu'][:12]}…")
    d = manifeste["decoupage"]
    print(
        f"découpage {d['comptes_entrainement']} / {d['comptes_test']} comptes, "
        f"comptes de test {d['empreinte_comptes_test'][:12]}…"
    )
    conforme = bool(jeux["conforme"].all() and decoupage["conforme"].all())
    print("Manifeste conforme au code." if conforme else "Manifeste NON conforme au code.")
    return 0 if conforme else 1


if __name__ == "__main__":
    raise SystemExit(main())
