"""What a recorded result depends on, and what a model is - read, never declared.

`modules_utilises(outil)` walks the import graph of a tool, statically, through every
`import` statement of every followed file - function-level imports included. A package's
`__init__.py` is read only to find which submodule defines each imported name: importing
`appliquer_regle` from `churn_saas.evaluation` follows `evaluation/decision.py`, not the
whole package. Other tools loaded dynamically (`_outil("name")`, a path to `tools/x.py`)
are followed too. Infrastructure that cannot change a result - tracking and packaging,
notebook helpers, figures - is left out.

`decrire_modele(modele)` reads a fitted model down its wrappers (calibration, pipeline,
target transform) and returns its family, exact estimator class, calibration and key
settings, always in the same form: what a result or a card says about its model comes
from the object itself.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from ..config import RACINE

PAQUET = RACINE / "src" / "churn_saas"
INFRASTRUCTURE = ("packaging", "notebook.py", "features/graphiques.py")


def _fichier(module: str) -> Path | None:
    """`churn_saas.a.b` -> its .py file, or the package's __init__.py."""
    parties = module.split(".")[1:]
    chemin = PAQUET.joinpath(*parties)
    if chemin.with_suffix(".py").is_file():
        return chemin.with_suffix(".py")
    if (chemin / "__init__.py").is_file():
        return chemin / "__init__.py"
    return None


def _infrastructure(fichier: Path) -> bool:
    relatif = fichier.relative_to(PAQUET).as_posix()
    return any(relatif == i or relatif.startswith(f"{i}/") for i in INFRASTRUCTURE)


def _imports(fichier: Path, module: str) -> list[tuple[str, list[str] | None]]:
    """(absolute module, imported names or None) for every churn_saas import of a file."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    paquet_courant = module if fichier.name == "__init__.py" else module.rpartition(".")[0]
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves += [(a.name, None) for a in noeud.names if a.name.startswith("churn_saas")]
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                base = paquet_courant.split(".")
                base = base[: len(base) - (noeud.level - 1)]
                cible = ".".join(base + ([noeud.module] if noeud.module else []))
            else:
                cible = noeud.module or ""
            if cible.startswith("churn_saas"):
                trouves.append((cible, [a.name for a in noeud.names]))
    return trouves


def _exportes(init: Path, paquet: str) -> dict[str, str]:
    """Name -> defining submodule, from a package's `from .sub import name` lines."""
    correspondance = {}
    for cible, noms in _imports(init, paquet):
        for nom in noms or []:
            correspondance[nom] = cible
    return correspondance


def modules_utilises(outil: Path) -> set[Path]:
    """The package files a tool's results may depend on (see the module docstring)."""
    outil = Path(outil)
    fichiers: set[Path] = set()
    vus: set[str] = set()
    outils = [outil]
    a_suivre: list[tuple[str, list[str] | None]] = []
    while outils:
        courant = outils.pop()
        texte = courant.read_text(encoding="utf-8")
        a_suivre += _imports(courant, "outil")
        for nom in re.findall(r'_outil\("(\w+)"\)|"tools"\s*/\s*"(\w+)\.py"', texte):
            appele = RACINE / "tools" / f"{next(n for n in nom if n)}.py"
            if appele.is_file() and appele not in fichiers:
                fichiers.add(appele)
                outils.append(appele)
    while a_suivre:
        module, noms = a_suivre.pop()
        cle = f"{module}:{sorted(noms) if noms else '*'}"
        if cle in vus:
            continue
        vus.add(cle)
        fichier = _fichier(module)
        if fichier is None:
            continue
        if fichier.name == "__init__.py":
            exportes = _exportes(fichier, module)
            sous_modules = sorted(p for p in fichier.parent.glob("*.py") if p.name != "__init__.py")
            for nom in noms or [None]:
                if nom in exportes:
                    a_suivre.append((exportes[nom], [nom]))
                elif nom and (fichier.parent / f"{nom}.py").is_file():
                    a_suivre.append((f"{module}.{nom}", None))
                else:  # unresolved: conservatively, the whole package
                    a_suivre += [(f"{module}.{p.stem}", None) for p in sous_modules]
            continue
        if _infrastructure(fichier) or fichier in fichiers:
            continue
        fichiers.add(fichier)
        a_suivre += _imports(fichier, module)
    return fichiers


# --- What a model is ---------------------------------------------------------------------------
FAMILLES = {
    "LogisticRegression": "regression_logistique",
    "RandomForestClassifier": "foret_aleatoire",
    "RandomForestRegressor": "foret_de_regression",
    "XGBClassifier": "xgboost",
    "Ridge": "regression_lineaire",
    "LinearRegression": "regression_lineaire",
}
CLES = {
    "regression_logistique": ("C", "class_weight", "penalty"),
    "foret_aleatoire": ("n_estimators", "max_depth", "min_samples_leaf", "class_weight"),
    "foret_de_regression": ("n_estimators", "min_samples_leaf"),
    "xgboost": ("n_estimators", "max_depth", "learning_rate", "min_child_weight"),
    "regression_lineaire": ("alpha",),
}


def decrire_modele(modele: Any) -> dict:
    """Family, exact estimator class, calibration and key settings, read on the object."""
    calibration, copies = None, None
    if (
        hasattr(modele, "calibrated_classifiers_")
        or type(modele).__name__ == "CalibratedClassifierCV"
    ):
        calibration = getattr(modele, "method", None)
        enveloppes = getattr(modele, "calibrated_classifiers_", None)
        copies = len(enveloppes) if enveloppes is not None else None
        modele = enveloppes[0].estimator if enveloppes else modele.estimator
    if hasattr(modele, "steps"):
        modele = modele.steps[-1][1]
    if hasattr(modele, "regressor"):  # TransformedTargetRegressor
        modele = getattr(modele, "regressor_", modele.regressor)
    classe = type(modele)
    famille = FAMILLES.get(classe.__name__, classe.__name__.lower())
    reglages = modele.get_params() if hasattr(modele, "get_params") else {}
    if reglages.get("penalty") == "deprecated":  # scikit-learn >= 1.8: l2 by default
        reglages["penalty"] = "l2"
    return {
        "famille": famille,
        "estimateur": f"{classe.__module__.split('._')[0]}.{classe.__name__}",
        "calibration": calibration,
        "copies": copies,
        "hyperparametres_cles": {
            k: (str(v) if v is None else v)
            for k, v in reglages.items()
            if k in CLES.get(famille, ())
        },
    }
