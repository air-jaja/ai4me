"""Demonstration batches for the phase 11 monitoring - simulated, and labelled as such.

No production batch exists yet, and the test part may not be read again. The monthly
monitoring is therefore shown on batches built from the training part only (decision S1
to S7, 04/10/2026, docs/00.README_choix_methodologiques.md): the sample's training
accounts, completed by resampling, with a documented drift injected in the second month.
They prove the mechanics - computations, alerts, actions - never the model's performance.
"""

from __future__ import annotations

from ..config import GRAINE, RACINE

# Decision S1 to S7, validated by the project owner on 04/10/2026 before any implementation.
TAILLE_LOT_SIMULE = 5_000  # S2: portfolio size
GRAINE_SIMULATION = GRAINE  # S2: recorded seed
MOIS_SIMULES = ("mois_1_sans_derive", "mois_2_avec_derive")  # S3
# S4: one scenario per rule. M5: disengagement; M8: collection incident; M9: nothing injected.
DERIVE_CONNEXION = {"variable": "derniere_connexion_jours", "part": 0.30, "facteur": 2.0}
DERIVE_MANQUANTS = {"variable": "delai_reponse_support_h", "part": 0.25}
# S5: simulated outcomes three months later.
REDUCTION_RISQUE_CONTACT = 0.25  # the retention efficacy hypothesis (R1)
PART_TEMOIN_SIMULE = 0.10  # the control group share of the list (phase 10)
DOSSIER_SIMULATION = RACINE / "data" / "simulation"  # S7: versioned, never data/raw
MENTION = "SIMULÉ — démonstration"  # S7: on every simulated file and report
