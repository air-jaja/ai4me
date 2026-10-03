"""Phase 7, rule B5: the customer lifetime value model for accounts too recent to have one.

    uv run python tools/modele_valeur_vie.py            # writes resultats/modele_valeur_vie.json
    uv run python tools/modele_valeur_vie.py --forcer   # redo an identical comparison

Compares a linear regression and a regression forest of log(value) on 5 folds of the
training part, keeps the forest only if its paired R² gain exceeds one standard deviation
(rule B5, validated before this tool first ran), fits the retained model on the training
part and writes it under models/ with its card. Same execution identity as the other
tools (A1): an identical comparison already recorded is not redone.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "modele_valeur_vie.json"


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import (
        choisir_modele_valeur,
        comparer_modeles_valeur,
        construire_foret_valeur,
        construire_regression_valeur,
    )
    from churn_saas.packaging import (
        FicheModele,
        etiquettes_tracabilite,
        identite_execution,
        sauvegarder_modele,
    )

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("7", "tools/modele_valeur_vie.py", manifeste)
    identite = identite_execution(etiquettes, outil="valeur_vie")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print("Comparaison identique déjà enregistrée : rien n'est recalculé.", flush=True)
            return existant

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X = parties.X_entrainement
    valeur = resultat.silver.loc[X.index, "valeur_vie_client_eur"].astype(float)
    scores = comparer_modeles_valeur(X, valeur)
    retenu = choisir_modele_valeur(scores)
    fabrique = {
        "régression linéaire": construire_regression_valeur,
        "forêt de régression": construire_foret_valeur,
    }[retenu]
    garder = valeur.notna() & (valeur > 0)
    modele = fabrique(X).fit(X.loc[garder], valeur.loc[garder])
    fiche = FicheModele(
        nom="valeur_vie_client",
        version="1.0",
        empreinte_donnees=str(etiquettes.get("empreinte_gold", ""))[:16],
        hyperparametres={"famille": retenu, "cible": "log(valeur_vie_client_eur)"},
        metriques_validation={
            f"r2_log_{n.split()[0]}": round(float(scores[n].mean()), 4) for n in scores
        },
        variables=list(X.columns),
        responsable_validation="porteur du projet",
    )
    chemin = sauvegarder_modele(modele, fiche)
    bilan = {
        "identite_execution": identite,
        "regle": "B5 validée le 02/10/2026 (commit « decision(phase 7) »)",
        "r2_log_par_pli": {n: [round(float(v), 6) for v in scores[n]] for n in scores},
        "r2_log_moyen": {n: round(float(scores[n].mean()), 4) for n in scores},
        "seuil_un_ecart_type": round(float(scores["régression linéaire"].std()), 4),
        "modele_retenu": retenu,
        "comptes": int(garder.sum()),
        "artefact": chemin.relative_to(RACINE).as_posix(),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    try:
        from churn_saas.packaging import activer_experience, configurer_suivi, nom_experience

        mlflow = configurer_suivi()
        if mlflow is not None:
            activer_experience(nom_experience("phase7-valeur-vie"))
            with mlflow.start_run(run_name=f"valeur vie {bilan['date']}"):
                mlflow.set_tags(
                    etiquettes | {"identite_execution": identite, "modele_retenu": retenu}
                )
                for nom, moyenne in bilan["r2_log_moyen"].items():
                    mlflow.log_metric(f"r2_log_{nom.split()[0]}", moyenne)
                mlflow.log_dict(bilan, "modele_valeur_vie.json")
    except ImportError:
        pass
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included,
    # which escaped the first version of this fix (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Modèle de valeur vie client (règle B5).")
    analyseur.add_argument(
        "--forcer", action="store_true", help="refaire une comparaison identique"
    )
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    print(
        json.dumps(executer(arguments.forcer, Path(arguments.sortie)), ensure_ascii=False, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
