"""HTTP service: the risk of one account, on demand - never a decision.

The monthly batch decides (the list); the API informs: an account manager opening an
account in the CRM, or an event (critical ticket, late payment), asks for the current
score. Same model, same preparation, same labels and reasons as the list.

Configuration, by environment variables (docker-compose sets them, values in .env):
- CHURN_API_KEY: accepted key(s) for `X-API-Key`, comma-separated for rotation;
- CHURN_ALIASES, CHURN_MODELES: the champion is loaded BY ALIAS, its file hash checked;
- CHURN_CATALOGUE: the plan catalogue (price, SLA, quotas: without it scores drift from
  the batch's - register D-02);
- CHURN_DONNEES: the portfolio file, read once at startup for the explanations' baseline.
"""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, create_model

from ..config import EFFICACITE_RETENTION, FICHIER_CATALOGUE, FICHIER_COMPLET, MODELES
from .dictionnaire import ENTREES, harmoniser, vocabulaire
from .liste import LIBELLES, motif, tranche

TYPES = {"entier": int, "décimal": float, "texte": str}
AVERTISSEMENT = "Score indicatif : la priorité et l'action se lisent dans la liste du mois."


def _champ(v):
    description = f"{v.description} ({v.unite})" if v.unite else v.description
    type_ = TYPES[v.type] if v.obligatoire else TYPES[v.type] | None
    defaut = ... if v.obligatoire else None
    return type_, Field(defaut, title=v.libelle, description=description, examples=[v.exemple])


# Input schema generated from the data dictionary: what /docs shows is what the list uses.
CompteEntree = create_model("CompteEntree", **{v.colonne: _champ(v) for v in ENTREES})


class ScoreSortie(BaseModel):
    """Score of one account, with the operational list's labels."""

    client_id: str | None = Field(None, title=LIBELLES["client_id"])
    risque_pct: int = Field(
        title=LIBELLES["proba_pct"], description="Probabilité calibrée de départ, en %."
    )
    tranche_risque: str = Field(
        title=LIBELLES["tranche_risque"], description="Très élevé, Élevé, Modéré ou Faible."
    )
    probabilite: float = Field(
        title="Probabilité de départ", description="Valeur exacte, de 0 à 1."
    )
    gain_attendu_contact_eur: float = Field(
        title=LIBELLES["gain_eur"],
        description="Probabilité × valeur × efficacité − coût d'un contact.",
    )
    motif: str = Field(
        title=LIBELLES["motif"], description="Les trois principaux facteurs, avec leur sens."
    )
    modele: str = Field(
        title=LIBELLES["modele"], description="Nom et version du modèle en service."
    )
    avertissement: str = AVERTISSEMENT


etat: dict[str, Any] = {}


def _chemin(variable: str, defaut: Path) -> Path:
    return Path(os.environ.get(variable, str(defaut)))


def charger_etat() -> None:
    """Champion by alias (hash checked), catalogue, explanation baseline - once."""
    from ..features import executer_pipeline, parties_du_decoupage
    from ..packaging import charger_champion, lire_aliases

    aliases = _chemin("CHURN_ALIASES", MODELES.parent / "resultats" / "aliases_modeles.json")
    etat["modele"], etat["fiche"] = charger_champion(aliases, _chemin("CHURN_MODELES", MODELES))
    champion = lire_aliases(aliases)["champion"]
    etat["version"] = f"{champion['nom']} {champion['version']}"
    catalogue = _chemin("CHURN_CATALOGUE", FICHIER_CATALOGUE)
    etat["catalogue"] = pd.read_csv(catalogue, dtype=str, encoding="utf-8-sig")
    resultat = executer_pipeline(_chemin("CHURN_DONNEES", FICHIER_COMPLET), catalogue)
    etat["fond"] = parties_du_decoupage(resultat).X_entrainement
    etat["vocabulaire"] = vocabulaire(etat["fond"])
    from ..evaluation import moyennes_de_reference

    etat["moyennes"] = moyennes_de_reference(etat["modele"], etat["fond"])


@asynccontextmanager
async def cycle_de_vie(_app: FastAPI):
    try:
        charger_etat()
    except (FileNotFoundError, ValueError, KeyError, StopIteration) as erreur:  # /ready says why
        etat["erreur"] = str(erreur)
    yield


app = FastAPI(
    title="Scoring churn — aide à la décision",
    description=(
        "Risque de départ d'un compte, à la demande, avec ses trois principaux motifs. "
        "**Aucune décision** : la priorité et l'action se lisent dans la liste mensuelle. "
        "Guide : `docs/API.md`."
    ),
    version="1.1.0",
    lifespan=cycle_de_vie,
)


def verifier_cle(
    x_api_key: str | None = Header(None, description="Clé d'API (variable CHURN_API_KEY)."),
) -> None:
    cles = [c.strip() for c in os.environ.get("CHURN_API_KEY", "").split(",") if c.strip()]
    if not cles:
        raise HTTPException(status_code=503, detail="Aucune clé d'API configurée (CHURN_API_KEY).")
    if not x_api_key or not any(secrets.compare_digest(x_api_key, c) for c in cles):
        raise HTTPException(
            status_code=401, detail="Clé d'API absente ou invalide (en-tête X-API-Key)."
        )


@app.get("/health", summary="Le processus répond")
def health() -> dict[str, str]:
    """The process answers. Does not imply the service is usable."""
    return {"statut": "ok"}


@app.get("/ready", summary="Le modèle est chargé et le service peut répondre")
def ready() -> dict[str, Any]:
    """The champion is loaded: the service can actually serve."""
    if "modele" not in etat:
        raise HTTPException(
            status_code=503, detail=f"Modèle non chargé : {etat.get('erreur', 'démarrage')}"
        )
    return {
        "statut": "pret",
        "modele": etat["version"],
        "descriptif": etat["fiche"].get("descriptif", {}),
    }


@app.post(
    "/score",
    response_model=ScoreSortie,
    dependencies=[Depends(verifier_cle)],
    summary="Risque de départ d'un compte",
    responses={
        401: {"description": "Clé d'API absente ou invalide"},
        422: {"description": "Champ obligatoire manquant ou de mauvais type"},
        503: {"description": "Modèle non chargé, ou aucune clé configurée"},
    },
)
def score(compte: CompteEntree) -> ScoreSortie:  # type: ignore[valid-type]
    """Score one account with the model in service; never returns a decision."""
    from ..config import COUT_CONTACT_CSM_EUR
    from ..donnees import typer_pour_modele
    from ..evaluation import contributions_lineaires
    from .scoring import preparer

    if "modele" not in etat:
        raise HTTPException(status_code=503, detail="Modèle non chargé.")
    donnees = harmoniser(compte.model_dump(), etat["vocabulaire"])
    brut = pd.DataFrame([{k: (None if v is None else str(v)) for k, v in donnees.items()}])
    X = typer_pour_modele(
        preparer(brut, catalogue=etat["catalogue"]).drop(columns=["churn"], errors="ignore")
    )
    probabilite = float(etat["modele"].predict_proba(X)[:, 1][0])
    contributions, _ = contributions_lineaires(etat["modele"], X, moyennes=etat["moyennes"])
    valeur = float(donnees["valeur_vie_client_eur"])
    return ScoreSortie(
        client_id=donnees.get("client_id"),
        risque_pct=round(100 * probabilite),
        tranche_risque=tranche(probabilite),
        probabilite=probabilite,
        gain_attendu_contact_eur=round(
            probabilite * valeur * EFFICACITE_RETENTION - COUT_CONTACT_CSM_EUR, 2
        ),
        motif=motif(contributions.iloc[0], X.iloc[0]),
        modele=etat["version"],
    )


def instrumenter() -> None:
    """Expose /metrics for Prometheus, if the `observabilite` group is installed."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        return
    # Out of the OpenAPI contract: /metrics exists only where the observability group is
    # installed, and the contract must not depend on the environment that exports it.
    Instrumentator().instrument(app).expose(app, include_in_schema=False)


instrumenter()
