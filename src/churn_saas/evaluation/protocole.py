"""Evaluation protocol, fixed on 02/10/2026 before any baseline was run (phase 6).

What is measured, on which folds, and what counts as success are declared here as data,
once, for every model the project will compare. A protocol written after the results
adjusts to them (rule 8).

- Folds: the 25 shared folds of phase 5 (5 stratified folds x 5 repetitions, seed 42),
  inside the training part only. The test part stays sealed until the single final
  evaluation.
- Metrics, each with a role (`METRIQUES`): PR-AUC decides; ROC-AUC is required by the
  brief; recall and precision in the top 10 % read the ranking as a CSM uses it; Brier
  score and calibration error check that probabilities can be multiplied by a value.

The models are passed as factories (`construire_modele(X) -> estimator`): activity 4 may
not import activity 3 (rule 6).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from ..config import (
    GRAINE,
    PART_HAUT_CLASSEMENT,
    PLIS_VALIDATION,
    REPETITIONS_VALIDATION,
    SEUIL_ERREUR_CALIBRATION,
)


@dataclass(frozen=True)
class Metrique:
    """One metric of the protocol and why it is there."""

    nom: str
    role: str
    motif: str


METRIQUES: tuple[Metrique, ...] = (
    Metrique(
        "PR-AUC", "critère principal", "insensible au confort des 72 % de clients qui restent"
    ),
    Metrique(
        "ROC-AUC", "secondaire, exigé par l'énoncé", "capacité générale à ordonner les comptes"
    ),
    Metrique(
        "rappel haut",
        "lecture métier",
        f"part des départs trouvés dans les {PART_HAUT_CLASSEMENT:.0%} de comptes les plus risqués",
    ),
    Metrique(
        "précision haut",
        "lecture métier",
        f"part de vrais départs parmi ces {PART_HAUT_CLASSEMENT:.0%} de comptes",
    ),
    Metrique("Brier", "calibration", "écart quadratique entre probabilité annoncée et issue"),
    Metrique(
        "erreur de calibration",
        "calibration",
        f"écart moyen par tranche de probabilité ; au-delà de {SEUIL_ERREUR_CALIBRATION}, "
        "la phase 7 calibre le modèle retenu",
    ),
)

ConstructeurModele = Callable[[pd.DataFrame], object]


def plis_du_protocole() -> RepeatedStratifiedKFold:
    """The 25 shared folds - identical to those of the phase 5 selection."""
    return RepeatedStratifiedKFold(
        n_splits=PLIS_VALIDATION, n_repeats=REPETITIONS_VALIDATION, random_state=GRAINE
    )


def rappel_precision_haut(
    y: pd.Series, score: np.ndarray, part: float = PART_HAUT_CLASSEMENT
) -> tuple[float, float]:
    """Recall and precision among the `part` of accounts ranked riskiest."""
    y = np.asarray(y).astype(int)
    k = max(1, int(np.ceil(part * len(y))))
    haut = np.argsort(-np.asarray(score), kind="mergesort")[:k]
    trouves = y[haut].sum()
    return float(trouves / max(y.sum(), 1)), float(trouves / k)


def erreur_calibration(y: pd.Series, proba: np.ndarray, tranches: int = 10) -> float:
    """Expected calibration error: weighted gap between mean probability and observed rate,
    over equal-width probability buckets."""
    y, proba = np.asarray(y).astype(float), np.asarray(proba).astype(float)
    bornes = np.linspace(0, 1, tranches + 1)
    indices = np.clip(np.digitize(proba, bornes[1:-1]), 0, tranches - 1)
    erreur = 0.0
    for t in range(tranches):
        dans = indices == t
        if dans.any():
            erreur += dans.mean() * abs(y[dans].mean() - proba[dans].mean())
    return float(erreur)


def mesurer(y: pd.Series, score: np.ndarray, probabiliste: bool = True) -> dict[str, float]:
    """Every metric of the protocol on one set of predictions.

    A ranking rule is not a probability: its Brier score and calibration error mean
    nothing and are reported as missing rather than as numbers.
    """
    rappel, precision = rappel_precision_haut(y, score)
    return {
        "PR-AUC": float(average_precision_score(y, score)),
        "ROC-AUC": float(roc_auc_score(y, score)),
        "rappel haut": rappel,
        "précision haut": precision,
        "Brier": float(brier_score_loss(y, score)) if probabiliste else float("nan"),
        "erreur de calibration": erreur_calibration(y, score) if probabiliste else float("nan"),
    }


@dataclass
class ResultatProtocole:
    """Per-fold metrics, and the out-of-fold predictions of the first repetition."""

    par_pli: pd.DataFrame
    hors_pli: pd.Series


def evaluer_selon_protocole(
    construire_modele: ConstructeurModele,
    X: pd.DataFrame,
    y: pd.Series,
    probabiliste: bool = True,
) -> ResultatProtocole:
    """Train and score the model on each of the 25 folds; keep one full out-of-fold pass.

    The first repetition covers every training account exactly once: its predictions draw
    the PR, ROC and calibration curves. The 25 folds give the means and their spread.
    """
    y = pd.Series(y).astype(int)
    lignes, hors_pli = [], pd.Series(np.nan, index=X.index)
    for numero, (entrainement, validation) in enumerate(plis_du_protocole().split(X, y)):
        modele = clone(construire_modele(X)).fit(X.iloc[entrainement], y.iloc[entrainement])
        score = modele.predict_proba(X.iloc[validation])[:, 1]
        lignes.append({"pli": numero, **mesurer(y.iloc[validation], score, probabiliste)})
        if numero < PLIS_VALIDATION:
            hors_pli.iloc[validation] = score
    return ResultatProtocole(pd.DataFrame(lignes).set_index("pli"), hors_pli)


def resumer(resultats: dict[str, ResultatProtocole]) -> pd.DataFrame:
    """Mean and standard deviation of each metric, one row per model."""
    lignes = {}
    for nom, resultat in resultats.items():
        moyennes = resultat.par_pli.mean()
        ecarts = resultat.par_pli.std()
        lignes[nom] = {
            m: (f"{moyennes[m]:.3f} ± {ecarts[m]:.3f}" if pd.notna(moyennes[m]) else "—")
            for m in resultat.par_pli.columns
        }
    return pd.DataFrame(lignes).T
