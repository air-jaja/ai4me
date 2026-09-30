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
TRANSVERSES = {"__init__", "config", "notebook"}

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
