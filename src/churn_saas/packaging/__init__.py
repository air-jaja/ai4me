"""Activité 5 — Packaging du modèle : artefacts et fiche modèle.

Un modèle livré sans sa fiche est un artefact orphelin : personne ne sait sur quelles
données il a appris, ce qu'il sait faire, ni ce qu'il ne sait pas faire. La fiche modèle
(*model card*) est donc produite **en même temps** que l'artefact, à partir des mêmes
métadonnées — jamais rédigée après coup à la main.
"""

from .artefacts import FicheModele, charger_modele, sauvegarder_modele
from .model_card import generer_model_card

__all__ = ["FicheModele", "sauvegarder_modele", "charger_modele", "generer_model_card"]
