"""Activity 1 - Data management.

Three refinement levels, the usual data engineering convention:

    BRONZE  raw data exactly as received, never modified
    SILVER  cleaned and normalised, faithful to the business, human readable
    GOLD    ready for learning: derived features added, forbidden columns removed,
            target separated

The silver -> gold boundary carries the heaviest decision of the project: leaking
columns are dropped there (notebook section 7).
"""

from .gold import construire_gold, separer_cible
from .ingestion import charger_bronze, inventaire
from .silver import construire_silver

__all__ = [
    "charger_bronze",
    "inventaire",
    "construire_silver",
    "construire_gold",
    "separer_cible",
]
