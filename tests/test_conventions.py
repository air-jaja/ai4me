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


@pytest.mark.parametrize(
    "carnet",
    sorted((RACINE / "notebooks").glob("*.ipynb")),
    ids=lambda p: p.name,
)
def test_les_carnets_respectent_le_format_notebook(carnet: Path):
    """Every notebook validates against the nbformat schema.

    A markdown cell carrying an `outputs` field is accepted by Jupyter and rejected by
    stricter readers - the linter caught one that had survived several executions. A
    deliverable that some tools refuse to open is a risk not worth running the week of
    submission.
    """
    import nbformat

    nb = nbformat.read(carnet, as_version=4)
    nbformat.validate(nb)


def test_le_notebook_de_certification_reste_sans_sorties():
    """The certification notebook ships without outputs until the freeze.

    Committed outputs would make every run produce a diff, drowning the real changes. The
    notebook is executed at the freeze milestone, deliberately and once.
    """
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    avec_sorties = [i for i, c in enumerate(nb.cells) if c.cell_type == "code" and c.get("outputs")]
    assert not avec_sorties, (
        f"Cellules avec sorties : {avec_sorties}. "
        "Le notebook de certification est exécuté au moment du gel, pas avant."
    )


def test_les_dependances_des_tests_sont_declarees():
    """Every third-party module the tests import is declared in base or dev dependencies.

    A dependency inherited transitively from another group works locally, where the full
    environment is installed, and fails in CI, which installs only `dev`. That is exactly
    how `nbformat` slipped through: imported by the tests, provided by `nbconvert` in the
    `notebook` group, absent from the pipeline.

    Declaring it where the tests run turns a pipeline failure into a static check.
    """
    import sys
    import tomllib
    from importlib.metadata import packages_distributions

    manifeste = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    declarees = set(manifeste["project"]["dependencies"])
    declarees |= set(manifeste["dependency-groups"]["dev"])
    # Keep the distribution name, dropping the version specifier.
    declarees = {re.split(r"[<>=!\[ ]", d, maxsplit=1)[0].lower() for d in declarees}

    modules: set[str] = set()
    for fichier in (RACINE / "tests").glob("*.py"):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules |= {a.name.split(".")[0] for a in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                modules.add(noeud.module.split(".")[0])

    # Modules defined inside tests/ are local, not distributions: `conftest` is imported
    # by the tests that cover the reporting plugin.
    locaux = {f.stem for f in (RACINE / "tests").glob("*.py")}

    correspondance = packages_distributions()
    manquantes = []
    for module in sorted(modules):
        if module in sys.stdlib_module_names or module == "churn_saas" or module in locaux:
            continue
        distributions = {d.lower() for d in correspondance.get(module, [])}
        if not distributions & declarees:
            manquantes.append(f"{module} (distribution : {', '.join(distributions) or '?'})")

    assert not manquantes, (
        "Modules importés par les tests mais non déclarés dans `dependencies` ou dans le "
        "groupe `dev` :\n  " + "\n  ".join(manquantes) + "\n"
        "Les ajouter avec `uv add --group dev <paquet>` : la CI n'installe que `dev`."
    )


def test_le_catalogue_s_ecrit_en_utf8_quel_que_soit_le_terminal(tmp_path):
    """The catalogue writes itself in UTF-8 rather than relying on shell redirection.

    Redirecting the output tied the result to the terminal encoding: a Windows console
    opens `sys.stdout` in cp1252 and cannot represent the arrows the document contains,
    so `catalogue_tests.py > docs/TESTS.md` failed there while working on Linux.

    A tool whose success depends on the operating system of whoever runs it is a tool the
    CI cannot vouch for.
    """
    import subprocess
    import sys

    destination = tmp_path / "TESTS.md"
    resultat = subprocess.run(
        [sys.executable, "tools/catalogue_tests.py", "--sortie", str(destination)],
        cwd=RACINE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert resultat.returncode == 0, resultat.stderr

    contenu = destination.read_text(encoding="utf-8")
    assert "→" in contenu, "Le caractère qui déclenchait l'échec doit être présent"
    assert contenu.startswith("# Catalogue des tests")


OUTILS_ET_ARGUMENTS = {
    "catalogue_tests.py": ["--sortie", "{tmp}/TESTS.md"],
    "registre_ecarts.py": ["--sortie", "{tmp}/REGISTRE.md"],
    "ressources_calcul.py": ["--sortie", "{tmp}/SOBRIETE.md"],
    "materialiser.py": ["--manifeste", "{tmp}/manifeste.json", "--dossier", "{tmp}/processed"],
    "campagne_tests.py": ["--lister"],
    "resultats_reference.py": ["--sortie", "{tmp}/reference.json"],
    "pipeline_mlflow.py": ["--help"],
    "retracer_mlflow.py": ["--phase", "6"],
}


def test_chaque_outil_est_couvert_par_le_controle_d_encodage():
    """A new tool must join the check below; a forgotten one would escape it silently."""
    outils = {f.name for f in (RACINE / "tools").glob("*.py")}
    ecart = outils ^ set(OUTILS_ET_ARGUMENTS)
    assert not ecart, f"Outils non couverts par le contrôle d'encodage : {ecart}"


@pytest.mark.parametrize("outil", sorted(OUTILS_ET_ARGUMENTS))
def test_chaque_outil_ecrit_sa_sortie_en_utf8_quel_que_soit_le_terminal(outil, tmp_path):
    """Every tool prints UTF-8, even when the terminal announces cp1252.

    A Windows terminal hands a piped child process cp1252: "…" became byte 0x85, which a
    UTF-8 reader cannot decode. That is how the materialisation test failed on the
    development laptop while passing on Linux. The terminal is simulated here, so the CI
    reproduces what Windows does.
    """
    import os
    import shutil
    import subprocess
    import sys

    if outil == "materialiser.py":
        shutil.copy(RACINE / "data" / "manifeste_v1.0.json", tmp_path / "manifeste.json")
    arguments = [a.format(tmp=tmp_path) for a in OUTILS_ET_ARGUMENTS[outil]]
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "tools" / outil), *arguments],
        cwd=RACINE,
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        timeout=300,
    )
    assert resultat.returncode == 0, resultat.stderr.decode("utf-8", "replace")
    resultat.stdout.decode("utf-8")  # raises if the tool wrote the terminal's encoding


def test_les_fichiers_ecrits_par_le_code_se_terminent_par_un_saut_de_ligne(tmp_path):
    """Files our code writes and Git versions must end with a newline.

    Without it, `end-of-file-fixer` rewrites the file at every commit: the hook fails, the
    CI fails, and the diff shows a single character on a file whose content never changed.
    The noise then trains everyone to run `--no-verify`, which is how a guardrail dies.

    Covers the three writers: the data manifest, the model card written next to the
    serialised model, and the generated model card.
    """
    from sklearn.dummy import DummyClassifier

    from churn_saas.donnees import construire_manifeste, ecrire_manifeste
    from churn_saas.packaging import FicheModele, generer_model_card, sauvegarder_modele

    source = tmp_path / "donnees.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    chemin = ecrire_manifeste(
        construire_manifeste({"source": source}, version_donnees="v1", racine=tmp_path),
        tmp_path / "manifeste.json",
    )
    assert chemin.read_bytes().endswith(b"\n"), "manifeste sans saut de ligne final"

    modele = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    artefact = sauvegarder_modele(modele, FicheModele(nom="essai", version="1.0"), dossier=tmp_path)
    assert artefact.with_suffix(".json").read_bytes().endswith(b"\n"), (
        "fiche modèle sans saut de ligne final"
    )

    carte = tmp_path / "MODEL_CARD.md"
    generer_model_card({"model_id": "essai"}, destination=carte)
    assert carte.read_bytes().endswith(b"\n"), "model card sans saut de ligne final"
