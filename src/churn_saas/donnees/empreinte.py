"""Dataset fingerprinting and manifests.

**Why this exists.** Versioning code is easy; versioning data is where reproducibility is
usually lost. A model trained three months ago cannot be reproduced from its code alone if
the training set has changed in the meantime - and nothing in Git will tell you it did.

A fingerprint answers one question precisely: *is this the same dataset as the one used
then?* It is computed on the content, not on the file, so a re-export producing identical
rows yields the same fingerprint even if the file timestamp differs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def empreinte_fichier(chemin: Path | str, taille_bloc: int = 65_536) -> str:
    """SHA-256 of a file's bytes, read in blocks to bound memory use."""
    condensat = hashlib.sha256()
    with open(chemin, "rb") as flux:
        for bloc in iter(lambda: flux.read(taille_bloc), b""):
            condensat.update(bloc)
    return condensat.hexdigest()


def empreinte_donnees(df: pd.DataFrame) -> str:
    """SHA-256 of a DataFrame's content, independent of column and row order.

    Content rather than file: two exports of the same rows produce the same fingerprint
    even if the CSV was written differently. Order independence avoids false alarms when
    the source system changes its sort.
    """
    ordonne = df.reindex(sorted(df.columns), axis=1)
    ordonne = ordonne.sort_values(by=list(ordonne.columns), kind="mergesort").reset_index(drop=True)
    octets = ordonne.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(octets).hexdigest()


def construire_manifeste(
    sources: dict[str, Path | str],
    version_donnees: str,
    commentaire: str = "",
) -> dict[str, Any]:
    """Build the manifest tying a data version to the exact content of its sources.

    This is the object that makes "code + data + model" versioning real rather than
    declarative (notebook section 10).
    """
    fichiers = {}
    for nom, chemin in sources.items():
        chemin = Path(chemin)
        fichiers[nom] = {
            "chemin": str(chemin.as_posix()),
            "octets": chemin.stat().st_size,
            "sha256": empreinte_fichier(chemin),
        }
    return {
        "version_donnees": version_donnees,
        "date_construction": datetime.now(UTC).isoformat(timespec="seconds"),
        "commentaire": commentaire,
        "fichiers": fichiers,
    }


def ecrire_manifeste(manifeste: dict[str, Any], destination: Path | str) -> Path:
    """Write the manifest as JSON. Versioned in Git: it is small and it is the contract."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def verifier_manifeste(manifeste: dict[str, Any]) -> pd.DataFrame:
    """Recompute every fingerprint and report drift between the manifest and the files.

    Run before any training: if a source has changed since the manifest was written, the
    run is not reproducing what it claims to reproduce.
    """
    lignes = []
    for nom, details in manifeste["fichiers"].items():
        chemin = Path(details["chemin"])
        present = chemin.exists()
        actuelle = empreinte_fichier(chemin) if present else None
        lignes.append(
            {
                "source": nom,
                "présent": present,
                "empreinte attendue": details["sha256"][:16] + "…",
                "empreinte constatée": (actuelle[:16] + "…") if actuelle else "—",
                "conforme": bool(present and actuelle == details["sha256"]),
            }
        )
    return pd.DataFrame(lignes)


def charger_manifeste(chemin: Path | str) -> dict[str, Any]:
    """Read a manifest back from disk."""
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def manifeste_stable(
    sources: dict[str, Path | str],
    chemin: Path | str,
    version_donnees: str,
    commentaire: str = "",
) -> tuple[dict[str, Any], bool]:
    """Return the manifest for these sources, rewriting it only when it no longer holds.

    Rebuilding on every run would change `date_construction` each time and produce a diff
    on every commit, for fingerprints that did not move. Noise of that kind trains readers
    to skip the file - and a manifest nobody reads certifies nothing.

    Returns the manifest and whether it had to be rewritten.
    """
    chemin = Path(chemin)
    if chemin.exists():
        existant = charger_manifeste(chemin)
        controle = verifier_manifeste(existant)
        if bool(controle["conforme"].all()) and existant.get("version_donnees") == version_donnees:
            return existant, False

    manifeste = construire_manifeste(sources, version_donnees, commentaire)
    ecrire_manifeste(manifeste, chemin)
    return manifeste, True
