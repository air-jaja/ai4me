"""Data dictionary of one account as the services receive it - the single source of truth.

Technical name (the CRM export column, the JSON key: stable, no spaces nor accents) ->
business label, description, type, unit, example. The API schemas are generated from it,
the operational list shows the same labels, and the documentation reads it: they cannot
drift apart. The outputs' labels are `LIBELLES` (industrialisation/liste.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variable:
    colonne: str
    libelle: str
    description: str
    type: str  # "entier", "décimal", "texte"
    unite: str
    exemple: object
    obligatoire: bool = False  # a missing value is imputed, as in training


ENTREES: tuple[Variable, ...] = (
    Variable(
        "client_id",
        "Compte",
        "Identifiant du compte dans le CRM, renvoyé tel quel.",
        "texte",
        "",
        "CLI-004593",
        False,
    ),
    Variable(
        "jour_souscription",
        "Jour de souscription",
        "Jour de la semaine de la souscription.",
        "texte",
        "",
        "Mardi",
    ),
    Variable("secteur", "Secteur", "Secteur d'activité du client.", "texte", "", "Santé", False),
    Variable(
        "taille_entreprise",
        "Taille d'entreprise",
        "TPE, PME, ETI ou Grand compte.",
        "texte",
        "",
        "PME",
    ),
    Variable(
        "plan",
        "Formule souscrite",
        "Formule du catalogue (Starter, Pro, Business, Enterprise).",
        "texte",
        "",
        "Starter",
    ),
    Variable(
        "anciennete_mois", "Ancienneté", "Mois depuis la souscription.", "entier", "mois", 8, False
    ),
    Variable(
        "sieges_souscrits", "Sièges souscrits", "Nombre de licences payées.", "entier", "sièges", 12
    ),
    Variable(
        "utilisateurs_actifs",
        "Utilisateurs actifs",
        "Utilisateurs connectés sur les 30 derniers jours.",
        "entier",
        "utilisateurs",
        7,
    ),
    Variable(
        "taux_adoption_pct",
        "Adoption des licences",
        "Part des sièges réellement utilisés.",
        "décimal",
        "%",
        58.3,
    ),
    Variable(
        "connexions_30j",
        "Connexions (30 j)",
        "Connexions sur les 30 derniers jours.",
        "entier",
        "connexions",
        41,
    ),
    Variable(
        "heures_usage_30j",
        "Heures d'usage (30 j)",
        "Temps d'usage cumulé sur 30 jours.",
        "décimal",
        "heures",
        63.5,
    ),
    Variable(
        "fonctionnalites_utilisees",
        "Fonctionnalités utilisées",
        "Fonctionnalités utilisées au moins une fois.",
        "entier",
        "fonctionnalités",
        6,
    ),
    Variable(
        "nb_integrations",
        "Intégrations actives",
        "Connecteurs actifs vers d'autres outils du client.",
        "entier",
        "intégrations",
        0,
    ),
    Variable(
        "derniere_connexion_jours",
        "Jours depuis la dernière connexion",
        "Jours écoulés depuis la dernière connexion d'un utilisateur.",
        "entier",
        "jours",
        30,
    ),
    Variable(
        "tickets_support_90j",
        "Tickets de support (90 j)",
        "Tickets ouverts sur 90 jours.",
        "entier",
        "tickets",
        6,
    ),
    Variable(
        "delai_reponse_support_h",
        "Délai de réponse du support",
        "Délai moyen de première réponse.",
        "décimal",
        "heures",
        9.5,
        False,
    ),
    Variable(
        "csat", "Satisfaction (CSAT)", "Note de satisfaction de 1 à 5.", "entier", "sur 5", 3, False
    ),
    Variable(
        "retards_paiement_12m",
        "Retards de paiement (12 mois)",
        "Factures payées en retard sur 12 mois.",
        "entier",
        "retards",
        1,
    ),
    Variable(
        "revenu_mensuel_recurrent_eur",
        "Revenu mensuel",
        "Revenu récurrent mensuel ; reconstruit depuis le catalogue s'il manque.",
        "décimal",
        "€ par mois",
        1188.0,
        False,
    ),
    Variable(
        "valeur_vie_client_eur",
        "Valeur client estimée",
        "Valeur vie du compte : nécessaire au gain attendu d'un contact.",
        "décimal",
        "€",
        18400.0,
        True,
    ),
)


def colonnes_obligatoires() -> list[str]:
    return [v.colonne for v in ENTREES if v.obligatoire]


def par_colonne() -> dict[str, Variable]:
    return {v.colonne: v for v in ENTREES}


CATEGORIELLES = ("jour_souscription", "secteur", "taille_entreprise", "plan")


def vocabulaire(reference) -> dict[str, dict[str, str]]:
    """Canonical spelling of each category, learnt from the training rows."""
    import pandas as pd

    return {
        colonne: {
            str(v).strip().lower(): v for v in pd.Series(reference[colonne]).dropna().unique()
        }
        for colonne in CATEGORIELLES
        if colonne in reference
    }


def harmoniser(enregistrement: dict, vocabulaire_reference: dict[str, dict[str, str]]) -> dict:
    """One account's categories spelt as in training ('PRO', ' pro ' -> 'Pro').

    The batch harmonises letter case from the batch itself; a single account has no batch
    to learn from, and 'PRO' would reach the model as an unseen category - a different
    score from the list's for the same account (found on 04/10/2026, register D-09).
    """
    harmonise = dict(enregistrement)
    for colonne, correspondances in vocabulaire_reference.items():
        valeur = harmonise.get(colonne)
        if isinstance(valeur, str):
            harmonise[colonne] = correspondances.get(valeur.strip().lower(), valeur)
    return harmonise
