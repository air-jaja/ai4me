"""Demonstration batches for the phase 11 monitoring - simulated, and labelled as such.

No production batch exists yet, and the test part may not be read again. The monthly
monitoring is therefore shown on batches built from the training part only (decision S1
to S7, 04/10/2026, docs/00.README_choix_methodologiques.md): the sample's training
accounts, completed by resampling, with a documented drift injected in the second month.
They prove the mechanics - computations, alerts, actions - never the model's performance.
"""

from __future__ import annotations

from ..config import GRAINE, RACINE

# Decision S1 to S7, validated by the project owner on 04/10/2026 before any implementation.
TAILLE_LOT_SIMULE = 5_000  # S2: portfolio size
GRAINE_SIMULATION = GRAINE  # S2: recorded seed
MOIS_SIMULES = ("mois_1_sans_derive", "mois_2_avec_derive")  # S3
# S4: one scenario per rule. M5: disengagement; M8: collection incident; M9: nothing injected.
DERIVE_CONNEXION = {"variable": "derniere_connexion_jours", "part": 0.30, "facteur": 2.0}
DERIVE_MANQUANTS = {"variable": "delai_reponse_support_h", "part": 0.25}
# S8: a third month with a strong disengagement - month 2's drift left M5 silent (PSI 0.043).
MOIS_DERIVE_FORTE = "mois_3_derive_forte"
DERIVE_CONNEXION_FORTE = {"variable": "derniere_connexion_jours", "part": 0.30, "ajout_jours": 30}
# S5: simulated outcomes three months later.
REDUCTION_RISQUE_CONTACT = 0.25  # the retention efficacy hypothesis (R1)
PART_TEMOIN_SIMULE = 0.10  # the control group share of the list (phase 10)
DOSSIER_SIMULATION = RACINE / "data" / "simulation"  # S7: versioned, never data/raw
MENTION = "SIMULÉ — démonstration"  # S7: on every simulated file and report

# Columns a monthly batch cannot carry: the outcome is not known when it is scored.
COLONNES_POSTERIEURES = ("churn", "sante_compte_fin_periode")
PREFIXE_SIMULE = "SIM-"


def comptes_reels(echantillon, ids_entrainement: set, ids_test: set):
    """S1: the sample's accounts that belong to the training part - never one of the test.

    The check refuses rather than filters silently: a test account reaching a simulated
    batch would be a third reading of the test part.
    """
    reels = echantillon[echantillon["client_id"].isin(ids_entrainement)]
    if reels["client_id"].isin(ids_test).any():
        raise ValueError("Compte du jeu de test dans un lot simulé : refusé (S1).")
    return reels.reset_index(drop=True)


def completer_lot(reels, reservoir, taille: int, generateur):
    """S2: real accounts, then rows drawn with replacement from the training part's raw rows.

    Drawn rows get a new identifier (SIM-00001...): a drawn account is not the real one,
    and two draws of the same row must not collapse as duplicates.
    """
    import pandas as pd

    tires = reservoir.iloc[generateur.integers(0, len(reservoir), taille - len(reels))].copy()
    tires["client_id"] = [f"{PREFIXE_SIMULE}{i:05d}" for i in range(1, len(tires) + 1)]
    lot = pd.concat([reels, tires], ignore_index=True)
    return lot.drop(columns=[c for c in COLONNES_POSTERIEURES if c in lot.columns])


def injecter_derive(lot, generateur):
    """S4, on the raw batch as the CRM would send it: disengagement (M5), lost field (M8)."""
    import pandas as pd

    lot = lot.copy()
    variable, part, facteur = (DERIVE_CONNEXION[k] for k in ("variable", "part", "facteur"))
    lignes = generateur.choice(len(lot), size=round(part * len(lot)), replace=False)
    valeurs = pd.to_numeric(lot[variable].iloc[lignes], errors="coerce") * facteur
    lot.loc[lot.index[lignes], variable] = [
        lot[variable].iloc[i] if pd.isna(v) else str(int(v))
        for i, v in zip(lignes, valeurs, strict=True)
    ]
    variable, part = DERIVE_MANQUANTS["variable"], DERIVE_MANQUANTS["part"]
    lignes = generateur.choice(len(lot), size=round(part * len(lot)), replace=False)
    lot.loc[lot.index[lignes], variable] = pd.NA
    return lot
