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


def afficher_tableau(
    df: Any,
    titre: str | None = None,
    index: bool = False,
    retourner_html: bool = False,
) -> str | None:
    """Render a DataFrame with full cell content, wrapped rather than truncated.

    Pandas truncates long strings with an ellipsis, which hides exactly the columns that
    carry the reasoning - rationales, decisions, rules. In a deliverable meant to be read
    without oral explanation, a truncated table is a lost argument.

    This renders an HTML table where text wraps instead of being cut. Falls back to a
    plain print with truncation disabled when IPython is unavailable.

    `retourner_html` returns the markup instead of displaying it, which makes the
    no-truncation contract testable.
    """
    import pandas as pd

    try:
        from IPython.display import HTML, display
    except ImportError:
        with pd.option_context("display.max_colwidth", None, "display.width", None):
            if titre:
                print(titre)
            print(df.to_string(index=index))
        return None

    style = """
    <style>
    .tbl-complet { border-collapse: collapse; width: 100%; font-size: 0.86em;
                   margin: 0.4em 0 1em 0; }
    .tbl-complet th { background: #f2f5f8; text-align: left; vertical-align: bottom;
                      padding: 7px 10px; border-bottom: 2px solid #2a6f9e;
                      white-space: normal; }
    .tbl-complet td { text-align: left; vertical-align: top; padding: 7px 10px;
                      border-bottom: 1px solid #e4e4e4; white-space: normal;
                      word-break: normal; overflow-wrap: anywhere; line-height: 1.45; }
    .tbl-complet tr:hover td { background: #fafcfe; }
    .tbl-titre { font-weight: 600; font-size: 0.95em; margin-top: 0.6em; }
    </style>
    """
    tableau = df.to_html(index=index, escape=True, border=0, classes="tbl-complet")
    entete = f'<div class="tbl-titre">{titre}</div>' if titre else ""
    markup = style + entete + tableau
    if retourner_html:
        return markup
    display(HTML(markup))
    return None
