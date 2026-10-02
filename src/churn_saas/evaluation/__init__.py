"""Activity 4 - Performance evaluation.

Three reading levels, never to be conflated:

    metriques.py  statistical performance - what the model is worth
    decision.py   decision rule           - what we do with it
    impact.py     business translation    - what it earns

An excellent model whose alerts change nothing to retention creates no value. Reading
therefore goes from metrics towards impact, never the other way round.
"""

from .decision import prioriser, sensibilite_classement, seuil_par_compte
from .impact import mrr_a_risque, resume_impact
from .metriques import evaluer, intervalle_confiance_rappel
from .protocole import (
    METRIQUES,
    ResultatProtocole,
    erreur_calibration,
    evaluer_selon_protocole,
    mesurer,
    plis_du_protocole,
    rappel_precision_haut,
    resumer,
)
from .valeur_vie import diagnostiquer_valeur_vie, valeur_encode_l_issue

__all__ = [
    "evaluer",
    "intervalle_confiance_rappel",
    "seuil_par_compte",
    "prioriser",
    "sensibilite_classement",
    "mrr_a_risque",
    "resume_impact",
    # Does the lifetime value carry the outcome? (arbitrage 3, phase 5)
    "diagnostiquer_valeur_vie",
    "valeur_encode_l_issue",
    # Evaluation protocol, fixed before the baselines were run (phase 6)
    "METRIQUES",
    "plis_du_protocole",
    "rappel_precision_haut",
    "erreur_calibration",
    "mesurer",
    "evaluer_selon_protocole",
    "ResultatProtocole",
    "resumer",
]
