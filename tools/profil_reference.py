"""Phase 11, A1 - the drift reference profile, versioned with the model it describes.

    uv run python tools/profil_reference.py            # writes resultats/profil_reference.json
    uv run python tools/profil_reference.py --forcer   # redo an identical computation

What the monthly monitoring compares a batch to (decision M1 to M10, 04/10/2026): for each
of the model's variables and for its score, the bin edges and shares the PSI reads; for
each variable, its missing share AS RECEIVED, before any reconstruction - the input of M8.
Computed on the TRAINING part only, the score from the served model refitted as recorded
(deterministic, no models/ needed). The profile names the `champion` it belongs to: a new
champion changes the identity, so the profile is recomputed with it (notebook section 13).
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
DESTINATION = RACINE / "resultats" / "profil_reference.json"
ALIASES = RACINE / "resultats" / "aliases_modeles.json"


def _outil_servi():
    specification = importlib.util.spec_from_file_location(
        "modele_servi", RACINE / "tools" / "modele_servi.py"
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import pandas as pd

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline
    from churn_saas.monitoring import profil_variable
    from churn_saas.monitoring.alertes import VARIABLES_CLES
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution, lire_aliases

    champion = lire_aliases(ALIASES)["champion"]
    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("11", "tools/profil_reference.py", manifeste)
    identite = identite_execution(
        etiquettes, outil="profil_reference", champion=champion["fichier_sha256"]
    )
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print("Profil de référence déjà calculé à l'identique : rien n'est recalculé.")
            return existant

    debut = time.perf_counter()
    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    servi = _outil_servi().construire_servi(construire_baseline, "sigmoid", config)
    score = pd.Series(servi(X).fit(X, y).predict_proba(X)[:, 1], index=X.index)
    recus = resultat.silver.loc[X.index, list(X.columns)]
    bilan = {
        "identite_execution": identite,
        "decision": "M1 à M10 et S1 à S7, validées par le porteur le 04/10/2026",
        "source": "partie d'entraînement ; score du modèle servi réentraîné à l'identique",
        "modele": {c: champion[c] for c in ("nom", "version", "fichier", "fichier_sha256")},
        "comptes": int(len(X)),
        "variables_cles": list(VARIABLES_CLES),
        "variables": {colonne: profil_variable(X[colonne]) for colonne in X.columns},
        "score": profil_variable(score),
        "manquants_a_l_entree": {
            colonne: round(float(recus[colonne].isna().mean()), 6) for colonne in X.columns
        },
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
    analyseur = argparse.ArgumentParser(description="Profil de référence de la dérive (phase 11).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un calcul identique")
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.forcer)
    print(
        f"Profil de référence : {bilan['comptes']} comptes, {len(bilan['variables'])} variables "
        f"et le score, modèle {bilan['modele']['nom']} {bilan['modele']['version']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
