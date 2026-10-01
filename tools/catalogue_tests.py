"""Generate the test catalogue from the test files themselves.

**Why generate rather than write.** A hand-written test inventory drifts the moment a test
is added or renamed, and a stale inventory is worse than none: it claims coverage that no
longer exists. This reads the source, so the catalogue cannot describe a test that is not
there.

Each test is expected to carry a docstring explaining *what defect it prevents* rather than
what it asserts. "Checks that recall is 0.7" is a restatement of the code; "a change to the
cleaning chain would invalidate three deliverables at once" is the reason the test exists.

    uv run python tools/catalogue_tests.py

The catalogue is written by the script itself, in UTF-8. Redirecting its output would tie
the result to the terminal's encoding: on Windows `sys.stdout` opens in cp1252, which
cannot represent the arrows and accents the document contains.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_TESTS = RACINE / "tests"

# Each test file is tied to the lifecycle activity it protects and to the competencies the
# certification grid evaluates there. Keeping this mapping explicit is what turns a test
# suite into evidence.
CONTEXTE: dict[str, dict[str, str]] = {
    "test_structure.py": {
        "titre": "Structure du paquet",
        "activite": "Transverse",
        "competences": "C6",
        "protege": "L'organisation du code : aucun module ne doit masquer un paquet homonyme",
    },
    "test_donnees.py": {
        "titre": "Nettoyage et niveaux de raffinage",
        "activite": "1 · Gestion des données",
        "competences": "C3",
        "protege": "La chaîne bronze → silver → gold et les exclusions anti-fuite",
    },
    "test_donnees_gouvernance.py": {
        "titre": "Schéma, gouvernance et versionnement des données",
        "activite": "1 · Gestion des données",
        "competences": "C1, C2, C3",
        "protege": "Le contrat de schéma, le cycle de vie, la sensibilité et les empreintes",
    },
    "test_features.py": {
        "titre": "Construction et contrôle des variables",
        "activite": "2 · Contrôle des features",
        "competences": "C3, C5",
        "protege": "Les ratios d'usage et la détection générique de fuite",
    },
    "test_exploration.py": {
        "titre": "Profilage et exploration",
        "activite": "1 · Données · 2 · Features",
        "competences": "C3, C4",
        "protege": (
            "Le profilage qui décide la préparation, et le pipeline bronze → silver → gold"
        ),
    },
    "test_materialisation.py": {
        "titre": "Matérialisation des jeux dérivés",
        "activite": "2 · Features",
        "competences": "C3, C6",
        "protege": (
            "Le lien entre une version de modèle et le jeu exact qui l'a produite : "
            "écriture, empreinte, contrôle avant entraînement"
        ),
    },
    "test_evaluation.py": {
        "titre": "Métriques, décision et impact",
        "activite": "4 · Évaluation",
        "competences": "C5, C8",
        "protege": "La règle de priorisation par valeur espérée et sa robustesse",
    },
    "test_packaging.py": {
        "titre": "Artefacts et fiche modèle",
        "activite": "5 · Packaging",
        "competences": "C6",
        "protege": "La solidarité entre le modèle sérialisé et sa fiche",
    },
    "test_monitoring.py": {
        "titre": "Dérive et règles d'alerte",
        "activite": "7 · Monitoring",
        "competences": "C8, C9",
        "protege": "Le calcul de dérive et la boucle indicateur → seuil → action",
    },
    "test_notebook.py": {
        "titre": "Contrat d'affichage des notebooks",
        "activite": "Transverse",
        "competences": "C3, C6",
        "protege": "L'unicité du code affiché et l'absence de troncature des tableaux",
    },
    "test_recapitulatif.py": {
        "titre": "Récapitulatif de la suite",
        "activite": "Transverse",
        "competences": "—",
        "protege": (
            "Les taux affichés en fin de run : un taux faux donnerait confiance sans raison"
        ),
    },
    "test_conventions.py": {
        "titre": "Conventions de travail",
        "activite": "Transverse",
        "competences": "—",
        "protege": ("Les règles de langue : commentaires en anglais, contenu affiché en français"),
    },
    "test_regression_casse_modalites.py": {
        "titre": "Défaut de casse des modalités",
        "activite": "1 · Données",
        "competences": "C3",
        "protege": (
            "Le défaut trouvé en phase 3 : ce qu'il produisait, et ce que la correction "
            "produit — les deux sont figés pour rester traçables"
        ),
    },
    "test_non_regression.py": {
        "titre": "Non-régression des phases terminées",
        "activite": "Transverse",
        "competences": "C1, C2, C3, C4, C5",
        "protege": (
            "Les chiffres publiés dans les carnets, les documents et la soutenance — "
            "un fichier par projet, une section par phase close"
        ),
    },
}

ORDRE = [
    "test_structure.py",
    "test_donnees.py",
    "test_donnees_gouvernance.py",
    "test_features.py",
    "test_exploration.py",
    "test_materialisation.py",
    "test_evaluation.py",
    "test_packaging.py",
    "test_monitoring.py",
    "test_notebook.py",
    "test_conventions.py",
    "test_recapitulatif.py",
    "test_regression_casse_modalites.py",
    "test_non_regression.py",
]


def _premiere_phrase(docstring: str | None) -> str:
    """First sentence of a docstring, which is expected to state the intent."""
    if not docstring:
        return "_(sans description)_"
    texte = " ".join(docstring.strip().split())
    for separateur in (". ", " - "):
        if separateur in texte:
            return texte.split(separateur)[0].rstrip(".") + "."
    return texte if texte.endswith(".") else texte + "."


def _reste(docstring: str | None) -> str:
    """Remainder of the docstring: the rationale, when the author supplied one."""
    if not docstring:
        return ""
    texte = " ".join(docstring.strip().split())
    premiere = _premiere_phrase(docstring).rstrip(".")
    reste = texte[len(premiere) :].lstrip(". -")
    return reste


def _ancre(titre: str) -> str:
    """GitHub-style anchor: lowercase, punctuation removed, spaces turned into hyphens."""
    ancre = titre.lower().replace("·", "").replace(" ", "-")
    ancre = re.sub(r"[^\w\-]", "", ancre, flags=re.UNICODE)
    return re.sub(r"-{2,}", "-", ancre).strip("-")


def _parametres(noeud: ast.FunctionDef) -> str:
    """Fixtures a test relies on. `tmp_path` signals a filesystem test, for instance."""
    noms = [a.arg for a in noeud.args.args]
    return ", ".join(f"`{n}`" for n in noms) if noms else "—"


def _collecte_pytest() -> dict[str, int]:
    """Ask pytest how many cases each test function actually expands into.

    Counting parametrised cases by reading the source only works when the parameter list
    is a literal. `@parametrize("x", sorted(MAPPING))` defeats any static count, and a
    catalogue that silently undercounts contradicts `pytest --collect-only` - exactly the
    kind of small inconsistency that costs credibility.

    Falls back to one case per function if pytest cannot be run, and the caller says so.
    """
    try:
        resultat = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    comptes: dict[str, int] = {}
    for ligne in resultat.stdout.splitlines():
        if "::" not in ligne or not ligne.startswith("tests/"):
            continue
        chemin, _, reste = ligne.partition("::")
        nom = reste.split("[")[0].strip()
        comptes[f"{pathlib.PurePath(chemin).name}::{nom}"] = (
            comptes.get(f"{pathlib.PurePath(chemin).name}::{nom}", 0) + 1
        )
    return comptes


def cataloguer(fichier: Path, comptes: dict[str, int]) -> list[dict[str, str]]:
    """Extract one row per test function from a test module."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    cas = []
    for noeud in arbre.body:
        if not isinstance(noeud, ast.FunctionDef) or not noeud.name.startswith("test_"):
            continue
        cas.append(
            {
                "nom": noeud.name,
                "intention": _premiere_phrase(ast.get_docstring(noeud)),
                "raison": _reste(ast.get_docstring(noeud)),
                "fixtures": _parametres(noeud),
                "cas": comptes.get(f"{fichier.name}::{noeud.name}", 1),
                "ligne": str(noeud.lineno),
            }
        )
    return cas


def rendre_markdown() -> str:
    """Produce the full catalogue as Markdown."""
    fichiers = [f for f in ORDRE if (DOSSIER_TESTS / f).exists()]
    fichiers += sorted(f.name for f in DOSSIER_TESTS.glob("test_*.py") if f.name not in ORDRE)

    comptes = _collecte_pytest()
    total_fonctions = 0
    total_cas = 0
    sections = []
    resume = []

    for nom_fichier in fichiers:
        chemin = DOSSIER_TESTS / nom_fichier
        cas = cataloguer(chemin, comptes)
        total_fonctions += len(cas)
        cas_fichier = sum(c["cas"] for c in cas)
        total_cas += cas_fichier
        contexte = CONTEXTE.get(
            nom_fichier,
            {"titre": nom_fichier, "activite": "—", "competences": "—", "protege": "—"},
        )
        resume.append(
            f"| [{contexte['titre']}](#{_ancre(contexte['titre'])}) "
            f"| `{nom_fichier}` | {contexte['activite']} "
            f"| {contexte['competences']} | {cas_fichier} |"
        )

        lignes = [
            f"### {contexte['titre']}",
            "",
            (
                f"**Fichier :** `tests/{nom_fichier}` — "
                f"**Activité :** {contexte['activite']} — "
                f"**Compétences :** {contexte['competences']}"
            ),
            "",
            f"**Ce que ce fichier protège :** {contexte['protege']}",
            "",
            "| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |",
            "|---|---|---|---|",
        ]
        for i, c in enumerate(cas, start=1):
            raison = c["raison"] or "—"
            multiple = f" _(×{c['cas']})_" if c["cas"] > 1 else ""
            lignes.append(f"| {i} | `{c['nom']}`{multiple} | {c['intention']} | {raison} |")
        lignes.append("")
        sections.append("\n".join(lignes))

    entete = [
        "# Catalogue des tests",
        "",
        "> **Document généré.** Produit par `tools/catalogue_tests.py` à partir des fichiers de",
        "> tests eux-mêmes. Un inventaire écrit à la main dérive dès le premier test ajouté, et",
        "> un inventaire périmé est pire qu'aucun : il revendique une couverture qui n'existe",
        "> plus. Régénérer avec :",
        ">",
        "> ```bash",
        "> uv run python tools/catalogue_tests.py > docs/TESTS.md",
        "> ```",
        "",
        f"**{total_cas} cas de test** issus de {total_fonctions} fonctions, "
        f"répartis sur {len(fichiers)} fichiers.",
        "",
        "_Les deux nombres diffèrent parce qu'un test paramétré est une fonction unique "
        "exécutée plusieurs fois. Le décompte des cas provient de `pytest --collect-only`, "
        "non d'une lecture du code : une liste de paramètres calculée plutôt qu'écrite en "
        "dur échapperait à toute analyse statique._"
        + (
            ""
            if comptes
            else "\n\n> ⚠️ Collecte pytest indisponible : les cas paramétrés sont comptés pour un."
        ),
        "",
        "## Principe : tester ce qui casse sans bruit",
        "",
        "La suite ne vise pas la couverture de lignes. Elle vise les défauts qui ne lèvent",
        "aucune erreur : une jointure qui perd des lignes en silence, une virgule décimale mal",
        "convertie, une variable en fuite réintroduite, un infini qui se propage, un tableau",
        "tronqué qui ampute un argument.",
        "",
        "Un défaut bruyant se corrige en dix minutes. Un défaut silencieux se découvre en",
        "soutenance.",
        "",
        "## Vue d'ensemble",
        "",
        "| Domaine | Fichier | Activité du cycle de vie | Compétences | Cas |",
        "|---|---|---|---|---|",
        *resume,
        "",
        "---",
        "",
        "## Détail par domaine",
        "",
    ]
    return "\n".join(entete) + "\n" + "\n".join(sections)


DESTINATION_PAR_DEFAUT = RACINE / "docs" / "TESTS.md"


def main(argv: list[str] | None = None) -> int:
    """Write the catalogue, or print it when asked for standard output."""
    analyseur = argparse.ArgumentParser(description="Génère le catalogue des tests.")
    analyseur.add_argument(
        "--sortie",
        default=str(DESTINATION_PAR_DEFAUT),
        help="fichier de destination, ou « - » pour la sortie standard",
    )
    arguments = analyseur.parse_args(argv)
    contenu = rendre_markdown()

    if arguments.sortie == "-":
        # Force UTF-8: the default encoding of a Windows console cannot represent the
        # arrows and accents this document contains.
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(contenu)
        return 0

    destination = Path(arguments.sortie)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contenu, encoding="utf-8", newline="\n")

    # The freshness check writes to a temporary file outside the repository, so the path
    # is only shortened when it actually sits inside it.
    try:
        affiche = destination.relative_to(RACINE)
    except ValueError:
        affiche = destination
    print(f"Catalogue écrit : {affiche}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
