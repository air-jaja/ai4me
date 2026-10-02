"""Compute footprint, measured on the machine that runs the project and converted openly.

Arbitrage of 01/10/2026: CodeCarbon is not used. Without access to the processor's energy
counters - the usual case on a Windows laptop - it falls back to a constant-power estimate,
that is to the very computation below, shown with more decimals. This module does that
computation in the open instead:

    energy (Wh)   = duration (h) x power (W)
    emissions (g) = energy (kWh) x carbon intensity of electricity (g CO2e / kWh)

The durations are **measured** on the machine (`mesurer_temps`), with the project's own
model configuration. The workload is **declared** as data (`CHARGE_PHASE5`), so the jury can
read how many trainings each step costs. The power and intensity are **hypotheses**, kept as
project inputs in `config/ressources_poste.toml`, never buried in code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from ..config import GRAINE
from .baseline import construire_baseline
from .selection import construire_candidat


@dataclass(frozen=True)
class EtapeDeCalcul:
    """One step of the planned workload: how many of each elementary operation it runs."""

    etape: str
    entrainements_lr: int = 0
    entrainements_foret: int = 0
    importances_lr: int = 0
    importances_foret: int = 0
    scorings: int = 0


# Phase 5 workload, as planned in 00.README_choix_methodologiques § 7 bis. Forest trainings
# are counted at 300 trees, the project's setting: an upper bound for the grid, whose half
# uses 100 trees.
CHARGE_PHASE5: tuple[EtapeDeCalcul, ...] = (
    EtapeDeCalcul("Grille, régression logistique (8 × 5 plis)", entrainements_lr=40),
    EtapeDeCalcul("Grille, forêt aléatoire (36 × 5 plis)", entrainements_foret=180),
    EtapeDeCalcul("Courbes de validation", entrainements_lr=30, entrainements_foret=50),
    EtapeDeCalcul(
        "Apport des variables construites (2 jeux × 2 modèles × 25)",
        entrainements_lr=50,
        entrainements_foret=50,
    ),
    EtapeDeCalcul(
        "Ablation par groupe (7 groupes × 2 modèles × 25)",
        entrainements_lr=175,
        entrainements_foret=175,
    ),
    EtapeDeCalcul("Test de permutation des étiquettes (100 × 5 plis)", entrainements_lr=500),
    EtapeDeCalcul(
        "Courbes d'apprentissage (5 tailles × 5 plis × 2 modèles)",
        entrainements_lr=25,
        entrainements_foret=25,
    ),
    EtapeDeCalcul(
        "Importance par permutation (5 plis × 2 modèles)", importances_lr=5, importances_foret=5
    ),
    EtapeDeCalcul("Validation adverse (5 plis)", entrainements_foret=5),
)

# Yearly production workload, as framed in section 11: quarterly retraining of the final
# model, monthly scoring of the portfolio.
CHARGE_PRODUCTION_ANNUELLE: tuple[EtapeDeCalcul, ...] = (
    EtapeDeCalcul("Réentraînement trimestriel du modèle final (4 / an)", entrainements_foret=4),
    EtapeDeCalcul("Scoring mensuel du portefeuille (12 / an)", scorings=12),
)


def mesurer_temps(X: pd.DataFrame, y: pd.Series, repetitions: int = 3) -> dict[str, float]:
    """Median wall-clock time of each elementary operation, on this machine.

    One fold-sized training set (64 % of the data, as in a 5-fold CV inside an 80 % train)
    and its validation fold. The project's own pipelines are timed, preprocessing included,
    with their own parallelism settings: the forest uses every core, as it will in practice.
    Memory is measured by the caller, on the whole process (`tools/ressources_calcul.py`).
    """
    entrainement, _, y_entrainement, _ = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=GRAINE
    )
    X_a, X_v, y_a, y_v = train_test_split(
        entrainement, y_entrainement, test_size=0.2, stratify=y_entrainement, random_state=GRAINE
    )

    def chronometrer(action) -> float:
        durees = []
        for _ in range(repetitions):
            debut = time.perf_counter()
            action()
            durees.append(time.perf_counter() - debut)
        return float(np.median(durees))

    lr, foret = construire_baseline(X), construire_candidat(X)
    temps = {
        "entrainement_lr_s": chronometrer(lambda: lr.fit(X_a, y_a)),
        "entrainement_foret_s": chronometrer(lambda: foret.fit(X_a, y_a)),
    }
    temps["scoring_portefeuille_s"] = chronometrer(lambda: foret.predict_proba(X))
    for nom, modele in (("lr", lr), ("foret", foret)):
        temps[f"importance_{nom}_s"] = chronometrer(
            lambda modele=modele: permutation_importance(
                modele,
                X_v,
                y_v,
                n_repeats=10,
                random_state=GRAINE,
                scoring="average_precision",
            )
        )
    temps["lignes_entrainement"] = float(len(X_a))
    return temps


def estimer_charge(
    temps: dict[str, float], charge: tuple[EtapeDeCalcul, ...] = CHARGE_PHASE5
) -> pd.DataFrame:
    """Duration of each planned step, from the measured elementary times."""
    lignes = []
    for e in charge:
        secondes = (
            e.entrainements_lr * temps["entrainement_lr_s"]
            + e.entrainements_foret * temps["entrainement_foret_s"]
            + e.importances_lr * temps["importance_lr_s"]
            + e.importances_foret * temps["importance_foret_s"]
            + e.scorings * temps["scoring_portefeuille_s"]
        )
        lignes.append(
            {
                "étape": e.etape,
                "entraînements": e.entrainements_lr + e.entrainements_foret,
                "secondes": round(secondes, 1),
            }
        )
    return pd.DataFrame(lignes)


def convertir_empreinte(
    secondes: float, puissance_w: float, intensite_g_kwh: float, executions: int = 1
) -> dict[str, float]:
    """Energy and emissions of `executions` runs lasting `secondes` at `puissance_w`."""
    energie_wh = secondes / 3600 * puissance_w * executions
    return {
        "énergie (Wh)": energie_wh,
        "émissions (g CO₂e)": energie_wh / 1000 * intensite_g_kwh,
    }


def table_empreinte(
    secondes: float,
    puissances_w: dict[str, float],
    intensite_g_kwh: float,
    executions: int,
) -> pd.DataFrame:
    """One row per power hypothesis: energy and emissions, once and for `executions` runs."""
    lignes = []
    for libelle, puissance in puissances_w.items():
        une = convertir_empreinte(secondes, puissance, intensite_g_kwh)
        toutes = convertir_empreinte(secondes, puissance, intensite_g_kwh, executions)
        lignes.append(
            {
                "hypothèse": libelle,
                "puissance (W)": puissance,
                "énergie par exécution (Wh)": round(une["énergie (Wh)"], 2),
                f"énergie, {executions} exécutions (Wh)": round(toutes["énergie (Wh)"], 1),
                f"CO₂e, {executions} exécutions (g)": round(toutes["émissions (g CO₂e)"], 2),
            }
        )
    return pd.DataFrame(lignes)
