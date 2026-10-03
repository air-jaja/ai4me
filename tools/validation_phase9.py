"""Phase 9, steps 4 to 7 - the analyses, from the recorded test scores only (R7 to R9).

    uv run python tools/validation_phase9.py     # writes resultats/validation_phase9.json

Reads `resultats/scores_test.csv`, written by the single reporting read (R6): this tool
never touches the test part. Rules validated before any computation (choix § 7 septies):

- R7: PR-AUC and ROC-AUC with 95 % bootstrap intervals, the gap between cross-validation
  and test, the calibration error;
- R5: confusion matrices at the business operating point (28 accounts by net expected value)
  and at the protocol one (top 10 % by probability);
- R8: monthly recurring revenue exposed, covered and preserved, in euros, with intervals,
  and its extrapolation to the portfolio - presented as an extrapolation;
- R9: recall and precision by sector, country and company size at the protocol point, with
  intervals and base churn rates; inconclusive below 50 accounts or 10 departures;
  criterion: recall >= 0.8 x global recall, or an interval containing the global recall.

Deterministic (fixed seed): recomputed in a few seconds, no execution identity needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SCORES = RACINE / "resultats" / "scores_test.csv"
DESTINATION = RACINE / "resultats" / "validation_phase9.json"
TIRAGES = 1000


def _intervalle(valeurs) -> list[float]:
    import numpy as np

    return [
        round(float(np.quantile(valeurs, 0.025)), 4),
        round(float(np.quantile(valeurs, 0.975)), 4),
    ]


def metriques_globales(scores, graine: int) -> dict:
    """R7: PR-AUC, ROC-AUC and calibration error, with 95 % bootstrap intervals."""
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.evaluation import erreur_calibration

    y, p = scores["churn"].to_numpy(), scores["proba"].to_numpy()
    generateur = np.random.default_rng(graine)
    tirages = {"PR-AUC": [], "ROC-AUC": [], "erreur de calibration": []}
    for _ in range(TIRAGES):
        i = generateur.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        tirages["PR-AUC"].append(average_precision_score(y[i], p[i]))
        tirages["ROC-AUC"].append(roc_auc_score(y[i], p[i]))
        tirages["erreur de calibration"].append(erreur_calibration(y[i], p[i]))
    valeurs = {
        "PR-AUC": average_precision_score(y, p),
        "ROC-AUC": roc_auc_score(y, p),
        "erreur de calibration": erreur_calibration(y, p),
    }
    return {
        m: {"valeur": round(float(v), 4), "intervalle_95": _intervalle(tirages[m])}
        for m, v in valeurs.items()
    }


def matrice(scores, colonne: str) -> dict:
    """Confusion matrix of one operating point."""
    signale, reel = scores[colonne].astype(bool), scores["churn"].astype(bool)
    vp, fp = int((signale & reel).sum()), int((signale & ~reel).sum())
    fn, vn = int((~signale & reel).sum()), int((~signale & ~reel).sum())
    return {
        "vrais positifs": vp,
        "faux positifs": fp,
        "faux négatifs": fn,
        "vrais négatifs": vn,
        "précision": round(vp / max(vp + fp, 1), 4),
        "rappel": round(vp / max(vp + fn, 1), 4),
        "comptes signalés": vp + fp,
    }


def niveaux_mrr(scores, colonne: str, efficacite: float, graine: int, facteur: float) -> dict:
    """R8: MRR exposed (departing accounts), covered (departing AND treated), preserved
    (covered x retention efficacy), with bootstrap intervals and portfolio extrapolation."""
    import numpy as np

    mrr, reel = scores["mrr_eur"].fillna(0).to_numpy(), scores["churn"].to_numpy().astype(bool)
    traite = scores[colonne].to_numpy().astype(bool)

    def niveaux(i):
        expose = mrr[i][reel[i]].sum()
        couvert = mrr[i][reel[i] & traite[i]].sum()
        return expose, couvert, couvert * efficacite

    expose, couvert, preserve = niveaux(np.arange(len(mrr)))
    generateur = np.random.default_rng(graine)
    tirages = np.array(
        [niveaux(generateur.integers(0, len(mrr), len(mrr))) for _ in range(TIRAGES)]
    )
    resultat = {}
    for k, (nom, valeur) in enumerate(
        (("exposé", expose), ("couvert", couvert), ("préservé", preserve))
    ):
        resultat[nom] = {
            "€ par mois (test)": round(float(valeur), 0),
            "intervalle_95": [
                round(float(v), 0) for v in np.quantile(tirages[:, k], [0.025, 0.975])
            ],
            "€ par mois (extrapolé au portefeuille)": round(float(valeur * facteur), 0),
        }
    resultat["part couverte"] = round(float(couvert / expose), 4) if expose else None
    return resultat


def equite(scores, segments, colonne, taille_min, departs_min, ratio, graine) -> list[dict]:
    """R9: recall and precision by segment at the protocol point, with bootstrap intervals."""
    import numpy as np

    global_rappel = matrice(scores, colonne)["rappel"]
    generateur = np.random.default_rng(graine)
    lignes = []
    for segment in segments:
        # A missing segment value is a modality of its own, not a row silently dropped.
        modalites = scores[segment].fillna("non renseigné").replace({"nan": "non renseigné"})
        for modalite, groupe in scores.groupby(modalites):
            departs = int(groupe["churn"].sum())
            m = matrice(groupe, colonne)
            concluant = len(groupe) >= taille_min and departs >= departs_min
            rappels = []
            if departs:
                partis = groupe[groupe["churn"] == 1][colonne].to_numpy().astype(bool)
                rappels = [
                    partis[generateur.integers(0, len(partis), len(partis))].mean()
                    for _ in range(TIRAGES)
                ]
            intervalle = _intervalle(rappels) if rappels else None
            respecte = bool(
                m["rappel"] >= ratio * global_rappel
                or (intervalle and intervalle[0] <= global_rappel <= intervalle[1])
            )
            lignes.append(
                {
                    "segment": segment,
                    "modalité": str(modalite),
                    "comptes": int(len(groupe)),
                    "départs": departs,
                    "taux de départ": round(departs / len(groupe), 4),
                    "signalés": m["comptes signalés"],
                    "rappel": m["rappel"],
                    "intervalle du rappel": intervalle,
                    "précision": m["précision"],
                    "concluant": concluant,
                    "critère respecté": respecte if concluant else None,
                }
            )
    return lignes


def executer(sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    import pandas as pd

    from churn_saas import config

    scores = pd.read_csv(SCORES, dtype={"client_id": str})
    selection = json.loads(
        (RACINE / "resultats" / "selection_modele.json").read_text(encoding="utf-8")
    )
    reglage = json.loads((RACINE / "resultats" / "reglage_modele.json").read_text(encoding="utf-8"))
    restitution = json.loads(
        (RACINE / "resultats" / "restitution_test.json").read_text(encoding="utf-8")
    )
    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    taille_portefeuille = int(manifeste["jeux_derives"]["jeux"]["gold"]["lignes"])
    facteur = taille_portefeuille / len(scores)
    globales = metriques_globales(scores, config.GRAINE)
    cv = selection["calibration"]["methodes"]["sigmoid"]["PR-AUC"]
    lignes_equite = equite(
        scores,
        config.SEGMENTS_EQUITE,
        "signale_protocole",
        config.TAILLE_MIN_SEGMENT,
        config.DEPARTS_MIN_SEGMENT,
        config.RATIO_EQUITE,
        config.GRAINE,
    )
    concluantes = [ligne for ligne in lignes_equite if ligne["concluant"]]
    bilan = {
        "source": "resultats/scores_test.csv (lecture unique de restitution du "
        f"{restitution['date']}) ; le jeu de test n'est pas relu",
        "metriques": globales,
        "ecart_validation_croisee_test": {
            "PR-AUC validation croisée (25 plis, champion calibré)": cv,
            "PR-AUC validation croisée imbriquée": round(
                reglage["surapprentissage"]["S3"]["score_externe"], 4
            ),
            "PR-AUC test": globales["PR-AUC"]["valeur"],
            "écart": round(cv - globales["PR-AUC"]["valeur"], 4),
            "validation croisée dans l'intervalle du test": globales["PR-AUC"]["intervalle_95"][0]
            <= cv
            <= globales["PR-AUC"]["intervalle_95"][1],
        },
        "calibration": restitution["calibration"],
        "matrices": {
            "métier (28 comptes, valeur nette)": matrice(scores, "traite_metier"),
            "protocole (10 % les plus risqués)": matrice(scores, "signale_protocole"),
        },
        "mrr": {
            "métier": niveaux_mrr(
                scores, "traite_metier", config.EFFICACITE_RETENTION, config.GRAINE, facteur
            ),
            "protocole": niveaux_mrr(
                scores, "signale_protocole", config.EFFICACITE_RETENTION, config.GRAINE, facteur
            ),
            "extrapolation": f"x {facteur:g} (portefeuille de {taille_portefeuille} comptes) : "
            "ordre de grandeur, pas une mesure",
        },
        "equite": lignes_equite,
        "equite_synthese": {
            "segments concluants": len(concluantes),
            "segments non concluants": len(lignes_equite) - len(concluantes),
            "segments concluants hors critère": [
                f"{ligne['segment']} = {ligne['modalité']}"
                for ligne in concluantes
                if not ligne["critère respecté"]
            ],
        },
    }
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(description="Analyses de la phase 9 (scores enregistrés).").parse_args(
        argv
    )
    bilan = executer()
    print(
        json.dumps(
            {
                k: bilan[k]
                for k in (
                    "metriques",
                    "ecart_validation_croisee_test",
                    "matrices",
                    "equite_synthese",
                )
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
