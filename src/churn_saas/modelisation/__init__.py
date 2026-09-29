"""Activité 3 — Modélisation : baseline et sélection du modèle.

La baseline n'est pas un modèle de repli, c'est l'étalon. Sans elle, il est impossible de
dire qu'un modèle plus complexe apporte quoi que ce soit — et un modèle complexe qui
n'apporte rien coûte en maintenance, en explicabilité et en calcul.
"""

from .baseline import construire_baseline, construire_preprocesseur
from .selection import comparer, construire_candidat, grille_hyperparametres

__all__ = [
    "construire_preprocesseur",
    "construire_baseline",
    "construire_candidat",
    "grille_hyperparametres",
    "comparer",
]
