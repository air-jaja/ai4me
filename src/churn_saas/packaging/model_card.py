"""Model card generation from the Hugging Face template.

The `modelcard_template.md` template is filled through Jinja2 substitution. Values come
from the `FicheModele` produced at training time, so card and artefact cannot drift apart.

If Jinja2 is unavailable a minimal substitution takes over, keeping the notebook runnable
without an extra dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

GABARIT_PAR_DEFAUT = Path(__file__).parent / "modelcard_template.md"


def _substitution_minimale(gabarit: str, contexte: dict[str, Any]) -> str:
    """Replace {{ key | default(...) }} without Jinja2. Sufficient for this template."""

    def remplacer(correspondance: re.Match) -> str:
        expression = correspondance.group(1).strip()
        key = expression.split("|")[0].strip()
        valeur = contexte.get(key)
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
    """Render the completed model card, writing it out when a destination is given."""
    texte_gabarit = Path(gabarit).read_text(encoding="utf-8")
    try:
        from jinja2 import Template

        rendu = Template(texte_gabarit).render(**contexte)
    except ImportError:
        rendu = _substitution_minimale(texte_gabarit, contexte)

    if destination is not None:
        Path(destination).write_text(rendu, encoding="utf-8")
    return rendu
