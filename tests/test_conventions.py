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


def test_le_notebook_de_certification_est_execute_en_entier_sans_erreur():
    """The certification notebook is versioned WITH its outputs (rule 3, revised 03/10/2026).

    Outputs in the repository are only worth something if they are trustworthy: either the
    notebook carries none, or it carries ONE complete run, top to bottom - execution counts
    1, 2, ..., n with no gap or reordering (cells re-run by hand would show results the
    code in order does not produce) - with no error, and no path of the machine it ran on.
    """
    import json
    import re

    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    compteurs = [c.get("execution_count") for c in code]
    if all(n is None for n in compteurs) and not any(c.get("outputs") for c in code):
        return  # not executed at all: allowed, nothing to trust or distrust
    correction = (
        " Le réexécuter en entier : `make executer-notebook` (sans make : "
        "`uv run jupyter nbconvert --to notebook --execute --inplace "
        "notebooks/cas_usage_churn_saas.ipynb`)."
    )
    assert compteurs == list(range(1, len(code) + 1)), (
        "Le notebook n'a pas été exécuté en une seule fois, du début à la fin : compteurs "
        f"{compteurs[:12]}…" + correction
    )
    en_erreur = [i for i, c in enumerate(code) if any(o.output_type == "error" for o in c.outputs)]
    assert not en_erreur, f"Cellules de code en erreur : {en_erreur}." + correction
    chemin_local = re.compile(r"[A-Za-z]:\\\\Users|/home/[a-z]|/Users/[A-Za-z]")
    avec_chemin = [
        i for i, c in enumerate(code) if chemin_local.search(json.dumps(c.outputs, default=str))
    ]
    assert not avec_chemin, (
        f"Sorties contenant un chemin du poste (cellules {avec_chemin}) : le livrable ne doit "
        "dépendre d'aucune machine. Afficher des chemins relatifs à la racine du projet."
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


# Optimisation A1 (03/10/2026): the encoding of a tool's output does not depend on what it
# computes. `--help` prints its (accented) description through the same reconfigured
# streams in 0.04 s, where the real runs took up to 7 s each - about 19 s for the whole
# check. What `--help` does not exercise - the reconfiguration itself, and the error
# stream - is covered by the static test below and by the real refusal of a second test
# evaluation (test_les_erreurs_des_outils_s_ecrivent_aussi_en_utf8).
OUTILS_ET_ARGUMENTS = {
    "catalogue_tests.py": ["--help"],
    "registre_ecarts.py": ["--help"],
    "ressources_calcul.py": ["--help"],
    "materialiser.py": ["--help"],
    "campagne_tests.py": ["--lister"],
    "resultats_reference.py": ["--help"],
    "pipeline_mlflow.py": ["--help"],
    "retracer_mlflow.py": ["--help"],
    "nettoyer_mlflow.py": ["--help"],
    "selection_variables.py": ["--help"],
    "comparaison_explicabilite.py": ["--help"],
    "reglage_modele.py": ["--help"],
    "modele_servi.py": ["--help"],
    "regle_decision.py": ["--help"],
    "restitution_test.py": ["--help"],
    "validation_phase9.py": ["--help"],
    "selection_modele.py": ["--help"],
    "evaluation_finale.py": ["--help"],
    "modele_valeur_vie.py": ["--help"],
}


@pytest.mark.parametrize("outil", sorted(OUTILS_ET_ARGUMENTS))
def test_chaque_outil_reconfigure_ses_deux_sorties_avant_tout(outil):
    """Static half of the encoding check: `main()` forces stdout AND stderr to UTF-8 before
    parsing its arguments - so `--help` and a real run go through the same streams."""
    import ast

    arbre = ast.parse((RACINE / "tools" / outil).read_text(encoding="utf-8"))
    main = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    appels = [ast.unparse(n) for n in ast.walk(main) if isinstance(n, ast.Call)]
    for flux in ("stdout", "stderr"):
        assert any(f"sys.{flux}.reconfigure(encoding='utf-8')" in a for a in appels), (
            f"{outil} : main() ne force pas sys.{flux} en UTF-8."
        )
    lecture = [
        n
        for n in ast.walk(main)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func).endswith(("parse_args", "parse_known_args"))
    ]
    if lecture:
        debut_lecture = min(n.lineno for n in lecture)
        for flux in ("stdout", "stderr"):
            premiere = min(
                n.lineno
                for n in ast.walk(main)
                if isinstance(n, ast.Call) and ast.unparse(n.func) == f"sys.{flux}.reconfigure"
            )
            assert premiere < debut_lecture, (
                f"{outil} : sys.{flux} doit être reconfiguré avant la lecture des arguments."
            )


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
        # PYTHONUTF8=0: a Linux CI in the C locale turns UTF-8 mode on by itself and
        # would hide what a Windows terminal does.
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
        timeout=300,
    )
    assert resultat.returncode == 0, resultat.stderr.decode("utf-8", "replace")
    resultat.stdout.decode("utf-8")  # raises if the tool wrote the terminal's encoding
    resultat.stderr.decode("utf-8")  # errors and warnings too


def test_les_erreurs_des_outils_s_ecrivent_aussi_en_utf8(tmp_path):
    """stderr too: the refusal of a second test evaluation opens with an accented capital,
    which a Windows terminal turned into byte 0xC9 - unreadable for a UTF-8 reader. The
    first version of the encoding fix covered stdout only; this reproduces the refusal on a
    simulated cp1252 terminal."""
    import os
    import shutil
    import subprocess
    import sys

    source = RACINE / "resultats" / "evaluation_finale.json"
    if not source.exists():
        pytest.skip("Évaluation finale pas encore faite.")
    shutil.copy(source, tmp_path / "evaluation_finale.json")
    resultat = subprocess.run(
        [
            sys.executable,
            str(RACINE / "tools" / "evaluation_finale.py"),
            "--sortie",
            str(tmp_path / "evaluation_finale.json"),
        ],
        cwd=RACINE,
        capture_output=True,
        # PYTHONUTF8=0: a Linux CI in the C locale turns UTF-8 mode on by itself and
        # would hide what a Windows terminal does.
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
        timeout=120,
    )
    assert resultat.returncode != 0
    assert "ne sert qu'une fois" in resultat.stderr.decode("utf-8")


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
    artefact = sauvegarder_modele(
        modele,
        FicheModele(nom="essai", version="1.0"),
        dossier=tmp_path,
        entrainement=(__import__("pandas").DataFrame({"a": [0, 1]}), [0, 1]),
        registre=None,
    )
    assert artefact.with_suffix(".json").read_bytes().endswith(b"\n"), (
        "fiche modèle sans saut de ligne final"
    )

    carte = tmp_path / "MODEL_CARD.md"
    generer_model_card({"model_id": "essai"}, destination=carte)
    assert carte.read_bytes().endswith(b"\n"), "model card sans saut de ligne final"


def test_aucun_fichier_de_modele_n_est_versionne_hors_de_models():
    """Models live under models/ with their card, written by an absolute path; a model file
    elsewhere comes from a relative path (the legacy notebook wrote two into notebooks/).
    Tracked or not yet ignored, it must not reach the repository."""
    import subprocess

    suivis = subprocess.run(
        ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    hors_models = [
        f for f in suivis if f.endswith((".joblib", ".pkl")) and not f.startswith("models/")
    ]
    assert not hors_models, f"Fichiers de modèle suivis hors de models/ : {hors_models}"
    ignores = subprocess.run(
        ["git", "check-ignore", "notebooks/essai.joblib", "essai.pkl"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "notebooks/essai.joblib" in ignores, "Un .joblib hors de models/ ne serait pas ignoré."


def test_le_notebook_de_certification_lit_les_calculs_de_la_phase_5_sans_les_refaire():
    """B1: sections 8.A to 8.C read tools/selection_variables.py's recorded results. A
    notebook committed from an older working copy brought the computations back once
    (11 minutes here, 15 to 20 on the laptop) without any test noticing."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "_phase5.en_objets(_phase5.executer())" in code
    recalculs = [
        f
        for f in (
            "comparer_jeux(",
            "importances_par_permutation(",
            "ablation_par_groupe(",
            "tester_permutation(",
            "courbe_apprentissage(",
            "confirmer_retraits(",
        )
        if f in code
    ]
    assert not recalculs, f"Calculs de la phase 5 refaits dans le notebook : {recalculs}"


def test_la_session_de_tests_n_utilise_jamais_le_dossier_temporaire_partage(tmp_path):
    """Windows: the shared %TEMP%\\pytest-of-<user> tree made every campaign fail at the
    very end (PermissionError on `pytest-current`), all tests having passed. Every session now
    works in a unique directory of its own (tests/conftest.py), which pytest never scans."""
    assert "pytest-of-" not in str(tmp_path), tmp_path


def test_chaque_phase_close_a_son_carnet_de_travail():
    """Rule 4 (revised 02/10): each phase has its executed working notebook. Phases 7 (the
    modelling part) and 8 had none, and nothing noticed: the project tracker now says which
    phases are closed, and each of them must have a `notebooks/0N*_*.ipynb`."""
    import re

    suivi = (RACINE / "docs" / "suivi_projet_ia.md").read_text(encoding="utf-8")
    # Working notebooks were restored from phase 5 on (rule 4, 02/10/2026); phase 4 lives in
    # section 7 of the certification notebook only.
    closes = [
        int(n)
        for n in re.findall(r"^## (\d+) · [^\n]*🟢 terminé", suivi, flags=re.M)
        if int(n) >= 5
    ]
    assert closes, "Aucune phase close trouvée dans le suivi."
    sans_carnet = [n for n in closes if not list((RACINE / "notebooks").glob(f"{n:02d}*_*.ipynb"))]
    assert not sans_carnet, f"Phases closes sans carnet de travail : {sans_carnet}"
