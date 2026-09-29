"""Traçabilité des expérimentations et registre de modèles (MLflow).

**Pourquoi MLflow malgré la sobriété affichée.** La convention de versioning décrite au
notebook § 10 — nommer les fichiers et tenir une fiche — fonctionne pour un modèle et un
opérateur. Elle ne survit ni à plusieurs réentraînements, ni à plusieurs personnes : rien
n'empêche d'écraser un artefact ou de perdre le lien entre un score et le modèle qui l'a
produit. MLflow outille cette convention sans la changer : mêmes objets, contrôle en plus.

Le dispositif reste optionnel : le notebook s'exécute sans lui.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..packaging.artefacts import FicheModele


@contextmanager
def experience(nom: str, uri_suivi: str | None = None) -> Iterator[Any]:
    """Ouvre une exécution MLflow. Sans MLflow installé, ne fait rien et n'échoue pas."""
    try:
        import mlflow
    except ImportError:
        yield None
        return

    if uri_suivi:
        mlflow.set_tracking_uri(uri_suivi)
    mlflow.set_experiment(nom)
    with mlflow.start_run() as execution:
        yield execution


def journaliser(
    modele: Any,
    fiche: FicheModele,
    metriques: dict[str, float],
    uri_suivi: str | None = None,
) -> str | None:
    """Enregistre modèle, hyperparamètres et métriques dans une exécution MLflow.

    Renvoie l'identifiant de l'exécution, ou None si MLflow n'est pas installé.
    """
    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        return None

    with experience(fiche.nom, uri_suivi) as execution:
        if execution is None:
            return None
        mlflow.log_params(fiche.hyperparametres)
        mlflow.log_metrics({k: float(v) for k, v in metriques.items()})
        mlflow.set_tags(
            {
                "version": fiche.version,
                "empreinte_donnees": fiche.empreinte_donnees,
                "responsable_validation": fiche.responsable_validation,
            }
        )
        mlflow.sklearn.log_model(modele, name="modele", registered_model_name=fiche.nom)
        return execution.info.run_id


def promouvoir(nom_modele: str, version: str, etape: str = "Production") -> None:
    """Promeut une version du registre vers une étape (Staging, Production).

    La promotion reste un **acte humain** : cette fonction est appelée après validation,
    jamais automatiquement à la fin d'un entraînement (notebook § 13).
    """
    import mlflow

    client = mlflow.MlflowClient()
    client.set_registered_model_alias(nom_modele, etape.lower(), version)
