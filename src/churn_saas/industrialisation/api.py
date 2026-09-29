"""Service HTTP de scoring.

**Le service ne décide pas.** Il renvoie une probabilité et une valeur espérée. La
coupure relève du lot mensuel, qui seul dispose du classement de l'ensemble du
portefeuille et de la capacité disponible (notebook § 9 et § 10).

Trois routes, trois usages distincts :
    /health   le processus répond
    /ready    le modèle est chargé et le service peut réellement servir
    /score    scoring d'un compte

La distinction /health et /ready n'est pas cosmétique : un conteneur peut répondre
avant d'avoir chargé son modèle. Confondre les deux ferait basculer du trafic vers une
instance incapable de servir.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException

from ..config import EFFICACITE_RETENTION
from ..industrialisation.scoring import preparer
from ..industrialisation.service import reponse_scoring_unitaire
from ..packaging.artefacts import charger_modele

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
    """Charge le modèle une fois, au démarrage, et non à chaque requête."""
    global _modele, _fiche
    chemin = Path(os.environ.get("CHURN_MODEL_PATH", "models/churn_model.joblib"))
    if chemin.exists():
        _modele, _fiche = charger_modele(chemin)


@app.get("/health")
def health() -> dict[str, str]:
    """Le processus répond. N'implique pas que le service soit utilisable."""
    return {"statut": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    """Le modèle est chargé : le service peut réellement servir."""
    if _modele is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé.")
    return {"statut": "pret", "version_modele": _fiche.get("version", "inconnue")}


@app.post("/score")
def score(compte: dict[str, Any]) -> dict[str, Any]:
    """Score un compte. `valeur_vie_client_eur` est requise pour la valeur espérée."""
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
    """Expose /metrics pour Prometheus, si le groupe `observabilite` est installé."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        return
    Instrumentator().instrument(app).expose(app)


instrumenter()
