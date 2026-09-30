"""Unit scoring response.

Returns a probability and an expected value, **never a decision**. The cut-off belongs to
the monthly batch, which has the portfolio-wide view the ranking requires.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import EFFICACITE_RETENTION


def reponse_scoring_unitaire(
    modele_churn: Any,
    compte_prepare: pd.DataFrame,
    valeur_vie_client: float,
    version_modele: str,
    efficacite_retention: float = EFFICACITE_RETENTION,
) -> dict[str, Any]:
    """Payload returned by the service for one account."""
    proba = float(modele_churn.predict_proba(compte_prepare)[:, 1][0])
    return {
        "proba_churn": proba,
        "valeur_vie_client_eur": float(valeur_vie_client),
        "valeur_esperee_eur": proba * float(valeur_vie_client) * efficacite_retention,
        "version_modele": version_modele,
        # Deliberately absent: no "decision" field. See the module docstring.
    }
