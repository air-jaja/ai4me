"""Sérialisation du modèle et métadonnées de version.

Trois objets sont versionnés conjointement — code, données d'entraînement, modèle. Un
modèle reproductible à partir du seul code est une illusion si le jeu d'entraînement a
changé entre-temps (notebook § 10).
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
    """Métadonnées accompagnant obligatoirement chaque modèle mis en service."""

    nom: str
    version: str
    date_entrainement: str = field(default_factory=lambda: date.today().isoformat())
    empreinte_donnees: str = ""  # instantané utilisé, ex. churn_train_20260928
    hyperparametres: dict[str, Any] = field(default_factory=dict)
    metriques_validation: dict[str, float] = field(default_factory=dict)
    variables: list[str] = field(default_factory=list)
    variables_exclues: dict[str, str] = field(default_factory=dict)
    responsable_validation: str = ""
    version_python: str = field(default_factory=platform.python_version)

    def nom_fichier(self) -> str:
        return f"{self.nom}_v{self.version}_{self.date_entrainement.replace('-', '')}"


def sauvegarder_modele(modele: Any, fiche: FicheModele, dossier: Path | str = MODELES) -> Path:
    """Enregistre le modèle et sa fiche côte à côte, sous le même nom de base.

    Séparer les deux fichiers serait une erreur : la fiche doit rester lisible sans
    désérialiser le modèle, ce qui suppose d'avoir les mêmes versions de bibliothèques.
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
    """Recharge un modèle et sa fiche. Utilisé au scoring et au test d'intégration."""
    chemin = Path(chemin)
    modele = joblib.load(chemin)
    chemin_fiche = chemin.with_suffix(".json")
    fiche = json.loads(chemin_fiche.read_text(encoding="utf-8")) if chemin_fiche.exists() else {}
    return modele, fiche
