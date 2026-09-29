"""Outils d'affichage pour rendre le notebook auto-porteur.

**Le problème.** Le règlement exige un notebook compréhensible sans explication orale.
Si le code vit uniquement dans `src/`, le jury ne le voit pas. S'il est recopié dans le
notebook, il existe en double : deux versions qui divergeront, et des tests qui ne
portent que sur l'une des deux.

**La solution retenue.** Une seule source de vérité — `src/churn_saas/` — testée par
`pytest`. Le notebook l'importe, puis **affiche le code source** des fonctions clés au
moment où il les explique. Le lecteur voit le code ; il n'existe qu'à un seul endroit.

    from churn_saas.notebook import afficher_source
    from churn_saas.donnees.silver import nettoyer_decimal_texte

    afficher_source(nettoyer_decimal_texte)   # le jury lit le code ici même
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any


def preparer_import(racine: Path | str | None = None) -> Path:
    """Rend `churn_saas` importable même sans installation du paquet.

    Le notebook doit pouvoir être exécuté par un correcteur qui a simplement décompressé
    l'archive, sans lancer `uv sync`. Cette fonction ajoute `src/` au chemin d'import si
    le paquet n'est pas déjà installé.
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
    """Affiche le code source d'une fonction ou d'une classe dans le notebook.

    Utilise la coloration syntaxique si IPython est disponible, sinon un affichage texte.
    Le code montré est **celui qui s'exécute** : il ne peut pas diverger de la version
    testée, puisqu'il est lu dans le module au moment de l'affichage.
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
    """Affiche la docstring d'un module : son rôle et les décisions qu'il porte."""
    nom = getattr(module, "__name__", str(module))
    texte = inspect.getdoc(module) or "(pas de documentation)"
    try:
        from IPython.display import Markdown, display

        display(Markdown(f"**Module `{nom}`**\n\n{texte}"))
    except ImportError:
        print(f"--- {nom} ---\n{texte}")
