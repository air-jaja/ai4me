"""Activity 7 - Monitoring services.

    derive.py   detects the gap between current data and training data
    alertes.py  turns a gap into an action, with a named owner

An indicator without a threshold is not monitored; a threshold without an attached action
is useless. The two modules are inseparable.
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
