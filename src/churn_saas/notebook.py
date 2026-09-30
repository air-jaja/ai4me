"""Display helpers that keep the notebook self-contained.

**The problem.** The rules require a notebook understandable without oral explanation. If
the code lives only in `src/`, the jury never sees it. If it is copied into the notebook,
it exists twice: two versions that will drift, and tests covering only one of them.

**The chosen answer.** A single source of truth - `src/churn_saas/`, covered by `pytest`.
The notebook imports it, then **displays the source** of key functions where it explains
them. The reader sees the code; the code exists in exactly one place.

    from churn_saas.notebook import afficher_source
    from churn_saas.donnees.silver import nettoyer_decimal_texte

    afficher_source(nettoyer_decimal_texte)   # the jury reads the code right here
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any


def preparer_import(racine: Path | str | None = None) -> Path:
    """Make `churn_saas` importable even when the package is not installed.

    A grader must be able to run the notebook straight from an unzipped archive, without
    running `uv sync`. This walks up the tree to find `src/churn_saas` and prepends it to
    the import path.
    """
    if racine is None:
        racine = Path.cwd()
        for candidat in [racine, *racine.parents]:
            if (candidat / "src" / "churn_saas").is_dir():
                racine = candidat
                break
    racine = Path(racine)
    chemin_src = str((racine / "src").resolve())
    if chemin_src not in sys.path:
        sys.path.insert(0, chemin_src)
    return racine


def afficher_source(objet: Any, titre: str | None = None) -> str:
    """Render a function's or class's source code inside the notebook.

    Uses syntax highlighting when IPython is available, plain text otherwise. The code
    shown **is** the code that runs: it is read from the module at display time, so it
    cannot drift from the tested version. Returns it as well, which makes that invariant
    testable.
    """
    code = inspect.getsource(objet)
    module = getattr(objet, "__module__", "?")
    nom = getattr(objet, "__qualname__", str(objet))
    entete = titre or f"{module}.{nom}"

    try:
        from IPython.display import Markdown, display

        display(Markdown(f"**Source — `{entete}`**\n\n```python\n{code}\n```"))
    except ImportError:
        print(f"--- {entete} ---\n{code}")
    return code


def afficher_module(module: Any) -> None:
    """Render a module's docstring: its purpose and the decisions it carries."""
    nom = getattr(module, "__name__", str(module))
    texte = inspect.getdoc(module) or "(pas de documentation)"
    try:
        from IPython.display import Markdown, display

        display(Markdown(f"**Module `{nom}`**\n\n{texte}"))
    except ImportError:
        print(f"--- {nom} ---\n{texte}")
