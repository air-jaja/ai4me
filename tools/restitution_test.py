"""Phase 9, step 3 (rule R6): the single reporting read of the test part.

    uv run python tools/restitution_test.py

Decided by the project owner on 03/10/2026 and committed before this tool first ran: ONE
read of the test part, for reporting only - no decision may follow from it (R12). It
scores the 1,000 test accounts with the EVALUATED champion (five calibrated copies, as in
the phase 7 evaluation; decision i: the served model is not evaluated on the test part),
and records, in the same pass, everything that needs the test data itself:

- per-account scores, outcome, value, recurring revenue and segments
  (`resultats/scores_test.csv`): every later analysis reads this file, never the test part;
- permutation importance of the 18 variables on the test part, 30 repetitions (R10);
- exact local contributions of three accounts (R11);
- the calibration curve (R7).

Like the phase 7 evaluation, the tool refuses to run twice; `--refaire "motif"` overrides
it and keeps the motive in the file's history.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SCORES = RACINE / "resultats" / "scores_test.csv"
BILAN = RACINE / "resultats" / "restitution_test.json"


def executer(refaire: str | None = None) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import numpy as np
    import pandas as pd
    from sklearn.calibration import calibration_curve
    from sklearn.inspection import permutation_importance

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.evaluation import appliquer_regle, contributions_lineaires
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline, construire_calibre
    from churn_saas.packaging import etiquettes_tracabilite

    historique = []
    if BILAN.exists():
        precedent = json.loads(BILAN.read_text(encoding="utf-8"))
        if not refaire:
            raise SystemExit(
                f"Lecture de restitution déjà faite le {precedent['date']} : elle est unique "
                '(règle R6). --refaire "motif" pour la refaire, motif consigné.'
            )
        historique = precedent.get("historique", []) + [
            {
                "date": precedent["date"],
                "remplacee_le": time.strftime("%Y-%m-%d %H:%M"),
                "motif": refaire,
            }
        ]

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X_a, y_a = parties.X_entrainement, parties.y_entrainement.astype(int)
    X_t, y_t = parties.X_test, parties.y_test.astype(int)
    champion = construire_calibre(construire_baseline, "sigmoid")(X_a).fit(X_a, y_a)

    # --- the read itself ---------------------------------------------------------------------
    proba = pd.Series(champion.predict_proba(X_t)[:, 1], index=X_t.index)
    silver = resultat.silver.loc[X_t.index]
    valeur = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    capacite = round(config.CAPACITE_MENSUELLE * len(X_t) / len(resultat.X))
    regle = appliquer_regle(proba, valeur, capacite)
    seuil_protocole = proba.quantile(1 - config.PART_HAUT_CLASSEMENT)
    scores = pd.DataFrame(
        {
            "client_id": silver["client_id"],
            "churn": y_t,
            "proba": proba.round(6),
            "valeur_vie_client_eur": valeur,
            "mrr_eur": pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce"),
            **{s: silver[s].astype(str) for s in config.SEGMENTS_EQUITE},
            "valeur_nette_eur": regle["valeur_nette_eur"].round(2),
            "seuil_compte": regle["seuil_compte"].round(6),
            "rang_valeur": regle["rang"],
            "traite_metier": regle["a_traiter"],
            "signale_protocole": proba >= seuil_protocole,
        }
    )

    # R10: permutation importance on the test part
    def pr_auc(modele, X, y):
        from sklearn.metrics import average_precision_score

        return average_precision_score(y, modele.predict_proba(X)[:, 1])

    importance = permutation_importance(
        champion,
        X_t,
        y_t,
        scoring=pr_auc,
        n_repeats=config.REPETITIONS_PERMUTATION_TEST,
        random_state=config.GRAINE,
        n_jobs=1,
    )
    importances = pd.DataFrame(
        {
            "variable": X_t.columns,
            "baisse moyenne de PR-AUC": importance.importances_mean,
            "borne basse 95 %": np.quantile(importance.importances, 0.025, axis=1),
            "borne haute 95 %": np.quantile(importance.importances, 0.975, axis=1),
        }
    ).sort_values("baisse moyenne de PR-AUC", ascending=False)
    importances["apport démontré sur le test"] = importances["borne basse 95 %"] > 0

    # R11: three accounts - highest expected value, the limit of the list, a false positive
    traites = scores[scores["traite_metier"]].sort_values("rang_valeur")
    faux_positifs = traites[traites["churn"] == 0]
    choisis = {
        "plus forte valeur espérée": traites.index[0],
        "à la limite de la liste": scores.index[scores["rang_valeur"] == capacite][0],
        "faux positif traité": faux_positifs.index[0] if len(faux_positifs) else None,
    }
    contributions, base = contributions_lineaires(champion, X_t, X_a)
    locales = {}
    for role, indice in choisis.items():
        if indice is None:
            continue
        ligne = contributions.loc[indice]
        ordre = ligne.abs().sort_values(ascending=False).index[:6]
        locales[role] = {
            "client_id": str(scores.loc[indice, "client_id"]),
            "probabilite": float(scores.loc[indice, "proba"]),
            "depart_reel": int(scores.loc[indice, "churn"]),
            "base_cotes": round(base, 4),
            "contributions_cotes": {v: round(float(ligne[v]), 4) for v in ordre},
            "valeurs": {v: str(X_t.loc[indice, v]) for v in ordre},
        }

    # R7: calibration curve
    vrais, predits = calibration_curve(y_t, proba, n_bins=10, strategy="quantile")

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("9", "tools/restitution_test.py", manifeste)
    bilan = {
        "motif": config.MOTIF_LECTURE_RESTITUTION,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "modele": "champion évalué (5 copies calibrées, sigmoïde) — décision i",
        "comptes": int(len(X_t)),
        "capacite_ramenee": capacite,
        "empreinte_comptes_test": etiquettes.get("empreinte_comptes_test"),
        "importance_permutation": json.loads(
            importances.to_json(orient="records", force_ascii=False)
        ),
        "explications_locales": locales,
        "calibration": {
            "predit": [float(v) for v in predits],
            "observe": [float(v) for v in vrais],
        },
        "historique": historique,
    }
    SCORES.write_text(scores.to_csv(index=False), encoding="utf-8", newline="\n")
    BILAN.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Lecture unique de restitution du test (R6).")
    analyseur.add_argument("--refaire", metavar="MOTIF", help="refaire, motif consigné")
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.refaire)
    print(
        f"Lecture de restitution faite le {bilan['date']} : {bilan['comptes']} comptes, "
        f"scores dans {SCORES.relative_to(RACINE).as_posix()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
