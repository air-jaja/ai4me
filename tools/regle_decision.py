"""Phase 9, steps 1 and 2 - the decision rule and the stability of the list, WITHOUT the test.

    uv run python tools/regle_decision.py            # writes resultats/regle_decision.json
    uv run python tools/regle_decision.py --forcer   # redo an identical computation

Rules R1 to R5 were validated and committed before this tool first ran (config.py, choix
§ 7 septies). Everything here runs on the TRAINING part, scored by the served model:

- R2: each account's value - observed lifetime value, the B5 model's prediction if missing;
- R3: net expected value, per-account rational threshold (as a distribution), how many
  accounts are profitable under each economic hypothesis;
- R4: stability of the treated list under model uncertainty - 50 bootstrap refits.

The capacity is scaled to the scored sample: 140 per month for the whole portfolio.
Same execution identity as the other tools (A1).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "regle_decision.json"
VALEUR_VIE = RACINE / "resultats" / "modele_valeur_vie.json"


def _outil(nom: str):
    specification = importlib.util.spec_from_file_location(nom, RACINE / "tools" / f"{nom}.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def valeurs_des_comptes(resultat, X) -> tuple:
    """R2: observed lifetime value; the B5 model's prediction where it is missing."""
    import pandas as pd

    from churn_saas.packaging import charger_modele

    observee = pd.to_numeric(resultat.silver.loc[X.index, "valeur_vie_client_eur"], errors="coerce")
    manquantes = observee.isna() | (observee <= 0)
    if manquantes.any():
        chemin = RACINE / json.loads(VALEUR_VIE.read_text(encoding="utf-8"))["artefact"]
        if not chemin.exists():
            _outil("modele_valeur_vie").executer()
        modele, _ = charger_modele(chemin)
        observee.loc[manquantes] = modele.predict(X.loc[manquantes])
    return observee, int(manquantes.sum())


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import pandas as pd

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.evaluation import (
        appliquer_regle,
        distribution_seuils,
        part_rentable_selon_hypotheses,
        stabilite_liste,
    )
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("9", "tools/regle_decision.py", manifeste)
    identite = identite_execution(etiquettes, outil="regle_decision")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print(
                "Règle de décision déjà calculée à l'identique : rien n'est recalculé.", flush=True
            )
            return existant

    debut = time.perf_counter()
    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    capacite = round(config.CAPACITE_MENSUELLE * len(X) / len(resultat.X))
    valeur, completees = valeurs_des_comptes(resultat, X)
    servi = _outil("modele_servi").construire_servi(construire_baseline, "sigmoid", config)
    probabilites = pd.Series(servi(X).fit(X, y).predict_proba(X)[:, 1], index=X.index)

    regle = appliquer_regle(probabilites, valeur, capacite)
    hypotheses = part_rentable_selon_hypotheses(
        probabilites,
        valeur,
        config.EFFICACITES_SENSIBILITE,
        config.VARIATION_COUT_SENSIBILITE,
        capacite,
    )
    stabilite = stabilite_liste(
        servi, X, y, valeur, capacite, config.REPETITIONS_STABILITE, config.GRAINE
    )
    traites = regle[regle["a_traiter"]]
    bilan = {
        "identite_execution": identite,
        "regles": "R1 à R5 validées le 03/10/2026 (commit « decision(phase 9) »)",
        "echantillon": "partie d'entraînement, scorée par le modèle servi",
        "comptes": int(len(X)),
        "capacite_ramenee": capacite,
        "valeurs_completees_par_B5": completees,
        "seuils": distribution_seuils(regle["seuil_compte"]),
        "seuils_par_compte": [round(float(s), 6) for s in regle["seuil_compte"]],
        "comptes_rentables": int(regle["rentable"].sum()),
        "comptes_traites": int(len(traites)),
        "valeur_nette_traitee_eur": round(float(traites["valeur_nette_eur"].sum()), 0),
        "taux_de_depart_des_traites": round(float(y.loc[traites.index].mean()), 4),
        "taux_de_depart_global": round(float(y.mean()), 4),
        "hypotheses": json.loads(hypotheses.to_json(orient="records", force_ascii=False)),
        "stabilite": stabilite,
        "stabilite_conforme": stabilite["jaccard_moyen"] >= config.SEUIL_JACCARD_STABILITE,
        "duree_s": round(time.perf_counter() - debut, 1),
        "date": time.strftime("%Y-%m-%d %H:%M"),
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
    analyseur = argparse.ArgumentParser(description="Règle de décision et stabilité (phase 9).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un calcul identique")
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.forcer)
    print(
        json.dumps(
            {
                k: bilan[k]
                for k in (
                    "capacite_ramenee",
                    "seuils",
                    "comptes_rentables",
                    "comptes_traites",
                    "taux_de_depart_des_traites",
                    "stabilite_conforme",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        "Jaccard moyen :",
        round(bilan["stabilite"]["jaccard_moyen"], 3),
        "| minimum :",
        round(bilan["stabilite"]["jaccard_minimum"], 3),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
