"""Activity 5 - Model packaging: artefacts and model card.

A model shipped without its card is an orphan artefact: nobody knows what data it learned
from, what it can do, or what it cannot. The model card is therefore produced **alongside**
the artefact, from the same metadata - never hand-written afterwards.
"""

from .artefacts import FicheModele, charger_modele, sauvegarder_modele
from .model_card import generer_model_card
from .suivi import (
    CLES_MLFLOW,
    charger,
    configurer_suivi,
    enregistrer,
    etiquettes_tracabilite,
    experience,
    journaliser,
    journaliser_modele,
    journaliser_protocole,
    nom_experience,
    promouvoir,
    tracer_donnees,
    uri_suivi,
)

__all__ = [
    "FicheModele",
    "sauvegarder_modele",
    "charger_modele",
    "generer_model_card",
    # Experiment tracking and registry (MLflow, phase 7 bloc 7.0) - optional
    "CLES_MLFLOW",
    "uri_suivi",
    "configurer_suivi",
    "nom_experience",
    "etiquettes_tracabilite",
    "journaliser_protocole",
    "journaliser_modele",
    "experience",
    "journaliser",
    "enregistrer",
    "charger",
    "promouvoir",
    "tracer_donnees",
]
