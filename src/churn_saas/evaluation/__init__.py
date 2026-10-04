"""Activity 4 - Performance evaluation.

Three reading levels, never to be conflated:

    metriques.py  statistical performance - what the model is worth
    decision.py   decision rule           - what we do with it
    impact.py     business translation    - what it earns

An excellent model whose alerts change nothing to retention creates no value. Reading
therefore goes from metrics towards impact, never the other way round.
"""

from .decision import (
    appliquer_regle,
    distribution_seuils,
    part_rentable_selon_hypotheses,
    prioriser,
    sensibilite_classement,
    seuil_par_compte,
    stabilite_liste,
)
from .explicabilite import (
    contributions_lineaires,
    expliquer_compte,
    expliquer_par_contributions,
    motif_lisible,
    moyennes_de_reference,
)
from .impact import mrr_a_risque, resume_impact
from .metriques import evaluer, intervalle_confiance_rappel
from .protocole import (
    METRIQUES,
    ResultatProtocole,
    comparer_a_la_reference,
    erreur_calibration,
    evaluer_selon_protocole,
    mesurer,
    plis_du_protocole,
    rappel_precision_haut,
    resumer,
    selectionner,
)
from .valeur_vie import diagnostiquer_valeur_vie, valeur_encode_l_issue

__all__ = [
    # Phase 9: decision rule R3, stability R4
    "appliquer_regle",
    "distribution_seuils",
    "part_rentable_selon_hypotheses",
    "stabilite_liste",
    # Explainability (B6, option C): exact linear contributions in production, SHAP for analysis
    "contributions_lineaires",
    "moyennes_de_reference",
    "expliquer_par_contributions",
    "expliquer_compte",
    "motif_lisible",
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
    # Phase 7, rule B1
    "comparer_a_la_reference",
    "selectionner",
]
