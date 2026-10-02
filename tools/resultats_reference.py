"""Record the baselines' reference results, or check that the code still reproduces them.

    uv run python tools/resultats_reference.py              # writes the reference file
    uv run python tools/resultats_reference.py --verifier   # recompute and compare, exit 1 if not

Phase 7 must prove it does better than the logistic regression. Compared with a figure
recomputed on the fly, a regression anywhere in the chain would move both sides at once
and go unseen; compared with a recorded reference, it shows. The file stores the protocol
(seed, folds, top share), the gold fingerprint the results were computed on, and every
metric on every fold for the three baselines.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "reference_baseline.json"
TOLERANCE = 1e-6


def calculer() -> dict:
    """Run the three baselines under the protocol, on the training part of the gold."""
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas import config
    from churn_saas.donnees import empreinte_donnees
    from churn_saas.evaluation import evaluer_selon_protocole
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import (
        construire_baseline,
        construire_baseline_metier,
        construire_baseline_naive,
    )

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement
    baselines = {
        "naïve": (construire_baseline_naive, True),
        "règle métier": (construire_baseline_metier, False),
        "régression logistique": (construire_baseline, True),
    }
    scores = {}
    for nom, (fabrique, probabiliste) in baselines.items():
        par_pli = evaluer_selon_protocole(fabrique, X, y, probabiliste).par_pli
        scores[nom] = {
            "par_pli": {m: [_nombre(v) for v in par_pli[m]] for m in par_pli.columns},
            "moyenne": {m: _nombre(par_pli[m].mean()) for m in par_pli.columns},
        }
    return {
        "protocole": {
            "graine": config.GRAINE,
            "plis": config.PLIS_VALIDATION,
            "repetitions": config.REPETITIONS_VALIDATION,
            "part_haut_classement": config.PART_HAUT_CLASSEMENT,
            "seuil_erreur_calibration": config.SEUIL_ERREUR_CALIBRATION,
            "regle_metier": config.VARIABLE_REGLE_METIER,
            "partie": "entraînement (le test reste sous scellés)",
        },
        "donnees": {
            "empreinte_gold": empreinte_donnees(resultat.gold),
            "comptes_entrainement": len(y),
            "variables": list(X.columns),
        },
        "baselines": scores,
    }


def _nombre(valeur: float) -> float | None:
    """JSON has no NaN: a metric that does not apply is recorded as null."""
    return None if valeur is None or math.isnan(float(valeur)) else round(float(valeur), 10)


def ecarts(reference: dict, recalcule: dict) -> list[str]:
    """Every difference between two result files, beyond the numeric tolerance."""
    differences = []
    for section in ("protocole", "donnees"):
        if reference.get(section) != recalcule.get(section):
            differences.append(f"{section} : enregistré ≠ recalculé")
    for nom, valeurs in recalcule["baselines"].items():
        enregistre = reference.get("baselines", {}).get(nom)
        if enregistre is None:
            differences.append(f"{nom} : absente de la référence")
            continue
        for metrique, liste in valeurs["par_pli"].items():
            for a, b in zip(enregistre["par_pli"].get(metrique, []), liste, strict=False):
                if (a is None) != (b is None) or (a is not None and abs(a - b) > TOLERANCE):
                    differences.append(f"{nom} · {metrique} : {a} ≠ {b}")
                    break
    return differences


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Résultats de référence des baselines.")
    analyseur.add_argument("--verifier", action="store_true", help="recalculer et comparer")
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)

    recalcule = calculer()
    destination = Path(arguments.sortie)
    if arguments.verifier:
        reference = json.loads(destination.read_text(encoding="utf-8"))
        differences = ecarts(reference, recalcule)
        for difference in differences:
            print(f"  - {difference}")
        print(
            "Résultats de référence reproduits."
            if not differences
            else "Résultats de référence NON reproduits."
        )
        return 1 if differences else 0

    destination.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(recalcule, ensure_ascii=False, indent=2)
    destination.write_text(texte + "\n", encoding="utf-8", newline="\n")
    for nom, valeurs in recalcule["baselines"].items():
        print(f"{nom:24s} PR-AUC {valeurs['moyenne']['PR-AUC']:.3f}")
    try:
        affiche = destination.relative_to(RACINE)
    except ValueError:
        affiche = destination
    print(f"Référence écrite : {affiche}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
