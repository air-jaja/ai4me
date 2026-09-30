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
    charger_manifeste,
    construire_manifeste,
    ecrire_manifeste,
    empreinte_donnees,
    empreinte_fichier,
    manifeste_stable,
    verifier_manifeste,
)
from .gold import MOTIFS_EXCLUSION, construire_gold, separer_cible, table_exclusions
from .gouvernance import (
    comparer_stockage,
    exemples_anonymises,
    scanner_texte_libre,
    table_cycle_de_vie,
    table_sensibilite,
)
from .ingestion import charger_bronze, inventaire
from .schema import auditer_qualite, controler_jointure, decrire_schema
from .silver import (
    construire_silver,
    nettoyer_decimal_texte,
    normaliser_cle,
    parser_dates_multiformat,
)

__all__ = [
    # Ingestion and refinement levels
    "charger_bronze",
    "inventaire",
    "construire_silver",
    "construire_gold",
    "separer_cible",
    "MOTIFS_EXCLUSION",
    # Cleaning primitives, reused at scoring time and shown in the notebooks
    "nettoyer_decimal_texte",
    "parser_dates_multiformat",
    "normaliser_cle",
    # Schema and quality
    "decrire_schema",
    "auditer_qualite",
    "controler_jointure",
    # Governance
    "table_cycle_de_vie",
    "table_sensibilite",
    "comparer_stockage",
    "scanner_texte_libre",
    "exemples_anonymises",
    "table_exclusions",
    # Data versioning
    "empreinte_donnees",
    "empreinte_fichier",
    "construire_manifeste",
    "ecrire_manifeste",
    "charger_manifeste",
    "manifeste_stable",
    "verifier_manifeste",
]
