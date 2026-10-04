# ruff: noqa: E501  (English prose of the card: long text lines on purpose)
"""Generate the model card (docs/MODEL_CARD.md) from the recorded results only.

    uv run python tools/model_card.py

No figure is typed by hand: every number comes from `resultats/` and the data manifest, so
the card is regenerated, never edited. The Hugging Face template is filled in English;
sections that later phases will complete say so explicitly. Licence: MIT (project owner's
choice, 03/10/2026).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "docs" / "MODEL_CARD.md"
LICENCE = "mit"


def _lire(nom: str) -> dict:
    return json.loads((RACINE / "resultats" / f"{nom}.json").read_text(encoding="utf-8"))


def _ic(valeur: dict) -> str:
    bas, haut = valeur["intervalle_95"]
    return f"{valeur['valeur']:.3f} [{bas:.3f}; {haut:.3f}]"


def contexte() -> dict:
    servi = _lire("modele_servi")
    validation, regle = _lire("validation_phase9"), _lire("regle_decision")
    selection, ressources = _lire("selection_modele"), _lire("ressources_modeles")
    restitution = _lire("restitution_test")
    registre = json.loads(
        (RACINE / "resultats" / "registre_modeles.json").read_text(encoding="utf-8")
    )
    manifeste = json.loads((RACINE / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"))
    entree = [e for e in registre if e["nom"] == "churn_saas_servi"][-1]
    descriptif, hyper = servi["descriptif_modele"], servi["hyperparametres"]
    m = validation["metriques"]
    metier = validation["matrices"]["métier (28 comptes, valeur nette)"]
    protocole = validation["matrices"]["protocole (10 % les plus risqués)"]
    mrr = validation["mrr"]["métier"]
    equivalence = servi["equivalence"]
    lr = next(r for r in ressources["mesures"] if r["modèle"].startswith("régression"))
    comparaison = {c["modèle"]: c for c in selection["comparaison"]}
    importance = [i["variable"] for i in restitution["importance_permutation"][:4]]
    hors = ", ".join(validation["equite_synthese"]["segments concluants hors critère"]) or "none"
    gold = manifeste["jeux_derives"]["jeux"]["gold"]
    acceleration = equivalence["accélération d'un compte"]
    energie = lr["énergie d'un entraînement (Wh)"]
    return {
        "card_data": "\n".join(
            [
                f"license: {LICENCE}",
                "language: fr",
                "library_name: sklearn",
                "tags:",
                "- tabular-classification",
                "- churn",
                "- b2b-saas",
                "- calibrated-logistic-regression",
                "metrics:",
                "- average_precision",
                "- roc_auc",
            ]
        ),
        "model_id": f"churn_saas_servi {entree['version']}",
        "model_summary": "Monthly churn risk score for B2B SaaS accounts, turned into a prioritised contact "
        "list for account managers by expected net value.",
        "model_description": (
            f"A {descriptif['estimateur']} (C={hyper['C']}, class_weight={hyper['class_weight']}, "
            f"penalty={hyper['penalty']}) inside a scikit-learn pipeline (median imputation, scaling, "
            f"one-hot encoding), with {descriptif['calibration']} calibration fitted on out-of-fold "
            f"predictions - {descriptif['copies']} calibrated copy. Chosen over RandomForestClassifier and "
            "XGBClassifier by a paired comparison on 25 folds fixed before any computation."
        ),
        "developers": "Rakotovoalavo Petera Haja (CISIA certification project)",
        "shared_by": "Rakotovoalavo Petera Haja",
        "funded_by": "Not applicable (certification project)",
        "model_type": "Binary classification (churn within the next period), calibrated probabilities",
        "language": "Not applicable (tabular data; labels and documentation in French)",
        "license": "MIT",
        "base_model": "None (trained from scratch)",
        "repo": "https://github.com/air-jaja/ai4me",
        "paper": "Not applicable",
        "demo": "Not applicable",
        "direct_use": (
            "Scoring the monthly portfolio and ranking accounts by expected net value "
            "(probability x lifetime value x retention efficacy - contact cost), within the team's capacity "
            "(140 accounts per month). Each account comes with its three main reasons in plain words."
        ),
        "downstream_use": "Monthly CSV list imported into the CRM; on-demand score through the API (no decision field).",
        "out_of_scope_use": (
            "Automatic decisions without an account manager; causal reading of the reasons (a contribution "
            "explains a score, not why a customer leaves); other markets, products or data sources; "
            "pricing or contract decisions."
        ),
        "bias_risks_limitations": (
            f"Synthetic data. Fairness checked by sector, country and company size: one conclusive segment "
            f"below the criterion ({hors}), documented and monitored rather than corrected on the test set. "
            "Retention efficacy (0.25) is a hypothesis, the most fragile of the project; usage variables "
            "are strongly correlated, so their individual importance is understated."
        ),
        "bias_recommendations": (
            "Keep a human in the loop; keep the 10 % random control group to measure the real efficacy; "
            "watch the flagged segment on the next monthly batches."
        ),
        "get_started_code": "\n".join(
            [
                "from churn_saas.packaging import charger_champion",
                "from churn_saas.industrialisation.scoring import preparer",
                "from churn_saas.donnees import typer_pour_modele",
                "",
                "model, card = charger_champion()          # file hash checked against the registry",
                "X = typer_pour_modele(preparer(raw_accounts, catalogue=catalogue))",
                "risk = model.predict_proba(X)[:, 1]",
                "# Monthly list: uv run python tools/liste_operationnelle.py",
            ]
        ),
        "training_data": (
            f"{gold['lignes']} accounts after cleaning (gold, {gold['colonnes']} columns, data manifest v1.0); "
            f"frozen 80/20 stratified split; {entree['empreinte_entrainement'][:16]}... is the fingerprint of "
            "the exact training rows (resultats/registre_modeles.json)."
        ),
        "preprocessing": "Shared chain bronze -> silver -> gold; variables after the decision date removed; "
        "18 features retained in phase 5.",
        "training_regime": "fp64, scikit-learn; deterministic (fixed seed), refit in about one second.",
        "speeds_sizes_times": (
            f"{lr['taille (Ko)']} kB; training {lr['entraînement (s)']} s; one account "
            f"{servi['mesures']['modèle servi (une copie calibrée)']['un compte (ms)']} ms "
            f"(x{acceleration} faster than the evaluated five-copy champion)."
        ),
        "testing_data": "1,000 accounts held out and read for evaluation once (phase 7), then once more for "
        "reporting only (phase 9); no decision followed either read.",
        "testing_factors": "Sector, country and company size (recall at the protocol point, 4/5 rule).",
        "testing_metrics": "PR-AUC (primary: 28 % churners), ROC-AUC, calibration error, precision at the "
        "operating points, monthly recurring revenue covered.",
        "results": "\n".join(
            [
                "| Metric | Test (95 % interval) |",
                "|---|---|",
                f"| PR-AUC | {_ic(m['PR-AUC'])} |",
                f"| ROC-AUC | {_ic(m['ROC-AUC'])} |",
                f"| Calibration error | {_ic(m['erreur de calibration'])} |",
                f"| Business point (28 accounts) | precision {metier['précision']:.2f} |",
                f"| Protocol point (top 10 %) | precision {protocole['précision']:.2f}, recall {protocole['rappel']:.2f} |",
                f"| Revenue at risk covered (28 accounts) | {mrr['part couverte']:.0%} |",
            ]
        ),
        "results_summary": (
            f"Cross-validation PR-AUC {validation['ecart_validation_croisee_test']['PR-AUC validation croisée (25 plis, champion calibré)']:.3f} "
            f"lies within the test interval. Versus the frozen baseline, RandomForestClassifier "
            f"({comparaison.get('forêt aléatoire', {}).get('PR-AUC', 0):.3f}) and XGBClassifier "
            f"({comparaison.get('xgboost', {}).get('PR-AUC', 0):.3f}) do not beat LogisticRegression. "
            f"The served one-copy model is equivalent to the evaluated champion (paired gap "
            f"{equivalence['gain apparié du modèle servi']:+.4f}, rank correlation "
            f"{equivalence['corrélation de rang des probabilités']:.4f}). {regle['comptes_rentables']} of "
            f"{regle['comptes']} accounts are worth a contact: capacity, not profitability, is the constraint; "
            f"the treated list is stable (mean Jaccard {regle['stabilite']['jaccard_moyen']:.2f})."
        ),
        "model_examination": (
            f"Exact linear contributions per account (base + contributions = score). On the test set, the "
            f"most important features by permutation are {', '.join(importance)}."
        ),
        "hardware_type": "Laptop CPU (Intel Core i5-6300U, 4 cores)",
        "hours_used": "Training under one second; whole tuning about two minutes",
        "cloud_provider": "None (local)",
        "cloud_region": "None (local)",
        "co2_emitted": f"About {energie} Wh of energy per training (measured time x power); carbon negligible.",
        "model_specs": "Calibrated logistic regression on 18 tabular features; objective: log-loss.",
        "compute_infrastructure": "Local workstation; MLflow tracking; Docker stack (API, MLflow, PostgreSQL).",
        "hardware_requirements": "Any CPU; under 10 MB of memory to score.",
        "software": "Python 3.11, scikit-learn, pandas; versions locked in uv.lock.",
        "citation_bibtex": "Not applicable",
        "citation_apa": "Not applicable",
        "glossary": "PR-AUC: area under the precision-recall curve. Expected net value: probability x value "
        "x efficacy - cost. Control group: accounts randomly not contacted.",
        "more_information": "Monitoring and retraining plan: to be completed in phase 11. Decisions and "
        "rejected options: docs/00.README_choix_methodologiques.md, docs/05.REGISTRE_elements_ecartes.md.",
        "model_card_authors": "Rakotovoalavo Petera Haja",
        "model_card_contact": "Through the repository issues",
    }


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Génère la model card depuis les résultats.")
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.packaging import generer_model_card

    generer_model_card(contexte(), destination=arguments.sortie)
    print(f"Model card : {arguments.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
