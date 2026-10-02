"""Activity 3 - Modelling: baseline and model selection.

The baseline is not a fallback, it is the yardstick. Without it there is no way to claim a
more complex model adds anything - and a complex model that adds nothing costs
maintenance, explainability and compute.
"""

from .baseline import construire_baseline, construire_preprocesseur
from .selection import comparer, construire_candidat, grille_hyperparametres
from .sobriete import (
    CHARGE_PHASE5,
    CHARGE_PRODUCTION_ANNUELLE,
    EtapeDeCalcul,
    convertir_empreinte,
    estimer_charge,
    mesurer_temps,
    table_empreinte,
)

__all__ = [
    "construire_preprocesseur",
    "construire_baseline",
    "construire_candidat",
    "grille_hyperparametres",
    "comparer",
    # Compute footprint, measured and converted openly (CodeCarbon not used, 01/10/2026)
    "mesurer_temps",
    "estimer_charge",
    "convertir_empreinte",
    "table_empreinte",
    "EtapeDeCalcul",
    "CHARGE_PHASE5",
    "CHARGE_PRODUCTION_ANNUELLE",
]
