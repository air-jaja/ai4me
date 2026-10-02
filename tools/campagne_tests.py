"""Run the tests an activity needs: its own, then those proving it broke nothing.

    uv run python tools/campagne_tests.py                     # activity: both levels below
    uv run python tools/campagne_tests.py --niveau courants   # the activity's own tests
    uv run python tools/campagne_tests.py --niveau non-regression   # integration tests
    uv run python tools/campagne_tests.py --niveau tout       # the whole suite
    uv run python tools/campagne_tests.py --lister            # show, do not run

The campaigns are declared in `tests/campagnes.toml`. The first level selects the tests
carrying the activity's marker; the second runs the integration files listed for it. The
whole suite stays one option away, and the CI always runs it: a campaign speeds up the work
on an activity, it never replaces the full check.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CONFIGURATION = RACINE / "tests" / "campagnes.toml"
NIVEAUX = ("activite", "courants", "non-regression", "tout")


def charger_configuration(chemin: Path = CONFIGURATION) -> dict:
    with open(chemin, "rb") as flux:
        return tomllib.load(flux)


def commandes(niveau: str, campagne: dict) -> list[tuple[str, list[str]]]:
    """The pytest invocations a level stands for, each with a readable label."""
    courants = [("Tests courants", ["-m", campagne["marqueur"]])]
    non_regression = [("Non-régression", list(campagne["non_regression"]))]
    precedents = campagne.get("marqueurs_precedents", [])
    if precedents:
        # The unit tests of earlier activities stay in the safety net.
        non_regression.append(
            ("Non-régression (activités précédentes)", ["-m", " or ".join(precedents)])
        )
    return {
        "courants": courants,
        "non-regression": non_regression,
        "activite": courants + non_regression,
        "tout": [("Suite complète", [])],
    }[niveau]


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    configuration = charger_configuration()
    analyseur = argparse.ArgumentParser(description="Lance une campagne de tests.")
    analyseur.add_argument("--niveau", choices=NIVEAUX, default="activite")
    analyseur.add_argument("--campagne", default=configuration["activite"])
    analyseur.add_argument("--lister", action="store_true", help="afficher sans lancer")
    arguments, supplementaires = analyseur.parse_known_args(argv)

    campagne = configuration["campagnes"][arguments.campagne]
    print(f"Campagne : {campagne['titre']} — niveau « {arguments.niveau} »")
    codes = []
    for libelle, selection in commandes(arguments.niveau, campagne):
        commande = [sys.executable, "-m", "pytest", "-q", *selection, *supplementaires]
        print(f"\n=== {libelle} : pytest -q {' '.join(selection)}")
        if arguments.lister:
            continue
        codes.append(subprocess.run(commande, cwd=RACINE).returncode)
    if arguments.lister:
        return 0
    bilan = "réussie" if not any(codes) else "en échec"
    print(
        f"\nCampagne {bilan} : "
        + ", ".join(
            f"{libelle} {'OK' if code == 0 else 'KO'}"
            for (libelle, _), code in zip(commandes(arguments.niveau, campagne), codes, strict=True)
        )
    )
    return max(codes, default=0)


if __name__ == "__main__":
    raise SystemExit(main())
