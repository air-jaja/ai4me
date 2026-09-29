"""Stockage relationnel des scores et des exécutions.

Met en œuvre le modèle de stockage retenu au notebook § 3 : relationnel pour
l'exploitation courante, stockage objet pour les instantanés d'entraînement.

La table des scores porte la **version du modèle** qui les a produits. Sans cette
colonne, une dégradation observée après un réentraînement serait impossible à
rattacher à sa cause.
"""

from .entrepot import METADONNEES, creer_schema, ecrire_scores, lire_derniers_scores

__all__ = ["METADONNEES", "creer_schema", "ecrire_scores", "lire_derniers_scores"]
