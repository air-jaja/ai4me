"""Figure storage, with a cache keyed on what actually determines the image.

**The problem.** A figure drawn in a notebook exists only as base64 inside the output cell.
Reusing it in a document or a slide deck means taking a screenshot, and the screenshot
stops matching the notebook the moment the data move.

**The storage.** Figures are written under `reports/figures/`, named by phase and subject:

    reports/figures/03_desequilibre_cible.png
    reports/figures/03_desequilibre_cible.svg

PNG for documents and slides, SVG for anything that may be enlarged. Callers never write a
path: they give a name, and `chemin_figure()` resolves it from the repository root.

**The cache, and why it is keyed the way it is.** Regenerating every figure on every run is
wasteful, but a cache that serves a stale image is worse than no cache: the reader sees a
picture that no longer matches the code or the data, and nothing says so.

The key therefore combines both things that determine the image:

    - a signature of the **data** (usually a dataset fingerprint);
    - the **source code** of the function that draws it.

Hashing the drawing function's source is what makes the cache safe. Editing a colour, a
threshold or a label changes the source, hence the key, hence forces regeneration - without
anyone having to remember to bump a version number. That is the failure mode of
version-string caches, and it is why this one does not use them.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import RAPPORTS

DOSSIER_FIGURES = RAPPORTS / "figures"
FORMATS = ("png", "svg")


def chemin_figure(nom: str, extension: str = "png", dossier: Path | str | None = None) -> Path:
    """Resolve a figure's path from its name, so no caller hardcodes one."""
    base = Path(dossier) if dossier else DOSSIER_FIGURES
    return base / f"{nom}.{extension}"


def _chemin_signature(nom: str, dossier: Path | str | None = None) -> Path:
    base = Path(dossier) if dossier else DOSSIER_FIGURES
    return base / f"{nom}.signature.json"


def cle_cache(signature_donnees: str, tracer: Callable[..., Any]) -> str:
    """Cache key: the data signature plus the source of the drawing function.

    Including the source is the point. A key built on the data alone would keep serving an
    old image after the plotting code changed - the exact situation a cache must never
    create.
    """
    try:
        source = inspect.getsource(tracer)
    except (OSError, TypeError):
        # A function defined interactively has no retrievable source. Falling back to its
        # qualified name is weaker, so the caller is told through `raison`.
        source = f"<source indisponible:{getattr(tracer, '__qualname__', tracer)}>"
    condensat = hashlib.sha256()
    condensat.update(signature_donnees.encode("utf-8"))
    condensat.update(source.encode("utf-8"))
    return condensat.hexdigest()


def etat_cache(nom: str, cle: str, dossier: Path | str | None = None) -> tuple[bool, str]:
    """Say whether the figure must be redrawn, and why.

    Returning the reason rather than a bare boolean lets the notebook print it: a cache
    that silently decides is a cache nobody trusts.
    """
    chemin_png = chemin_figure(nom, "png", dossier)
    chemin_sig = _chemin_signature(nom, dossier)

    if not chemin_png.exists():
        return True, "figure absente"
    if not chemin_sig.exists():
        return True, "signature absente"
    try:
        enregistree = json.loads(chemin_sig.read_text(encoding="utf-8")).get("cle")
    except (OSError, json.JSONDecodeError):
        return True, "signature illisible"
    if enregistree != cle:
        return True, "données ou code de tracé modifiés"
    return False, "inchangée"


def enregistrer_figure(
    figure: Any,
    nom: str,
    cle: str,
    dossier: Path | str | None = None,
    formats: tuple[str, ...] = FORMATS,
) -> list[Path]:
    """Write the figure in every format, and record the key that produced it."""
    base = Path(dossier) if dossier else DOSSIER_FIGURES
    base.mkdir(parents=True, exist_ok=True)

    ecrits = []
    for extension in formats:
        chemin = chemin_figure(nom, extension, base)
        figure.savefig(chemin, bbox_inches="tight", dpi=150)
        ecrits.append(chemin)

    _chemin_signature(nom, base).write_text(
        json.dumps({"nom": nom, "cle": cle, "formats": list(formats)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return ecrits


def figure_en_cache(
    nom: str,
    signature_donnees: str,
    tracer: Callable[[], Any],
    dossier: Path | str | None = None,
    formats: tuple[str, ...] = FORMATS,
) -> tuple[Path, str]:
    """Return the figure's path, redrawing it only when data or code changed.

    `tracer` takes no argument and returns a matplotlib figure. Passing a function rather
    than a block of code is what allows its source to be hashed - and therefore what makes
    the cache trustworthy.

    Returns the PNG path and the reason the figure was or was not redrawn.
    """
    cle = cle_cache(signature_donnees, tracer)
    obsolete, raison = etat_cache(nom, cle, dossier)

    if obsolete:
        figure = tracer()
        enregistrer_figure(figure, nom, cle, dossier, formats)

    return chemin_figure(nom, "png", dossier), raison


def inventaire_figures(dossier: Path | str | None = None) -> Any:
    """List the stored figures, for the notebook and for the documents that reuse them."""
    import pandas as pd

    base = Path(dossier) if dossier else DOSSIER_FIGURES
    if not base.exists():
        return pd.DataFrame(columns=["figure", "phase", "formats", "taille"])

    lignes = []
    for chemin in sorted(base.glob("*.png")):
        nom = chemin.stem
        disponibles = [e for e in FORMATS if chemin_figure(nom, e, base).exists()]
        lignes.append(
            {
                "figure": nom,
                "phase": nom.split("_")[0],
                "formats": ", ".join(disponibles),
                "taille": f"{chemin.stat().st_size / 1024:,.0f} Ko".replace(",", " "),
            }
        )
    return pd.DataFrame(lignes)
