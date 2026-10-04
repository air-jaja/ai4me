"""Phase 8, decision c: the model put into service - one calibrated copy of the regression.

    uv run python tools/modele_servi.py            # equivalence evidence, model, card, registry
    uv run python tools/modele_servi.py --forcer   # redo an identical computation

The champion evaluated on the test part (phase 7) averages five calibrated copies of the
logistic regression - the inner cross-validation of its calibration. Each prediction runs
all five: 57 ms per account on the development laptop, over the 50 ms budget (P4).

The served model is ONE copy: the same regression (same variables, same settings), fitted
on the whole training part, calibrated by the same sigmoid learnt on the out-of-fold
predictions (`CalibratedClassifierCV(ensemble=False)`). Decision i: the test part is NOT
read again. This tool therefore proves the equivalence where it may be proved - on the
protocol's 25 folds and on the training part - and records it next to the test result of
the evaluated champion:

- paired PR-AUC on the 25 folds (B1 logic: no significant difference either way);
- calibration error on the 25 folds;
- closeness of the probabilities and of the rankings on the training part;
- latency of one account and of the monthly batch, for both, on this machine.

It then writes the served model and its card under models/ and, when MLflow is installed,
points the `champion` alias at it. Same execution identity as the other tools (A1).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "modele_servi.json"
SELECTION = RACINE / "resultats" / "selection_modele.json"
EVALUATION = RACINE / "resultats" / "evaluation_finale.json"
REFERENCE_ECHANTILLON = RACINE / "resultats" / "scores_echantillon_reference.csv"


def construire_servi(construire_baseline, methode: str, config):
    """One calibrated copy: the champion's regression and calibration, combined once."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedKFold

    def fabrique(X):
        return CalibratedClassifierCV(
            construire_baseline(X),
            method=methode,
            cv=StratifiedKFold(config.PLIS_VALIDATION, shuffle=True, random_state=config.GRAINE),
            ensemble=False,
        )

    return fabrique


def _latences(modele, X_lot) -> dict:
    un_compte = X_lot.iloc[[0]]
    unitaires, lots = [], []
    for _ in range(50):
        debut = time.perf_counter()
        modele.predict_proba(un_compte)
        unitaires.append(time.perf_counter() - debut)
    for _ in range(3):
        debut = time.perf_counter()
        modele.predict_proba(X_lot)
        lots.append(time.perf_counter() - debut)
    return {
        "un compte (ms)": round(1000 * statistics.median(unitaires), 2),
        "lot de 5 000 comptes (s)": round(statistics.median(lots), 3),
    }


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.evaluation import comparer_a_la_reference, evaluer_selon_protocole
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline, construire_calibre
    from churn_saas.packaging import (
        FicheModele,
        decrire_modele,
        etiquettes_tracabilite,
        identite_execution,
        sauvegarder_modele,
    )

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("8", "tools/modele_servi.py", manifeste)
    identite = identite_execution(etiquettes, outil="modele_servi")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if (
            existant.get("identite_execution") == identite
            and (RACINE / existant["artefact"]).exists()
        ):
            print("Modèle servi déjà construit à l'identique : rien n'est recalculé.", flush=True)
            return existant

    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    methode = selection["calibration"]["methode_retenue"]
    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)

    variantes = {
        "champion évalué (5 copies calibrées)": construire_calibre(construire_baseline, methode),
        "modèle servi (une copie calibrée)": construire_servi(construire_baseline, methode, config),
    }
    protocoles, modeles, latences = {}, {}, {}
    for nom, fabrique in variantes.items():
        protocoles[nom] = evaluer_selon_protocole(fabrique, X, y)
        modeles[nom] = fabrique(X).fit(X, y)
        latences[nom] = _latences(modeles[nom], resultat.X)

    noms = list(variantes)
    comparaison = comparer_a_la_reference(
        {n: protocoles[n].par_pli["PR-AUC"].tolist() for n in noms}, noms[0]
    )
    p_champion = modeles[noms[0]].predict_proba(X)[:, 1]
    p_servi = modeles[noms[1]].predict_proba(X)[:, 1]
    tableau = {
        nom: {
            "PR-AUC (25 plis)": round(float(protocoles[nom].par_pli["PR-AUC"].mean()), 4),
            "erreur de calibration (25 plis)": round(
                float(protocoles[nom].par_pli["erreur de calibration"].mean()), 4
            ),
            **latences[nom],
        }
        for nom in noms
    }
    equivalence = {
        "gain apparié du modèle servi": float(comparaison.iloc[1]["gain apparié"]),
        "seuil (1 écart-type)": float(comparaison.iloc[1]["seuil (1 écart-type)"]),
        "équivalent en performance": abs(float(comparaison.iloc[1]["gain apparié"]))
        <= float(comparaison.iloc[1]["seuil (1 écart-type)"]),
        "corrélation de rang des probabilités": round(
            float(spearmanr(p_champion, p_servi).statistic), 5
        ),
        "écart moyen des probabilités": round(float(np.abs(p_champion - p_servi).mean()), 4),
        "écart maximal des probabilités": round(float(np.abs(p_champion - p_servi).max()), 4),
        "comptes comparés": "partie d'entraînement (le jeu de test n'est pas relu : décision i)",
        "calibration conforme": tableau[noms[1]]["erreur de calibration (25 plis)"]
        < config.SEUIL_ERREUR_CALIBRATION,
        "budget d'un compte respecté": tableau[noms[1]]["un compte (ms)"] < config.BUDGET_COMPTE_MS,
        "budget du lot respecté": tableau[noms[1]]["lot de 5 000 comptes (s)"]
        < config.BUDGET_LOT_MENSUEL_S,
        "accélération d'un compte": round(
            tableau[noms[0]]["un compte (ms)"] / tableau[noms[1]]["un compte (ms)"], 1
        ),
    }

    servi = modeles[noms[1]]
    regression = servi.calibrated_classifiers_[0].estimator.steps[-1][1]
    hyperparametres = {
        "famille": "régression logistique",
        "C": regression.C,
        "class_weight": str(regression.class_weight),
        "penalty": str(regression.penalty) if regression.penalty != "deprecated" else "l2",
        "solver": regression.solver,
        "max_iter": regression.max_iter,
        "calibration": methode,
        "copies calibrées": 1,
        "plis de calibration": config.PLIS_VALIDATION,
        "graine": config.GRAINE,
    }
    fiche = FicheModele(
        nom="churn_saas_servi",
        version="1.1",
        empreinte_donnees=str(etiquettes.get("empreinte_gold", ""))[:16],
        hyperparametres=hyperparametres,
        metriques_validation={
            "pr_auc_cv": tableau[noms[1]]["PR-AUC (25 plis)"],
            "erreur_calibration_cv": tableau[noms[1]]["erreur de calibration (25 plis)"],
            "test_pr_auc_du_champion_evalue": evaluation["metriques"]["PR-AUC"],
        },
        variables=list(X.columns),
        responsable_validation="porteur du projet",
    )
    chemin = sauvegarder_modele(servi, fiche, entrainement=(X, y), lignage=etiquettes)
    bilan = {
        "identite_execution": identite,
        "decision": "P4 option c et jeu de test option i, décidées par le porteur le 03/10/2026",
        "descriptif_modele": decrire_modele(servi),
        "hyperparametres": hyperparametres,
        "mesures": tableau,
        "equivalence": equivalence,
        "test_du_champion_evalue": {
            k: evaluation[k] for k in ("metriques", "intervalles_95", "date")
        },
        "artefact": chemin.relative_to(RACINE).as_posix(),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    # Reference scores of the sample file (phase 10): reloading this model, or rebuilding it
    # from code and data, must give exactly these probabilities. A functional check, not an
    # evaluation: the 50 accounts were seen in training or belong to the test part.
    from churn_saas.donnees import typer_pour_modele
    from churn_saas.industrialisation.scoring import preparer

    brut = pd.read_csv(config.FICHIER_ECHANTILLON, dtype=str, encoding="utf-8-sig")
    catalogue = pd.read_csv(config.FICHIER_CATALOGUE, dtype=str, encoding="utf-8-sig")
    entree = preparer(brut, catalogue=catalogue).drop(columns=["churn"], errors="ignore")
    pd.DataFrame(
        {
            "client_id": brut["client_id"].to_numpy(),
            "proba": servi.predict_proba(typer_pour_modele(entree))[:, 1],
        }
    ).to_csv(REFERENCE_ECHANTILLON, index=False, float_format="%.12f", lineterminator="\n")
    bilan["scores_echantillon_reference"] = REFERENCE_ECHANTILLON.relative_to(RACINE).as_posix()
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    try:
        from churn_saas.config import ALIAS_RETENU
        from churn_saas.packaging import (
            activer_experience,
            configurer_suivi,
            enregistrer_si_nouveau,
            journaliser_modele,
            nom_experience,
        )

        mlflow = configurer_suivi()
        if mlflow is not None:
            import hashlib

            activer_experience(nom_experience("phase8-modele-servi"))
            with mlflow.start_run(run_name=f"modele servi {bilan['date']}") as run:
                configuration = json.dumps(hyperparametres, sort_keys=True, default=str)
                mlflow.set_tags(
                    etiquettes
                    | {
                        "identite_execution": identite,
                        "configuration": hashlib.sha256(configuration.encode()).hexdigest()[:16],
                    }
                )
                mlflow.log_dict(bilan, "modele_servi.json")
                journaliser_modele(servi, X)
            bilan["version_registre"], _ = enregistrer_si_nouveau(
                run.info.run_id, alias=ALIAS_RETENU
            )
    except ImportError:
        pass
    return bilan


def reconstruire() -> Path:
    """Rebuild the served model's FILE only, as recorded - no result, no registry written.

    For the CI, where models/ is not versioned: the model is refitted from code and data
    (deterministic) under the recorded file name, so the fidelity test runs too. Nothing
    measured on this machine reaches resultats/.
    """
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import FicheModele, sauvegarder_modele

    attendu = RACINE / json.loads(DESTINATION.read_text(encoding="utf-8"))["artefact"]
    registre = json.loads(
        (RACINE / "resultats" / "registre_modeles.json").read_text(encoding="utf-8")
    )
    entree = next(e for e in registre if e["fichier"] == attendu.name)
    parties = parties_du_decoupage(
        executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    )
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    modele = construire_servi(construire_baseline, "sigmoid", config)(X).fit(X, y)
    fiche = FicheModele(
        nom=entree["nom"], version=entree["version"], date_entrainement=entree["date_entrainement"]
    )
    chemin = sauvegarder_modele(modele, fiche, attendu.parent, entrainement=(X, y), registre=None)
    if chemin != attendu:
        raise SystemExit(f"Nom inattendu : {chemin.name} au lieu de {attendu.name}")
    return chemin


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    import os

    os.environ.setdefault("MPLBACKEND", "Agg")
    analyseur = argparse.ArgumentParser(description="Modèle servi : une copie calibrée (phase 8).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un calcul identique")
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    analyseur.add_argument(
        "--reconstruire-seulement",
        action="store_true",
        help="refaire le fichier du modèle à l'identique, sans écrire de résultat (CI)",
    )
    arguments = analyseur.parse_args(argv)
    if arguments.reconstruire_seulement:
        print(f"Modèle reconstruit : {reconstruire().relative_to(RACINE)}")
        return 0
    bilan = executer(arguments.forcer, Path(arguments.sortie))
    print(
        json.dumps(
            {k: bilan[k] for k in ("mesures", "equivalence", "artefact")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
