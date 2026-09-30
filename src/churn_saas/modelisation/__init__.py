"""Activity 3 - Modelling: baseline and model selection.

The baseline is not a fallback, it is the yardstick. Without it there is no way to claim a
more complex model adds anything - and a complex model that adds nothing costs
maintenance, explainability and compute.
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
