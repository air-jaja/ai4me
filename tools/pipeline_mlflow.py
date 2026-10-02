"""Four tracked runs, one comparison, one registered model, one scoring from the registry.

    uv run python tools/pipeline_mlflow.py              # the four runs, then the registry
    uv run python tools/pipeline_mlflow.py --sans-grille   # skip the grid search (fast)

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
import json
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


def _matrice_confusion(y, score, part: float):
    """Confusion matrix at the top `part` of the ranking, as a figure."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.metrics import ConfusionMatrixDisplay

    k = int(np.ceil(part * len(score)))
    seuil = float(np.sort(np.asarray(score))[::-1][k - 1])
    predit = (np.asarray(score) >= seuil).astype(int)
    fig, ax = plt.subplots(figsize=(4.4, 4.0))
    ConfusionMatrixDisplay.from_predictions(
        y, predit, display_labels=["reste", "part"], cmap="Blues", ax=ax, colorbar=False
    )
    ax.set_title(f"Haut {part:.0%} du classement (seuil {seuil:.2f})", fontsize=10)
    fig.tight_layout()
    return fig, seuil


def executer(avec_grille: bool = True) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost
    import pandas as pd
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.pipeline import Pipeline
    from xgboost import XGBClassifier

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste, typer_pour_modele
    from churn_saas.evaluation import evaluer_selon_protocole
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.industrialisation.scoring import preparer
    from churn_saas.modelisation import (
        construire_baseline,
        construire_candidat,
        construire_preprocesseur,
        grille_hyperparametres,
    )
    from churn_saas.packaging import (
        charger,
        configurer_suivi,
        enregistrer,
        etiquettes_tracabilite,
        journaliser_modele,
        journaliser_protocole,
        nom_experience,
    )

    configurer_suivi()
    mlflow.set_experiment(nom_experience(EXPERIENCE))
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

    def tracer(nom: str, fabrique, mode: str, ajuster=None):
        """One run: fit on the training part, protocol metrics, pipeline logged."""
        debut = time.perf_counter()
        with mlflow.start_run(run_name=nom) as run:
            mlflow.set_tags(
                etiquettes_tracabilite(
                    "7.0", "tools/pipeline_mlflow.py", manifeste, journalisation=mode
                )
            )
            mlflow.log_params({f"protocole_{k}": v for k, v in protocole.items()})
            modele = ajuster() if ajuster else fabrique(X).fit(X, y)
            protocole_ = evaluer_selon_protocole(
                (lambda _X: modele.best_estimator_)
                if hasattr(modele, "best_estimator_")
                else fabrique,
                X,
                y,
            )
            journaliser_protocole(protocole_.par_pli)
            final = getattr(modele, "best_estimator_", modele)
            journaliser_modele(final, X)
            mlflow.log_metric("duree_s", time.perf_counter() - debut)
            return run.info.run_id, final, protocole_

    _desactiver_autologs(mlflow)
    runs = {}

    # 1. Random forest, autolog. Models are logged by hand, whole pipeline included.
    mlflow.sklearn.autolog(log_models=False, silent=True)
    runs["forêt · autolog"] = tracer("foret · sklearn.autolog", construire_candidat, "autolog")
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
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    mlflow.xgboost.autolog(log_models=False, silent=True)
    runs["xgboost · autolog"] = tracer("xgboost · xgboost.autolog", xgboost, "autolog")
    _desactiver_autologs(mlflow)

    # 3. Logistic regression, by hand, with its confusion matrix.
    rid, lr, prot = tracer("regression logistique · manuel", construire_baseline, "manuelle")
    with mlflow.start_run(run_id=rid):
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
    if avec_grille:

        def grille():
            recherche = GridSearchCV(
                construire_candidat(X),
                grille_hyperparametres()["candidat"],
                scoring="average_precision",
                cv=StratifiedKFold(
                    config.PLIS_VALIDATION, shuffle=True, random_state=config.GRAINE
                ),
                n_jobs=-1,
            )
            return recherche.fit(X, y)

        mlflow.sklearn.autolog(log_models=False, silent=True, max_tuning_runs=10)
        runs["grille forêt · GridSearchCV"] = tracer(
            "grille foret · GridSearchCV autolog", construire_candidat, "autolog", grille
        )
        _desactiver_autologs(mlflow)

    # Comparison on the common out-of-fold keys only (decision D4).
    tableau = mlflow.search_runs(
        experiment_names=[nom_experience(EXPERIENCE)],
        filter_string="metrics.pr_auc_cv > 0",
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
    version = enregistrer(meilleur["run_id"])
    modele_registre = charger()
    nom_meilleur = next(n for n, (r, _, _) in runs.items() if r == meilleur["run_id"])
    en_memoire = runs[nom_meilleur][1]
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
        "comptes_scores": int(len(entree)),
        "registre_identique_au_modele_en_memoire": bool(
            abs(proba_registre - proba_memoire).max() < 1e-9
        ),
        "probabilites": [round(float(p), 4) for p in proba_registre[:5]],
    }


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Chaîne de quatre runs MLflow.")
    analyseur.add_argument("--sans-grille", action="store_true", help="sauter GridSearchCV")
    arguments = analyseur.parse_args(argv)
    try:
        import mlflow  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError as erreur:
        print(
            f"MLflow ou XGBoost absent ({erreur.name}) : installer les groupes suivi et boosting."
        )
        return 0
    bilan = executer(avec_grille=not arguments.sans_grille)
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0 if bilan["registre_identique_au_modele_en_memoire"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
