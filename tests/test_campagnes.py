"""Test campaigns: each activity runs its own tests, then the integration tests.

`tests/campagnes.toml` declares, for each activity, the marker selecting the tests of the
modules it created or updated, and the files proving it broke nothing. These tests protect
the campaign itself from silent failures: a misspelt marker selecting nothing, a missing
file, a test running twice, a campaign that would pass by running no test at all.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
CONFIGURATION = RACINE / "tests" / "campagnes.toml"

# Updated in phase 6 (previous markers in the non-regression level): the marker moves.
pytestmark = pytest.mark.phase6


def _configuration() -> dict:
    with open(CONFIGURATION, "rb") as flux:
        return tomllib.load(flux)


def _marqueurs_declares() -> set[str]:
    with open(RACINE / "pyproject.toml", "rb") as flux:
        projet = tomllib.load(flux)
    return {m.split(":")[0].strip() for m in projet["tool"]["pytest"]["ini_options"]["markers"]}


def test_l_activite_courante_a_une_campagne():
    configuration = _configuration()
    assert configuration["activite"] in configuration["campagnes"]


def test_chaque_marqueur_de_campagne_est_declare():
    """With --strict-markers, an undeclared marker fails loudly instead of selecting nothing."""
    marqueurs = {c["marqueur"] for c in _configuration()["campagnes"].values()}
    assert marqueurs <= _marqueurs_declares()


def test_chaque_fichier_de_non_regression_existe():
    for campagne in _configuration()["campagnes"].values():
        absents = [f for f in campagne["non_regression"] if not (RACINE / f).exists()]
        assert not absents, f"Fichiers de non-régression introuvables : {absents}"


def test_aucun_test_ne_tourne_deux_fois_dans_une_campagne():
    """A file listed for non-regression carries no activity marker, or it would run twice."""
    for campagne in _configuration()["campagnes"].values():
        marque = f"mark.{campagne['marqueur']}"
        doublons = [
            f
            for f in campagne["non_regression"]
            if marque in (RACINE / f).read_text(encoding="utf-8")
        ]
        assert not doublons, f"Tests à la fois courants et de non-régression : {doublons}"


def test_les_tests_courants_selectionnent_des_tests():
    """A campaign whose current level selects nothing would pass without testing anything."""
    configuration = _configuration()
    marqueur = configuration["campagnes"][configuration["activite"]]["marqueur"]
    sortie = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-m",
            marqueur,
            "-p",
            "no:randomly",
        ],
        cwd=RACINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    selectionnes = [ligne for ligne in sortie.stdout.splitlines() if "::" in ligne]
    assert len(selectionnes) >= 5, sortie.stdout[-500:]


def test_un_test_ne_porte_qu_un_marqueur_d_activite():
    """Two activity markers on one test would run it in both the current and the earlier
    level of the same campaign."""
    import re

    marqueurs = {c["marqueur"] for c in _configuration()["campagnes"].values()}
    for fichier in (RACINE / "tests").glob("test_*.py"):
        texte = fichier.read_text(encoding="utf-8")
        for bloc in re.split(r"\n(?=def test_)", texte):
            portes = {m for m in marqueurs if f"mark.{m}\n" in bloc.split("def ", 1)[0] + "\n"}
            assert len(portes) <= 1, f"{fichier.name} : plusieurs marqueurs d'activité {portes}"


def test_les_marqueurs_precedents_sont_declares():
    declares = _marqueurs_declares()
    for campagne in _configuration()["campagnes"].values():
        assert set(campagne.get("marqueurs_precedents", [])) <= declares
