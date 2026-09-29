"""Traduction métier de la performance.

Trois niveaux, que le jury cherchera à distinguer :

    EXPOSÉ    ce qui part si rien n'est fait
    COUVERT   ce que la priorisation permet d'atteindre à capacité donnée
              -> le seul niveau dont le modèle est responsable
    PRÉSERVÉ  ce qui est réellement sauvé, qui dépend en outre de l'efficacité des actions

Attribuer le troisième niveau au modèle surestime son apport d'un facteur égal à
l'inverse de l'efficacité de rétention.
"""

from __future__ import annotations

import pandas as pd

from ..config import EFFICACITE_RETENTION


def mrr_a_risque(mrr: pd.Series, churn_reel: pd.Series) -> dict[str, float]:
    """Assiette de référence : revenu total et revenu porté par les comptes qui résilient."""
    mrr = pd.to_numeric(mrr, errors="coerce")
    churn = pd.Series(churn_reel).astype(int)
    total = float(mrr.sum())
    expose = float(mrr[churn == 1].sum())
    return {
        "mrr_total_eur": total,
        "mrr_expose_eur": expose,
        "part_exposee_pct": round(100 * expose / total, 1) if total else float("nan"),
    }


def resume_impact(
    mrr: pd.Series,
    churn_reel: pd.Series,
    a_traiter: pd.Series,
    efficacite_retention: float = EFFICACITE_RETENTION,
) -> pd.DataFrame:
    """Tableau des trois niveaux, avec la responsabilité associée à chacun."""
    mrr = pd.to_numeric(mrr, errors="coerce")
    churn = pd.Series(churn_reel).astype(int)
    traite = pd.Series(a_traiter).astype(bool)

    expose = float(mrr[churn == 1].sum())
    couvert = float(mrr[(churn == 1) & traite].sum())
    preserve = couvert * efficacite_retention

    return pd.DataFrame(
        [
            {
                "niveau": "MRR exposé",
                "montant_eur": round(expose, 0),
                "definition": "revenu des comptes qui résilient, si rien n'est fait",
                "responsable": "aucun — constat de départ",
            },
            {
                "niveau": "MRR couvert",
                "montant_eur": round(couvert, 0),
                "definition": "revenu exposé effectivement atteint par la priorisation",
                "responsable": "le modèle et la règle de décision",
            },
            {
                "niveau": "MRR préservé",
                "montant_eur": round(preserve, 0),
                "definition": f"revenu réellement sauvé (hypothèse : {efficacite_retention:.0%})",
                "responsable": "les équipes Customer Success",
            },
        ]
    )
