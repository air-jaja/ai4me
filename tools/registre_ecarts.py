"""Generate the register of what was left aside, from its single source (rule 13).

**Why generate rather than write.** What a project leaves aside is scattered by nature:
a rejected tool in the tracking document, an excluded column in the code, a postponed
action in a delivery note. Written by hand, a register drifts from all three. Generated,
it cannot list an exclusion the code no longer makes, nor miss one it makes.

Two sources, merged:

    docs/registre_ecarts.toml        decisions taken by people: rejected, postponed,
                                     awaiting arbitration - with motive and evidence
    MOTIFS_EXCLUSION (donnees/gold)  columns excluded from the model, read from the code
                                     rather than copied, so the two cannot diverge

    uv run python tools/registre_ecarts.py
    uv run python tools/registre_ecarts.py --sortie /tmp/REGISTRE.md   # freshness check

Written in UTF-8 by the script itself, for the reason given in `catalogue_tests.py`: a
Windows console cannot represent the characters this document contains.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "docs" / "registre_ecarts.toml"
DESTINATION_PAR_DEFAUT = RACINE / "docs" / "05.REGISTRE_elements_ecartes.md"

STATUTS = ("écarté", "différé", "à arbitrer")
NATURES = ("méthode", "outil", "variable", "règle", "action", "architecture")
CHAMPS_OBLIGATOIRES = ("id", "titre", "nature", "statut", "phase", "competence", "section")
CHAMPS_OBLIGATOIRES += ("motif", "source")

INTITULES = {
    "à arbitrer": "En attente d'arbitrage",
    "différé": "Différé, faute de temps",
    "écarté": "Écarté, décision définitive",
}


def charger_elements(source: Path = SOURCE) -> list[dict[str, str]]:
    """Entries of the TOML source, in file order."""
    with open(source, "rb") as flux:
        return list(tomllib.load(flux).get("element", []))


def charger_exclusions() -> dict[str, str]:
    """Columns excluded from the model, as the code declares them."""
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.donnees import MOTIFS_EXCLUSION

    return dict(sorted(MOTIFS_EXCLUSION.items()))


def _cellule(texte: str | None) -> str:
    """Escape a value for a Markdown table cell."""
    return (texte or "—").replace("|", "\\|").replace("\n", " ")


def _tableau(elements: list[dict[str, str]]) -> list[str]:
    entetes = ["Id", "Élément", "Phase", "§", "Motif", "Preuve", "Condition de réexamen"]
    lignes = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    for e in elements:
        titre = e["titre"] + (" *(revirement)*" if e.get("revirement") == "oui" else "")
        cellules = [
            e["id"],
            titre,
            e["phase"],
            e["section"],
            e["motif"],
            e.get("preuve"),
            e.get("condition"),
        ]
        lignes.append("| " + " | ".join(_cellule(c) for c in cellules) + " |")
    return lignes


def rendre_markdown(
    elements: list[dict[str, str]] | None = None, exclusions: dict[str, str] | None = None
) -> str:
    """The readable register: open items first, then the settled ones."""
    elements = charger_elements() if elements is None else elements
    exclusions = charger_exclusions() if exclusions is None else exclusions

    sortie = [
        "# Registre des éléments laissés de côté",
        "",
        "> **Document généré — ne pas éditer.** Source : `docs/registre_ecarts.toml` et, pour les",
        "> colonnes exclues du modèle, `MOTIFS_EXCLUSION` dans le code. Régénérer avec",
        "> `make registre-doc` ; la CI vérifie qu'il est à jour (règle 13).",
        ">",
        "> Ce registre répond à la question : *qu'avez-vous laissé de côté, pourquoi, et à",
        "> quelle condition y reviendriez-vous ?* Il alimente les sections 2, 7 et 13 du",
        "> notebook de certification et la préparation de l'oral.",
        "",
        "## Synthèse",
        "",
        "| Statut | Nombre |",
        "|---|---|",
    ]
    for statut in STATUTS:
        nombre = sum(1 for e in elements if e["statut"] == statut)
        sortie.append(f"| {INTITULES[statut]} | {nombre} |")
    sortie.append(f"| Colonnes exclues du modèle (lues dans le code) | {len(exclusions)} |")
    revirements = sum(1 for e in elements if e.get("revirement") == "oui")
    sortie += ["", f"Dont **{revirements} revirements** : choix d'abord retenus, puis révisés.", ""]

    for statut in STATUTS:
        selection = [e for e in elements if e["statut"] == statut]
        if not selection:
            continue
        sortie += ["", f"## {INTITULES[statut]}", ""]
        sortie += _tableau(selection)

    sortie += [
        "",
        "## Colonnes exclues du modèle",
        "",
        "Lues dans `MOTIFS_EXCLUSION` (`src/churn_saas/donnees/gold.py`). Chaque motif est propre",
        "à sa colonne : la grille sépare l'exclusion éthique (C2) de l'exclusion technique (C3).",
        "",
        "| Colonne | Motif |",
        "|---|---|",
    ]
    sortie += [f"| `{c}` | {_cellule(m)} |" for c, m in exclusions.items()]

    sortie += ["", "## Par section du notebook", "", "| § | Éléments |", "|---|---|"]
    par_section: dict[str, list[str]] = {}
    for e in elements:
        par_section.setdefault(e["section"], []).append(e["id"])
    for section in sorted(par_section, key=lambda s: (len(s), s)):
        sortie.append(f"| {section} | {', '.join(par_section[section])} |")
    return "\n".join(sortie) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the register, or print it when asked for standard output."""
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Génère le registre des éléments écartés.")
    analyseur.add_argument(
        "--sortie",
        default=str(DESTINATION_PAR_DEFAUT),
        help="fichier de destination, ou « - » pour la sortie standard",
    )
    arguments = analyseur.parse_args(argv)
    contenu = rendre_markdown()

    if arguments.sortie == "-":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(contenu)
        return 0

    destination = Path(arguments.sortie)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contenu, encoding="utf-8", newline="\n")
    try:
        affiche = destination.relative_to(RACINE)
    except ValueError:
        affiche = destination
    print(f"Registre écrit : {affiche}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
