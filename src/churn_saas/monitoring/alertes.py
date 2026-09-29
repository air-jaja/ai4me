"""Règles d'alerte : indicateur, seuil, action déclenchée, responsable.

Chaque ligne ferme la boucle de décision exigée par le référentiel (notebook § 12).
Un tableau de bord sans destinataire d'action ne produit aucune décision.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RegleAlerte:
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
        "Rappel au point de fonctionnement",
        "technique",
        "< cible métier",
        "révision de la capacité ou du modèle",
        "Équipe Data + CSM",
    ),
    RegleAlerte(
        "PSI sur variables clés",
        "dérive",
        "> 0,25",
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
        "> 10 % sur une variable clé",
        "blocage du scoring et alerte",
        "Pipeline (automatique)",
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
    """Tableau des règles, à afficher tel quel dans le notebook."""
    return pd.DataFrame([vars(r) for r in REGLES_ALERTE])


def evaluer_alertes(mesures: dict[str, bool]) -> pd.DataFrame:
    """Confronte des mesures booléennes aux règles et liste les actions à déclencher."""
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
