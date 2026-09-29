"""Activité 4 — Évaluation de la performance.

Trois niveaux de lecture, à ne jamais confondre :

    metriques.py  performance statistique — ce que vaut le modèle
    decision.py   règle de décision       — ce qu'on en fait
    impact.py     traduction métier       — ce que ça rapporte

Un modèle excellent dont les alertes ne changent rien au taux de rétention ne crée
aucune valeur. L'ordre de lecture va donc des métriques vers l'impact, jamais l'inverse.
"""

from .decision import prioriser, sensibilite_classement, seuil_par_compte
from .impact import mrr_a_risque, resume_impact
from .metriques import evaluer, intervalle_confiance_rappel

__all__ = [
    "evaluer",
    "intervalle_confiance_rappel",
    "seuil_par_compte",
    "prioriser",
    "sensibilite_classement",
    "mrr_a_risque",
    "resume_impact",
]
