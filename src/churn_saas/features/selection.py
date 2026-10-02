"""Which variables earn their place - measured, under rules fixed before the results.

Three tools, one protocol. Every comparison runs on the **same** repeated stratified folds
(5 folds x 5 repetitions, fixed seed): two variable sets are compared fold by fold, so the
difference measured is the variables', not the split's.

- `comparer_jeux` / `resumer_apport`: do the constructed variables add anything? (bloc B)
- `ablation_par_groupe`: what does each family of variables carry? (bloc B)
- `importances_par_permutation` / `table_de_selection`: which variables fall under the
  noise floor set by the two decoys, and can be removed without loss? (bloc C)

The model is passed as a factory, `construire_modele(X) -> estimator`: activity 2 may not
import activity 3 (rule 6), and the factory rebuilds the preprocessing for each variable
subset. Rules applied (choix § 7 bis, fixed on 01/10/2026):

- keep a constructed variable if its gain exceeds one standard deviation between folds;
- remove a variable only if its importance is under the decoys' floor **for both models**
  and removing it costs no more than one standard deviation (precision fixed on 02/10,
  before running the selection);
- the decoys themselves leave the final model once the selection is done.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.inspection import permutation_importance
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, cross_val_score

from ..config import (
    EXCLUES_LEURRES,
    EXCLUES_PAR_SELECTION,
    GRAINE,
    PLIS_VALIDATION,
    REPETITIONS_VALIDATION,
)
from ..donnees import Decoupage, decouper_entrainement_test, separer_cible
from .pipeline import ResultatPipeline, preparer_gold

ConstructeurModele = Callable[[pd.DataFrame], object]

# Families of explanatory variables, as the business reads them. Every gold variable
# belongs to exactly one family (a test checks it).
GROUPES_DE_VARIABLES: dict[str, list[str]] = {
    "usage": [
        "utilisateurs_actifs",
        "sieges_souscrits",
        "taux_adoption_pct",
        "connexions_30j",
        "heures_usage_30j",
        "fonctionnalites_utilisees",
        "nb_integrations",
        "derniere_connexion_jours",
    ],
    "support": ["tickets_support_90j", "delai_reponse_support_h", "csat"],
    "facturation": ["revenu_mensuel_recurrent_eur", "retards_paiement_12m"],
    "contrat": [
        "anciennete_mois",
        "plan",
        "taille_entreprise",
        "secteur",
        "pays",
        "jour_souscription",
    ],
    "construites": [
        "compte_sans_utilisateur_actif",
        "taux_couverture_fonc",
        "usage_par_actif",
        "tickets_par_actif",
    ],
    "leurres": ["couleur_theme_interface", "code_datacenter"],
}
VARIABLES_CONSTRUITES = GROUPES_DE_VARIABLES["construites"]
LEURRES = list(EXCLUES_LEURRES)


def parties_avant_selection(resultat: ResultatPipeline) -> Decoupage:
    """The split, on the candidate set the selection started from (25 variables).

    The final gold no longer holds the variables the selection removed; reproducing the
    selection needs them back. Same accounts in each part as the final split: the split
    depends on the target only, which does not change.
    """
    gold = preparer_gold(resultat.silver, enrichir=False, garder=EXCLUES_PAR_SELECTION).gold
    X, y = separer_cible(gold)
    return decouper_entrainement_test(X, y.astype(int))


def plis_repetes(
    plis: int = PLIS_VALIDATION, repetitions: int = REPETITIONS_VALIDATION
) -> RepeatedStratifiedKFold:
    """The shared folds: the same splits for every variable set compared."""
    return RepeatedStratifiedKFold(n_splits=plis, n_repeats=repetitions, random_state=GRAINE)


def comparer_jeux(
    construire_modele: ConstructeurModele,
    X: pd.DataFrame,
    y: pd.Series,
    jeux: dict[str, list[str]],
    plis: int = 5,
    repetitions: int = 5,
) -> pd.DataFrame:
    """PR-AUC of each variable set on each fold - one column per set, one row per fold."""
    y = pd.Series(y).astype(int)
    validation = plis_repetes(plis, repetitions)
    scores = {
        nom: cross_val_score(
            construire_modele(X[colonnes]),
            X[colonnes],
            y,
            cv=validation,
            scoring="average_precision",
        )
        for nom, colonnes in jeux.items()
    }
    return pd.DataFrame(scores).rename_axis("pli")


def resumer_apport(scores: pd.DataFrame, reference: str, candidat: str) -> dict[str, float]:
    """Paired gain of `candidat` over `reference`, and the verdict of the one-std rule.

    The threshold is the standard deviation of the reference score between folds: a gain
    smaller than the variation due to the split alone cannot be told from it.
    """
    ecarts = scores[candidat] - scores[reference]
    seuil = float(scores[reference].std())
    return {
        "PR-AUC référence": float(scores[reference].mean()),
        "PR-AUC candidat": float(scores[candidat].mean()),
        "gain moyen": float(ecarts.mean()),
        "écart-type entre plis": seuil,
        "plis où le candidat gagne": float((ecarts > 0).mean()),
        "gain significatif": float(ecarts.mean()) > seuil,
    }


def ablation_par_groupe(
    construire_modele: ConstructeurModele,
    X: pd.DataFrame,
    y: pd.Series,
    groupes: dict[str, list[str]] | None = None,
    plis: int = 5,
    repetitions: int = 5,
) -> pd.DataFrame:
    """PR-AUC lost when each family is removed, against the full set, on the same folds."""
    groupes = GROUPES_DE_VARIABLES if groupes is None else groupes
    jeux = {"complet": list(X.columns)}
    for nom, colonnes in groupes.items():
        jeux[f"sans {nom}"] = [c for c in X.columns if c not in colonnes]
    scores = comparer_jeux(construire_modele, X, y, jeux, plis, repetitions)
    seuil = float(scores["complet"].std())
    lignes = []
    for nom in groupes:
        perte = scores["complet"] - scores[f"sans {nom}"]
        lignes.append(
            {
                "groupe": nom,
                "variables": len(groupes[nom]),
                "PR-AUC sans le groupe": round(float(scores[f"sans {nom}"].mean()), 4),
                "perte moyenne": round(float(perte.mean()), 4),
                "écart-type de la perte": round(float(perte.std()), 4),
                "perte significative": float(perte.mean()) > seuil,
            }
        )
    return pd.DataFrame(lignes).sort_values("perte moyenne", ascending=False)


def importances_par_permutation(
    construire_modele: ConstructeurModele,
    X: pd.DataFrame,
    y: pd.Series,
    plis: int = 5,
    repetitions: int = 10,
) -> pd.DataFrame:
    """Permutation importance of each variable on each validation fold (long format).

    Measured on held-out folds only: an importance computed on training rows rewards what
    the model memorised. The loss of PR-AUC when a column is shuffled is its importance.
    """
    y = pd.Series(y).astype(int)
    validation = StratifiedKFold(plis, shuffle=True, random_state=GRAINE)
    lignes = []
    for pli, (entrainement, test) in enumerate(validation.split(X, y)):
        modele = clone(construire_modele(X)).fit(X.iloc[entrainement], y.iloc[entrainement])
        resultat = permutation_importance(
            modele,
            X.iloc[test],
            y.iloc[test],
            n_repeats=repetitions,
            random_state=GRAINE,
            scoring="average_precision",
        )
        for colonne, valeurs in zip(X.columns, resultat.importances, strict=True):
            lignes += [{"pli": pli, "variable": colonne, "importance": v} for v in valeurs]
    return pd.DataFrame(lignes)


def plancher_des_leurres(importances: pd.DataFrame, leurres: list[str] | None = None) -> float:
    """The noise floor: the highest mean importance reached by a decoy."""
    leurres = LEURRES if leurres is None else leurres
    moyennes = importances.groupby("variable")["importance"].mean()
    return float(moyennes.reindex(leurres).max())


def candidates_au_retrait(
    importances_par_modele: dict[str, pd.DataFrame], leurres: list[str] | None = None
) -> pd.DataFrame:
    """Mean importance per variable and model, against each model's decoy floor.

    A variable is a candidate for removal only if it sits under the floor for **every**
    model: a variable useful to one model is kept.
    """
    leurres = LEURRES if leurres is None else leurres
    colonnes = {}
    sous_plancher = None
    for nom, importances in importances_par_modele.items():
        moyennes = importances.groupby("variable")["importance"].mean()
        plancher = plancher_des_leurres(importances, leurres)
        colonnes[f"importance ({nom})"] = moyennes
        colonnes[f"plancher ({nom})"] = pd.Series(plancher, index=moyennes.index)
        dessous = moyennes <= plancher
        sous_plancher = dessous if sous_plancher is None else (sous_plancher & dessous)
    table = pd.DataFrame(colonnes)
    table["sous le plancher pour tous les modèles"] = sous_plancher
    table["leurre"] = table.index.isin(leurres)
    return table.sort_values(table.columns[0], ascending=False)


def confirmer_retraits(
    construire_modele: ConstructeurModele,
    X: pd.DataFrame,
    y: pd.Series,
    candidates: list[str],
    plis: int = 5,
    repetitions: int = 5,
) -> pd.DataFrame:
    """Second proof: what removing each candidate costs, paired on the shared folds."""
    if not candidates:
        return pd.DataFrame(
            columns=["variable", "perte moyenne", "écart-type entre plis", "retrait sans perte"]
        )
    jeux = {"complet": list(X.columns)}
    jeux |= {f"sans {c}": [v for v in X.columns if v != c] for c in candidates}
    scores = comparer_jeux(construire_modele, X, y, jeux, plis, repetitions)
    seuil = float(scores["complet"].std())
    lignes = []
    for c in candidates:
        perte = float((scores["complet"] - scores[f"sans {c}"]).mean())
        lignes.append(
            {
                "variable": c,
                "perte moyenne": round(perte, 4),
                "écart-type entre plis": round(seuil, 4),
                "retrait sans perte": perte <= seuil,
            }
        )
    return pd.DataFrame(lignes)


def facteurs_inflation_variance(X: pd.DataFrame) -> pd.Series:
    """Variance inflation factor of each numeric variable: 1 / (1 - R²) on the others.

    Computed without a new dependency. Above 10, a variable is largely a combination of
    the others: its coefficient in a logistic regression is unstable.
    """
    from sklearn.linear_model import LinearRegression

    numeriques = X.select_dtypes("number").astype(float)
    numeriques = numeriques.fillna(numeriques.median())
    facteurs = {}
    for colonne in numeriques.columns:
        autres = numeriques.drop(columns=colonne)
        r2 = LinearRegression().fit(autres, numeriques[colonne]).score(autres, numeriques[colonne])
        facteurs[colonne] = np.inf if r2 >= 1 else 1 / (1 - r2)
    return pd.Series(facteurs, name="VIF").sort_values(ascending=False)
