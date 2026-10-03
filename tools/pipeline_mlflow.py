"""Four tracked runs, one comparison, one registered model, one scoring from the registry.

    uv run python tools/pipeline_mlflow.py              # the four runs, then the registry
    uv run python tools/pipeline_mlflow.py --sans-grille   # skip the grid search (fast)

Rerunning it is safe (bloc 7.0 bis): each execution is ONE parent run holding its runs as
children, and the comparison reads that execution only - an older run, obtained on other
code or data, can never win it. The registry gets a new version only if the best model
differs from the current `challenger` (code, data or configuration).

1. Random forest, traced by `mlflow.sklearn.autolog()`.
2. XGBoost, traced by `mlflow.xgboost.autolog()`; the whole pipeline is logged apart.
3. Logistic regression, traced by hand (`log_param`, `log_metric`), confusion matrix as
   an artefact - at the protocol's operating point, the top 10 %, not at 0.5 (E-601).
4. `GridSearchCV` on the forest, traced by autolog (parent run, bounded child runs).

Autolog measures its metrics on the training rows: a forest that memorises would win on
them. Every run therefore also logs the protocol's **out-of-fold** metrics under common
ASCII keys, and the comparison only reads those (decision D4: ranked by PR-AUC, the
top-10 % recall shown beside it).

The best run is registered under the alias `challenger` - neither tuned to the end nor
calibrated, so not `champion`. It is then loaded back from the registry and scores the 50
accounts of the sample file through the shared preparation chain. That scoring is a
**functional check**, not an evaluation: those accounts were seen in training, and the test
part stays sealed until the end of phase 7 (decision D5).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
EXPERIENCE = "phase7-chaine-mlflow"


def _desactiver_autologs(mlflow) -> None:
    """One autolog at a time: two active ones would log the same pipeline twice."""
    mlflow.sklearn.autolog(disable=True)
    mlflow.xgboost.autolog(disable=True)


def ajuster_sous_autolog(mlflow, activer, ajuster):
    """Autolog for the traced fit ONLY, switched off whatever happens.

    Left on, it also patched the 25 fits and predictions of the protocol evaluation that
    follows: each one logged into the run, and on Windows the threads it spawned on top of
    the forests' own exhausted the process ("RuntimeError: can't start new thread").
    """
    activer()
    try:
        return ajuster()
    finally:
        _desactiver_autologs(mlflow)


def construire_recherche(X, config, construire_candidat, grille_hyperparametres):
    """The forest's grid search, with ONE parallel layer: N_JOBS fits at once, each forest
    on a single core. The 7.0 bis fix had missed this tool: the search ran parallel forests."""
    from sklearn.model_selection import GridSearchCV, StratifiedKFold

    return GridSearchCV(
        construire_candidat(X).set_params(modele__n_jobs=1),
        grille_hyperparametres()["candidat"],
        scoring="average_precision",
        cv=StratifiedKFold(config.PLIS_VALIDATION, shuffle=True, random_state=config.GRAINE),
        n_jobs=config.N_JOBS,
    )


def _matrice_confusion(y, score, part: float):
    """Confusion matrix at the top `part` of the ranking, as a figure.

    Built on a bare `Figure`, without pyplot: no graphical backend is selected, so the
    function neither opens a window in a script nor switches a notebook's inline backend.
    """
    import numpy as np
    from matplotlib.figure import Figure
    from sklearn.metrics import ConfusionMatrixDisplay

    k = int(np.ceil(part * len(score)))
    seuil = float(np.sort(np.asarray(score))[::-1][k - 1])
    predit = (np.asarray(score) >= seuil).astype(int)
    fig = Figure(figsize=(4.4, 4.0))
    ax = fig.subplots()
    ConfusionMatrixDisplay.from_predictions(
        y, predit, display_labels=["reste", "part"], cmap="Blues", ax=ax, colorbar=False
    )
    ax.set_title(f"Haut {part:.0%} du classement (seuil {seuil:.2f})", fontsize=10)
    fig.tight_layout()
    return fig, seuil


def executer(avec_grille: bool = True, rapide: bool = False, forcer: bool = False) -> dict:
    """The tracked runs, compared within this execution only.

    `rapide` keeps the logistic regression only: the tests use it to rerun the chain
    twice in seconds and check it creates neither duplicates nor registry versions.
    """
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    # The grid's worker processes do not inherit warning filters, only the environment:
    # without this, each of them prints scikit-learn's notice about `delayed` and
    # `Parallel` - raised under MLflow's autolog, harmless, and 99 lines of noise.
    import os

    os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:sklearn.utils.parallel"
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost
    import pandas as pd
    from sklearn.base import clone
    from sklearn.pipeline import Pipeline
    from xgboost import XGBClassifier

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste, typer_pour_modele
    from churn_saas.evaluation import evaluer_selon_protocole
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.industrialisation.scoring import preparer
    from churn_saas.modelisation import (
        annoncer_duree,
        construire_baseline,
        construire_candidat,
        construire_preprocesseur,
        grille_hyperparametres,
    )
    from churn_saas.packaging import (
        activer_experience,
        charger,
        configurer_suivi,
        enregistrer_si_nouveau,
        etiquettes_tracabilite,
        identite_execution,
        journaliser_modele,
        journaliser_protocole,
        nom_experience,
        run_existant,
    )

    configurer_suivi()
    activer_experience(nom_experience(EXPERIENCE))
    foret = 0 if rapide else 26 + 26 + (206 if avec_grille else 0)  # XGBoost counted as forests
    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    protocole = {
        "graine": config.GRAINE,
        "plis": config.PLIS_VALIDATION,
        "repetitions": config.REPETITIONS_VALIDATION,
        "part_haut_classement": config.PART_HAUT_CLASSEMENT,
    }

    def tracer(nom: str, fabrique, mode: str, ajuster=None, activer=lambda: None):
        """One run: fit on the training part, protocol metrics, pipeline logged."""
        debut = time.perf_counter()
        with mlflow.start_run(run_name=nom, nested=True) as run:
            mlflow.set_tags(
                etiquettes_tracabilite(
                    "7.0", "tools/pipeline_mlflow.py", manifeste, journalisation=mode
                )
            )
            mlflow.log_params({f"protocole_{k}": v for k, v in protocole.items()})
            modele = ajuster_sous_autolog(
                mlflow, activer, ajuster or (lambda: fabrique(X).fit(X, y))
            )
            # The protocol runs folds one after the other: the model itself may use N_JOBS.
            protocole_ = evaluer_selon_protocole(
                (lambda _X: clone(modele.best_estimator_).set_params(modele__n_jobs=config.N_JOBS))
                if hasattr(modele, "best_estimator_")
                else fabrique,
                X,
                y,
            )
            journaliser_protocole(protocole_.par_pli)
            final = getattr(modele, "best_estimator_", modele)
            reglages = final.named_steps[list(final.named_steps)[-1]].get_params()
            configuration = json.dumps(
                {k: str(v) for k, v in sorted(reglages.items())}, ensure_ascii=False
            )
            mlflow.set_tag("configuration", hashlib.sha256(configuration.encode()).hexdigest()[:16])
            journaliser_modele(final, X)
            mlflow.log_metric("duree_s", time.perf_counter() - debut)
            return run.info.run_id, final, protocole_

    # A1: one identity per computation - code, data, protocol, options - shared with
    # retracer_mlflow.py. An identical execution already recorded is reused, not redone.
    etiquettes = etiquettes_tracabilite("7.0", "tools/pipeline_mlflow.py", manifeste)
    identite = identite_execution(
        etiquettes, outil="pipeline", avec_grille=avec_grille and not rapide, rapide=rapide
    )
    existante = run_existant(
        nom_experience(EXPERIENCE), {"identite_execution": identite, "execution": "parent"}
    )
    if existante and forcer:
        client = mlflow.MlflowClient()
        enfants = mlflow.search_runs(
            experiment_names=[nom_experience(EXPERIENCE)],
            filter_string=f"tags.mlflow.parentRunId = '{existante}'",
        )
        for run_id in [*enfants["run_id"], existante]:
            client.delete_run(run_id)
        existante = None
    runs = {}
    if existante:
        print(
            f"Exécution identique déjà enregistrée ({existante[:8]}) : rien n'est recalculé. "
            "--forcer pour la rejouer.",
            flush=True,
        )
        parent_id = existante
    else:
        print(annoncer_duree(entrainements_lr=26, entrainements_foret=foret), flush=True)
        horodatage = time.strftime("%Y-%m-%d %H:%M:%S")
        parent = mlflow.start_run(run_name=f"chaine {horodatage}")
        parent_id = parent.info.run_id
        mlflow.set_tags(etiquettes | {"execution": "parent", "identite_execution": identite})
        try:
            _desactiver_autologs(mlflow)
            runs = {}

            # 1. Random forest, autolog. Models are logged by hand, whole pipeline included.
            def autolog_sklearn(**options):
                return lambda: mlflow.sklearn.autolog(log_models=False, silent=True, **options)

            if not rapide:
                runs["forêt · autolog"] = tracer(
                    "foret · sklearn.autolog",
                    construire_candidat,
                    "autolog",
                    activer=autolog_sklearn(),
                )
            _desactiver_autologs(mlflow)

            # 2. XGBoost, autolog. scale_pos_weight plays the role of class_weight.
            poids = float((y == 0).sum() / (y == 1).sum())

            def xgboost(Xf):
                return Pipeline(
                    [
                        ("preparation", construire_preprocesseur(Xf)),
                        (
                            "modele",
                            XGBClassifier(
                                n_estimators=300,
                                max_depth=4,
                                learning_rate=0.05,
                                subsample=0.8,
                                scale_pos_weight=poids,
                                random_state=config.GRAINE,
                                n_jobs=config.N_JOBS,
                            ),
                        ),
                    ]
                )

            if not rapide:
                runs["xgboost · autolog"] = tracer(
                    "xgboost · xgboost.autolog",
                    xgboost,
                    "autolog",
                    activer=lambda: mlflow.xgboost.autolog(log_models=False, silent=True),
                )
            _desactiver_autologs(mlflow)

            # 3. Logistic regression, by hand, with its confusion matrix.
            rid, lr, prot = tracer(
                "regression logistique · manuel", construire_baseline, "manuelle"
            )
            with mlflow.start_run(run_id=rid, nested=True):
                etape = lr.named_steps[list(lr.named_steps)[-1]]
                mlflow.log_params(
                    {
                        k: v
                        for k, v in etape.get_params().items()
                        if isinstance(v, (int, float, str, type(None)))
                    }
                )
                figure, seuil = _matrice_confusion(y, prot.hors_pli, config.PART_HAUT_CLASSEMENT)
                mlflow.log_figure(figure, "matrice_confusion_haut_10pct.png")
                mlflow.log_metric("seuil_haut_10pct", seuil)
            runs["régression logistique · manuel"] = (rid, lr, prot)

            # 4. GridSearchCV on the forest, autolog (bounded child runs).
            if avec_grille and not rapide:

                def grille():
                    recherche = construire_recherche(
                        X, config, construire_candidat, grille_hyperparametres
                    )
                    return recherche.fit(X, y)

                runs["grille forêt · GridSearchCV"] = tracer(
                    "grille foret · GridSearchCV autolog",
                    construire_candidat,
                    "autolog",
                    grille,
                    activer=autolog_sklearn(max_tuning_runs=10),
                )
                _desactiver_autologs(mlflow)

        finally:
            mlflow.end_run()

    # Comparison on the common out-of-fold keys only (decision D4).
    tableau = mlflow.search_runs(
        experiment_names=[nom_experience(EXPERIENCE)],
        filter_string=f"tags.mlflow.parentRunId = '{parent_id}' and metrics.pr_auc_cv > 0",
        order_by=["metrics.pr_auc_cv DESC"],
    )
    colonnes = [
        "tags.mlflow.runName",
        "metrics.pr_auc_cv",
        "metrics.rappel_haut_cv",
        "metrics.roc_auc_cv",
        "metrics.erreur_calibration_cv",
        "run_id",
    ]
    tableau = tableau.drop_duplicates("tags.mlflow.runName")[colonnes]
    meilleur = tableau.iloc[0]

    # Registry: challenger, then load and score the sample (functional check, D5).
    version, nouvelle_version = enregistrer_si_nouveau(meilleur["run_id"])
    modele_registre = charger()
    if runs:
        nom_meilleur = next(n for n, (r, _, _) in runs.items() if r == meilleur["run_id"])
        en_memoire = runs[nom_meilleur][1]
    else:  # reused execution: the best run's own logged model stands for the one in memory
        nom_meilleur = meilleur["tags.mlflow.runName"]
        en_memoire = mlflow.sklearn.load_model(f"runs:/{meilleur['run_id']}/modele")
    brut = pd.read_csv(config.FICHIER_ECHANTILLON, dtype=str, encoding="utf-8-sig")
    catalogue = pd.read_csv(config.FICHIER_CATALOGUE, dtype=str, encoding="utf-8-sig")
    entree = typer_pour_modele(
        preparer(brut, catalogue=catalogue).drop(columns=["churn"], errors="ignore")
    )
    proba_registre = modele_registre.predict_proba(entree)[:, 1]
    proba_memoire = en_memoire.predict_proba(entree)[:, 1]
    return {
        "comparaison": tableau.drop(columns=["run_id"]).round(4).to_dict(orient="records"),
        "meilleur": nom_meilleur,
        "version_registre": version,
        "nouvelle_version": nouvelle_version,
        "execution": parent_id,
        "reutilisee": not runs,
        "comptes_scores": int(len(entree)),
        "registre_identique_au_modele_en_memoire": bool(
            abs(proba_registre - proba_memoire).max() < 1e-9
        ),
        "probabilites": [round(float(p), 4) for p in proba_registre[:5]],
    }


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included,
    # which escaped the first version of this fix (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    # A script draws nothing on screen. Without this, matplotlib picks Tk on Windows, and
    # the figures MLflow's autolog draws are destroyed by another thread at exit:
    # "main thread is not in main loop", "Tcl_AsyncDelete". Set before matplotlib loads.
    os.environ.setdefault("MPLBACKEND", "Agg")
    analyseur = argparse.ArgumentParser(description="Chaîne de quatre runs MLflow.")
    analyseur.add_argument("--sans-grille", action="store_true", help="sauter GridSearchCV")
    analyseur.add_argument(
        "--rapide", action="store_true", help="régression logistique seule (essais, tests)"
    )
    analyseur.add_argument(
        "--forcer", action="store_true", help="rejouer une exécution identique déjà enregistrée"
    )
    arguments = analyseur.parse_args(argv)
    try:
        import mlflow  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError as erreur:
        print(
            f"MLflow ou XGBoost absent ({erreur.name}) : installer les groupes suivi et boosting."
        )
        return 0
    bilan = executer(
        avec_grille=not arguments.sans_grille, rapide=arguments.rapide, forcer=arguments.forcer
    )
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0 if bilan["registre_identique_au_modele_en_memoire"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
