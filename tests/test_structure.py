"""Package structure invariants.

These checks caught a real defect: leftover flat modules from an earlier layout
(`evaluation.py`, `features.py`, `monitoring.py`) sat next to the packages that replaced
them. Python resolves the package and the code still ran, so nothing failed - but the
repository shipped dead modules shadowing live ones, and any editor jumping to definition
landed in the wrong file.
"""

from pathlib import Path

RACINE_PAQUET = Path(__file__).resolve().parents[1] / "src" / "churn_saas"


def test_aucun_module_ne_porte_le_nom_d_un_paquet():
    """A module and a package with the same name must never coexist."""
    paquets = {
        d.name for d in RACINE_PAQUET.iterdir() if d.is_dir() and (d / "__init__.py").exists()
    }
    modules = {f.stem for f in RACINE_PAQUET.glob("*.py")}
    collisions = sorted(paquets & modules)
    assert not collisions, (
        f"Modules masquant un paquet homonyme : {collisions}. "
        "Supprimer le fichier .py hérité de l'ancienne structure."
    )


def test_seuls_les_modules_transverses_restent_a_la_racine():
    """Only cross-cutting modules belong at package root; the rest lives in activities."""
    attendus = {"__init__", "config", "notebook"}
    presents = {f.stem for f in RACINE_PAQUET.glob("*.py")}
    inattendus = sorted(presents - attendus)
    assert not inattendus, (
        f"Modules inattendus à la racine du paquet : {inattendus}. "
        "Chaque module doit appartenir à l'activité du cycle de vie qu'il sert."
    )


def test_chaque_activite_expose_une_interface():
    """Every activity package declares __all__, which documents its public surface."""
    activites = [
        "donnees",
        "features",
        "modelisation",
        "evaluation",
        "packaging",
        "industrialisation",
        "monitoring",
        "stockage",
    ]
    manquants = [
        a
        for a in activites
        if "__all__" not in (RACINE_PAQUET / a / "__init__.py").read_text(encoding="utf-8")
    ]
    assert not manquants, f"Paquets sans __all__ : {manquants}"
