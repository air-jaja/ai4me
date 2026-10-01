"""Writing the derived datasets to disk, and recording what was written.

**Why write them at all.** The chain is deterministic: two runs on the same sources give
the same gold dataset. One could argue that storing it is redundant, since code and raw
data are both versioned.

That argument assumes determinism instead of verifying it. A pandas upgrade, a change in
join order, and tomorrow's gold differs from today's - with nothing to report it. The model
would then be trained on data its own card claims to describe, and does not.

**What is written, and where.**

    data/processed/silver_v<version>_<date>.parquet    derived, recomputable
    data/processed/gold_v<version>_<date>.parquet      the training snapshot
    data/manifeste_v<version>.json                     extended, versioned in Git

Parquet rather than CSV: types survive the round trip. Reparsing decimals and dates on
reload would undo the whole preparation step.

The Parquet files are **not** versioned in Git. They are derived: versioning them would
produce a binary diff at every change to the cleaning rules, for information already held
by the sources plus the code. What Git keeps is the manifest - small, textual, and the
contract itself.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..donnees import charger_manifeste, ecrire_manifeste, empreinte_donnees, racine_projet
from .pipeline import ResultatPipeline

DOSSIER_PAR_DEFAUT = "data/processed"


def version_code() -> str:
    """Current commit, short form, so a snapshot names the code that produced it.

    Returns "inconnue" outside a Git working copy: an archive unzipped by a grader has no
    repository, and failing there would serve nobody.
    """
    try:
        resultat = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=racine_projet(),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "inconnue"
    return resultat.stdout.strip() or "inconnue"


def _descriptif(nom: str, df: pd.DataFrame, chemin: Path, racine: Path) -> dict[str, Any]:
    """One manifest entry for a derived dataset."""
    try:
        chemin_relatif = chemin.resolve().relative_to(racine).as_posix()
    except ValueError:
        chemin_relatif = chemin.as_posix()
    return {
        "chemin": chemin_relatif,
        "lignes": int(len(df)),
        "colonnes": int(df.shape[1]),
        "octets": chemin.stat().st_size,
        "empreinte_contenu": empreinte_donnees(df),
        "version_code": version_code(),
    }


def materialiser(
    resultat: ResultatPipeline,
    version_donnees: str = "v1.0",
    dossier: Path | str | None = None,
    chemin_manifeste: Path | str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """Write silver and gold, and record them in the manifest.

    The bronze level is not written: it already exists under `data/raw/`, versioned in Git.
    Rewriting it would create a second copy that could drift from the first.

    Returns the updated manifest.
    """
    racine = racine_projet()
    dossier = Path(dossier) if dossier else racine / DOSSIER_PAR_DEFAUT
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = date or datetime.now(UTC).strftime("%Y%m%d")

    ecrits: dict[str, dict[str, Any]] = {}
    for nom, df in (("silver", resultat.silver), ("gold", resultat.gold)):
        chemin = dossier / f"{nom}_{version_donnees}_{horodatage}.parquet"
        df.to_parquet(chemin, index=False)
        ecrits[nom] = _descriptif(nom, df, chemin, racine)

    chemin_manifeste = Path(chemin_manifeste or racine / f"data/manifeste_{version_donnees}.json")
    manifeste = (
        charger_manifeste(chemin_manifeste)
        if chemin_manifeste.exists()
        else {"version_donnees": version_donnees, "fichiers": {}}
    )
    manifeste["jeux_derives"] = {
        "date_materialisation": horodatage,
        "jeux": ecrits,
    }
    ecrire_manifeste(manifeste, chemin_manifeste)
    return manifeste


def table_materialisation(manifeste: dict[str, Any]) -> pd.DataFrame:
    """Readable view of the recorded snapshots, displayed in the notebook."""
    derives = manifeste.get("jeux_derives", {}).get("jeux", {})
    return pd.DataFrame(
        [
            {
                "Jeu": nom,
                "Fichier": Path(details["chemin"]).name,
                "Lignes": details["lignes"],
                "Colonnes": details["colonnes"],
                "Taille": f"{details['octets'] / 1024:,.0f} Ko".replace(",", " "),
                "Empreinte du contenu": details["empreinte_contenu"][:16] + "…",
                "Version du code": details["version_code"],
            }
            for nom, details in derives.items()
        ]
    )


def verifier_jeux_derives(resultat: ResultatPipeline, manifeste: dict[str, Any]) -> pd.DataFrame:
    """Recompute the fingerprints and compare them to what the manifest recorded.

    Run before any training. A mismatch does not necessarily mean the code is wrong - a
    source may legitimately have changed - but it does mean the run no longer reproduces
    what the manifest describes, and that training on it would produce a model whose card
    is false.
    """
    derives = manifeste.get("jeux_derives", {}).get("jeux", {})
    courants = {"silver": resultat.silver, "gold": resultat.gold}

    lignes = []
    for nom, details in derives.items():
        df = courants.get(nom)
        constatee = empreinte_donnees(df) if df is not None else None
        chemin = racine_projet() / details["chemin"]
        lignes.append(
            {
                "jeu": nom,
                "fichier présent": chemin.exists(),
                "empreinte attendue": details["empreinte_contenu"][:16] + "…",
                "empreinte constatée": (constatee[:16] + "…") if constatee else "—",
                "conforme": bool(constatee == details["empreinte_contenu"] and chemin.exists()),
            }
        )
    return pd.DataFrame(lignes)


def charger_jeu_derive(
    manifeste: dict[str, Any], nom: str = "gold", controler: bool = True
) -> pd.DataFrame:
    """Reload a snapshot from disk, checking it is the one the manifest describes.

    `controler` exists for the rare case of inspecting a snapshot known to have drifted;
    it defaults to True because loading a snapshot without checking it defeats its purpose.
    """
    details = manifeste["jeux_derives"]["jeux"][nom]
    chemin = racine_projet() / details["chemin"]
    df = pd.read_parquet(chemin)

    if controler:
        constatee = empreinte_donnees(df)
        if constatee != details["empreinte_contenu"]:
            raise ValueError(
                f"Le jeu `{nom}` relu depuis {chemin.name} ne correspond pas au manifeste "
                f"(attendu {details['empreinte_contenu'][:16]}…, "
                f"constaté {constatee[:16]}…). L'instantané a été modifié ou régénéré."
            )
    return df
