"""Model serialisation and version metadata.

Three objects are versioned together - code, training data, model. A model reproducible
from code alone is an illusion if the training set changed in the meantime
(notebook section 10).
"""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import joblib

from ..config import MODELES
from .dependances import decrire_modele


@dataclass
class FicheModele:
    """Metadata that must accompany every model put into service."""

    nom: str
    version: str
    date_entrainement: str = field(default_factory=lambda: date.today().isoformat())
    empreinte_donnees: str = ""  # training snapshot used, e.g. churn_train_20260928
    hyperparametres: dict[str, Any] = field(default_factory=dict)
    metriques_validation: dict[str, float] = field(default_factory=dict)
    variables: list[str] = field(default_factory=list)
    variables_exclues: dict[str, str] = field(default_factory=dict)
    responsable_validation: str = ""
    version_python: str = field(default_factory=platform.python_version)

    def nom_fichier(self) -> str:
        """Base filename shared by the artefact and its card."""
        return f"{self.nom}_v{self.version}_{self.date_entrainement.replace('-', '')}"


REGISTRE = MODELES.parent / "resultats" / "registre_modeles.json"


def empreinte_entrainement(X, y) -> dict[str, Any]:
    """Fingerprint of the exact training rows: which accounts, with which values and outcome."""
    import hashlib

    import pandas as pd

    # Explicit line ending: to_csv defaults to os.linesep, so the same rows gave another
    # fingerprint on Windows (CRLF) than on Linux (LF) - found on 04/10/2026.
    contenu = X.assign(__cible__=pd.Series(y, index=X.index)).to_csv(
        index=True, lineterminator="\n"
    )
    comptes = "\n".join(map(str, sorted(X.index.astype(str))))
    return {
        "comptes": int(len(X)),
        "empreinte_comptes": hashlib.sha256(comptes.encode()).hexdigest(),
        "empreinte_contenu": hashlib.sha256(contenu.encode()).hexdigest(),
        "contrat_entree": [{"colonne": c, "type": str(t)} for c, t in X.dtypes.items()],
    }


def sauvegarder_modele(
    modele: Any,
    fiche: FicheModele,
    dossier: Path | str = MODELES,
    *,
    entrainement: tuple,
    lignage: dict[str, Any] | None = None,
    registre: Path | str | None = REGISTRE,
) -> Path:
    """Write the model and its identity card side by side; record it in the registry.

    The card is mandatory and complete: the file's SHA-256, the exact training rows
    (`entrainement=(X, y)`, required), the input contract, the descriptor read on the
    object, plus the caller's lineage (manifest, code). Kept apart from the model so it
    stays readable without deserialising it. The registry (versioned in Git, unlike
    models/) keeps one line per saved model.
    """
    import hashlib

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    base = fiche.nom_fichier()
    chemin_modele = dossier / f"{base}.joblib"
    joblib.dump(modele, chemin_modele)
    carte = asdict(fiche) | {
        "fichier_sha256": hashlib.sha256(chemin_modele.read_bytes()).hexdigest(),
        "entrainement": empreinte_entrainement(*entrainement),
        "descriptif": decrire_modele(modele),
        "lignage": lignage or {},
    }
    # Trailing newline: a versioned text file without one is rewritten at every commit
    # by `end-of-file-fixer`, failing the hook for a file whose content never changed.
    (dossier / f"{base}.json").write_text(
        json.dumps(carte, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if registre:
        enregistrer_au_registre(carte, chemin_modele, Path(registre))
    return chemin_modele


def enregistrer_au_registre(carte: dict, chemin: Path, registre: Path) -> None:
    """One line per model version: what it is, what it learnt from, which file."""
    lignes = json.loads(registre.read_text(encoding="utf-8")) if registre.exists() else []
    ligne = {
        "nom": carte["nom"],
        "version": carte["version"],
        "date_entrainement": carte["date_entrainement"],
        "fichier": chemin.name,
        "fichier_sha256": carte["fichier_sha256"],
        "famille": carte["descriptif"]["famille"],
        "copies": carte["descriptif"]["copies"],
        "empreinte_entrainement": carte["entrainement"]["empreinte_contenu"],
        "empreinte_gold": carte["lignage"].get("empreinte_gold"),
        "commit": carte["lignage"].get("commit"),
    }
    # Same hash or same file name: the file on disk is this one, the older line is stale.
    lignes = [
        x
        for x in lignes
        if x["fichier_sha256"] != ligne["fichier_sha256"] and x["fichier"] != ligne["fichier"]
    ] + [ligne]
    registre.parent.mkdir(parents=True, exist_ok=True)
    registre.write_text(
        json.dumps(lignes, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def charger_modele(chemin: Path | str) -> tuple[Any, dict[str, Any]]:
    """Reload a model and its card. Used at scoring time and in the integration test."""
    chemin = Path(chemin)
    modele = joblib.load(chemin)
    chemin_fiche = chemin.with_suffix(".json")
    fiche = json.loads(chemin_fiche.read_text(encoding="utf-8")) if chemin_fiche.exists() else {}
    return modele, fiche
