"""Activity 7 - Monitoring services.

    derive.py   detects the gap between current data and training data
    alertes.py  turns a gap into an action, with a named owner
    suivi.py    the monthly verdicts of M5, M8 and M9 against the reference profile
    simulation.py  demonstration batches, simulated and labelled as such (phase 11)

An indicator without a threshold is not monitored; a threshold without an attached action
is useless. The two modules are inseparable.
"""

from .alertes import REGLES_ALERTE, evaluer_alertes, table_regles
from .derive import (
    ks_deux_echantillons,
    profil_variable,
    psi,
    psi_categoriel,
    psi_contre_profil,
    rapport_derive,
)
from .exporteur import publier_lot
from .suivi import derive_combinee, ecart_volume, manquants_relatifs, mesures_du_mois

__all__ = [
    "psi",
    "psi_categoriel",
    "profil_variable",
    "psi_contre_profil",
    "ks_deux_echantillons",
    "rapport_derive",
    "REGLES_ALERTE",
    "table_regles",
    "evaluer_alertes",
    "publier_lot",
    "derive_combinee",
    "manquants_relatifs",
    "ecart_volume",
    "mesures_du_mois",
]
