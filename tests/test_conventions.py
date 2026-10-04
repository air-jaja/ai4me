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
    "promouvoir.py": ["--help"],
    "liste_operationnelle.py": ["--help"],
    "livraison.py": ["--help"],
    "journal_modifications.py": ["--help"],
    "retours_terrain.py": ["--help"],
    "model_card.py": ["--help"],
    "exporter_openapi.py": ["--help"],
    "documenter_champs.py": ["--help"],
    "profil_reference.py": ["--help"],
    "suivi_simule.py": ["--help"],
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


def test_le_notebook_de_certification_n_a_plus_de_texte_provisoire():
    """Placeholders survived several phases unnoticed (summary, conclusion, 'not deployed
    yet'): a deliverable must not promise text it does not contain."""
    import re

    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    motif = re.compile(r"à rédiger|rédigés? en dernier|pas encore déployé|todo\b", re.I)
    provisoires = [
        i for i, c in enumerate(nb.cells) if c.cell_type == "markdown" and motif.search(c.source)
    ]
    assert not provisoires, f"Texte provisoire dans les cellules {provisoires}."


def test_l_annexe_b_couvre_les_47_criteres_de_la_grille():
    """Annex B lists every criterion of the evaluation grid, competency by competency."""
    import re

    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    annexes = next(c.source for c in nb.cells if "### Annexe B" in c.source)
    bloc = annexes[annexes.index("### Annexe B") : annexes.index("### Annexe C")]
    lignes = re.findall(r"^\| \*\*(C\d)\*\* \|", bloc, flags=re.M)
    grille = {"C1": 5, "C2": 6, "C3": 7, "C4": 10, "C5": 6, "C6": 3, "C7": 3, "C8": 4, "C9": 3}
    assert {c: lignes.count(c) for c in grille} == grille


def test_le_notebook_de_certification_ne_cite_plus_d_element_perime():
    """Sketches and conventions written before phase 10 survived next to the real service:
    a `/score-churn` pseudo-API, `staging`/`production` aliases, model and snapshot names
    nobody uses, an MLflow image the compose no longer builds (corrected 04/10/2026). A
    reader comparing the notebook with the repository would find two versions of the truth.
    The oral preparation document is the candidate's, not the jury's: the notebook does not
    cite it."""
    import re

    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    motif = re.compile(
        r"/score-churn|API_SKETCH|\*staging\*|churn_model_v|churn_train_AAAAMMJJ|mlflow:v3\.1\.1"
        r"|04\.SOUTENANCE"
    )
    perimes = [i for i, c in enumerate(nb.cells) if motif.search(c.source)]
    assert not perimes, f"Éléments périmés dans les cellules {perimes}."


def test_chaque_iteration_de_l_annexe_d_est_rattachee_a_une_boucle_du_cycle():
    """Section 2 listed five loops while Annex D logged fifteen iterations, and labelled the
    modelling-to-framing loop "weak signal" although the real trigger was a too-good score
    (AUC 0.999, a leak). Every logged iteration now appears in the section 2 loop table."""
    import re

    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    cycle = next((c.source for c in nb.cells if "**Les boucles de rétroaction.**" in c.source), "")
    assert cycle, "Le § 2 n'a pas de table des boucles de rétroaction."
    rattachees = {
        int(n)
        for ligne in cycle.split("\n")
        if (m := re.match(r"^\|[^|]+\|\s*([\d, ]+) —", ligne))
        for n in m.group(1).split(",")
    }
    annexes = next(c.source for c in nb.cells if "### Annexe D" in c.source)
    journal = annexes[annexes.index("### Annexe D") : annexes.index("### Annexe E")]
    iterations = {int(n) for n in re.findall(r"^\| (\d+) \|", journal, re.M)}
    assert iterations and rattachees == iterations, (
        f"Itérations non rattachées : {sorted(iterations - rattachees)} ; "
        f"inconnues de l'Annexe D : {sorted(rattachees - iterations)}"
    )
    assert "Annexe D" in cycle and "signal faible" in cycle


def test_le_notebook_n_affiche_pas_deux_fois_la_meme_information():
    """The cell audit of 04/10/2026 found tables repeating the figure next to them, the test
    metrics shown twice with two intervals, an exclusion table listing decisions taken two
    sections later, a probability rounded to "100 %", and a reading placed after the
    demonstration that followed what it commented. None of them may come back."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    for titre in (
        "Manquants des ratios construits",
        "Nombre de catégories par colonne",
        "Distribution des seuils rationnels par compte",
        "Grille de la régression logistique (25 plis)",
        "Jeu de test — 1 000 comptes",
        "Revenu récurrent mensuel (€) — ",
    ):
        assert titre not in code, f"Tableau redondant revenu : « {titre} »."
    assert "Colonnes exclues à la préparation (phase 4)" in code
    assert "risque {_risque[compte]:.0%}" not in code
    textes = [c.source for c in nb.cells]
    lecture = next(i for i, s in enumerate(textes) if s.startswith("**Lecture.** La séparation"))
    fuite = next(i for i, s in enumerate(textes) if s.startswith("**La fuite, démontrée.**"))
    assert lecture < fuite, "La lecture du découpage doit précéder la démonstration de la fuite."


def test_aucune_cellule_de_texte_ne_depasse_la_lecture_en_trente_secondes():
    """Outside the annexes, the longest text cells reached 11,000 characters before the
    04/10/2026 audit: a cell the candidate cannot justify in thirty seconds. They were
    condensed to at most about 7,000; this ceiling keeps them there."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    trop_longues = [
        (i, len(c.source))
        for i, c in enumerate(nb.cells)
        if c.cell_type == "markdown" and not c.source.startswith("## 15.") and len(c.source) > 7_500
    ]
    assert not trop_longues, f"Cellules de texte trop longues (indice, caractères) : {trop_longues}"


def _textes_livres() -> dict[str, str]:
    """Every delivered text: README, project file, documents, and the notebooks' cells.

    Left out: the generated test catalogue, which quotes the docstrings below, and the
    working documents, prefixed "99." (cell audit, verification report, presentation
    outline), which describe the obsolete facts they asked to correct."""
    import nbformat

    textes = {
        nom: (RACINE / nom).read_text(encoding="utf-8") for nom in ("README.md", "pyproject.toml")
    }
    for document in sorted((RACINE / "docs").glob("*.md")):
        if document.name != "TESTS.md" and not document.name.startswith("99."):
            textes[f"docs/{document.name}"] = document.read_text(encoding="utf-8")
    for carnet in sorted((RACINE / "notebooks").glob("*.ipynb")):
        nb = nbformat.read(carnet, as_version=4)
        textes[f"notebooks/{carnet.name}"] = "\n".join(c.source for c in nb.cells)
    return textes


def test_les_documents_livres_ne_citent_plus_d_element_perime():
    """The certification notebook was cleaned on 04/10/2026, but the same obsolete facts lived
    on elsewhere - an MLflow 3.1.1 image in two READMEs, file names nobody uses in the phase 2
    notebook, a staging alias in a comment, a ROC-AUC rounded by hand to 0,882 where the tool
    writes 0,881, a test set said to be read once although the phase 9 report read it again."""
    import re

    motif = re.compile(
        r"/score-churn|API_SKETCH|\bstaging\b|churn_model_v|churn_train_AAAAMMJJ|v3\.1\.1\b"
        r"|ROC-AUC 0,882|\b(lu|ouvert) une seule fois"
    )
    perimes = {
        nom: sorted({m.group(0) for m in motif.finditer(texte)})
        for nom, texte in _textes_livres().items()
        if motif.search(texte)
    }
    assert not perimes, f"Éléments périmés : {perimes}"


def test_l_intervalle_de_la_pr_auc_du_test_est_celui_de_l_evaluation_finale():
    """Two bootstrap draws on the same 1,000 test scores gave two intervals, [0,712 ; 0,806]
    at the final evaluation and [0,710 ; 0,807] in the phase 9 report, both quoted until
    04/10/2026. One test evaluation, one interval: every document quotes the final one."""
    import json
    import re

    def fr(intervalle):
        return "[{} ; {}]".format(*(f"{b:.3f}".replace(".", ",") for b in intervalle))

    resultats = RACINE / "resultats"
    finale = json.loads((resultats / "evaluation_finale.json").read_text(encoding="utf-8"))
    phase9 = json.loads((resultats / "validation_phase9.json").read_text(encoding="utf-8"))
    calcules = {fr(finale["intervalles_95"]["PR-AUC"])}
    assert fr(phase9["metriques"]["PR-AUC"]["intervalle_95"]) not in calcules
    motif = re.compile(r"0,761\*{0,2} (\[0,7\d\d ; 0,8\d\d\])")
    cites = {
        (nom, m.group(1)) for nom, texte in _textes_livres().items() for m in motif.finditer(texte)
    }
    inconnus = sorted(c for c in cites if c[1] not in calcules)
    assert cites and not inconnus, f"Intervalles saisis à la main : {inconnus}"


def test_le_paragraphe_10_decrit_la_chaine_ci_telle_qu_elle_tourne():
    """Until 04/10/2026 section 10 described a textbook chain - unit tests at each commit -
    while the repository runs fast checks at commit, the test campaign at push and both CI
    jobs on GitHub. The section now shows the real levels, with a capture of each."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    titres = [c.source.split("\n", 1)[0] for c in nb.cells]
    debut = next(i for i, t in enumerate(titres) if t.startswith("## 10."))
    fin = next(i for i, t in enumerate(titres) if t.startswith("## 11."))
    section = nb.cells[debut:fin]
    texte = "".join(c.source for c in section)
    assert "Tests unitaires des fonctions de nettoyage" not in texte
    assert all(niveau in texte for niveau in ("pre-commit", "pre-push", "`qualite`", "`complet`"))
    jointes = {nom for c in section for nom in c.get("attachments", {})}
    assert {"ci_precommit.png", "ci_actions.png"} <= jointes
    assert "attachment:ci_precommit.png" in texte and "attachment:ci_actions.png" in texte
    assert "docs/MODEL_CARD.md" in texte, "Le § 10 ne renvoie pas à la model card."


def test_le_paragraphe_11_montre_l_architecture_et_la_plateforme_verifiee():
    """Section 11 carries the architecture diagram (C7) - its cell was an empty comment until
    04/10/2026 - and the captures that prove the platform ran, attached to the notebook so
    that it stays readable on its own."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    titres = [c.source.split("\n", 1)[0] for c in nb.cells]
    debut = next(i for i, t in enumerate(titres) if t.startswith("## 11."))
    fin = next(i for i, t in enumerate(titres) if t.startswith("## 12."))
    section = nb.cells[debut:fin]
    assert any("```mermaid" in c.source for c in section if c.cell_type == "markdown")
    assert any("FancyBboxPatch" in c.source for c in section if c.cell_type == "code")
    jointes = {nom for c in section for nom in c.get("attachments", {})}
    attendues = {
        "v2_ready.png",
        "v2_score.png",
        "v4_prometheus.png",
        "v5_grafana.png",
        "v3_mlflow_pile.png",
        "v3_mlflow_local.png",
    }
    assert attendues <= jointes, f"Captures absentes : {sorted(attendues - jointes)}"
    citees = "".join(c.source for c in section)
    assert all(f"attachment:{nom}" in citees for nom in attendues)


def _section_certification(debut: str, fin: str) -> list:
    """Cells of the certification notebook from the heading `debut` to the heading `fin`."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    titres = [c.source.split("\n", 1)[0] for c in nb.cells]
    i = next(k for k, t in enumerate(titres) if t.startswith(debut))
    j = next(k for k, t in enumerate(titres) if t.startswith(fin))
    return nb.cells[i:j]


def test_la_latence_citee_au_9g_est_celle_du_modele_servi():
    """Section 9.G quoted 57 ms for one account, a figure from an earlier run, beside a table
    showing 58.5 ms (04/10/2026). The text quotes the served model's results, so that a new
    measurement makes this test fail until the text follows."""
    import json

    servi = json.loads((RACINE / "resultats" / "modele_servi.json").read_text(encoding="utf-8"))
    champion, servi_seul = (
        next(v for k, v in servi["mesures"].items() if k.startswith(prefixe))
        for prefixe in ("champion", "modèle servi")
    )
    lecture = next(
        c.source
        for c in _section_certification("## 9.", "## 10.")
        if c.source.startswith("**Lecture.** Appliquée à la lettre, P4")
    )
    assert f"{champion['un compte (ms)']:.1f} ms".replace(".", ",") in lecture
    assert f"({servi_seul['un compte (ms)']:.0f} ms)" in lecture


def _aretes_mermaid(source: str) -> set[tuple[str, str, bool]]:
    """(origin, target, directed) for each link of a Mermaid flowchart, node labels removed."""
    aretes = set()
    for ligne in source.split("\n"):
        ligne = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", ligne)
        if "--" not in ligne and "-." not in ligne:
            continue
        noeuds = re.findall(r"\b\w+\b", ligne.replace("si CHURN_DB_URL", ""))
        dirigee = "->" in ligne
        aretes.add((noeuds[0], noeuds[-1], dirigee))
    return aretes


def test_le_schema_du_11_ne_dessine_que_les_liaisons_que_le_code_realise():
    """Until 04/10/2026 the section 11 diagram drew the monthly batch feeding Prometheus and
    MLflow handing the model over. The flow updates its gauges without starting the exporter,
    and the model in service is named by the alias file, MLflow being a mirror: a link the
    code does not make is not drawn, neither in the Mermaid source nor in the figure."""
    paquet = RACINE / "src" / "churn_saas"
    flux = (paquet / "industrialisation" / "flux.py").read_text(encoding="utf-8")
    # The exporter's starters: the functions of exporteur.py that open the HTTP endpoint.
    exporteur = ast.parse((paquet / "monitoring" / "exporteur.py").read_text(encoding="utf-8"))
    demarreurs = {
        f.name
        for f in ast.walk(exporteur)
        if isinstance(f, ast.FunctionDef)
        and any(
            getattr(n.func, "id", "") == "start_http_server"
            for n in ast.walk(f)
            if isinstance(n, ast.Call)
        )
    }
    assert demarreurs
    section = _section_certification("## 11.", "## 12.")
    mermaid = next(c.source for c in section if "```mermaid" in c.source)
    figure = next(c.source for c in section if "FancyBboxPatch" in c.source)
    aretes = _aretes_mermaid(mermaid[mermaid.index("flowchart") :].split("```")[0])
    assert ("R", "M", True) not in aretes, "MLflow ne fournit pas le modèle : l'alias le désigne."
    assert not re.search(r'\("mlflow", "\w", "modele"', figure)
    if not any(nom in flux for nom in demarreurs):
        assert ("L", "P", True) not in aretes, "Le flux ne démarre pas l'exporteur."
        assert not re.search(r'\("lot", "\w", "prometheus"', figure)


def test_la_carence_de_la_liste_est_decrite_telle_que_l_outil_l_applique():
    """`tools/liste_operationnelle.py` accepts `--historique` but does not hand it to
    `construire_liste`: the two-month cooling-off period is coded, not applied. Until
    04/10/2026 the notebook said it was. While the tool ignores the history, section 10 says so."""
    arbre = ast.parse((RACINE / "tools" / "liste_operationnelle.py").read_text(encoding="utf-8"))
    appel = next(
        n
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "construire_liste"
    )
    transmis = "historique" in {k.arg for k in appel.keywords} or len(appel.args) >= 10
    texte = "".join(c.source for c in _section_certification("## 10.", "## 11."))
    if not transmis:
        assert "`--historique`" in texte and "non branchée" in texte


def test_la_promotion_n_est_pas_decrite_comme_conditionnee_par_l_outil():
    """`tools/promouvoir.py` moves the alias without comparing any score. Until 04/10/2026 the
    notebook announced a promotion blocked by an automated comparison: while the promotion
    code reads no PR-AUC, no delivered text claims it."""
    code = "".join(
        (RACINE / chemin).read_text(encoding="utf-8")
        for chemin in ("tools/promouvoir.py", "src/churn_saas/packaging/versions.py")
    )
    if "pr_auc" in code.lower() or "PR-AUC" in code:
        return
    motif = re.compile(r"comparaison automatisée|pas de promotion si dégradation", re.I)
    affirmations = sorted(nom for nom, texte in _textes_livres().items() if motif.search(texte))
    assert not affirmations, f"Promotion présentée comme bloquée par l'outil : {affirmations}"


def test_les_doublons_de_cle_annonces_stricts_le_sont():
    """Section 6.1 shows 35 strict duplicates and 35 key duplicates, the second row warning that
    no automatic deduplication is possible; the text reads them as the same 35 rows. That holds
    only if no key is left duplicated once the strict copies are dropped."""
    from churn_saas.config import FICHIER_COMPLET
    from churn_saas.donnees import charger_bronze, profil_doublons

    bronze = charger_bronze(FICHIER_COMPLET)
    assert profil_doublons(bronze, cle="client_id")["nombre"].nunique() == 1
    assert not bronze.drop_duplicates()["client_id"].duplicated().any()


def test_la_taille_des_sources_citee_est_celle_du_manifeste():
    """The three source files weigh 0.7 MB according to the manifest; "2 Mo" lived in the
    notebooks and five documents until 04/10/2026."""
    import json

    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    octets = sum(f["octets"] for f in manifeste["fichiers"].values())
    taille = f"{octets / 1e6:.1f} Mo".replace(".", ",")
    assert taille == "0,7 Mo"
    faux = sorted(nom for nom, texte in _textes_livres().items() if re.search(r"\b2 Mo\b", texte))
    assert not faux, f"Taille des sources fausse (manifeste : {taille}) : {faux}"


def test_la_soutenance_de_l_annexe_c_tient_en_trente_minutes():
    """Annex C planned a 30-minute defence whose durations added up to 32 (until 04/10/2026)."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    annexes = next(c.source for c in nb.cells if c.source.startswith("## 15."))
    annexe_c = annexes[annexes.index("### Annexe C") : annexes.index("### Annexe D")]
    assert "30 minutes" in annexe_c
    assert sum(int(m) for m in re.findall(r"^\| (\d+) min \|", annexe_c, re.M)) == 30


def test_l_annexe_e_rattache_chaque_dossier_a_ses_tests():
    """Annex E showed "—" (no tests) for `modelisation/` and `industrialisation/`, which have
    theirs, and an obsolete count of test files (until 04/10/2026)."""
    import nbformat

    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    annexes = next(c.source for c in nb.cells if c.source.startswith("## 15."))
    annexe_e = annexes[annexes.index("### Annexe E") :]
    lignes = re.findall(r"^\| \d · [^|]+\| `(\w+)/` \| ([^|]+) \|", annexe_e, re.M)
    assert len(lignes) == 7
    for dossier, tests in lignes:
        noms = re.findall(r"`(test_\w+\.py)`", tests)
        assert noms, f"Aucun fichier de tests cité pour {dossier}/."
        assert all((RACINE / "tests" / nom).exists() for nom in noms), noms
    nombre = len(list((RACINE / "tests").glob("test_*.py")))
    assert f"({nombre} au total)" in annexe_e


def test_chaque_element_du_registre_cite_par_le_notebook_existe():
    """On 04/10/2026 the notebook started citing D-11, the deferred deployment of the batch and
    its monitoring into the Docker stack: a register identifier quoted in the certification
    notebook must name an entry of `docs/registre_ecarts.toml`."""
    import tomllib

    import nbformat

    registre = tomllib.loads((RACINE / "docs" / "registre_ecarts.toml").read_text(encoding="utf-8"))
    connus = {e["id"] for e in registre["element"]}
    nb = nbformat.read(RACINE / "notebooks" / "cas_usage_churn_saas.ipynb", as_version=4)
    texte = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    cites = set(re.findall(r"\b[ED]-\d{2,3}\b", texte))
    assert {"D-06", "D-10", "D-11"} <= cites
    assert not cites - connus, f"Identifiants absents du registre : {sorted(cites - connus)}"
