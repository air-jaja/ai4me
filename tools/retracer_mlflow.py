"""Replay the measured results of phases 5 and 6 into MLflow, once, tagged `retrace`.

    uv run python tools/retracer_mlflow.py              # phases 5 and 6
    uv run python tools/retracer_mlflow.py --phase 6    # the baselines only (seconds)

The computations are deterministic (fixed seeds, shared folds): replayed, they give back
the figures already frozen by the non-regression tests and `resultats/`. The MLflow
history thus starts complete, without a single figure being entered by hand - and a test
checks the replayed figures equal the frozen ones.

Rerunning it changes nothing (bloc 7.0 bis): a run already replayed - same name, same gold
fingerprint, same phase - is skipped. `--forcer` deletes those runs and replays them.
"Identical" means the shared execution identity: code, data, protocol, phase (A1).
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def _deja_retrace(experience: str, nom_run: str, etiquettes: dict, forcer: bool) -> float | None:
    """PR-AUC of an identical replay already recorded; deletes it instead when forcing.

    "Identical" is the shared execution identity - code, data, protocol and replayed phase
    (A1). A change of code or protocol therefore replays the run instead of keeping the
    old figures in silence, which the first version of this tool did.
    """
    from churn_saas.packaging import configurer_suivi, identite_execution, run_existant

    identite = identite_execution(etiquettes, outil="retracer", phase=etiquettes.get("phase"))
    existant = run_existant(experience, {"identite_execution": identite}, nom_run)
    if existant is None:
        return None
    mlflow = configurer_suivi()
    if forcer:
        mlflow.MlflowClient().delete_run(existant)
        return None
    return float(mlflow.get_run(existant).data.metrics["pr_auc_cv"])


def _identite(etiquettes: dict) -> dict[str, str]:
    from churn_saas.packaging import identite_execution

    identite = identite_execution(etiquettes, outil="retracer", phase=etiquettes.get("phase"))
    return etiquettes | {"retrace": "true", "identite_execution": identite}


def retracer_phase6(mlflow, etiquettes, forcer: bool = False) -> dict[str, float]:
    """The three baselines, from the reference file's own computation."""
    import pandas as pd

    sys.path.insert(0, str(RACINE / "tools"))
    from resultats_reference import calculer

    from churn_saas.packaging import activer_experience, journaliser_protocole, nom_experience

    experience = nom_experience("phase6-baselines")
    activer_experience(experience)
    moyennes = {}
    for nom, valeurs in calculer()["baselines"].items():
        deja = _deja_retrace(experience, nom, etiquettes, forcer)
        if deja is not None:
            moyennes[nom] = deja
            continue
        with mlflow.start_run(run_name=nom):
            mlflow.set_tags(_identite(etiquettes))
            par_pli = pd.DataFrame(valeurs["par_pli"]).astype(float)
            moyennes[nom] = journaliser_protocole(par_pli)["pr_auc_cv"]
    return moyennes


def retracer_phase5(mlflow, etiquettes, X, y, forcer: bool = False) -> dict[str, float]:
    """Constructed variables' contribution and the final selection, both models."""
    from churn_saas.config import EXCLUES_PAR_SELECTION
    from churn_saas.features import VARIABLES_CONSTRUITES, comparer_jeux
    from churn_saas.modelisation import construire_baseline, construire_candidat
    from churn_saas.packaging import activer_experience, nom_experience

    experience = nom_experience("phase5-selection")
    activer_experience(experience)
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
        deja = {j: _deja_retrace(experience, f"{modele} · {j}", etiquettes, forcer) for j in jeux}
        if all(v is not None for v in deja.values()):
            moyennes |= {f"{modele} · {j}": v for j, v in deja.items()}
            continue
        scores = comparer_jeux(fabrique, X, y, jeux)
        for jeu, valeurs in scores.items():
            with mlflow.start_run(run_name=f"{modele} · {jeu}"):
                mlflow.set_tags(_identite(etiquettes) | {"jeu_de_variables": jeu})
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
    analyseur.add_argument("--forcer", action="store_true", help="rejouer les runs déjà retracés")
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
    from churn_saas.modelisation import annoncer_duree

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    lr = (75 if arguments.phase != "5" else 0) + (75 if arguments.phase != "6" else 0)
    print(annoncer_duree(lr, 75 if arguments.phase != "6" else 0), "Runs déjà retracés : sautés.")
    bilan = {}
    if arguments.phase in ("6", "tout"):
        etiquettes = etiquettes_tracabilite("6", "tools/retracer_mlflow.py", manifeste)
        bilan["phase 6"] = retracer_phase6(mlflow, etiquettes, arguments.forcer)
    if arguments.phase in ("5", "tout"):
        resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
        parties = parties_avant_selection(resultat)
        etiquettes = etiquettes_tracabilite("5", "tools/retracer_mlflow.py", manifeste)
        bilan["phase 5"] = retracer_phase5(
            mlflow,
            etiquettes,
            parties.X_entrainement,
            parties.y_entrainement.astype(int),
            arguments.forcer,
        )
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
