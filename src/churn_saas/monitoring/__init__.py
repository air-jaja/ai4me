"""Activity 7 - Monitoring services.

    derive.py   detects the gap between current data and training data
    alertes.py  turns a gap into an action, with a named owner
    suivi.py    the monthly verdicts of M5, M8 and M9 against the reference profile
    reentrainement.py  which data a retraining learns from, and when it is due (M2-M4)
    simulation.py  demonstration batches, simulated and labelled as such (phase 11)

An indicator without a threshold is not monitored; a threshold without an attached action
is useless. The two modules are inseparable.
"""

from .alertes import REGLES_ALERTE, evaluer_alertes, table_regles
from .derive import (
    ks_deux_echantillons,
    parts_selon_profil,
    profil_variable,
    psi,
    psi_categoriel,
    psi_contre_profil,
    rapport_derive,
)
from .exporteur import publier_lot, publier_suivi
from .reentrainement import decider_reentrainement, selectionner_donnees_reentrainement
from .simulation import (
    completer_lot,
    comptes_reels,
    injecter_derive,
    injecter_derive_forte,
    simuler_issues,
)
from .suivi import (
    couverture_revenu,
    derive_combinee,
    ecart_volume,
    manquants_relatifs,
    mesures_du_mois,
    mesures_du_trimestre,
    pr_auc_en_production,
    rappel_segment,
    retention_contre_temoin,
)

__all__ = [
    "psi",
    "psi_categoriel",
    "profil_variable",
    "psi_contre_profil",
    "parts_selon_profil",
    "ks_deux_echantillons",
    "rapport_derive",
    "REGLES_ALERTE",
    "table_regles",
    "evaluer_alertes",
    "publier_lot",
    "publier_suivi",
    "derive_combinee",
    "manquants_relatifs",
    "ecart_volume",
    "mesures_du_mois",
    "comptes_reels",
    "completer_lot",
    "injecter_derive",
    "injecter_derive_forte",
    "simuler_issues",
    "couverture_revenu",
    "rappel_segment",
    "retention_contre_temoin",
    "pr_auc_en_production",
    "mesures_du_trimestre",
    "selectionner_donnees_reentrainement",
    "decider_reentrainement",
]
