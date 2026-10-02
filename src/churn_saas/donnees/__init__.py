"""Activity 1 - Data management.

Three refinement levels, the usual data engineering convention:

    BRONZE  raw data exactly as received, never modified
    SILVER  cleaned and normalised, faithful to the business, human readable
    GOLD    ready for learning: derived features added, forbidden columns removed,
            target separated

`profilage.py` measures what the data actually contain, which is what decides the
preparation. `qualite.py` holds the data contract every batch must pass, at training and
at scoring time alike. The pipeline composing the three levels lives in activity 2, since it ends
with the gold dataset and its derived variables.

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
    racine_projet,
    verifier_manifeste,
)
from .gold import (
    MOTIFS_EXCLUSION,
    Decoupage,
    construire_gold,
    decouper_entrainement_test,
    resume_decoupage,
    separer_cible,
    table_exclusions,
    typer_pour_modele,
)
from .gouvernance import (
    comparer_stockage,
    exemples_anonymises,
    scanner_texte_libre,
    table_cycle_de_vie,
    table_sensibilite,
)
from .ingestion import charger_bronze, inventaire
from .profilage import (
    bornes_valeurs_extremes,
    manquants_structurels,
    mecanisme_manquants,
    profil_distributions,
    profil_doublons,
    profil_manquants,
    resume_profilage,
)
from .qualite import (
    BLOQUANT,
    CONFORME,
    SURVEILLANCE,
    colonnes_attendues_au_scoring,
    exiger_contrat,
    referentiel_modalites,
    statut_global,
    verifier_contrat,
)
from .reconstruction import REGLES_RECONSTRUCTION, reconstruire_valeurs_deterministes
from .schema import auditer_qualite, controler_jointure, decrire_schema
from .silver import (
    construire_silver,
    nettoyer_decimal_texte,
    normaliser_cle,
    normaliser_modalites,
    parser_dates_multiformat,
    pertes_de_conversion,
    silver_lisible,
    typer_colonnes_catalogue,
)

__all__ = [
    # Ingestion and refinement levels
    "charger_bronze",
    "inventaire",
    "construire_silver",
    "silver_lisible",
    "construire_gold",
    "separer_cible",
    # Training / test split, set aside once (phase 5)
    "decouper_entrainement_test",
    "resume_decoupage",
    "Decoupage",
    "typer_pour_modele",
    "MOTIFS_EXCLUSION",
    # Cleaning primitives, reused at scoring time and shown in the notebooks
    "nettoyer_decimal_texte",
    "parser_dates_multiformat",
    "normaliser_cle",
    "normaliser_modalites",
    "pertes_de_conversion",
    "typer_colonnes_catalogue",
    # Deterministic reconstruction, row by row (phase 4)
    "reconstruire_valeurs_deterministes",
    "REGLES_RECONSTRUCTION",
    # Data contract, run identically at training and at scoring time
    "verifier_contrat",
    "exiger_contrat",
    "colonnes_attendues_au_scoring",
    "statut_global",
    "referentiel_modalites",
    "CONFORME",
    "SURVEILLANCE",
    "BLOQUANT",
    # Profiling
    "profil_manquants",
    "profil_doublons",
    "profil_distributions",
    "mecanisme_manquants",
    "manquants_structurels",
    "resume_profilage",
    "bornes_valeurs_extremes",
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
    "racine_projet",
    "verifier_manifeste",
]
