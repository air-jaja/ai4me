"""Data governance: lifecycle, sensitivity classification, storage options.

Governance is the part of the project nobody sees and everybody assumes. Writing it down
turns implicit expectations - "we keep the data as long as needed" - into decisions with
an owner and a duration.
"""

from __future__ import annotations

import re

import pandas as pd

# --- Data lifecycle -----------------------------------------------------------------
# Each stage answers three questions: what happens, for how long, and who owns it. A
# stage without an owner is a stage nobody performs.
CYCLE_DE_VIE: tuple[dict[str, str], ...] = (
    {
        "etape": "1. Collecte",
        "contenu": "Extraction depuis les systèmes d'usage, de facturation et de support",
        "rythme": "Mensuel",
        "duree": "—",
        "responsable": "Équipe Data",
    },
    {
        "etape": "2. Ingestion",
        "contenu": "Lecture brute sans transformation, contrôle du schéma et des volumes",
        "rythme": "À chaque extraction",
        "duree": "—",
        "responsable": "Équipe Data",
    },
    {
        "etape": "3. Préparation",
        "contenu": "Nettoyage, typage, jointure catalogue, variables dérivées",
        "rythme": "À chaque extraction",
        "duree": "—",
        "responsable": "Équipe Data",
    },
    {
        "etape": "4. Instantané d'entraînement",
        "contenu": "Jeu figé, horodaté et empreinté, servant de référence reproductible",
        "rythme": "À chaque réentraînement (trimestriel)",
        "duree": "Conservé tant qu'une version de modèle l'utilise",
        "responsable": "Équipe Data",
    },
    {
        "etape": "5. Exploitation",
        "contenu": "Scoring mensuel, écriture des résultats dans le CRM",
        "rythme": "Mensuel",
        "duree": "—",
        "responsable": "Équipe Data / Ops CRM",
    },
    {
        "etape": "6. Conservation des scores",
        "contenu": "Historique nécessaire au suivi de dérive et à la mesure d'impact",
        "rythme": "Continu",
        "duree": "À arbitrer avec le DPO — point ouvert",
        "responsable": "DPO",
    },
    {
        "etape": "7. Archivage",
        "contenu": "Instantanés conservés pour audit et retour arrière",
        "rythme": "—",
        "duree": "Alignée sur la durée de vie des modèles actifs",
        "responsable": "Équipe Data",
    },
    {
        "etape": "8. Purge",
        "contenu": "Suppression automatisée au-delà de la durée retenue",
        "rythme": "Automatique",
        "duree": "—",
        "responsable": "Équipe Data / DPO",
    },
)


def table_cycle_de_vie() -> pd.DataFrame:
    """Lifecycle table, displayed in the notebook and submitted to the stakeholders."""
    return pd.DataFrame(CYCLE_DE_VIE).rename(
        columns={
            "etape": "Étape",
            "contenu": "Contenu",
            "rythme": "Rythme",
            "duree": "Durée de conservation",
            "responsable": "Responsable",
        }
    )


# --- Sensitivity classification -----------------------------------------------------
# GDPR-oriented reading. "Pseudonymised" is not "anonymous": an identifier that can be
# traced back to a customer through another table remains personal data.
SENSIBILITE: dict[str, tuple[str, str, str]] = {
    "client_id": (
        "Pseudonyme",
        "Identifiant réversible vers une entreprise cliente via le CRM",
        "Conservé pour la restitution, exclu des variables explicatives",
    ),
    "commentaire_csm": (
        "Donnée personnelle possible",
        "Texte libre pouvant nommer des personnes ou porter des jugements",
        "Exclue du modèle et du jeu gold ; non exportée hors du système source",
    ),
    "pays": (
        "Donnée d'entreprise",
        "Pays de facturation, peut servir de variable indirecte de discrimination",
        "Conservée, mais surveillée dans l'analyse d'équité",
    ),
    "secteur": (
        "Donnée d'entreprise",
        "Secteur d'activité, variable indirecte possible",
        "Conservée, surveillée dans l'analyse d'équité",
    ),
    "taille_entreprise": (
        "Donnée d'entreprise",
        "Segment de taille, corrélé à la valeur du compte",
        "Conservée, surveillée dans l'analyse d'équité",
    ),
    "revenu_mensuel_recurrent_eur": (
        "Donnée commerciale confidentielle",
        "Revenu d'un client identifiable : information sensible au sens contractuel",
        "Conservée en interne, jamais diffusée hors périmètre autorisé",
    ),
    "valeur_vie_client_eur": (
        "Donnée commerciale confidentielle",
        "Valorisation d'un client identifiable",
        "Utilisée en pondération de décision, jamais comme variable explicative",
    ),
    "groupe_experimentation": (
        "Donnée de process",
        "Appartenance à un test A/B : sans portée RGPD mais non métier",
        "Exclue du modèle, utile pour construire un groupe témoin",
    ),
}

# Patterns for a first-pass personal data scan in free-text fields. Deliberately narrow:
# the aim is to demonstrate the risk is real, not to build a detection engine.
MOTIFS_PERSONNELS: dict[str, str] = {
    "adresse e-mail": r"[\w\.\-]+@[\w\.\-]+\.\w{2,}",
    "numéro de téléphone": r"(?:\+33|0)\s?[1-9](?:[\s\.\-]?\d{2}){4}",
    "prénom ou nom cité": r"\b(?:M\.|Mme|Monsieur|Madame)\s+[A-ZÀ-Ý][a-zà-ÿ]+",
    "URL": r"https?://\S+",
}


def table_sensibilite(colonnes_presentes: list[str] | None = None) -> pd.DataFrame:
    """Sensitivity table: nature, rationale, treatment applied."""
    lignes = [
        {
            "Colonne": colonne,
            "Nature": nature,
            "Pourquoi c'est sensible": motif,
            "Traitement retenu": traitement,
        }
        for colonne, (nature, motif, traitement) in SENSIBILITE.items()
        if colonnes_presentes is None or colonne in colonnes_presentes
    ]
    return pd.DataFrame(lignes)


def scanner_texte_libre(serie: pd.Series, motifs: dict[str, str] | None = None) -> pd.DataFrame:
    """Count personal-data patterns in a free-text column.

    Turns an assumption into a measurement: instead of claiming that `commentaire_csm`
    *could* contain personal data, this reports how often it actually does.
    """
    motifs = motifs or MOTIFS_PERSONNELS
    texte = serie.dropna().astype(str)
    total = len(texte)
    lignes = []
    for libelle, motif in motifs.items():
        occurrences = int(texte.str.contains(motif, regex=True, na=False).sum())
        lignes.append(
            {
                "Motif recherché": libelle,
                "Occurrences": occurrences,
                "Part des champs renseignés": f"{occurrences / total:.2%}" if total else "—",
            }
        )
    return pd.DataFrame(lignes)


def exemples_anonymises(serie: pd.Series, n: int = 3, longueur: int = 60) -> list[str]:
    """Return truncated, redacted samples of a free-text column.

    Displaying raw free text in a deliverable would itself be a personal-data leak. The
    samples are therefore masked before being shown - the demonstration must not commit
    the offence it describes.
    """
    echantillon = serie.dropna().astype(str).head(n).tolist()
    masques = []
    for texte in echantillon:
        for motif in MOTIFS_PERSONNELS.values():
            texte = re.sub(motif, "[masqué]", texte)
        masques.append(texte[:longueur] + ("…" if len(texte) > longueur else ""))
    return masques


# --- Storage options ----------------------------------------------------------------
OPTIONS_STOCKAGE: tuple[dict[str, str], ...] = (
    {
        "Option": "Git seul",
        "Principe": "Les fichiers sont versionnés comme du code",
        "Volume adapté": "< 50 Mo par fichier",
        "Atout": "Aucune dépendance, historique complet, diff lisible",
        "Limite": "Le dépôt grossit à chaque version ; illisible au-delà de quelques Mo",
        "Retenu": "Oui, appliqué — pour les 3 CSV sources (≈ 2 Mo au total)",
    },
    {
        "Option": "Git-LFS",
        "Principe": "Git stocke un pointeur, le fichier part sur un serveur dédié",
        "Volume adapté": "Dizaines de Mo à quelques Go",
        "Atout": "Dépôt léger, intégré au flux Git habituel",
        "Limite": (
            "Dépendance côté client : sans git-lfs installé, le clone ne récupère "
            "que des pointeurs de 128 octets, sans erreur"
        ),
        "Retenu": (
            "Conservé pour les Parquet et les modèles sérialisés ; retiré des CSV, "
            "où il était surdimensionné et risqué pour un correcteur"
        ),
    },
    {
        "Option": "DVC",
        "Principe": "Versioning de données adossé à un stockage distant",
        "Volume adapté": "Go à To",
        "Atout": (
            "Lien explicite entre version de données et version de code, pipelines reproductibles"
        ),
        "Limite": "Outil supplémentaire à installer et à comprendre",
        "Retenu": "Cible si le jeu devient volumineux ou multi-instantanés",
    },
    {
        "Option": "Stockage objet (S3, MinIO, Azure Blob)",
        "Principe": "Fichiers immuables adressés par clé, versionnés côté serveur",
        "Volume adapté": "Illimité en pratique",
        "Atout": "Idéal pour des instantanés figés, coût faible, contrôle d'accès fin",
        "Limite": "Pas de diff, pas d'historique lisible sans convention de nommage",
        "Retenu": "Oui — pour les instantanés d'entraînement en Parquet",
    },
    {
        "Option": "Base relationnelle (PostgreSQL)",
        "Principe": "Données interrogeables par SQL, schéma contraint",
        "Volume adapté": "Millions de lignes",
        "Atout": "Requêtes, jointures, intégrité, accès concurrent",
        "Limite": "Ne versionne rien par nature : une mise à jour écrase l'état précédent",
        "Retenu": "Oui — pour les scores produits, pas pour les données d'entraînement",
    },
    {
        "Option": "Entrepôt analytique (BigQuery, Snowflake)",
        "Principe": "Stockage colonne distribué, calcul déporté",
        "Volume adapté": "To et au-delà",
        "Atout": "Passage à l'échelle, historisation native",
        "Limite": "Coût récurrent, latence de mise en place, surdimensionné ici",
        "Retenu": "Non — 5 000 lignes ne justifient pas cette brique",
    },
)


def comparer_stockage() -> pd.DataFrame:
    """Storage options compared on the criteria that actually decide the choice."""
    return pd.DataFrame(OPTIONS_STOCKAGE)
