"""Build a delivery: patches for `git am`, changed files, and a pre-filled A_LIRE.md.

    uv run python tools/livraison.py                      # since origin/develop
    uv run python tools/livraison.py --verifier           # + make check and campaign, isolated

The A_LIRE.md is generated, not written by hand: base commit, files added / modified /
deleted, the actions they imply (lock file -> uv sync, manifest -> materialise, ...) and,
with --verifier, the results of `make check` and of the activity campaign run in a
separate working tree on the base commit with the patches applied.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

# Changed file -> action the project owner must take after `git am`.
ACTIONS = (
    (
        "uv.lock",
        "uv sync --frozen --group dev --group notebook --group plateforme   # VS Code fermé",
    ),
    ("data/manifeste_v1.0.json", "uv run python tools/materialiser.py"),
    (
        "tools/reglage_modele.py",
        "uv run python tools/reglage_modele.py --forcer   # ressources du poste",
    ),
    ("tools/modele_servi.py", "uv run python tools/modele_servi.py --forcer"),
    (
        "docs/MODEL_CARD.md",
        "uv run python tools/model_card.py   # après les --forcer : la carte reprend vos mesures",
    ),
    (".pre-commit-config.yaml", "uv run pre-commit install"),
    ("docker/", "docker compose build"),
)


def _git(*arguments: str, cwd: Path = RACINE) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def actions_requises(fichiers: list[str]) -> list[str]:
    """The follow-up commands implied by the changed files, in order, without duplicates."""
    return [
        action
        for motif, action in ACTIONS
        if any(f == motif or f.startswith(motif) for f in fichiers)
    ]


def verifier(base: str, patchs: list[Path]) -> dict[str, str]:
    """`git am` on the base commit in a separate working tree, then make check and campaign."""
    dossier = Path(tempfile.mkdtemp(prefix="livraison-"))
    arbre = dossier / "arbre"
    try:
        _git("worktree", "add", "--detach", str(arbre), base)
        # A throwaway check: a local committer identity, so it runs on any machine.
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=verification",
                "-c",
                "user.email=verification@local",
                "am",
                "-q",
                *map(str, patchs),
            ],
            cwd=arbre,
            check=True,
        )
        resultats = {}
        for nom, commande in (
            ("make check", ["make", "check"]),
            ("campagne", [sys.executable, "tools/campagne_tests.py"]),
        ):
            sortie = subprocess.run(
                commande,
                cwd=arbre,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            propre = __import__("re").sub(r"\x1b\[[0-9;]*m", "", sortie.stdout)
            derniere = [
                x for x in propre.splitlines() if x.strip() and ("passed" in x or "Campagne" in x)
            ][-1:] or ["(sans sortie)"]
            resultats[nom] = ("OK — " if sortie.returncode == 0 else "ÉCHEC — ") + derniere[0][:150]
        return resultats
    finally:
        _git("worktree", "remove", "--force", str(arbre))
        shutil.rmtree(dossier, ignore_errors=True)


def construire(base: str, sortie: Path, avec_verification: bool) -> Path:
    travail = Path(tempfile.mkdtemp(prefix="paquet-"))
    patchs_dossier = travail / "patches"
    _git("format-patch", "-q", base, "-o", str(patchs_dossier))
    patchs = sorted(patchs_dossier.glob("*.patch"))
    if not patchs:
        raise SystemExit(f"Rien à livrer depuis {base}.")
    statut = [x.split("\t") for x in _git("diff", "--name-status", base, "HEAD").splitlines()]
    fichiers = [chemin[-1] for chemin in statut]
    for lettre, *chemins in statut:
        if lettre != "D":
            cible = travail / "fichiers" / chemins[-1]
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(RACINE / chemins[-1], cible)
    compte = {c: sum(1 for s in statut if s[0].startswith(c)) for c in "AMD"}
    sujets = _git("log", "--format=%h %s", f"{base}..HEAD").splitlines()[::-1]
    actions = actions_requises(fichiers)
    lignes = [
        f"# Livraison du {time.strftime('%d/%m/%Y')}",
        "",
        f"Base : `{_git('rev-parse', '--short', base).strip()}` ({base}). "
        f"{compte['A']} ajoutés, {compte['M']} modifiés, **{compte['D']} supprimés**.",
        "",
        "## Procédure",
        "",
        "```powershell",
        "git rev-list --left-right --count origin/develop...HEAD    # attendu : 0  0",
        "git am chemin\\vers\\patches\\*.patch",
        *actions,
        "uv run python tools/campagne_tests.py",
        "```",
        "",
        "## Commits",
        "",
        *[f"- `{s}`" for s in sujets],
    ]
    if compte["D"]:
        lignes += [
            "",
            "## Fichiers supprimés",
            "",
            *[f"- `{s[-1]}`" for s in statut if s[0] == "D"],
        ]
    if avec_verification:
        lignes += [
            "",
            "## Vérification (arbre séparé : base + patchs)",
            "",
            *[f"- **{k}** : {v}" for k, v in verifier(base, patchs).items()],
        ]
    (travail / "A_LIRE.md").write_text("\n".join(lignes) + "\n", encoding="utf-8", newline="\n")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as archive:
        for chemin in sorted(travail.rglob("*")):
            if chemin.is_file():
                archive.write(chemin, chemin.relative_to(travail))
    shutil.rmtree(travail, ignore_errors=True)
    return sortie


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Construit une livraison prête pour git am.")
    analyseur.add_argument("--base", default="origin/develop")
    analyseur.add_argument(
        "--sortie",
        default=str(RACINE / "sorties" / f"livraison_{time.strftime('%Y%m%d_%H%M')}.zip"),
    )
    analyseur.add_argument("--verifier", action="store_true", help="make check et campagne isolés")
    arguments = analyseur.parse_args(argv)
    chemin = construire(arguments.base, Path(arguments.sortie), arguments.verifier)
    print(f"Livraison : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
