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

# --- Phase 5 decision rules, fixed on 01/10/2026 before any result (choix § 7 bis) -----
ECART_STRATIFICATION_MAX_PTS = 1.0  # churn rate gap between train and test, in points
SEUIL_PSI_DECOUPAGE = 0.10  # per-variable stability between train and test
SEUIL_AUC_ADVERSE = 0.60  # a classifier must not tell train from test
SEUIL_P_PERMUTATION = 0.05  # the model must beat shuffled labels

# --- Phase 6 evaluation protocol, fixed on 02/10/2026 before any baseline result ---------
PLIS_VALIDATION = 5  # stratified folds...
REPETITIONS_VALIDATION = 5  # ...repeated: the same 25 folds as the phase 5 selection
PART_HAUT_CLASSEMENT = 0.10  # top of the ranking read for recall and precision
SEUIL_ERREUR_CALIBRATION = 0.05  # above it, phase 7 calibrates the retained model
VARIABLE_REGLE_METIER = "derniere_connexion_jours"  # what a CSM would rank by, without a model

# --- Experiment tracking (MLflow), phase 7 bloc 7.0 ----------------------------------------
# A local SQLite store, built from the project root as an ABSOLUTE path: with a relative
# `sqlite:///mlflow.db`, a notebook run from notebooks/ and a tool run from the root would
# write to two different stores without any error. MLFLOW_TRACKING_URI overrides it (tests,
# and the Docker server in phase 10). The registry needs a database: SQLite provides it.
DOSSIER_SUIVI = RACINE / "mlruns"
URI_SUIVI = f"sqlite:///{(DOSSIER_SUIVI / 'mlflow.db').as_posix()}"
ARTEFACTS_SUIVI = (DOSSIER_SUIVI / "artefacts").as_uri()
PREFIXE_EXPERIENCES = "churn-saas"
MODELE_REGISTRE = "churn-saas"
ALIAS_CANDIDAT = "challenger"  # best model so far, neither tuned nor calibrated
ALIAS_RETENU = "champion"  # reserved to the model retained at the end of phase 7


def _coeurs_paralleles() -> int:
    """Workers for parallel computations: the measured logical cores minus one.

    Read from the project input `config/ressources_poste.toml` (the development laptop),
    one core left free so the machine stays usable; CHURN_N_JOBS overrides it. Results do
    not depend on it - every model has a fixed seed - only durations do.
    """
    import os
    import tomllib

    if os.environ.get("CHURN_N_JOBS"):
        return max(1, int(os.environ["CHURN_N_JOBS"]))
    try:
        with open(RACINE / "config" / "ressources_poste.toml", "rb") as flux:
            coeurs = int(tomllib.load(flux)["poste"]["coeurs_logiques"])
    except (OSError, KeyError, ValueError):
        coeurs = os.cpu_count() or 2
    return max(1, coeurs - 1)


# --- Phase 7 decision rules, validated on 02/10/2026 BEFORE any comparison (rule 8) --------
# B1 - selection: a candidate replaces the logistic regression only if its PR-AUC gain,
# paired over the 25 shared folds, exceeds one standard deviation; on a tie, the simplest.
ORDRE_DE_SIMPLICITE = ("régression logistique", "forêt aléatoire", "xgboost")
# B2 - calibration: method chosen inside the folds on the calibration error, target below
# SEUIL_ERREUR_CALIBRATION.
METHODES_CALIBRATION = ("sigmoid", "isotonic")
# B4 - the single evaluation on the test part: every protocol metric, with bootstrap 95 %
# confidence intervals.
TIRAGES_BOOTSTRAP = 1000
NIVEAU_CONFIANCE = 0.95
# B5 - customer lifetime value model: linear regression on log value from pre-decision
# variables, against a regression forest; the forest is kept only if its gain in R²
# over 5 folds exceeds one standard deviation.
MODELES_VALEUR_VIE = ("régression linéaire", "forêt de régression")

# --- Phase 8 rules, validated on 03/10/2026 BEFORE any tuning computation (rule 8) ---------
# S1/P3 - overfitting: a combination whose training PR-AUC exceeds its validation PR-AUC by
# more than this gap is discarded.
SEUIL_ECART_SURAPPRENTISSAGE = 0.05
# S3 - nested cross-validation: selection optimism above this is reported and deducted.
SEUIL_OPTIMISME_SELECTION = 0.01
# S4 - learning curve of the retained configuration: final train-validation gap.
SEUIL_ECART_APPRENTISSAGE = 0.02
# P1 - within one standard deviation of the best, the most regularised (smallest C).
# P2 - the champion is replaced only by a paired gain above one standard deviation (as B1).
# P4 - resources: at equivalent performance (within one standard deviation), the cheapest;
# budgets for the monthly batch (5,000 accounts) and for one account through the API.
BUDGET_LOT_MENSUEL_S = 60.0
BUDGET_COMPTE_MS = 50.0

# One parallel layer only: a parallel search over parallel forests would run up to
# N_JOBS x N_JOBS tasks on N_JOBS cores (and, on Windows, trips joblib's memmapping cleanup).
N_JOBS = _coeurs_paralleles()

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
# Phase 5, blocs B and C: removed by the rules fixed on 01/10, measured on the training part.
# Constructed variables: no significant gain as a family (bloc B), the raw variables
# already carry what they say.
EXCLUES_SANS_APPORT = [
    "compte_sans_utilisateur_actif",
    "taux_couverture_fonc",
    "usage_par_actif",
    "tickets_par_actif",
]
# Under the decoys' floor for both models, removable without loss (bloc C).
EXCLUES_SOUS_LE_PLANCHER = ["pays"]
# The decoys measure the noise during selection, then leave the final model.
EXCLUES_LEURRES = ["couleur_theme_interface", "code_datacenter"]
EXCLUES_PAR_SELECTION = EXCLUES_SANS_APPORT + EXCLUES_SOUS_LE_PLANCHER + EXCLUES_LEURRES

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
