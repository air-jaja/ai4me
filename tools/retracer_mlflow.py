"""Replay the measured results of phases 5 and 6 into MLflow, once, tagged `retrace`.

    uv run python tools/retracer_mlflow.py              # phases 5 and 6
    uv run python tools/retracer_mlflow.py --phase 6    # the baselines only (seconds)

The computations are deterministic (fixed seeds, shared folds): replayed, they give back
the figures already frozen by the non-regression tests and `resultats/`. The MLflow
history thus starts complete, without a single figure being entered by hand - and a test
checks the replayed figures equal the frozen ones.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def retracer_phase6(mlflow, etiquettes) -> dict[str, float]:
    """The three baselines, from the reference file's own computation."""
    import pandas as pd

    sys.path.insert(0, str(RACINE / "tools"))
    from resultats_reference import calculer

    from churn_saas.packaging import journaliser_protocole, nom_experience

    mlflow.set_experiment(nom_experience("phase6-baselines"))
    moyennes = {}
    for nom, valeurs in calculer()["baselines"].items():
        with mlflow.start_run(run_name=nom):
            mlflow.set_tags(etiquettes | {"retrace": "true"})
            par_pli = pd.DataFrame(valeurs["par_pli"]).astype(float)
            moyennes[nom] = journaliser_protocole(par_pli)["pr_auc_cv"]
    return moyennes


def retracer_phase5(mlflow, etiquettes, X, y) -> dict[str, float]:
    """Constructed variables' contribution and the final selection, both models."""
    from churn_saas.config import EXCLUES_PAR_SELECTION
    from churn_saas.features import VARIABLES_CONSTRUITES, comparer_jeux
    from churn_saas.modelisation import construire_baseline, construire_candidat
    from churn_saas.packaging import nom_experience

    mlflow.set_experiment(nom_experience("phase5-selection"))
    brutes = [c for c in X.columns if c not in VARIABLES_CONSTRUITES]
    retenues = [c for c in X.columns if c not in EXCLUES_PAR_SELECTION]
    jeux = {
        "brutes": brutes,
        "brutes + construites": list(X.columns),
        f"{len(retenues)} retenues": retenues,
    }
    moyennes = {}
    for modele, fabrique in (
        ("regression logistique", construire_baseline),
        ("foret aleatoire", construire_candidat),
    ):
        scores = comparer_jeux(fabrique, X, y, jeux)
        for jeu, valeurs in scores.items():
            with mlflow.start_run(run_name=f"{modele} · {jeu}"):
                mlflow.set_tags(etiquettes | {"retrace": "true", "jeu_de_variables": jeu})
                mlflow.log_param("variables", len(jeux[jeu]))
                mlflow.log_metric("pr_auc_cv", float(valeurs.mean()))
                mlflow.log_metric("pr_auc_cv_ecart_type", float(valeurs.std()))
                for pli, valeur in enumerate(valeurs):
                    mlflow.log_metric("pr_auc_cv_par_pli", float(valeur), step=pli)
                moyennes[f"{modele} · {jeu}"] = float(valeurs.mean())
    return moyennes


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Retrace les phases 5 et 6 dans MLflow.")
    analyseur.add_argument("--phase", choices=["5", "6", "tout"], default="tout")
    arguments = analyseur.parse_args(argv)
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas.packaging import configurer_suivi, etiquettes_tracabilite

    mlflow = configurer_suivi()
    if mlflow is None:
        print("MLflow absent : rien à retracer (installer le groupe suivi).")
        return 0
    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.features import executer_pipeline, parties_avant_selection

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    bilan = {}
    if arguments.phase in ("6", "tout"):
        etiquettes = etiquettes_tracabilite("6", "tools/retracer_mlflow.py", manifeste)
        bilan["phase 6"] = retracer_phase6(mlflow, etiquettes)
    if arguments.phase in ("5", "tout"):
        resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
        parties = parties_avant_selection(resultat)
        etiquettes = etiquettes_tracabilite("5", "tools/retracer_mlflow.py", manifeste)
        bilan["phase 5"] = retracer_phase5(
            mlflow, etiquettes, parties.X_entrainement, parties.y_entrainement.astype(int)
        )
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
