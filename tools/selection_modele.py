"""Phase 7: tune the candidates, compare them to the frozen reference, calibrate the winner.

    uv run python tools/selection_modele.py            # writes resultats/selection_modele.json
    uv run python tools/selection_modele.py --forcer   # redo an identical selection

Every rule applied here was validated and committed BEFORE this tool first ran (rules B1
to B3, config.py, choix § 7 quinquies):

1. Tuning (B3): the forest's grid (36 combinations) and XGBoost's (24), on PR-AUC.
2. Comparison (B1): the tuned candidates on the protocol's 25 folds, paired against the
   logistic regression's folds recorded in resultats/reference_baseline.json - the frozen
   reference, not a figure recomputed on the fly. A candidate replaces the regression only
   with a paired gain above one standard deviation; on a tie, the simplest.
3. Calibration (B2): sigmoid or isotonic for the retained model, chosen inside the folds on
   the calibration error; target below 0.05.

Nothing here touches the test part: the single test evaluation is a separate tool (B4).
The results file is the source of truth; MLflow mirrors it under the same execution
identity as the other tools (A1).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "selection_modele.json"
REFERENCE = RACINE / "resultats" / "reference_baseline.json"
REGRESSION = "régression logistique"


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import os

    os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:sklearn.utils.parallel"
    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.evaluation import (
        comparer_a_la_reference,
        erreur_calibration,
        evaluer_selon_protocole,
        selectionner,
    )
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import (
        annoncer_duree,
        construire_baseline,
        construire_calibre,
        construire_candidat,
        construire_xgboost,
        grille_hyperparametres,
        regler,
    )
    from churn_saas.packaging import (
        CLES_MLFLOW,
        configurer_suivi,
        decrire_modele,
        etiquettes_tracabilite,
        identite_execution,
    )

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("7", "tools/selection_modele.py", manifeste)
    identite = identite_execution(etiquettes, outil="selection")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print(
                "Sélection identique déjà enregistrée : rien n'est recalculé (--forcer pour la "
                "refaire).",
                flush=True,
            )
            return existant

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    grilles = grille_hyperparametres()
    print(
        annoncer_duree(entrainements_lr=250, entrainements_foret=180 + 120 + 50 + 250),
        "XGBoost compté comme une forêt.",
        flush=True,
    )

    # 1. Tuning (B3)
    debut = time.perf_counter()
    familles = {"forêt aléatoire": construire_candidat, "xgboost": construire_xgboost}
    reglages = {
        nom: regler(f, grilles["candidat" if nom == "forêt aléatoire" else "xgboost"], X, y)
        for nom, f in familles.items()
    }

    def regle(nom):
        parametres = {
            k.removeprefix("modele__"): v for k, v in reglages[nom].meilleurs_parametres.items()
        }
        return lambda Xf: familles[nom](Xf).set_params(
            **{f"modele__{k}": v for k, v in parametres.items()}
        )

    # 2. Comparison against the frozen reference (B1), on the protocol's 25 folds
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    scores = {REGRESSION: reference["baselines"][REGRESSION]["par_pli"]["PR-AUC"]}
    protocoles = {}
    for nom in familles:
        protocoles[nom] = evaluer_selon_protocole(regle(nom), X, y)
        scores[nom] = protocoles[nom].par_pli["PR-AUC"].tolist()
    comparaison = comparer_a_la_reference(scores, REGRESSION)
    retenu = selectionner(comparaison, REGRESSION, config.ORDRE_DE_SIMPLICITE)

    # 3. Calibration of the retained model (B2), inside the folds
    fabrique_retenue = construire_baseline if retenu == REGRESSION else regle(retenu)
    calibrations = {}
    for methode in config.METHODES_CALIBRATION:
        evaluation = evaluer_selon_protocole(construire_calibre(fabrique_retenue, methode), X, y)
        calibrations[methode] = {
            "PR-AUC": round(float(evaluation.par_pli["PR-AUC"].mean()), 4),
            "erreur de calibration": round(
                float(evaluation.par_pli["erreur de calibration"].mean()), 4
            ),
            "erreur hors pli (première répétition)": round(
                erreur_calibration(y, evaluation.hors_pli), 4
            ),
        }
    methode = min(calibrations, key=lambda m: calibrations[m]["erreur de calibration"])
    duree = time.perf_counter() - debut

    bilan = {
        "identite_execution": identite,
        "regles": "B1 à B3 validées le 02/10/2026 (commit « decision(phase 7) »)",
        "reglages": {
            nom: {
                "meilleurs_parametres": {k: str(v) for k, v in r.meilleurs_parametres.items()},
                "pr_auc_grille": round(r.meilleur_score, 4),
            }
            for nom, r in reglages.items()
        },
        "comparaison": comparaison.to_dict(orient="records"),
        "par_pli": {nom: [round(float(v), 10) for v in valeurs] for nom, valeurs in scores.items()},
        "modele_retenu": retenu,
        "descriptifs": {nom: decrire_modele(regle(nom)(X)) for nom in familles}
        | {REGRESSION: decrire_modele(construire_baseline(X))},
        "calibration": {
            "methodes": calibrations,
            "methode_retenue": methode,
            "objectif_atteint": calibrations[methode]["erreur de calibration"]
            < config.SEUIL_ERREUR_CALIBRATION,
        },
        "duree_s": round(duree, 1),
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    mlflow = configurer_suivi()
    if mlflow is not None:
        from churn_saas.packaging import activer_experience, nom_experience

        activer_experience(nom_experience("phase7-selection"))
        with mlflow.start_run(run_name=f"selection {time.strftime('%Y-%m-%d %H:%M:%S')}"):
            mlflow.set_tags(
                etiquettes
                | {"identite_execution": identite, "modele_retenu": retenu, "calibration": methode}
            )
            for nom, valeurs in scores.items():
                cle = "".join(c if c.isalnum() else "_" for c in nom)
                mlflow.log_metric(
                    f"{CLES_MLFLOW['PR-AUC']}_cv_{cle}", float(sum(valeurs) / len(valeurs))
                )
            mlflow.log_dict(bilan, "selection_modele.json")
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included,
    # which escaped the first version of this fix (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    import os

    os.environ.setdefault("MPLBACKEND", "Agg")
    analyseur = argparse.ArgumentParser(description="Réglage, comparaison et calibration.")
    analyseur.add_argument("--forcer", action="store_true", help="refaire une sélection identique")
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    bilan = executer(forcer=arguments.forcer, sortie=Path(arguments.sortie))
    print(
        json.dumps(
            {k: bilan[k] for k in ("modele_retenu", "comparaison", "calibration")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
