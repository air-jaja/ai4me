"""HTTP scoring service.

**The service does not decide.** It returns a probability and an expected value. The
cut-off belongs to the monthly batch, which alone holds the portfolio-wide ranking and the
available capacity (notebook sections 9 and 10).

Three routes, three distinct purposes:
    /health   the process answers
    /ready    the model is loaded and the service can actually serve
    /score    score one account

The /health versus /ready distinction is not cosmetic: a container can answer before it
has loaded its model. Conflating the two would route traffic to an instance unable to
serve.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException

from ..config import EFFICACITE_RETENTION
from ..packaging import charger_modele
from .scoring import preparer
from .service import reponse_scoring_unitaire

app = FastAPI(
    title="Scoring churn — aide à la décision",
    description=(
        "Estime la probabilité de résiliation d'un compte et sa valeur espérée. "
        "Ne renvoie aucune décision : la priorisation est établie par le lot mensuel."
    ),
    version="1.0.0",
)

_modele: Any = None
_fiche: dict[str, Any] = {}


@app.on_event("startup")
def charger_au_demarrage() -> None:
    """Load the model once, at startup, rather than on every request."""
    global _modele, _fiche
    chemin = Path(os.environ.get("CHURN_MODEL_PATH", "models/churn_model.joblib"))
    if chemin.exists():
        _modele, _fiche = charger_modele(chemin)


@app.get("/health")
def health() -> dict[str, str]:
    """The process answers. Does not imply the service is usable."""
    return {"statut": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    """The model is loaded: the service can actually serve."""
    if _modele is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé.")
    return {"statut": "pret", "version_modele": _fiche.get("version", "inconnue")}


@app.post("/score")
def score(compte: dict[str, Any]) -> dict[str, Any]:
    """Score one account. `valeur_vie_client_eur` is required for the expected value."""
    if _modele is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé.")
    if "valeur_vie_client_eur" not in compte:
        raise HTTPException(
            status_code=422,
            detail=(
                "`valeur_vie_client_eur` est requise : la valeur espérée ne peut pas "
                "être calculée sans la valeur du compte."
            ),
        )
    prepare = preparer(pd.DataFrame([compte]))
    prepare = prepare.drop(columns=[c for c in ("churn",) if c in prepare.columns])
    return reponse_scoring_unitaire(
        _modele,
        prepare,
        float(compte["valeur_vie_client_eur"]),
        version_modele=_fiche.get("version", "inconnue"),
        efficacite_retention=EFFICACITE_RETENTION,
    )


def instrumenter() -> None:
    """Expose /metrics for Prometheus, if the `observabilite` group is installed."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        return
    Instrumentator().instrument(app).expose(app)


instrumenter()
