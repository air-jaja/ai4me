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
    FICHIER_RESSOURCES,
    MODELE_REGISTRE,
    N_JOBS,
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


def emplacement_artefacts(uri: str | None = None) -> str | None:
    """Where artefacts go: beside the store in use, as an absolute location.

    Left to MLflow, artefacts land in a `mlruns/` folder relative to the CURRENT directory:
    a notebook run from notebooks/ and a tool run from the root would scatter models in
    two places, and tests would write theirs into the project. Placing them beside the
    SQLite file keeps one store per database - the project's, or a test's temporary one.
    """
    uri = uri or uri_suivi()
    if not uri.startswith("sqlite:///"):
        return None  # a tracking server (phase 10) decides for itself
    from pathlib import Path

    return (Path(uri.removeprefix("sqlite:///")).parent / "artefacts").as_uri()


def activer_experience(nom: str) -> str | None:
    """Make `nom` the active experiment, creating it with the absolute artefact location."""
    mlflow = configurer_suivi()
    if mlflow is None:
        return None
    existante = mlflow.get_experiment_by_name(nom)
    identifiant = (
        existante.experiment_id
        if existante
        else mlflow.create_experiment(nom, artifact_location=emplacement_artefacts())
    )
    mlflow.set_experiment(experiment_id=identifiant)
    return identifiant


def run_existant(nom: str, etiquettes: dict[str, str], nom_run: str | None = None) -> str | None:
    """The id of a finished run of experiment `nom` carrying these tags, if any.

    What makes a replay idempotent: the same result, on the same data, under the same
    protocol, is recorded once.
    """
    mlflow = configurer_suivi()
    if mlflow is None or mlflow.get_experiment_by_name(nom) is None:
        return None
    filtre = ["attributes.status = 'FINISHED'"]
    filtre += [f"tags.`{cle}` = '{valeur}'" for cle, valeur in etiquettes.items()]
    if nom_run:
        filtre.append(f"attributes.run_name = '{nom_run}'")
    trouves = mlflow.search_runs(experiment_names=[nom], filter_string=" and ".join(filtre))
    return None if trouves.empty else str(trouves.iloc[0]["run_id"])


# The code that PRODUCES results (bloc 7.0 bis, refined 03/10/2026): data preparation,
# variables, models, evaluation, and the configuration. Left out on purpose: tracking and
# packaging (packaging/), serving and monitoring (industrialisation/, monitoring/), the
# notebook helpers, and figures (features/graphiques.py) - changing them changes no figure.
PERIMETRE_RESULTATS = ("config.py", "donnees", "features", "modelisation", "evaluation")
HORS_PERIMETRE = ("features/graphiques.py",)


def fichiers_du_perimetre(origine: str | None = None) -> list:
    """The source files whose change may change a result produced by `origine`.

    The package's result-producing code, plus the tool that produced the result - and
    no other tool: correcting MLflow logging, a figure or an unrelated tool no longer
    invalidates fifteen minutes of recorded computations.
    """
    paquet = RACINE / "src" / "churn_saas"
    fichiers = []
    for element in PERIMETRE_RESULTATS:
        chemin = paquet / element
        fichiers += [chemin] if chemin.is_file() else sorted(chemin.rglob("*.py"))
    # `__init__.py` files only list what a package exports: adding a figure to an
    # interface changes no result (it invalidated every recorded result once, 03/10/2026).
    fichiers = [
        f
        for f in fichiers
        if f.relative_to(paquet).as_posix() not in HORS_PERIMETRE and f.name != "__init__.py"
    ]
    if origine and (RACINE / origine).is_file():
        fichiers.append(RACINE / origine)
    return sorted(fichiers)


def empreinte_code(origine: str | None = None) -> str:
    """Fingerprint of the code that produces a result (see `fichiers_du_perimetre`).

    A commit identifies committed code only; this fingerprint also tells two runs apart
    when the working tree holds uncommitted changes. Line endings are normalised, so a
    Windows checkout and a Linux one agree.
    """
    import hashlib

    condense = hashlib.sha256()
    for fichier in fichiers_du_perimetre(origine):
        condense.update(fichier.relative_to(RACINE).as_posix().encode())
        condense.update(fichier.read_bytes().replace(b"\r\n", b"\n"))
    return condense.hexdigest()[:16]


def empreinte_protocole() -> str:
    """Fingerprint of the evaluation protocol and decision rules read from the configuration.

    The seed, the folds, the top share, the thresholds, the selection rules: change any of
    them and every measured result may change. N_JOBS is left out on purpose - with fixed
    seeds it changes durations, never results.
    """
    import hashlib
    import json

    from .. import config

    noms = sorted(
        n
        for n in dir(config)
        if n.isupper()
        and n not in {"N_JOBS"}
        and isinstance(getattr(config, n), (int, float, str, tuple, list))
        and not str(getattr(config, n)).startswith(("sqlite:", "file:"))
    )
    contenu = json.dumps({n: getattr(config, n) for n in noms}, sort_keys=True, default=str)
    return hashlib.sha256(contenu.encode()).hexdigest()[:16]


def identite_execution(etiquettes: dict[str, str], **parametres: object) -> str:
    """One identity for a tracked computation, shared by every MLflow tool.

    Same code, same data, same protocol, same tool options: the same results. Both
    `retracer_mlflow.py` and `pipeline_mlflow.py` skip a computation whose identity is
    already recorded, and replay it only with --forcer (bloc 7.0 bis, A1).
    """
    import hashlib
    import json

    composantes = {
        "empreinte_code": etiquettes.get("empreinte_code", ""),
        "empreinte_gold": etiquettes.get("empreinte_gold", ""),
        "empreinte_protocole": etiquettes.get("empreinte_protocole", ""),
        "parametres": {k: str(v) for k, v in sorted(parametres.items())},
    }
    return hashlib.sha256(json.dumps(composantes, sort_keys=True).encode()).hexdigest()[:16]


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
    etiquettes["n_jobs"] = str(N_JOBS)
    etiquettes["empreinte_code"] = empreinte_code(origine)
    etiquettes["empreinte_protocole"] = empreinte_protocole()
    try:
        import tomllib

        with open(FICHIER_RESSOURCES, "rb") as flux:
            poste = tomllib.load(flux)["poste"]
        etiquettes |= {
            "poste_processeur": poste["processeur"],
            "poste_coeurs_logiques": str(poste["coeurs_logiques"]),
        }
    except (OSError, KeyError):
        pass
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
    activer_experience(nom)
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


def dependances_du_modele(modele: Any) -> list[str]:
    """The packages a logged model needs, pinned to the installed versions (optimisation B2).

    Left to infer them, MLflow exports the whole uv project and then looks for pip at every
    logged model: 1 to 5 s each on the development laptop, with a warning when pip is
    absent from a uv environment. The model's needs are known: the libraries its pipeline
    is made of, at the versions the lock file installed.
    """
    from importlib.metadata import PackageNotFoundError, version

    paquets = ["scikit-learn", "pandas", "numpy", "scipy", "cloudpickle"]
    if "xgboost" in repr(modele).lower():
        paquets.append("xgboost-cpu")
    epingles = []
    for paquet in paquets:
        try:
            epingles.append(f"{paquet}=={version(paquet)}")
        except PackageNotFoundError:
            continue
    return epingles


def environnement_du_modele(modele: Any) -> dict:
    """The model's full environment, declared - so MLflow infers nothing at all (B2).

    Declaring the pip requirements alone was not enough: MLflow still built a conda file
    around them and looked for pip's own version, absent from a uv environment - 10 s on
    the development laptop at the first logged model, and the "Failed to resolve installed
    pip version" warning at every one. With the whole environment given, it looks for
    nothing (0.4 s instead of 3.4 s here for the first model).
    """
    import sys

    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    return {
        "name": "churn-saas",
        "channels": ["conda-forge"],
        "dependencies": [f"python={version}", "pip", {"pip": dependances_du_modele(modele)}],
    }


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
        conda_env=environnement_du_modele(modele),
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
    # One run per version of the data: a re-materialisation of the same gold adds nothing.
    deja = run_existant(nom_experience("donnees"), {"empreinte_gold": empreinte})
    if deja:
        return deja
    activer_experience(nom_experience("donnees"))
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
        # Plain objects, not pandas 3's `str` dtype: MLflow selects text columns as `object`,
        # which pandas now warns will stop matching `str` columns.
        mlflow.log_table(journal.astype(str).astype(object), "journal_de_la_chaine.json")
        if profil is not None:
            mlflow.log_table(
                profil.reset_index().astype(str).astype(object), "profil_de_reference.json"
            )
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


# What makes two models "the same": the code that built them (fingerprint of the sources,
# valid with or without uncommitted changes), the data, and the configuration.
CLES_IDENTITE_MODELE = ("empreinte_code", "empreinte_gold", "empreinte_protocole", "configuration")


def enregistrer_si_nouveau(
    run_id: str, alias: str = ALIAS_CANDIDAT, nom_modele: str = MODELE_REGISTRE
) -> tuple[str, bool]:
    """Register the run's model unless the alias already points at the same model.

    "The same" means: same code (commit, no uncommitted change), same data (gold
    fingerprint), same configuration. A rerun that changed nothing then creates no new
    version. Returns the version the alias points at, and whether it is new.
    """
    mlflow = configurer_suivi()
    client = mlflow.MlflowClient()
    candidat = client.get_run(run_id).data.tags
    try:
        actuelle = client.get_model_version_by_alias(nom_modele, alias)
        retenu = client.get_run(actuelle.run_id).data.tags
        if all(candidat.get(c) and candidat.get(c) == retenu.get(c) for c in CLES_IDENTITE_MODELE):
            return str(actuelle.version), False
    except Exception:  # noqa: BLE001 - no model, or no alias yet: register
        pass
    return enregistrer(run_id, alias, nom_modele), True


def durees_des_runs(nom: str) -> pd.DataFrame:
    """Measured duration of each finished run of an experiment, from MLflow's own clock."""
    mlflow = configurer_suivi()
    if mlflow is None or mlflow.get_experiment_by_name(nom) is None:
        return pd.DataFrame(columns=["run", "secondes"])
    runs = mlflow.search_runs(
        experiment_names=[nom], filter_string="attributes.status = 'FINISHED'"
    )
    return pd.DataFrame(
        {
            "run": runs["tags.mlflow.runName"],
            "secondes": (runs["end_time"] - runs["start_time"]).dt.total_seconds().round(1),
        }
    )


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
