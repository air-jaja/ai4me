"""Paramètres du projet, centralisés pour rester traçables et modifiables en un seul endroit.

Les valeurs marquées HYPOTHÈSE ne sont pas observables dans les données : elles sont
assumées comme telles devant le jury (voir notebook § 9).
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

GRAINE = 42
PART_TEST = 0.20

# --- Variables exclues, avec le motif de l'exclusion (notebook § 4 et § 7) ---
EXCLUES_FUITE = ["sante_compte_fin_periode"]  # postérieure à la décision
EXCLUES_IDENTIFIANT = ["client_id"]  # identifiant, aucun pouvoir prédictif
EXCLUES_RGPD = ["commentaire_csm"]  # texte libre, données personnelles
EXCLUES_ARTEFACT = ["groupe_experimentation"]  # artefact de process interne
EXCLUES_CIBLE_SECONDAIRE = ["valeur_vie_client_eur"]  # pondération de décision, jamais feature

CIBLE = "churn"
CIBLE_SECONDAIRE = "valeur_vie_client_eur"

# --- Hypothèses métier (notebook § 9) ---
EFFICACITE_RETENTION = 0.25  # HYPOTHÈSE — sensibilité testée de 0.15 à 0.40
COUT_CONTACT_CSM_EUR = 135.0  # HYPOTHÈSE — 1,5 h chargée + geste commercial pondéré
CAPACITE_MENSUELLE = 140  # HYPOTHÈSE de cadrage — à confirmer avec le commanditaire

# --- Seuils de surveillance (notebook § 12 et § 13) ---
SEUIL_PSI_ALERTE = 0.25
SEUIL_DEGRADATION_PR_AUC = 0.15  # baisse relative déclenchant un diagnostic
