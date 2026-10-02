"""The reference results tool: what it compares, and with which tolerance.

`tools/resultats_reference.py` records the baselines' results that phase 7 must beat, and
checks the code still reproduces them. Its comparison must catch a moved fold value and a
metric that stopped applying, while ignoring floating-point noise.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.phase6


def _outil():
    specification = importlib.util.spec_from_file_location(
        "resultats_reference", RACINE / "tools" / "resultats_reference.py"
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _resultats(valeur: float | None) -> dict:
    return {
        "protocole": {"graine": 42},
        "donnees": {"empreinte_gold": "abc"},
        "baselines": {"m": {"par_pli": {"PR-AUC": [0.5, valeur]}, "moyenne": {}}},
    }


def test_un_ecart_sur_un_pli_est_detecte():
    outil = _outil()
    assert outil.ecarts(_resultats(0.6), _resultats(0.61))


def test_le_bruit_numerique_est_ignore():
    outil = _outil()
    assert not outil.ecarts(_resultats(0.6), _resultats(0.6 + 1e-9))


def test_une_metrique_qui_cesse_de_s_appliquer_est_detectee():
    outil = _outil()
    assert outil.ecarts(_resultats(0.6), _resultats(None))


def test_un_changement_de_donnees_est_detecte():
    outil = _outil()
    autre = _resultats(0.6)
    autre["donnees"]["empreinte_gold"] = "def"
    assert outil.ecarts(_resultats(0.6), autre)


def test_une_valeur_manquante_s_ecrit_null():
    outil = _outil()
    assert outil._nombre(float("nan")) is None and outil._nombre(0.25) == 0.25
