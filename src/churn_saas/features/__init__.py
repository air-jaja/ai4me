"""Activité 2 — Construction et contrôle des features.

Deux responsabilités distinctes, volontairement séparées :

    construction.py  fabrique les variables dérivées
    controle.py      vérifie qu'elles sont légitimes et utilisables

Le contrôle n'est pas une formalité. Une variable construite peut réintroduire une fuite
sans que personne ne s'en aperçoive : un ratio calculé à partir d'une colonne postérieure
à la décision reste postérieur à la décision.
"""

from .construction import ajouter_ratios_usage
from .controle import controler_schema, detecter_fuite_suspecte, verifier_leurres

__all__ = [
    "ajouter_ratios_usage",
    "controler_schema",
    "detecter_fuite_suspecte",
    "verifier_leurres",
]
