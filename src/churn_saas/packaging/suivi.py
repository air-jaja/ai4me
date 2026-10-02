"""Experiment tracking and model registry (MLflow) - a journal and a showcase.

MLflow **links** what the project already holds as authoritative - the manifest for data,
`resultats/` for reference results, the non-regression tests for published figures - it
does not replace them. Tests check that what MLflow says matches those sources (rule 7).

Configuration (phase 7, bloc 7.0): a local SQLite store at an absolute path
(`config.URI_SUIVI`), overridden by `MLFLOW_TRACKING_URI` for the tests and, in phase 10,
for the Docker server. The registry uses aliases - `challenger` for the best model so
far, `champion` for the retained one - since MLflow 3 dropped stages.

Everything here is optional: without MLflow installed, the functions do nothing and do
not fail, so the CI and the notebooks run without it.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pandas as pd

from ..config import (
    ALIAS_CANDIDAT,
    MODELE_REGISTRE,
    PREFIXE_EXPERIENCES,
    RACINE,
    URI_SUIVI,
)
from .artefacts import FicheModele

# MLflow refuses accents in metric keys: the protocol's names map to ASCII keys.
CLES_MLFLOW: dict[str, str] = {
    "PR-AUC": "pr_auc",
    "ROC-AUC": "roc_auc",
    "rappel haut": "rappel_haut",
    "précision haut": "precision_haut",
    "Brier": "brier",
    "erreur de calibration": "erreur_calibration",
}


def uri_suivi() -> str:
    """The tracking store in use: the environment first, the project's store otherwise."""
    return os.environ.get("MLFLOW_TRACKING_URI") or URI_SUIVI


def configurer_suivi() -> Any | None:
    """Point MLflow at the project's store; None when MLflow is not installed."""
    try:
        import mlflow
    except ImportError:
        return None
    # Progress bars clutter tool and notebook outputs; they carry no information here.
    os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
    uri = uri_suivi()
    if uri.startswith("sqlite:///"):
        chemin = uri.removeprefix("sqlite:///")
        os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    return mlflow


def nom_experience(sujet: str) -> str:
    return f"{PREFIXE_EXPERIENCES}/{sujet}"


def etiquettes_tracabilite(
    phase: str, origine: str, manifeste: dict | None = None, **autres: str
) -> dict[str, str]:
    """Tags tying a run to the exact code and data it was obtained with."""
    etiquettes = {"phase": phase, "origine": origine, **autres}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        modifie = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        etiquettes |= {"commit": commit, "modifications_non_committees": str(bool(modifie))}
    except (OSError, subprocess.CalledProcessError):
        etiquettes["commit"] = "inconnu"
    if manifeste:
        jeux = manifeste.get("jeux_derives", {}).get("jeux", {})
        if "gold" in jeux:
            etiquettes["empreinte_gold"] = jeux["gold"]["empreinte_contenu"]
        if "decoupage" in manifeste:
            etiquettes["empreinte_comptes_test"] = manifeste["decoupage"]["empreinte_comptes_test"]
    return etiquettes


def journaliser_protocole(par_pli: pd.DataFrame, suffixe: str = "_cv") -> dict[str, float]:
    """Log the protocol's metrics into the active run: mean, spread, and each fold.

    Each fold is logged as a step of the same metric, so the MLflow interface draws the
    spread. Returns the mean metrics logged, under their MLflow keys.
    """
    mlflow = configurer_suivi()
    moyennes = {}
    for nom, cle in CLES_MLFLOW.items():
        if nom not in par_pli or par_pli[nom].isna().all():
            continue
        valeurs = par_pli[nom].astype(float)
        moyennes[f"{cle}{suffixe}"] = float(valeurs.mean())
        if mlflow is None:
            continue
        mlflow.log_metric(f"{cle}{suffixe}", float(valeurs.mean()))
        mlflow.log_metric(f"{cle}{suffixe}_ecart_type", float(valeurs.std()))
        for pli, valeur in enumerate(valeurs):
            mlflow.log_metric(f"{cle}{suffixe}_par_pli", float(valeur), step=pli)
    return moyennes


@contextmanager
def experience(nom: str, uri: str | None = None, run: str | None = None) -> Iterator[Any]:
    """Open an MLflow run in the named experience. Without MLflow it yields None."""
    if uri:
        os.environ["MLFLOW_TRACKING_URI"] = uri
    mlflow = configurer_suivi()
    if mlflow is None:
        yield None
        return
    mlflow.set_experiment(nom)
    with mlflow.start_run(run_name=run) as execution:
        yield execution


def journaliser(
    modele: Any,
    fiche: FicheModele,
    metriques: dict[str, float],
    uri_suivi: str | None = None,
) -> str | None:
    """Log model, hyperparameters and metrics into an MLflow run (packaging, phase 10).

    Returns the run id, or None when MLflow is not installed.
    """
    with experience(nom_experience(fiche.nom), uri_suivi) as execution:
        if execution is None:
            return None
        import mlflow
        import mlflow.sklearn

        mlflow.log_params(fiche.hyperparametres)
        mlflow.log_metrics({k: float(v) for k, v in metriques.items()})
        mlflow.set_tags(
            {
                "version": fiche.version,
                "empreinte_donnees": fiche.empreinte_donnees,
                "responsable_validation": fiche.responsable_validation,
            }
        )
        journaliser_modele(modele, fiche.exemple) if hasattr(fiche, "exemple") else (
            mlflow.sklearn.log_model(modele, name="modele", serialization_format="cloudpickle")
        )
        return execution.info.run_id


def journaliser_modele(modele: Any, X_exemple: pd.DataFrame, nom: str = "modele") -> None:
    """Log a fitted pipeline - preprocessing included - with its signature and an example.

    The whole pipeline is logged, never the bare estimator: a model registered without
    its imputation and encoding could not score prepared data (training-serving skew).
    The signature is inferred on rows holding missing values, so the registry accepts
    them at prediction time.

    Serialised with cloudpickle: MLflow 3's default (skops) rejects the numpy and
    xgboost types these pipelines hold unless each is declared trusted. The trust model
    is the one of the joblib artefacts already used by the project: models are only ever
    loaded from the project's own store.
    """
    mlflow = configurer_suivi()
    if mlflow is None:
        return
    from mlflow import sklearn as mlflow_sklearn
    from mlflow.models import infer_signature

    exemple = pd.concat([X_exemple[X_exemple.isna().any(axis=1)].head(25), X_exemple.head(25)])
    signature = infer_signature(exemple, modele.predict_proba(exemple)[:, 1])
    mlflow_sklearn.log_model(
        modele,
        name=nom,
        signature=signature,
        input_example=X_exemple.head(3),
        serialization_format="cloudpickle",
    )


def tracer_donnees(
    gold: pd.DataFrame,
    journal: pd.DataFrame,
    manifeste: dict,
    profil: pd.DataFrame | None = None,
) -> str | None:
    """One run per materialisation: the data lineage every model run can point to.

    The gold dataset is attached as a run input whose digest is the manifest's own
    fingerprint - a test checks they match. The chain's journal (rows and columns at each
    level, contract status) and the reference profile for the phase 11 drift monitoring
    go in as artefacts. Returns the run id, or None without MLflow.
    """
    mlflow = configurer_suivi()
    if mlflow is None:
        return None
    empreinte = manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"]
    mlflow.set_experiment(nom_experience("donnees"))
    with mlflow.start_run(run_name=f"materialisation {empreinte[:12]}") as run:
        mlflow.set_tags(etiquettes_tracabilite("donnees", "tools/materialiser.py", manifeste))
        mlflow.log_param("version_donnees", manifeste.get("version", "v1.0"))
        for _, etape in journal.iterrows():
            cle = "".join(c if c.isalnum() else "_" for c in str(etape["niveau"]))
            mlflow.log_metric(f"lignes_{cle}", float(etape["lignes"]))
            mlflow.log_metric(f"colonnes_{cle}", float(etape["colonnes"]))
        # MLflow keeps at most 36 characters of a dataset digest: the full fingerprint
        # stays in the tags, the digest carries its prefix.
        jeu = mlflow.data.from_pandas(gold, name="gold", digest=empreinte[:32])
        mlflow.log_input(jeu, context="gold")
        mlflow.log_table(journal.astype(str), "journal_de_la_chaine.json")
        if profil is not None:
            mlflow.log_table(profil.reset_index().astype(str), "profil_de_reference.json")
        return run.info.run_id


def enregistrer(
    run_id: str,
    alias: str = ALIAS_CANDIDAT,
    nom_modele: str = MODELE_REGISTRE,
    artefact: str = "modele",
) -> str:
    """Register the run's model and point the alias at the new version; returns it."""
    mlflow = configurer_suivi()
    version = mlflow.register_model(f"runs:/{run_id}/{artefact}", nom_modele).version
    mlflow.MlflowClient().set_registered_model_alias(nom_modele, alias, version)
    return str(version)


def charger(alias: str = ALIAS_CANDIDAT, nom_modele: str = MODELE_REGISTRE) -> Any:
    """Load the registered model behind an alias, as a scikit-learn object.

    The scikit-learn flavour keeps `predict_proba`: the project's decision needs
    probabilities, which the generic pyfunc flavour would turn into classes.
    """
    configurer_suivi()
    from mlflow import sklearn as mlflow_sklearn

    return mlflow_sklearn.load_model(f"models:/{nom_modele}@{alias}")


def promouvoir(nom_modele: str, version: str, alias: str = ALIAS_CANDIDAT) -> None:
    """Point an alias at a registry version (`challenger`, then `champion`).

    MLflow 3 replaced stages (Staging, Production) by aliases. Promotion stays a **human
    act**: called after validation, never automatically at the end of a training run.
    """
    mlflow = configurer_suivi()
    mlflow.MlflowClient().set_registered_model_alias(nom_modele, alias, version)
