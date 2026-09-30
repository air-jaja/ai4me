"""Activity 1 - Data management.

Three refinement levels, the usual data engineering convention:

    BRONZE  raw data exactly as received, never modified
    SILVER  cleaned and normalised, faithful to the business, human readable
    GOLD    ready for learning: derived features added, forbidden columns removed,
            target separated

The silver -> gold boundary carries the heaviest decision of the project: leaking
columns are dropped there (notebook section 7).
"""

from .empreinte import (
    construire_manifeste,
    empreinte_donnees,
    manifeste_stable,
    verifier_manifeste,
)
from .gold import MOTIFS_EXCLUSION, construire_gold, separer_cible
from .gouvernance import comparer_stockage, table_cycle_de_vie, table_sensibilite
from .ingestion import charger_bronze, inventaire
from .schema import auditer_qualite, controler_jointure, decrire_schema
from .silver import construire_silver

__all__ = [
    # Ingestion and refinement levels
    "charger_bronze",
    "inventaire",
    "construire_silver",
    "construire_gold",
    "separer_cible",
    "MOTIFS_EXCLUSION",
    # Schema and quality
    "decrire_schema",
    "auditer_qualite",
    "controler_jointure",
    # Governance
    "table_cycle_de_vie",
    "table_sensibilite",
    "comparer_stockage",
    # Data versioning
    "empreinte_donnees",
    "construire_manifeste",
    "manifeste_stable",
    "verifier_manifeste",
]
