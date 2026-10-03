"""Option C (B6): do the three models rely on the same risk factors? SHAP, once, for analysis.

    uv run python tools/comparaison_explicabilite.py            # writes the results file
    uv run python tools/comparaison_explicabilite.py --forcer   # redo an identical comparison

SHAP does not say which model is best - the protocol did (rule B1). It says what each
model relies on. If the logistic regression, the tuned forest and the tuned XGBoost agree
on the main risk factors, the finding does not depend on the model chosen: a robustness
argument. Each model is explained by SHAP's exact method for its family (linear for the
regression, tree paths for the forest and XGBoost), on 1,000 accounts of the training part;
one-hot columns are summed back into their variable.

The scales differ between families (log-odds for the regression and XGBoost, probability
for the forest): the comparison uses each variable's SHARE of the model's total attribution,
and the agreement of the rankings. Production does not use SHAP: the advisor's explanation
comes from the exact linear contributions (`evaluation.contributions_lineaires`).
Same execution identity as the other tools (A1): an identical comparison is not redone.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "explicabilite_comparee.json"
SELECTION = RACINE / "resultats" / "selection_modele.json"
TAILLE_ECHANTILLON = 1000
TOP = 5


def _reglages(selection: dict, famille: str) -> dict:
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


def calculer() -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    import numpy as np
    import pandas as pd
    import shap
    from scipy.stats import spearmanr

    from churn_saas import config
    from churn_saas.evaluation.explicabilite import _variable_source
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline, construire_candidat, construire_xgboost

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    echantillon = X.sample(min(TAILLE_ECHANTILLON, len(X)), random_state=config.GRAINE)
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    modeles = {
        "régression logistique": construire_baseline(X),
        "forêt aléatoire": construire_candidat(X).set_params(
            **{f"modele__{k}": v for k, v in _reglages(selection, "forêt aléatoire").items()}
        ),
        "xgboost": construire_xgboost(X, **_reglages(selection, "xgboost")),
    }
    parts = {}
    for nom, modele in modeles.items():
        modele.fit(X, y)
        preparation, estimateur = modele.named_steps["preparation"], modele.steps[-1][1]
        categorielles = next((list(c) for n, _, c in preparation.transformers_ if n == "cat"), [])
        noms = preparation.get_feature_names_out()
        Xt = np.asarray(preparation.transform(echantillon), dtype=float)
        if nom == "régression logistique":
            fond = np.asarray(preparation.transform(X), dtype=float)
            valeurs = shap.LinearExplainer(estimateur, fond).shap_values(Xt)
        else:
            valeurs = shap.TreeExplainer(estimateur).shap_values(Xt)
            if isinstance(valeurs, list):
                valeurs = valeurs[1]
            if np.ndim(valeurs) == 3:
                valeurs = valeurs[:, :, 1]
        importance = pd.Series(np.abs(valeurs).mean(axis=0), index=noms)
        importance = importance.groupby([_variable_source(n, categorielles) for n in noms]).sum()
        parts[nom] = (importance / importance.sum()).reindex(X.columns).fillna(0.0)

    table = pd.DataFrame(parts)
    rangs = table.rank(ascending=False)
    accords = []
    noms = list(parts)
    for i, a in enumerate(noms):
        for b in noms[i + 1 :]:
            hauts_a = set(table[a].nlargest(TOP).index)
            hauts_b = set(table[b].nlargest(TOP).index)
            accords.append(
                {
                    "paire": f"{a} / {b}",
                    "corrélation des rangs (Spearman)": round(
                        float(spearmanr(rangs[a], rangs[b]).statistic), 3
                    ),
                    f"variables communes au top {TOP}": len(hauts_a & hauts_b),
                }
            )
    communs = set.intersection(*(set(table[n].nlargest(TOP).index) for n in noms))
    return {
        "comptes_expliques": int(len(echantillon)),
        "parts": {
            nom: {v: round(float(p), 5) for v, p in serie.items()} for nom, serie in parts.items()
        },
        "accords": accords,
        f"top_{TOP}_commun_aux_trois": sorted(communs, key=lambda v: -table.loc[v].mean()),
    }


def executer(forcer: bool = False, sortie: Path = DESTINATION) -> dict:
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    from churn_saas.donnees import charger_manifeste
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution

    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("7", "tools/comparaison_explicabilite.py", manifeste)
    identite = identite_execution(etiquettes, outil="comparaison_explicabilite")
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print(
                "Comparaison des explications déjà enregistrée : rien n'est recalculé.", flush=True
            )
            return existant
    debut = time.perf_counter()
    bilan = {
        "identite_execution": identite,
        **calculer(),
        "duree_s": round(time.perf_counter() - debut, 1),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Facteurs de risque des trois modèles (SHAP).")
    analyseur.add_argument(
        "--forcer", action="store_true", help="refaire une comparaison identique"
    )
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    try:
        import shap  # noqa: F401
    except ImportError:
        print("SHAP absent : installer le groupe explicabilite.")
        return 0
    bilan = executer(arguments.forcer, Path(arguments.sortie))
    print(
        json.dumps(
            {k: bilan[k] for k in ("accords", f"top_{TOP}_commun_aux_trois", "duree_s")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
