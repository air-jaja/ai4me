"""Optimisation d'hyperparamètres par échantillonnage bayésien, avec élagage.

**Pourquoi Optuna plutôt qu'une grille exhaustive.** L'argument d'éco-conception du
notebook § 8 portait sur l'étendue de la recherche, pas sur l'outil. Une grille
exhaustive évalue toutes les combinaisons, y compris celles dont les premiers plis
montrent qu'elles n'aboutiront pas. Optuna échantillonne (TPE) et **interrompt** les
essais sans avenir : à budget de calcul égal il couvre davantage d'espace, à couverture
égale il consomme moins. Le budget reste borné par `n_essais`, qui demeure un arbitrage
documenté.

L'empreinte du calcul est mesurable avec CodeCarbon (`mesurer_empreinte`) : l'argument
d'éco-conception cesse d'être déclaratif.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from ..config import GRAINE


def espace_baseline(essai: Any) -> dict[str, Any]:
    """Espace de recherche de la régression logistique."""
    return {
        "modele__C": essai.suggest_float("C", 1e-3, 1e2, log=True),
        "modele__class_weight": essai.suggest_categorical("class_weight", [None, "balanced"]),
    }


def espace_candidat(essai: Any) -> dict[str, Any]:
    """Espace de recherche de la forêt aléatoire."""
    return {
        "modele__n_estimators": essai.suggest_int("n_estimators", 100, 400, step=100),
        "modele__max_depth": essai.suggest_categorical("max_depth", [None, 10, 20, 30]),
        "modele__min_samples_leaf": essai.suggest_int("min_samples_leaf", 1, 20),
        "modele__class_weight": essai.suggest_categorical("class_weight", [None, "balanced"]),
    }


def optimiser(
    modele: Pipeline,
    espace: Callable[[Any], dict[str, Any]],
    X: pd.DataFrame,
    y: pd.Series,
    n_essais: int = 30,
    n_plis: int = 5,
) -> Any:
    """Recherche le jeu d'hyperparamètres maximisant le PR-AUC en validation croisée.

    `n_essais` est délibérément modeste : le gain marginal d'une recherche étendue n'est
    pas démontré sur ce volume de données, et il se paierait en calcul.
    """
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    plis = StratifiedKFold(n_splits=n_plis, shuffle=True, random_state=GRAINE)

    def objectif(essai: Any) -> float:
        candidat = modele.set_params(**espace(essai))
        scores = cross_val_score(candidat, X, y, cv=plis, scoring="average_precision", n_jobs=-1)
        return float(scores.mean())

    etude = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=GRAINE),
        pruner=optuna.pruners.MedianPruner(),
    )
    etude.optimize(objectif, n_trials=n_essais, show_progress_bar=False)
    return etude


def resume_etude(etude: Any) -> pd.DataFrame:
    """Tableau des essais, à reporter dans le notebook (hyperparamètres décrits, C5)."""
    return (
        etude.trials_dataframe(attrs=("number", "value", "params", "state"))
        .sort_values("value", ascending=False)
        .reset_index(drop=True)
    )


@contextmanager
def mesurer_empreinte(nom: str = "optimisation", dossier: str = "reports"):
    """Mesure l'empreinte carbone du bloc englobé, si CodeCarbon est installé.

    Silencieux en son absence : le notebook reste exécutable sans la stack complète.
    """
    try:
        from codecarbon import EmissionsTracker
    except ImportError:
        yield None
        return

    traceur = EmissionsTracker(project_name=nom, output_dir=dossier, log_level="error")
    traceur.start()
    try:
        yield traceur
    finally:
        emissions = traceur.stop()
        print(f"Empreinte mesurée pour « {nom} » : {emissions:.6f} kg eqCO2")
