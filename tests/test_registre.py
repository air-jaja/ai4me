"""Rule 13 - nothing is left aside without a trace.

The register is generated from `docs/registre_ecarts.toml` and from the exclusions the code
declares. These tests protect what would otherwise rot quietly: an entry without a motive,
a postponement without a way back, a cited test that was renamed, a column dropped from
the model that nobody recorded, a readable document lagging behind its source.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "docs" / "registre_ecarts.toml"
DOCUMENT = RACINE / "docs" / "05.REGISTRE_elements_ecartes.md"
OUTIL = RACINE / "tools" / "registre_ecarts.py"

STATUTS = {"écarté", "différé", "à arbitrer"}
NATURES = {"méthode", "outil", "variable", "règle", "action", "architecture"}
OBLIGATOIRES = ("id", "titre", "nature", "statut", "phase", "competence", "section", "motif")
OBLIGATOIRES += ("source",)


@pytest.fixture(scope="module")
def elements() -> list[dict[str, str]]:
    with open(SOURCE, "rb") as flux:
        return tomllib.load(flux)["element"]


def test_chaque_entree_porte_les_champs_obligatoires(elements):
    """An entry without a motive or a source is an assertion, not a trace."""
    incompletes = [
        (e.get("id", "?"), [c for c in OBLIGATOIRES if not str(e.get(c, "")).strip()])
        for e in elements
    ]
    assert not [i for i in incompletes if i[1]], incompletes
    assert {e["statut"] for e in elements} <= STATUTS
    assert {e["nature"] for e in elements} <= NATURES
    assert all(re.fullmatch(r"C[1-9]", e["competence"]) for e in elements)


def test_les_identifiants_sont_uniques(elements):
    identifiants = [e["id"] for e in elements]
    assert len(identifiants) == len(set(identifiants))


def test_chaque_element_differe_a_une_condition_de_reexamen(elements):
    """A postponement without a criterion for coming back is an abandonment in disguise."""
    sans_condition = [
        e["id"]
        for e in elements
        if e["statut"] in {"différé", "à arbitrer"} and not e.get("condition", "").strip()
    ]
    assert not sans_condition, f"Sans condition de réexamen : {sans_condition}"


def test_les_preuves_citees_existent(elements):
    """A motive citing a renamed test, or a moved file, silently loses its evidence."""
    tests_existants = {
        nom
        for fichier in (RACINE / "tests").glob("test_*.py")
        for nom in re.findall(r"^def (test_\w+)", fichier.read_text(encoding="utf-8"), re.M)
    }
    manquantes = []
    for e in elements:
        for preuve in filter(None, (p.strip() for p in e.get("preuve", "").split("·"))):
            if preuve.startswith("test_"):
                if preuve not in tests_existants:
                    manquantes.append((e["id"], preuve))
            elif not (RACINE / preuve).exists():
                manquantes.append((e["id"], preuve))
    assert not manquantes, f"Preuves introuvables : {manquantes}"


def test_aucune_colonne_ne_disparait_sans_trace():
    """Every column of silver missing from the model carries a motive in the code.

    Generic: it names no column. Dropping a variable is a decision; this makes sure the
    decision is written down where the register reads it.
    """
    from churn_saas.donnees import MOTIFS_EXCLUSION
    from churn_saas.features import executer_pipeline

    donnees = RACINE / "data" / "raw"
    if (donnees / "churn_saas_complet.csv").stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    resultat = executer_pipeline(
        donnees / "churn_saas_complet.csv", donnees / "catalogue_plans.csv"
    )
    disparues = set(resultat.silver.columns) - set(resultat.X.columns) - {"churn"}
    sans_trace = sorted(disparues - set(MOTIFS_EXCLUSION))
    assert not sans_trace, f"Colonnes retirées du modèle sans motif : {sans_trace}"


def test_le_registre_reprend_chaque_exclusion_du_code():
    """The readable register lists every excluded column, read from the code."""
    from churn_saas.donnees import MOTIFS_EXCLUSION

    contenu = DOCUMENT.read_text(encoding="utf-8")
    absentes = [c for c in MOTIFS_EXCLUSION if f"`{c}`" not in contenu]
    assert not absentes, f"Exclusions absentes du registre : {absentes}"


def test_le_registre_genere_est_a_jour(tmp_path):
    """The document matches its source - otherwise it describes decisions no longer made."""
    sortie = tmp_path / "registre.md"
    subprocess.run([sys.executable, str(OUTIL), "--sortie", str(sortie)], check=True, cwd=RACINE)
    assert sortie.read_text(encoding="utf-8") == DOCUMENT.read_text(encoding="utf-8"), (
        "docs/05.REGISTRE_elements_ecartes.md est obsolète : lancer `make registre-doc`."
    )


def test_le_document_s_ouvre_par_l_avertissement_de_generation():
    """A reader must know not to edit it, or the next generation erases the edit."""
    assert "Document généré — ne pas éditer" in DOCUMENT.read_text(encoding="utf-8")
