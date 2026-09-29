"""Service de scoring unitaire.

Renvoie une probabilité et une valeur espérée, **jamais une décision**. La coupure relève
du lot mensuel, qui dispose de la vue d'ensemble nécessaire au classement.

L'esquisse FastAPI est fournie à titre d'illustration ; la fonction `reponse_scoring_unitaire`
est, elle, testable sans serveur.
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
    """Charge utile renvoyée par le service pour un compte."""
    proba = float(modele_churn.predict_proba(compte_prepare)[:, 1][0])
    return {
        "proba_churn": proba,
        "valeur_vie_client_eur": float(valeur_vie_client),
        "valeur_esperee_eur": proba * float(valeur_vie_client) * efficacite_retention,
        "version_modele": version_modele,
        # Absence volontaire : pas de champ "decision". Voir docstring du module.
    }


ESQUISSE_API = """
from fastapi import FastAPI
import pandas as pd

from churn_saas.industrialisation.scoring import preparer
from churn_saas.industrialisation.service import reponse_scoring_unitaire
from churn_saas.packaging.artefacts import charger_modele

app = FastAPI(title="Scoring churn — aide a la decision")
modele, fiche = charger_modele("models/churn_model_v1.0_20260928.joblib")


@app.post("/score-churn")
def score_churn(payload: dict):
    compte = preparer(pd.DataFrame([payload]))
    return reponse_scoring_unitaire(
        modele, compte, payload["valeur_vie_client_eur"], fiche["version"]
    )
"""
