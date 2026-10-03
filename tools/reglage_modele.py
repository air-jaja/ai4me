"""Phase 8: tune the retained model, watch overfitting, weigh performance against resources.

    uv run python tools/reglage_modele.py            # writes the two results files
    uv run python tools/reglage_modele.py --forcer   # redo an identical computation

Every rule applied here was validated and committed BEFORE this tool first ran (config.py,
choix § 7 sexies):

- the grid of the logistic regression (14 combinations) on the protocol's 25 folds, with
  training AND validation scores (S1);
- P3 then P1: combinations overfitting beyond the gap are discarded; within one standard
  deviation of the best, the most regularised is retained;
- S2 the validation curve along C, S3 the nested cross-validation (selection optimism),
  S4 the learning curve, S5 the calibration of the retained configuration;
- P2: the champion is replaced only by a paired gain above one standard deviation, against
  the frozen reference folds;
- P4: training time, batch and single-account scoring time, size, memory and energy of the
  three tuned models; at equivalent performance, the cheapest.

Nothing here reads the test part.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import tracemalloc
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
REGLAGE = RACINE / "resultats" / "reglage_modele.json"
RESSOURCES = RACINE / "resultats" / "ressources_modeles.json"
REFERENCE = RACINE / "resultats" / "reference_baseline.json"
SELECTION = RACINE / "resultats" / "selection_modele.json"
REGRESSION = "régression logistique"


def _mesurer_ressources(nom: str, modele, X, y, X_lot, poste: dict) -> dict:
    """P4: what the model costs to train, to score a batch, to score one account, to keep."""
    import statistics

    import joblib

    from churn_saas.modelisation import convertir_empreinte

    durees = []
    for _ in range(3):
        debut = time.perf_counter()
        modele.fit(X, y)
        durees.append(time.perf_counter() - debut)
    tracemalloc.start()
    modele.fit(X, y)
    _, pic = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    lots = []
    for _ in range(3):
        debut = time.perf_counter()
        modele.predict_proba(X_lot)
        lots.append(time.perf_counter() - debut)
    un_compte = X_lot.iloc[[0]]
    unitaires = []
    for _ in range(50):
        debut = time.perf_counter()
        modele.predict_proba(un_compte)
        unitaires.append(time.perf_counter() - debut)
    tampon = io.BytesIO()
    joblib.dump(modele, tampon)
    entrainement = statistics.median(durees)
    energie = convertir_empreinte(
        entrainement, poste["puissance_haute_w"], poste["intensite_carbone_g_kwh"]
    )
    return {
        "modèle": nom,
        "entraînement (s)": round(entrainement, 3),
        "lot de 5 000 comptes (s)": round(statistics.median(lots), 3),
        "un compte (ms)": round(1000 * statistics.median(unitaires), 2),
        "taille (Ko)": round(len(tampon.getvalue()) / 1024, 1),
        "mémoire de pointe à l'entraînement (Mo)": round(pic / 1e6, 1),
        "énergie d'un entraînement (Wh)": round(energie["énergie (Wh)"], 5),
    }


def calculer() -> tuple[dict, dict]:
    sys.path.insert(0, str(RACINE / "src"))
    import tomllib

    import numpy as np
    import pandas as pd

    from churn_saas import config
    from churn_saas.evaluation import (
        comparer_a_la_reference,
        evaluer_selon_protocole,
        plis_du_protocole,
        selectionner,
    )
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import (
        construire_baseline,
        construire_calibre,
        construire_candidat,
        construire_xgboost,
        courbe_apprentissage,
        explorer_grille,
        grille_hyperparametres,
        optimisme_imbrique,
        regle_un_ecart_type,
    )

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    grille = grille_hyperparametres()["regression"]

    # Grid, S1, P3, P1
    table = explorer_grille(construire_baseline, grille, X, y, plis_du_protocole())
    # pandas 3 stores None in a text column as NaN: name it explicitly.
    table["class_weight"] = table["class_weight"].map(
        lambda v: "balanced" if v == "balanced" else "None"
    )
    retenue = regle_un_ecart_type(table, config.SEUIL_ECART_SURAPPRENTISSAGE)
    reglage = {
        "C": float(table.loc[retenue, "C"]),
        "class_weight": None
        if table.loc[retenue, "class_weight"] == "None"
        else table.loc[retenue, "class_weight"],
    }

    def fabrique(Xf):
        return construire_baseline(Xf).set_params(**{f"modele__{k}": v for k, v in reglage.items()})

    # P2: paired against the champion's frozen folds
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    champion = reference["baselines"][REGRESSION]["par_pli"]["PR-AUC"]
    candidat = "régression logistique réglée"
    comparaison = comparer_a_la_reference(
        {REGRESSION: champion, candidat: table.loc[retenue, "par_pli"]}, REGRESSION
    )
    remplacer = selectionner(comparaison, REGRESSION, (REGRESSION, candidat)) == candidat

    # S3, S4, S5
    imbrique = optimisme_imbrique(
        construire_baseline, grille, X, y, config.SEUIL_ECART_SURAPPRENTISSAGE
    )
    courbe = courbe_apprentissage(fabrique(X), X, y)
    calibre = evaluer_selon_protocole(construire_calibre(fabrique, "sigmoid"), X, y)
    erreur_calibration = float(calibre.par_pli["erreur de calibration"].mean())

    # S2: validation curve along C, for the retained class weight
    courbe_c = table[table["class_weight"] == str(reglage["class_weight"])].sort_values("C")

    bilan_reglage = {
        "grille": json.loads(
            table.drop(columns=["par_pli"]).to_json(orient="records", force_ascii=False)
        ),
        "par_pli": {
            f"C={r.C}, class_weight={r.class_weight}": r.par_pli for r in table.itertuples()
        },
        "reglage_retenu": {k: (str(v) if v is None else v) for k, v in reglage.items()},
        "indice_retenu": retenue,
        "meilleur_score": float(table["PR-AUC validation"].max()),
        "score_retenu": float(table.loc[retenue, "PR-AUC validation"]),
        "courbe_validation_C": json.loads(
            courbe_c[["C", "PR-AUC entraînement", "PR-AUC validation"]].to_json(orient="records")
        ),
        "surapprentissage": {
            "S1_ecart_max_grille": float(table["écart entraînement - validation"].max()),
            "S1_ecart_retenu": float(table.loc[retenue, "écart entraînement - validation"]),
            "S1_combinaisons_ecartees": int(
                (
                    table["écart entraînement - validation"] > config.SEUIL_ECART_SURAPPRENTISSAGE
                ).sum()
            ),
            "S3": imbrique,
            "S3_conforme": imbrique["optimisme"] <= config.SEUIL_OPTIMISME_SELECTION,
            "S4_ecart_final": float(courbe["écart entraînement - validation"].iloc[-1]),
            "S4_conforme": float(courbe["écart entraînement - validation"].iloc[-1])
            <= config.SEUIL_ECART_APPRENTISSAGE,
            "S4_courbe": json.loads(courbe.to_json(orient="records", force_ascii=False)),
            "S5_erreur_calibration": erreur_calibration,
            "S5_conforme": erreur_calibration < config.SEUIL_ERREUR_CALIBRATION,
        },
        "P2_comparaison": json.loads(comparaison.to_json(orient="records", force_ascii=False)),
        "P2_remplacer_le_champion": bool(remplacer),
    }

    # P4: the three tuned models, side by side
    with open(config.FICHIER_RESSOURCES, "rb") as flux:
        hypotheses = tomllib.load(flux)["hypotheses"]
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))

    def reglages_arbres(famille):
        brut = selection["reglages"][famille]["meilleurs_parametres"]
        return {
            k.removeprefix("modele__"): (
                None
                if v == "None"
                else int(v)
                if v.isdigit()
                else float(v)
                if v.replace(".", "", 1).isdigit()
                else v
            )
            for k, v in brut.items()
        }

    modeles = {
        "régression logistique (calibrée)": construire_calibre(fabrique, "sigmoid")(X),
        "forêt aléatoire réglée": construire_candidat(X).set_params(
            **{f"modele__{k}": v for k, v in reglages_arbres("forêt aléatoire").items()}
        ),
        "xgboost réglé": construire_xgboost(X, **reglages_arbres("xgboost")),
    }
    performances = {
        "régression logistique (calibrée)": table.loc[retenue, "par_pli"],
        "forêt aléatoire réglée": selection["par_pli"]["forêt aléatoire"],
        "xgboost réglé": selection["par_pli"]["xgboost"],
    }
    mesures = []
    for nom, modele in modeles.items():
        mesure = _mesurer_ressources(nom, modele, X, y, resultat.X, hypotheses)
        mesure["PR-AUC (25 plis)"] = round(float(np.mean(performances[nom])), 4)
        mesures.append(mesure)
    ressources = pd.DataFrame(mesures)
    meilleur = ressources["PR-AUC (25 plis)"].idxmax()
    plancher = ressources.loc[meilleur, "PR-AUC (25 plis)"] - float(
        np.std(performances[ressources.loc[meilleur, "modèle"]])
    )
    equivalents = ressources[ressources["PR-AUC (25 plis)"] >= plancher]
    cout = equivalents["entraînement (s)"] + equivalents["lot de 5 000 comptes (s)"]
    bilan_ressources = {
        "mesures": json.loads(ressources.to_json(orient="records", force_ascii=False)),
        "equivalents_en_performance": equivalents["modèle"].tolist(),
        "P4_retenu": ressources.loc[cout.idxmin(), "modèle"],
        "budgets": {
            "lot_mensuel_s": config.BUDGET_LOT_MENSUEL_S,
            "un_compte_ms": config.BUDGET_COMPTE_MS,
        },
        "budgets_respectes": {
            m["modèle"]: bool(
                m["lot de 5 000 comptes (s)"] < config.BUDGET_LOT_MENSUEL_S
                and m["un compte (ms)"] < config.BUDGET_COMPTE_MS
            )
            for m in mesures
        },
        "poste": "mesures sur la machine qui exécute l'outil",
    }
    return bilan_reglage, bilan_ressources


def executer(forcer: bool = False) -> tuple[dict, dict]:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas.donnees import charger_manifeste
    from churn_saas.modelisation import annoncer_duree
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("8", "tools/reglage_modele.py", manifeste)
    identite = identite_execution(etiquettes, outil="reglage_modele")
    if REGLAGE.exists() and RESSOURCES.exists() and not forcer:
        reglage = json.loads(REGLAGE.read_text(encoding="utf-8"))
        if reglage.get("identite_execution") == identite:
            print("Réglage identique déjà enregistré : rien n'est recalculé.", flush=True)
            return reglage, json.loads(RESSOURCES.read_text(encoding="utf-8"))
    print(
        annoncer_duree(entrainements_lr=350 + 150 + 25 + 250 + 10, entrainements_foret=8),
        "(réglage, imbriqué, courbes, calibration, ressources)",
        flush=True,
    )
    debut = time.perf_counter()
    reglage, ressources = calculer()
    date = time.strftime("%Y-%m-%d %H:%M")
    reglage = {
        "identite_execution": identite,
        **reglage,
        "duree_s": round(time.perf_counter() - debut, 1),
        "date": date,
    }
    ressources = {"identite_execution": identite, **ressources, "date": date}
    for chemin, contenu in ((REGLAGE, reglage), (RESSOURCES, ressources)):
        chemin.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
    return reglage, ressources


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Réglage du modèle retenu (phase 8).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un calcul identique")
    arguments = analyseur.parse_args(argv)
    reglage, ressources = executer(arguments.forcer)
    resume = {
        "reglage_retenu": reglage["reglage_retenu"],
        "score_retenu": round(reglage["score_retenu"], 4),
        "remplacer_le_champion": reglage["P2_remplacer_le_champion"],
        "optimisme": round(reglage["surapprentissage"]["S3"]["optimisme"], 4),
        "P4_retenu": ressources["P4_retenu"],
    }
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
