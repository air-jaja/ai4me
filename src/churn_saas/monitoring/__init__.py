"""Activité 7 — Services de monitoring.

    derive.py   détecte l'écart entre les données courantes et celles d'entraînement
    alertes.py  transforme un écart en action, avec un responsable nommé

Un indicateur sans seuil ne se surveille pas ; un seuil sans action associée ne sert à
rien. Les deux modules sont donc indissociables.
"""

from .alertes import REGLES_ALERTE, evaluer_alertes, table_regles
from .derive import ks_deux_echantillons, psi, rapport_derive

__all__ = [
    "psi",
    "ks_deux_echantillons",
    "rapport_derive",
    "REGLES_ALERTE",
    "table_regles",
    "evaluer_alertes",
]
