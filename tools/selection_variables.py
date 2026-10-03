"""Phase 5's heavy computations, recorded once and read by the notebooks (optimisation B1).

    uv run python tools/selection_variables.py            # writes the results file
    uv run python tools/selection_variables.py --forcer   # redo an identical computation

The certification notebook used to redo, at every run, about eleven minutes of phase 5
computations: adversarial validation, label permutation test, learning curves, leak
demonstration, contribution of the constructed variables, ablation by family, permutation
importances, removal confirmations, final selection. They are deterministic - fixed seed,
shared folds - so their result only changes with the code, the data or the protocol: the
very components of the execution identity shared by every tool (A1).

This tool computes them, records them with that identity, and returns the recorded results
as long as the identity is unchanged. The notebook draws its figures and tables from them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "selection_variables.json"
MODELES = ("Régression logistique", "Forêt aléatoire")


def _tableau(df) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def calculer() -> dict:
    """Every phase 5 computation the notebook shows, on the parts it shows them on."""
    sys.path.insert(0, str(RACINE / "src"))
    import pandas as pd

    from churn_saas import config
    from churn_saas.features import (
        VARIABLES_CONSTRUITES,
        ablation_par_groupe,
        candidates_au_retrait,
        comparer_jeux,
        confirmer_retraits,
        executer_pipeline,
        importances_par_permutation,
        parties_avant_selection,
        parties_du_decoupage,
    )
    from churn_saas.modelisation import (
        construire_baseline,
        construire_candidat,
        courbe_apprentissage,
        demontrer_fuite,
        tester_permutation,
        validation_adverse,
    )

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, Xa, ya = resultat.X, parties.X_entrainement, parties.y_entrainement
    fabriques = {MODELES[0]: construire_baseline, MODELES[1]: construire_candidat}

    adverse = validation_adverse(construire_candidat(X, equilibrer=False), Xa, parties.X_test)
    permutation = tester_permutation(construire_baseline(X), Xa, ya, n_permutations=100)
    courbes = {nom: courbe_apprentissage(f(X), Xa, ya) for nom, f in fabriques.items()}
    sante = pd.to_numeric(resultat.silver["sante_compte_fin_periode"], errors="coerce")
    fuites = {nom: demontrer_fuite(f, Xa, ya, sante) for nom, f in fabriques.items()}

    candidats = parties_avant_selection(resultat)
    XC, yC = candidats.X_entrainement, candidats.y_entrainement
    brutes = [c for c in XC.columns if c not in VARIABLES_CONSTRUITES]
    apports = {
        nom: comparer_jeux(f, XC, yC, {"brutes": brutes, "brutes + construites": list(XC.columns)})
        for nom, f in fabriques.items()
    }
    ablations = {nom: ablation_par_groupe(f, XC, yC) for nom, f in fabriques.items()}
    importances = {nom: importances_par_permutation(f, XC, yC) for nom, f in fabriques.items()}
    table = candidates_au_retrait(importances)
    liste = [
        v
        for v in table.index
        if table.loc[v, "sous le plancher pour tous les modèles"] and not table.loc[v, "leurre"]
    ]
    confirmations = {nom: confirmer_retraits(f, XC, yC, liste) for nom, f in fabriques.items()}
    retenues = [c for c in XC.columns if c not in config.EXCLUES_PAR_SELECTION]
    final = {
        nom: comparer_jeux(
            f, XC, yC, {"25 candidates": list(XC.columns), f"{len(retenues)} retenues": retenues}
        )
        for nom, f in fabriques.items()
    }

    return {
        "adverse": {
            "auc": adverse["auc"],
            "conforme": bool(adverse["conforme"]),
            "taux_faux_positifs": list(map(float, adverse["taux_faux_positifs"])),
            "taux_vrais_positifs": list(map(float, adverse["taux_vrais_positifs"])),
        },
        "permutation": {
            "score": permutation["score"],
            "p_valeur": permutation["p_valeur"],
            "moyenne_permutee": permutation["moyenne_permutee"],
            "conforme": bool(permutation["conforme"]),
            "scores_permutes": list(map(float, permutation["scores_permutes"])),
        },
        "courbes": {nom: _tableau(c) for nom, c in courbes.items()},
        "fuites": {nom: _tableau(f) for nom, f in fuites.items()},
        "apports": {nom: _tableau(s) for nom, s in apports.items()},
        "ablations": {nom: _tableau(a) for nom, a in ablations.items()},
        "importances": {nom: _tableau(i) for nom, i in importances.items()},
        "candidates_au_retrait": liste,
        "confirmations": {nom: _tableau(c) for nom, c in confirmations.items()},
        "final": {nom: _tableau(s) for nom, s in final.items()},
    }


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    """The recorded results if their identity is unchanged; computed and recorded otherwise."""
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas.donnees import charger_manifeste
    from churn_saas.modelisation import annoncer_duree
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("5", "tools/selection_variables.py", manifeste)
    identite = identite_execution(etiquettes, outil="selection_variables")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print(
                "Calculs de la phase 5 déjà enregistrés à l'identique : rien n'est recalculé.",
                flush=True,
            )
            return existant
    print(
        annoncer_duree(entrainements_lr=1150, entrainements_foret=700),
        "(calculs de la phase 5)",
        flush=True,
    )
    debut = time.perf_counter()
    bilan = {
        "identite_execution": identite,
        **calculer(),
        "duree_s": round(time.perf_counter() - debut, 1),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(bilan, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return bilan


def en_objets(bilan: dict) -> dict:
    """The recorded results as the objects the notebook's figures and tables expect."""
    import numpy as np
    import pandas as pd

    tables = lambda d: {nom: pd.DataFrame(v) for nom, v in d.items()}  # noqa: E731
    adverse = dict(bilan["adverse"])
    adverse["taux_faux_positifs"] = np.asarray(adverse["taux_faux_positifs"])
    adverse["taux_vrais_positifs"] = np.asarray(adverse["taux_vrais_positifs"])
    permutation = dict(bilan["permutation"])
    permutation["scores_permutes"] = np.asarray(permutation["scores_permutes"])
    return {
        "adverse": adverse,
        "permutation": permutation,
        "courbes": tables(bilan["courbes"]),
        "fuites": tables(bilan["fuites"]),
        "apports": tables(bilan["apports"]),
        "ablations": tables(bilan["ablations"]),
        "importances": tables(bilan["importances"]),
        "candidates_au_retrait": bilan["candidates_au_retrait"],
        "confirmations": tables(bilan["confirmations"]),
        "final": tables(bilan["final"]),
    }


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Calculs de la phase 5, enregistrés (B1).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un calcul identique")
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.forcer, Path(arguments.sortie))
    print(f"Durée du calcul : {bilan['duree_s']} s ; enregistré le {bilan['date']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
