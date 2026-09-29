"""Génération de la fiche modèle à partir du gabarit Hugging Face.

Le gabarit `modelcard_template.md` est rempli par substitution Jinja2. Les valeurs
proviennent de la `FicheModele` produite à l'entraînement : la fiche et l'artefact ne
peuvent donc pas diverger.

Si Jinja2 n'est pas installé, une substitution minimale prend le relais — le notebook
reste exécutable sans dépendance supplémentaire.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

GABARIT_PAR_DEFAUT = Path(__file__).parent / "modelcard_template.md"


def _substitution_minimale(gabarit: str, contexte: dict[str, Any]) -> str:
    """Remplace {{ cle | default(...) }} sans Jinja2. Suffisant pour ce gabarit."""

    def remplacer(correspondance: re.Match) -> str:
        expression = correspondance.group(1).strip()
        cle = expression.split("|")[0].strip()
        valeur = contexte.get(cle)
        if valeur not in (None, ""):
            return str(valeur)
        defaut = re.search(r'default\(\s*"([^"]*)"', expression)
        return defaut.group(1) if defaut else ""

    return re.sub(r"\{\{(.*?)\}\}", remplacer, gabarit, flags=re.DOTALL)


def generer_model_card(
    contexte: dict[str, Any],
    gabarit: Path | str = GABARIT_PAR_DEFAUT,
    destination: Path | str | None = None,
) -> str:
    """Produit la fiche modèle complétée, et l'écrit si une destination est fournie."""
    texte_gabarit = Path(gabarit).read_text(encoding="utf-8")
    try:
        from jinja2 import Template

        rendu = Template(texte_gabarit).render(**contexte)
    except ImportError:
        rendu = _substitution_minimale(texte_gabarit, contexte)

    if destination is not None:
        Path(destination).write_text(rendu, encoding="utf-8")
    return rendu
