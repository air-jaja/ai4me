"""Working conventions enforced by the suite rather than left to discipline.

A convention nobody checks is a convention that decays. These tests turn two agreed rules
into facts: comments and docstrings stay in English, displayed content stays in French.

See `docs/00.REGLES_DE_TRAVAIL.md` for the rules and their rationale.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
DOSSIERS_CODE = ("src", "tests", "tools")

# Accented characters are a reliable, cheap proxy for French prose. English comments never
# need them; French ones almost always do.
ACCENTS = re.compile(r"[àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇœ]")

# Identifiers and data values stay in French (column names, business terms). Only the
# *prose* written for developers is checked, never the strings rendered to the reader.


def _fichiers_python() -> list[Path]:
    fichiers: list[Path] = []
    for dossier in DOSSIERS_CODE:
        fichiers += sorted((RACINE / dossier).rglob("*.py"))
    return fichiers


def _commentaires_accentues(fichier: Path) -> list[str]:
    """Comment lines carrying accented characters, i.e. very likely written in French."""
    lignes = fichier.read_text(encoding="utf-8").split("\n")
    return [
        f"ligne {i} : {ligne.strip()[:70]}"
        for i, ligne in enumerate(lignes, start=1)
        if ligne.strip().startswith("#") and ACCENTS.search(ligne)
    ]


def _docstrings_accentuees(fichier: Path) -> list[str]:
    """Docstrings carrying accented characters.

    Docstrings count as code documentation, not as displayed content: `afficher_source`
    renders them to the reader, but they describe the implementation.
    """
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    fautives = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            texte = ast.get_docstring(noeud)
            if texte and ACCENTS.search(texte):
                fautives.append(getattr(noeud, "name", fichier.name))
    return fautives


@pytest.mark.parametrize("fichier", _fichiers_python(), ids=lambda p: p.name)
def test_les_commentaires_sont_en_anglais(fichier: Path):
    """Comments stay in English across the whole source tree.

    Mixed-language comments make a file harder to scan than either language alone: the
    reader switches context line by line.
    """
    fautifs = _commentaires_accentues(fichier)
    assert not fautifs, (
        f"Commentaires vraisemblablement en français dans {fichier.relative_to(RACINE)} :\n  "
        + "\n  ".join(fautifs)
    )


@pytest.mark.parametrize("fichier", _fichiers_python(), ids=lambda p: p.name)
def test_les_docstrings_sont_en_anglais(fichier: Path):
    """Docstrings stay in English: they document the implementation, not the deliverable."""
    fautives = _docstrings_accentuees(fichier)
    assert not fautives, (
        f"Docstrings vraisemblablement en français dans {fichier.relative_to(RACINE)} : {fautives}"
    )


def test_le_contenu_affiche_reste_en_francais():
    """Displayed labels stay in French: the deliverable is read by a French-speaking jury.

    Checked on the governance and alerting tables, which are rendered as-is in the
    notebooks. An English column heading there would be a mistake, not a convention.
    """
    from churn_saas.donnees import table_cycle_de_vie, table_sensibilite
    from churn_saas.monitoring import table_regles

    for nom, table in (
        ("cycle de vie", table_cycle_de_vie()),
        ("sensibilité", table_sensibilite()),
        ("règles d'alerte", table_regles()),
    ):
        contenu = " ".join(table.astype(str).to_numpy().ravel().tolist())
        assert ACCENTS.search(contenu), (
            f"La table « {nom} » ne contient aucun caractère accentué : "
            "son contenu a-t-il été traduit par erreur ?"
        )
