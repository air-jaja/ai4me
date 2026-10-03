"""Activity 3 - Modelling: baseline and model selection.

The baseline is not a fallback, it is the yardstick. Without it there is no way to claim a
more complex model adds anything - and a complex model that adds nothing costs
maintenance, explainability and compute.
"""

from .baseline import (
    RegleMetier,
    construire_baseline,
    construire_baseline_metier,
    construire_baseline_naive,
    construire_preprocesseur,
)
from .reglage import (
    ResultatReglage,
    construire_calibre,
    explorer_grille,
    optimisme_imbrique,
    regle_un_ecart_type,
    regler,
)
from .selection import (
    POIDS_POSITIFS,
    comparer,
    construire_candidat,
    construire_xgboost,
    grille_hyperparametres,
)
from .sobriete import (
    CHARGE_PHASE5,
    CHARGE_PRODUCTION_ANNUELLE,
    EtapeDeCalcul,
    annoncer_duree,
    convertir_empreinte,
    estimer_charge,
    estimer_duree,
    mesurer_temps,
    table_empreinte,
)
from .valeur_vie import (
    choisir_modele_valeur,
    comparer_modeles_valeur,
    construire_foret_valeur,
    construire_regression_valeur,
)
from .validation import (
    courbe_apprentissage,
    demontrer_fuite,
    tester_permutation,
    validation_adverse,
)

__all__ = [
    "construire_preprocesseur",
    "construire_baseline",
    # Phase 6: the simpler references the logistic regression must beat
    "construire_baseline_naive",
    "construire_baseline_metier",
    "RegleMetier",
    "construire_candidat",
    "grille_hyperparametres",
    "comparer",
    # Phase 7: third family, tuning, calibration
    "construire_xgboost",
    "POIDS_POSITIFS",
    "regler",
    "ResultatReglage",
    "construire_calibre",
    # Phase 8: tuning the retained model, overfitting watched
    "explorer_grille",
    "regle_un_ecart_type",
    "optimisme_imbrique",
    # Phase 7, rule B5: customer lifetime value of recent accounts
    "construire_regression_valeur",
    "construire_foret_valeur",
    "comparer_modeles_valeur",
    "choisir_modele_valeur",
    # Validating the prepared dataset and its split (phase 5)
    "validation_adverse",
    "tester_permutation",
    "courbe_apprentissage",
    "demontrer_fuite",
    # Compute footprint, measured and converted openly (CodeCarbon not used, 01/10/2026)
    "mesurer_temps",
    "estimer_charge",
    "convertir_empreinte",
    "estimer_duree",
    "annoncer_duree",
    "table_empreinte",
    "EtapeDeCalcul",
    "CHARGE_PHASE5",
    "CHARGE_PRODUCTION_ANNUELLE",
]
