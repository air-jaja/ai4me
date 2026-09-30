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


def sauvegarder_modele(modele: Any, fiche: FicheModele, dossier: Path | str = MODELES) -> Path:
    """Write the model and its card side by side, under the same base name.

    Keeping them in separate files is deliberate: the card must stay readable without
    deserialising the model, which would require matching library versions.
    """
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    base = fiche.nom_fichier()
    chemin_modele = dossier / f"{base}.joblib"
    joblib.dump(modele, chemin_modele)
    (dossier / f"{base}.json").write_text(
        json.dumps(asdict(fiche), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return chemin_modele


def charger_modele(chemin: Path | str) -> tuple[Any, dict[str, Any]]:
    """Reload a model and its card. Used at scoring time and in the integration test."""
    chemin = Path(chemin)
    modele = joblib.load(chemin)
    chemin_fiche = chemin.with_suffix(".json")
    fiche = json.loads(chemin_fiche.read_text(encoding="utf-8")) if chemin_fiche.exists() else {}
    return modele, fiche
