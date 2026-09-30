"""Alert rules: indicator, threshold, triggered action, owner.

Each row closes the decision loop required by the certification grid (notebook section 12).
A dashboard with no action owner produces no decision.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


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
