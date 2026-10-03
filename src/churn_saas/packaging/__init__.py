"""Activity 5 - Model packaging: artefacts and model card.

A model shipped without its card is an orphan artefact: nobody knows what data it learned
from, what it can do, or what it cannot. The model card is therefore produced **alongside**
the artefact, from the same metadata - never hand-written afterwards.
"""

from .artefacts import (
    FicheModele,
    charger_modele,
    empreinte_entrainement,
    enregistrer_au_registre,
    sauvegarder_modele,
)
from .dependances import decrire_modele, modules_utilises
from .model_card import generer_model_card
from .suivi import (
    CLES_IDENTITE_MODELE,
    CLES_MLFLOW,
    PERIMETRE_RESULTATS,
    activer_experience,
    charger,
    configurer_suivi,
    dependances_du_modele,
    durees_des_runs,
    emplacement_artefacts,
    empreinte_code,
    empreinte_protocole,
    enregistrer,
    enregistrer_si_nouveau,
    environnement_du_modele,
    etiquettes_tracabilite,
    experience,
    fichiers_du_perimetre,
    identite_execution,
    journaliser,
    journaliser_modele,
    journaliser_protocole,
    nom_experience,
    promouvoir,
    run_existant,
    tracer_donnees,
    uri_suivi,
)
from .versions import (
    a_conserver,
    charger_champion,
    incrementer,
    lire_aliases,
    majeure,
    retour_arriere,
)
from .versions import promouvoir as promouvoir_modele

__all__ = [
    "FicheModele",
    "sauvegarder_modele",
    "charger_modele",
    "generer_model_card",
    "empreinte_entrainement",
    "enregistrer_au_registre",
    # Versioning and rollback (phase 10)
    "incrementer",
    "majeure",
    "promouvoir_modele",
    "retour_arriere",
    "charger_champion",
    "lire_aliases",
    "a_conserver",
    # What a result depends on, what a model is (03/10/2026)
    "modules_utilises",
    "decrire_modele",
    # Experiment tracking and registry (MLflow, phase 7 bloc 7.0) - optional
    "CLES_MLFLOW",
    "uri_suivi",
    "configurer_suivi",
    "nom_experience",
    "etiquettes_tracabilite",
    "journaliser_protocole",
    "journaliser_modele",
    "dependances_du_modele",
    "environnement_du_modele",
    "experience",
    "journaliser",
    "enregistrer",
    "charger",
    "promouvoir",
    "tracer_donnees",
    # Bloc 7.0 bis: one artefact location, idempotent runs, measured durations
    "emplacement_artefacts",
    "activer_experience",
    "run_existant",
    "enregistrer_si_nouveau",
    "CLES_IDENTITE_MODELE",
    "durees_des_runs",
    # A1: one execution identity shared by every MLflow tool
    "empreinte_protocole",
    "empreinte_code",
    "fichiers_du_perimetre",
    "PERIMETRE_RESULTATS",
    "identite_execution",
]
