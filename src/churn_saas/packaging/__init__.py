"""Activity 5 - Model packaging: artefacts and model card.

A model shipped without its card is an orphan artefact: nobody knows what data it learned
from, what it can do, or what it cannot. The model card is therefore produced **alongside**
the artefact, from the same metadata - never hand-written afterwards.
"""

from .artefacts import FicheModele, charger_modele, sauvegarder_modele
from .model_card import generer_model_card

__all__ = ["FicheModele", "sauvegarder_modele", "charger_modele", "generer_model_card"]
