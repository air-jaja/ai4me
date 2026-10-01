"""Package structure invariants: the activity split is enforced, not merely intended.

The code is organised by lifecycle activity. That split only holds if something checks it:
a module filed in the wrong package, or an activity reaching into another's internals,
degrades silently until the organisation is a comment rather than a fact.

These checks caught a real defect once already - leftover flat modules from an earlier
layout (`evaluation.py`, `features.py`, `monitoring.py`) sitting next to the packages that
replaced them. Python resolved the package, so nothing failed; the repository simply
shipped dead code shadowing live code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RACINE_PAQUET = Path(__file__).resolve().parents[1] / "src" / "churn_saas"

# The seven activities of the lifecycle, in order. The number is part of the contract:
# it is what lets a reader map a package to a project phase without reading its code.
ACTIVITES: dict[str, str] = {
    "donnees": "Activity 1",
    "features": "Activity 2",
    "modelisation": "Activity 3",
    "evaluation": "Activity 4",
    "packaging": "Activity 5",
    "industrialisation": "Activity 6",
    "monitoring": "Activity 7",
}

# Modules that legitimately sit at package root because they serve every activity.
#   config    parameters read by all seven
#   notebook  display helpers used by every notebook
#   figures   figure storage, written by every phase and read by the documents
# Anything else belongs to the activity it serves, and the test below says so.
TRANSVERSES = {"__init__", "config", "notebook", "figures"}

# Permitted dependency edges between activities.
#
# The rule is directional: an activity may rely on those that precede it in the lifecycle.
# One edge goes forward on purpose - the monthly batch (6) publishes its indicators to
# monitoring (7). Publishing is not a dependency on monitoring's decisions: the exporter
# exposes, it never decides. That exception is declared here rather than tolerated.
DEPENDANCES_AUTORISEES: dict[str, set[str]] = {
    "donnees": set(),
    "features": {"donnees"},
    "modelisation": set(),
    "evaluation": set(),
    "packaging": set(),
    "industrialisation": {
        "donnees",
        "features",
        "modelisation",
        "evaluation",
        "packaging",
        "monitoring",
    },
    "monitoring": set(),
}


def _paquets_presents() -> set[str]:
    return {d.name for d in RACINE_PAQUET.iterdir() if d.is_dir() and (d / "__init__.py").exists()}


def _imports_relatifs(fichier: Path) -> list[tuple[int, str]]:
    """Relative imports of a module, as (level, dotted target)."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    return [
        (n.level, n.module)
        for n in ast.walk(arbre)
        if isinstance(n, ast.ImportFrom) and n.level and n.module
    ]


# --- The split exists -----------------------------------------------------------------
def test_les_sept_activites_existent():
    """Each lifecycle activity has its own package. No activity, no separation."""
    manquantes = sorted(set(ACTIVITES) - _paquets_presents())
    assert not manquantes, f"Activités absentes du code : {manquantes}"


def test_aucun_paquet_hors_des_sept_activites():
    """A package outside the agreed seven means an activity was invented along the way.

    `stockage` lived here for a while before being folded into activity 6: the score
    warehouse holds what the batch *produces*, not what it consumes.
    """
    intrus = sorted(_paquets_presents() - set(ACTIVITES))
    assert not intrus, (
        f"Paquets hors du découpage convenu : {intrus}. "
        "Rattacher à une activité ou justifier explicitement l'ajout."
    )


@pytest.mark.parametrize(("paquet", "numero"), sorted(ACTIVITES.items()))
def test_chaque_activite_annonce_son_numero(paquet: str, numero: str):
    """The package docstring states which lifecycle activity it implements."""
    doc = ast.get_docstring(ast.parse((RACINE_PAQUET / paquet / "__init__.py").read_text("utf-8")))
    assert doc, f"`{paquet}` n'a pas de docstring de module"
    assert doc.startswith(numero), (
        f"`{paquet}` devrait commencer par « {numero} » — actuellement : {doc.splitlines()[0]!r}"
    )


@pytest.mark.parametrize("paquet", sorted(ACTIVITES))
def test_chaque_activite_expose_une_interface(paquet: str):
    """`__all__` is the activity's contract: what the other activities may rely on."""
    source = (RACINE_PAQUET / paquet / "__init__.py").read_text(encoding="utf-8")
    assert "__all__" in source, f"`{paquet}` n'expose pas d'interface publique"


# --- Nothing leaks outside the split --------------------------------------------------
def test_aucun_module_ne_porte_le_nom_d_un_paquet():
    """A module and a package with the same name must never coexist.

    Python resolves the package and the code keeps running, so the duplicate is invisible
    until someone edits the wrong file.
    """
    modules = {f.stem for f in RACINE_PAQUET.glob("*.py")}
    collisions = sorted(_paquets_presents() & modules)
    assert not collisions, (
        f"Modules masquant un paquet homonyme : {collisions}. "
        "Supprimer le fichier .py hérité de l'ancienne structure."
    )


def test_seuls_les_modules_transverses_restent_a_la_racine():
    """Every module belongs to an activity, except those serving all of them."""
    inattendus = sorted({f.stem for f in RACINE_PAQUET.glob("*.py")} - TRANSVERSES)
    assert not inattendus, (
        f"Modules inattendus à la racine du paquet : {inattendus}. "
        "Chaque module doit appartenir à l'activité du cycle de vie qu'il sert."
    )


# --- Dependencies follow the lifecycle ------------------------------------------------
def test_les_dependances_respectent_l_ordre_du_cycle_de_vie():
    """An activity may only rely on those the declaration allows.

    Without this check the split survives on the filename alone: a backward dependency -
    data management calling the model, say - would make the two activities inseparable
    while the folders still suggest otherwise.
    """
    infractions = []
    for paquet in sorted(_paquets_presents()):
        autorisees = DEPENDANCES_AUTORISEES.get(paquet, set())
        for fichier in (RACINE_PAQUET / paquet).glob("*.py"):
            for niveau, module in _imports_relatifs(fichier):
                if niveau != 2:  # level 1 stays inside the activity, level 2 leaves it
                    continue
                cible = module.split(".")[0]
                if cible in ACTIVITES and cible not in autorisees:
                    infractions.append(f"{paquet}/{fichier.name} -> {cible}")
    assert not infractions, "Dépendances non autorisées entre activités :\n  " + "\n  ".join(
        infractions
    )


def test_les_activites_communiquent_par_leur_interface_publique():
    """Cross-activity imports target the package, never one of its submodules.

    Reaching into `..donnees.gold` rather than `..donnees` ties the caller to an internal
    layout it does not own: any reorganisation inside the activity then breaks code
    elsewhere. `__all__` exists precisely to prevent that.
    """
    profonds = []
    for paquet in sorted(_paquets_presents()):
        for fichier in (RACINE_PAQUET / paquet).glob("*.py"):
            for niveau, module in _imports_relatifs(fichier):
                parties = module.split(".")
                if niveau == 2 and parties[0] in ACTIVITES and len(parties) > 1:
                    profonds.append(f"{paquet}/{fichier.name} -> ..{module}")
    assert not profonds, (
        "Imports contournant l'interface publique d'une activité :\n  "
        + "\n  ".join(profonds)
        + "\nUtiliser `from ..<activite> import <nom>` et exporter le nom dans __all__."
    )


# Framework entry points are called by FastAPI and Prefect, never imported by our code.
# Exporting them would advertise an API nobody may call directly.
MODULES_POINTS_D_ENTREE = {"api.py", "flux.py"}


def _noms_publics(fichier: Path) -> list[str]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    return [
        n.name for n in arbre.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    ]


def _exportes(paquet: str) -> set[str]:
    arbre = ast.parse((RACINE_PAQUET / paquet / "__init__.py").read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(
            getattr(c, "id", "") == "__all__" for c in noeud.targets
        ):
            return {e.value for e in noeud.value.elts}
    return set()


@pytest.mark.parametrize("paquet", sorted(ACTIVITES))
def test_tout_nom_utilise_hors_de_son_module_est_exporte(paquet: str):
    """A function used outside its own module belongs to the activity's public surface.

    Otherwise callers reach into a submodule they do not own, and `__all__` stops
    describing what the activity actually offers. The rule already applies between
    activities; this extends it to the notebooks and the test suite, which are the other
    consumers of that surface.
    """
    import json
    import re

    racine = RACINE_PAQUET.parents[1]
    contextes: dict[str, str] = {}
    for fichier in list(RACINE_PAQUET.rglob("*.py")) + list((racine / "tests").glob("*.py")):
        contextes[str(fichier)] = fichier.read_text(encoding="utf-8")
    for carnet in (racine / "notebooks").glob("*.ipynb"):
        contenu = json.loads(carnet.read_text(encoding="utf-8"))
        contextes[str(carnet)] = "\n".join(
            "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
            for c in contenu["cells"]
            if c["cell_type"] == "code"
        )

    exportes = _exportes(paquet)
    manquants = []
    for fichier in (RACINE_PAQUET / paquet).glob("*.py"):
        if fichier.name == "__init__.py" or fichier.name in MODULES_POINTS_D_ENTREE:
            continue
        for nom in _noms_publics(fichier):
            if nom in exportes:
                continue
            motif = re.compile(rf"\b{re.escape(nom)}\b")
            if any(
                motif.search(contenu)
                for chemin, contenu in contextes.items()
                if Path(chemin) != fichier
            ):
                manquants.append(f"{nom} ({fichier.name})")

    assert not manquants, (
        f"Noms utilisés hors de leur module mais absents de `{paquet}.__all__` :\n  "
        + "\n  ".join(sorted(manquants))
    )


# --- The README tree describes the package as it is ------------------------------------
# The tree in README.md is hand-written: each line carries a description no generator could
# produce. It is therefore checked rather than generated, like the test catalogue is checked
# in CI: a module added without its line, or a line left behind by a removed module, fails
# the suite. Until this check existed, `features/graphiques.py` shipped without a line.
README = RACINE_PAQUET.parents[1] / "README.md"
SECTION_ARBORESCENCE = "## Structure du dépôt"
MARQUEURS = ("├── ", "└── ")


def lire_arborescence(texte: str) -> set[str]:
    """Paths listed in a `tree`-style block, rebuilt from the indentation.

    Each level is four characters wide ("│   " or "    "). An entry ending with "/" opens
    a directory for the deeper lines below it; an entry may span several path segments
    ("src/churn_saas/"). Whatever follows the name, after whitespace, is a description.
    """
    chemins: set[str] = set()
    pile: list[str] = []
    for ligne in texte.splitlines():
        position = next((ligne.find(m) for m in MARQUEURS if m in ligne), -1)
        if position < 0:
            continue
        profondeur = position // 4
        nom = ligne[position + len(MARQUEURS[0]) :].split()[0]
        del pile[profondeur:]
        chemins.add("".join(pile) + nom)
        if nom.endswith("/"):
            pile.append(nom)
    return chemins


def _arborescence_du_readme() -> set[str]:
    texte = README.read_text(encoding="utf-8")
    debut = texte.index(SECTION_ARBORESCENCE)
    bloc = texte[debut:].split("```")[1]
    return lire_arborescence(bloc)


def _modules_du_paquet() -> set[str]:
    racine = RACINE_PAQUET.parents[1]
    return {
        chemin.relative_to(racine).as_posix()
        for chemin in RACINE_PAQUET.rglob("*.py")
        if chemin.name != "__init__.py" and "__pycache__" not in chemin.parts
    }


def test_le_lecteur_d_arborescence_reconstruit_les_chemins():
    """The parser itself: without this, an empty result would make the checks pass vacuously."""
    exemple = "\n".join(
        [
            "projet/",
            "├── docs/                   documents",
            "│",
            "└── src/paquet/             code",
            "    ├── config.py                 paramètres",
            "    └── donnees/            1. DONNÉES",
            "        ├── silver.py             nettoyage",
            "        └── gold.py               exclusions",
        ]
    )
    assert lire_arborescence(exemple) == {
        "docs/",
        "src/paquet/",
        "src/paquet/config.py",
        "src/paquet/donnees/",
        "src/paquet/donnees/silver.py",
        "src/paquet/donnees/gold.py",
    }


def test_l_arborescence_du_readme_est_lue():
    """The README tree yields the package modules - a broken parse would return nothing."""
    modules = {c for c in _arborescence_du_readme() if c.endswith(".py")}
    assert len(modules) >= 30, f"Arborescence du README mal lue : {len(modules)} modules trouvés"


def test_chaque_module_figure_dans_l_arborescence_du_readme():
    """A module the README does not list is a module a newcomer will not find."""
    absents = sorted(_modules_du_paquet() - _arborescence_du_readme())
    assert not absents, (
        "Modules absents de l'arborescence du README (section « Structure du dépôt ») : "
        f"{absents}. Ajouter pour chacun une ligne avec sa description."
    )


def test_l_arborescence_du_readme_ne_cite_aucun_module_disparu():
    """A line left behind by a removed or renamed module describes code that does not exist."""
    cites = {c for c in _arborescence_du_readme() if c.startswith("src/") and c.endswith(".py")}
    disparus = sorted(cites - _modules_du_paquet())
    assert not disparus, (
        f"Modules cités par le README mais absents du paquet : {disparus}. "
        "Retirer ou renommer leur ligne dans la section « Structure du dépôt »."
    )
