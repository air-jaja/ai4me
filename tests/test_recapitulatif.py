"""Reporting logic of the test suite itself (`tests/conftest.py`).

The summary is read to decide whether a run proves anything. A rate computed wrong would
be worse than no rate at all: it would give confidence without grounds.
"""

from __future__ import annotations

import pytest
from conftest import ISSUES, _style_fichier, _taux


def test_un_test_ignore_fait_chuter_le_taux_d_execution():
    """A skipped test lowers the execution rate without touching the success rate.

    This is the whole point of separating the two: a suite reported as "100% green" while
    half of it never ran proves nothing, and the success rate alone would say nothing
    about it.
    """
    total, executes, reussis, execution, reussite = _taux({"passed": 5, "skipped": 5})
    assert (total, executes, reussis) == (10, 5, 5)
    assert execution == 50.0
    assert reussite == 100.0


def test_un_echec_fait_chuter_le_taux_de_reussite_pas_celui_d_execution():
    _, _, _, execution, reussite = _taux({"passed": 3, "failed": 1})
    assert execution == 100.0
    assert reussite == 75.0


def test_une_erreur_de_fixture_compte_comme_un_echec():
    """A test that never started is not a neutral event: the guarantee is missing."""
    _, executes, _, execution, reussite = _taux({"passed": 2, "error": 2})
    assert executes == 4
    assert execution == 100.0
    assert reussite == 50.0


def test_un_echec_attendu_compte_comme_une_reussite():
    """An expected failure documents an observed behaviour: it is a verified guarantee."""
    _, _, reussis, _, reussite = _taux({"passed": 1, "xfailed": 1})
    assert reussis == 2
    assert reussite == 100.0


def test_les_taux_restent_definis_sur_une_suite_vide():
    """No division by zero on an empty selection: `pytest -k` may match nothing."""
    assert _taux({}) == (0, 0, 0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("issues", "couleur"),
    [
        ({"passed": 3}, "green"),
        ({"passed": 2, "failed": 1}, "red"),
        ({"passed": 2, "error": 1}, "red"),
        ({"skipped": 3}, "yellow"),
        ({"passed": 2, "skipped": 1}, "cyan"),
    ],
)
def test_un_fichier_prend_la_couleur_de_son_issue_la_plus_grave(issues, couleur):
    """One failure among twenty passes must colour the file red, not green."""
    assert _style_fichier(issues) == {couleur: True}


def test_chaque_issue_porte_un_symbole_distinct():
    """The symbol carries the meaning when colour is unavailable: CI logs, redirection."""
    symboles = [symbole for symbole, _, _ in ISSUES.values()]
    assert len(set(symboles)) == len(symboles)


@pytest.mark.parametrize(
    ("taux", "attendu"),
    [(100.0, "100%"), (0.0, "0%"), (99.5, "99.5%"), (99.96, "99.9%"), (50.0, "50.0%")],
)
def test_un_taux_arrondi_ne_pretend_jamais_atteindre_cent(taux, attendu):
    """99.5% must never be displayed as "100%".

    Announcing a flawless run while a test failed is the single most misleading thing a
    summary can do - and rounding does it silently.
    """
    from conftest import _format_taux

    assert _format_taux(taux) == attendu
