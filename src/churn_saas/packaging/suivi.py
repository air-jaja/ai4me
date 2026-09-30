"""Experiment tracking and model registry (MLflow).

**Why MLflow despite the stated sobriety.** The naming convention described in notebook
section 10 - name the files, keep a card - works for one model and one operator. It
survives neither several retrainings nor several people: nothing prevents overwriting an
artefact or losing the link between a score and the model that produced it. MLflow tools
that convention without changing it: same objects, plus control.

The mechanism stays optional: the notebook runs without it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..packaging.artefacts import FicheModele


@contextmanager
def experience(nom: str, uri_suivi: str | None = None) -> Iterator[Any]:
    """Open an MLflow run. With MLflow absent it does nothing and does not fail."""
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
    """Log model, hyperparameters and metrics into an MLflow run.

    Returns the run id, or None when MLflow is not installed.
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
    """Promote a registry version to a stage (Staging, Production).

    Promotion stays a **human act**: this function is called after validation, never
    automatically at the end of a training run (notebook section 13).
    """
    import mlflow

    client = mlflow.MlflowClient()
    client.set_registered_model_alias(nom_modele, etape.lower(), version)
