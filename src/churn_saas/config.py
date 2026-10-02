"""Project parameters, centralised so they stay traceable and editable in one place.

Values marked HYPOTHESIS are not observable in the data: they are owned as assumptions in
front of the jury (notebook section 9).
"""

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DONNEES_BRUTES = RACINE / "data" / "raw"
DONNEES_TRAITEES = RACINE / "data" / "processed"
MODELES = RACINE / "models"
RAPPORTS = RACINE / "reports"

FICHIER_COMPLET = DONNEES_BRUTES / "churn_saas_complet.csv"
FICHIER_ECHANTILLON = DONNEES_BRUTES / "churn_saas_echantillon.csv"
FICHIER_CATALOGUE = DONNEES_BRUTES / "catalogue_plans.csv"

# Project inputs describing the machine that runs it, and the energy hypotheses applied to
# its measured compute times (tools/ressources_calcul.py, `make ressources`).
FICHIER_RESSOURCES = RACINE / "config" / "ressources_poste.toml"

# Fixed seed: reproducibility is an acceptance criterion, not a nicety.
GRAINE = 42
PART_TEST = 0.20

# --- Excluded columns, each with its own rationale (notebook sections 4 and 7) -------
# The motives are distinct and not interchangeable: the grid separates ethics from
# technical preparation, so one blanket justification would satisfy neither.
EXCLUES_FUITE = ["sante_compte_fin_periode"]  # computed after the decision
EXCLUES_IDENTIFIANT = ["client_id"]  # identifier, no predictive power
EXCLUES_RGPD = ["commentaire_csm"]  # free text, personal data risk
EXCLUES_ARTEFACT = ["groupe_experimentation"]  # internal process artefact
EXCLUES_CIBLE_SECONDAIRE = ["valeur_vie_client_eur"]  # decision weight, never a feature
# Added in phase 4. Neither is forbidden in principle: both are redundant, and one of them
# could not be encoded meaningfully as it stood.
# Duplicate -> the column already carrying the same information.
EXCLUES_DOUBLON = {
    "fonctionnalites_incluses": "fonctionnalites_total",  # exact catalogue copy
    "taux_activation": "taux_adoption_pct",  # same ratio, scaled by 100 (phase 4)
}
EXCLUES_DATE_BRUTE = ["date_souscription"]  # one category per day; anciennete_mois carries it
# Phase 5, arbitrage 2: each takes a single value per subscription plan, so `plan` already
# carries all of it. Kept, they gave the model the same four-valued information six times.
EXCLUES_ATTRIBUT_FORMULE = [
    "prix_mensuel_par_siege_eur",
    "sla_reponse_h",
    "quota_stockage_go",
    "support_dedie",
    "fonctionnalites_total",
]

CIBLE = "churn"
CIBLE_SECONDAIRE = "valeur_vie_client_eur"

# --- Business assumptions (notebook section 9) --------------------------------------
# Common factor across every account: it shifts the absolute gain estimate but not the
# ranking. That is what makes the decision rule robust to this uncertainty.
EFFICACITE_RETENTION = 0.25  # HYPOTHESIS - sensitivity tested from 0.15 to 0.40
COUT_CONTACT_CSM_EUR = 135.0  # HYPOTHESIS - 1.5 loaded hours + weighted commercial gesture
CAPACITE_MENSUELLE = 140  # HYPOTHESIS - framing assumption, to confirm with the sponsor

# --- Monitoring thresholds (notebook sections 12 and 13) ----------------------------
SEUIL_PSI_ALERTE = 0.25
SEUIL_DEGRADATION_PR_AUC = 0.15  # relative drop triggering a diagnosis
