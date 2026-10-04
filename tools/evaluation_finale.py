"""The single evaluation on the test part (rule B4), then the model put into service.

    uv run python tools/evaluation_finale.py

The test part has been sealed since phase 5. This tool opens it ONCE:

1. It refuses to run if `resultats/evaluation_finale.json` already exists - a second look
   at the test part would turn it into a validation set. `--refaire "motif"` overrides
   that, and the motif is kept in the file's history: a second evaluation is possible,
   never silent.
2. It fits the model retained by `tools/selection_modele.py` - with the calibration
   retained there - on the WHOLE training part.
3. It measures every metric of the protocol on the test part, with 95 % bootstrap
   confidence intervals (1,000 draws).
4. It writes the model and its card under models/ (`packaging.sauvegarder_modele`) and,
   when MLflow is installed, registers it under the alias `champion`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "evaluation_finale.json"
SELECTION = RACINE / "resultats" / "selection_modele.json"


def intervalles_bootstrap(y, score, mesurer, tirages: int, niveau: float, graine: int) -> dict:
    """Percentile bootstrap of every protocol metric on the test part."""
    import numpy as np

    y, score = np.asarray(y).astype(int), np.asarray(score, dtype=float)
    generateur = np.random.default_rng(graine)
    echantillons = []
    for _ in range(tirages):
        indices = generateur.integers(0, len(y), len(y))
        if y[indices].min() == y[indices].max():
            continue  # a draw without both classes has no PR-AUC
        echantillons.append(mesurer(y[indices], score[indices]))
    bas, haut = (1 - niveau) / 2, 1 - (1 - niveau) / 2
    return {
        metrique: [
            round(float(np.quantile([e[metrique] for e in echantillons], bas)), 4),
            round(float(np.quantile([e[metrique] for e in echantillons], haut)), 4),
        ]
        for metrique in echantillons[0]
    }


def executer(refaire: str | None = None, sortie: Path = DESTINATION, publier: bool = False) -> dict:
    """Evaluate once and publish; with `publier`, only publish the already-evaluated model.

    Publishing refits the retained model on the training part, writes it under models/
    and registers it as `champion` - without looking at the test part again: a fresh clone
    or a cleaned MLflow store gets its champion back without a second evaluation.
    """
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas import config
    from churn_saas.donnees import charger_manifeste
    from churn_saas.evaluation import mesurer
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import (
        construire_baseline,
        construire_calibre,
        construire_candidat,
        construire_xgboost,
    )
    from churn_saas.packaging import etiquettes_tracabilite

    historique = []
    if publier:
        if not sortie.exists():
            raise SystemExit("Rien à publier : l'évaluation finale n'a pas encore été faite.")
    elif sortie.exists():
        precedent = json.loads(sortie.read_text(encoding="utf-8"))
        if not refaire:
            raise SystemExit(
                f"Évaluation finale déjà faite le {precedent['date']} : le jeu de test ne sert "
                'qu\'une fois (règle B4). --refaire "motif" pour la refaire, motif consigné.'
            )
        historique = precedent.get("historique", []) + [
            {
                "date": precedent["date"],
                "remplacee_le": time.strftime("%Y-%m-%d %H:%M"),
                "motif": refaire,
                "metriques": precedent["metriques"],
            }
        ]

    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    retenu = selection["modele_retenu"]
    methode = selection["calibration"]["methode_retenue"]
    reglages = {
        k.removeprefix("modele__"): (None if v == "None" else (int(v) if v.isdigit() else v))
        for k, v in selection["reglages"].get(retenu, {}).get("meilleurs_parametres", {}).items()
    }
    familles = {
        "régression logistique": construire_baseline,
        "forêt aléatoire": construire_candidat,
        "xgboost": construire_xgboost,
    }

    def fabrique(X):
        modele = familles[retenu](X)
        return modele.set_params(**{f"modele__{k}": v for k, v in reglages.items()})

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X_a, y_a = parties.X_entrainement, parties.y_entrainement.astype(int)
    X_t, y_t = parties.X_test, parties.y_test.astype(int)
    modele = construire_calibre(fabrique, methode)(X_a).fit(X_a, y_a)

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("7", "tools/evaluation_finale.py", manifeste)
    if publier:
        bilan = json.loads(sortie.read_text(encoding="utf-8"))
        metriques = bilan["metriques"]
        return _publier(
            modele,
            bilan,
            metriques,
            etiquettes,
            retenu,
            methode,
            reglages,
            (X_a, y_a),
            sortie,
            ecrire=False,
        )
    score = modele.predict_proba(X_t)[:, 1]
    metriques = {k: round(v, 4) for k, v in mesurer(y_t, score).items()}
    intervalles = intervalles_bootstrap(
        y_t, score, mesurer, config.TIRAGES_BOOTSTRAP, config.NIVEAU_CONFIANCE, config.GRAINE
    )
    bilan = {
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "modele": f"{retenu}, calibration {methode}",
        "comptes_test": int(len(y_t)),
        "taux_churn_test": round(float(y_t.mean()), 4),
        "metriques": metriques,
        "intervalles_95": intervalles,
        "validation_croisee_pr_auc": selection["calibration"]["methodes"][methode]["PR-AUC"],
        "empreinte_gold": etiquettes.get("empreinte_gold"),
        "empreinte_comptes_test": etiquettes.get("empreinte_comptes_test"),
        "empreinte_code": etiquettes.get("empreinte_code"),
        "historique": historique,
    }

    return _publier(
        modele, bilan, metriques, etiquettes, retenu, methode, reglages, (X_a, y_a), sortie
    )


def _publier(
    modele,
    bilan,
    metriques,
    etiquettes,
    retenu,
    methode,
    reglages,
    entrainement,
    sortie,
    ecrire: bool = True,
) -> dict:
    """Model and card under models/, results file, `champion` alias when MLflow is there."""
    X_a = entrainement[0]
    from churn_saas.packaging import FicheModele, sauvegarder_modele

    fiche = FicheModele(
        nom="churn_saas",
        version="1.0",
        empreinte_donnees=str(etiquettes.get("empreinte_gold", ""))[:16],
        hyperparametres={"famille": retenu, "calibration": methode, **reglages},
        metriques_validation={f"test_{k}": v for k, v in metriques.items()},
        variables=list(X_a.columns),
        responsable_validation="porteur du projet",
    )
    chemin = sauvegarder_modele(modele, fiche, entrainement=entrainement, lignage=etiquettes)
    bilan["artefact"] = chemin.relative_to(RACINE).as_posix()
    from churn_saas.packaging import decrire_modele

    bilan["descriptif_modele"] = decrire_modele(modele)
    if not ecrire:  # --publier: metadata only (the test part is not read), kept in the file
        sortie.write_text(
            json.dumps(bilan, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if ecrire:
        sortie.parent.mkdir(parents=True, exist_ok=True)
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
            activer_experience(nom_experience("phase7-evaluation-finale"))
            with mlflow.start_run(run_name=f"evaluation finale {bilan['date']}") as run:
                import hashlib

                configuration = json.dumps(fiche.hyperparametres, sort_keys=True, default=str)
                mlflow.set_tags(
                    etiquettes
                    | {
                        "modele": bilan["modele"],
                        "configuration": hashlib.sha256(configuration.encode()).hexdigest()[:16],
                    }
                )
                mlflow.log_metrics(
                    {
                        f"test_{k.replace(' ', '_').replace('é', 'e')}": v
                        for k, v in metriques.items()
                        if v == v
                    }
                )
                mlflow.log_dict(bilan, "evaluation_finale.json")
                journaliser_modele(modele, X_a)
            bilan["version_registre"], _ = enregistrer_si_nouveau(
                run.info.run_id, alias=ALIAS_RETENU
            )
    except ImportError:
        pass
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included,
    # which escaped the first version of this fix (see test_conventions).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    import os

    os.environ.setdefault("MPLBACKEND", "Agg")
    analyseur = argparse.ArgumentParser(description="Évaluation unique sur le jeu de test.")
    analyseur.add_argument("--refaire", metavar="MOTIF", help="refaire, motif consigné")
    analyseur.add_argument(
        "--publier",
        action="store_true",
        help="republier le modèle déjà évalué (models/, alias champion), sans relire le test",
    )
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.refaire, Path(arguments.sortie), arguments.publier)
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
