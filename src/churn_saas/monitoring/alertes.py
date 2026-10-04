"""Alert rules: indicator, threshold, triggered action, owner.

Each row closes the decision loop required by the certification grid (notebook section 12).
A dashboard with no action owner produces no decision.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Phase 11 defaults, validated by the project owner on 04/10/2026 before any implementation
# (rule 8; docs/00.README_choix_methodologiques.md, M1 to M10). Kept here, not in config.py:
# config.py belongs to every tool's identity, and a monitoring setting must not invalidate
# the recorded results.
CIBLE_COUVERTURE_REVENU = 0.50  # M1: share of the at-risk MRR the monthly list must cover
FREQUENCE_REENTRAINEMENT_MOIS = 3  # M3: quarterly, and earlier on a qualified alert
FENETRE_REENTRAINEMENT_MOIS = 12  # M4: sliding window of training data
# M5: the four strongest variables of the phase 9 permutation importance (R10).
VARIABLES_CLES = (
    "derniere_connexion_jours",
    "anciennete_mois",
    "nb_integrations",
    "tickets_support_90j",
)
SEUIL_PSI_VARIABLE_CLE = 0.25  # M5: one key variable above it...
SEUIL_PSI_MODERE = 0.10  # ...or NB_VARIABLES_PSI_MODERE model variables above this one...
NB_VARIABLES_PSI_MODERE = 3
SEUIL_PSI_SCORE = 0.10  # ...or the score distribution above this one
FACTEUR_MANQUANTS = 2.0  # M8: missing share above twice the training share
ECART_VOLUME_SIGNALES = 0.30  # M9: gap in flagged accounts against the previous month
SEGMENTS_SURVEILLES = (("pays", "Suisse"),)  # M7: phase 9 fairness exception (R9, R12)


@dataclass(frozen=True)
class RegleAlerte:
    """One monitoring rule. Frozen: rules are configuration, not mutable state."""

    indicateur: str
    nature: str
    seuil: str
    action: str
    responsable: str


REGLES_ALERTE: tuple[RegleAlerte, ...] = (
    RegleAlerte(
        "PR-AUC en production",
        "technique",
        "baisse > 15 % vs référence",
        "diagnostic puis réentraînement",
        "Équipe Data",
    ),
    RegleAlerte(
        "Couverture du revenu à risque",
        "métier",
        "< 50 % du MRR des comptes partis",
        "révision de la capacité ou du modèle",
        "Équipe Data + CSM",
    ),
    RegleAlerte(
        "Dérive des entrées et du score (PSI)",
        "dérive",
        "> 0,25 sur une variable clé, ou > 0,10 sur trois variables, ou > 0,10 sur le score",
        "qualification de l'alerte puis retour aux données",
        "Équipe Data",
    ),
    RegleAlerte(
        "Volume de comptes signalés",
        "volumétrie",
        "écart > 30 % vs mois précédent",
        "contrôle qualité des données d'entrée",
        "Équipe Data",
    ),
    RegleAlerte(
        "Taux de manquants à l'entrée",
        "qualité",
        "> 2 × le taux d'entraînement, sur une variable",
        "avertissement, scoring maintenu ; qualification de la collecte",
        "Équipe Data",
    ),
    RegleAlerte(
        "Rappel sur le segment Suisse",
        "équité",
        "< 0,8 × rappel global, intervalle excluant le rappel global (critère R9)",
        "revue du segment avec les CSM, sans correction automatique",
        "Équipe Data + CSM",
    ),
    RegleAlerte(
        "Rétention des comptes traités",
        "métier",
        "non significative vs témoin",
        "remise en cause de l'utilité de l'outil",
        "Commanditaire",
    ),
    RegleAlerte(
        "Retours de faux positifs CSM",
        "métier",
        "volume anormal",
        "révision du point de fonctionnement",
        "CSM + Équipe Data",
    ),
)


def table_regles() -> pd.DataFrame:
    """Rule table, displayed as-is in the notebook."""
    return pd.DataFrame([vars(r) for r in REGLES_ALERTE])


def evaluer_alertes(mesures: dict[str, bool]) -> pd.DataFrame:
    """Match boolean measurements against the rules and list the actions to trigger."""
    lignes = []
    for regle in REGLES_ALERTE:
        declenchee = bool(mesures.get(regle.indicateur, False))
        lignes.append(
            {
                "indicateur": regle.indicateur,
                "seuil": regle.seuil,
                "declenchee": declenchee,
                "action": regle.action if declenchee else "—",
                "responsable": regle.responsable if declenchee else "—",
            }
        )
    return pd.DataFrame(lignes)
