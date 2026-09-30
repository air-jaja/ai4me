"""Business translation of model performance.

Three levels the jury will want distinguished:

    EXPOSED    revenue lost if nothing is done
    COVERED    revenue the prioritisation actually reaches at a given capacity
               -> the only level the model is responsible for
    PRESERVED  revenue actually saved, which further depends on how good the actions are

Attributing the third level to the model overstates its contribution by a factor equal to
the inverse of retention effectiveness.
"""

from __future__ import annotations

import pandas as pd

from ..config import EFFICACITE_RETENTION


def mrr_a_risque(mrr: pd.Series, churn_reel: pd.Series) -> dict[str, float]:
    """Reference base: total revenue and revenue carried by churning accounts."""
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
    """Three-level table, each with the party accountable for it."""
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
