"""Monthly monitoring: a batch against the reference profile, rule by rule (phase 11, A2-A4).

    M5  combined drift: PSI over the key-variable threshold on one key variable, or over the
        moderate threshold on three model variables, or on the score;
    M8  missing values: a variable's share above twice its training share, as received;
    M9  flagged accounts: a gap over 30 % against the previous month.

Each function returns the evidence (a table or a dict) and the verdict; `mesures_du_mois`
turns the verdicts into the {indicator: triggered} mapping `evaluer_alertes` reads. A
verdict warns, it never blocks the scoring (M6).
"""

from __future__ import annotations

import pandas as pd

from .alertes import (
    ECART_VOLUME_SIGNALES,
    FACTEUR_MANQUANTS,
    NB_VARIABLES_PSI_MODERE,
    SEUIL_PSI_MODERE,
    SEUIL_PSI_SCORE,
    SEUIL_PSI_VARIABLE_CLE,
)
from .derive import psi_contre_profil

INDICATEUR_DERIVE = "Dérive des entrées et du score (PSI)"
INDICATEUR_MANQUANTS = "Taux de manquants à l'entrée"
INDICATEUR_VOLUME = "Volume de comptes signalés"


def derive_combinee(profil: dict, lot: pd.DataFrame, score: pd.Series) -> tuple[pd.DataFrame, dict]:
    """M5: per-variable PSI against the profile, the score's PSI, and the combined verdict."""
    cles = set(profil["variables_cles"])
    lignes = [
        {
            "variable": colonne,
            "variable clé": colonne in cles,
            "psi": round(psi_contre_profil(reference, lot[colonne]), 4),
        }
        for colonne, reference in profil["variables"].items()
        if colonne in lot.columns
    ]
    table = pd.DataFrame(lignes).sort_values("psi", ascending=False).reset_index(drop=True)
    psi_score = round(psi_contre_profil(profil["score"], score), 4)
    cles_hautes = table.loc[table["variable clé"] & (table["psi"] > SEUIL_PSI_VARIABLE_CLE)]
    moderees = table.loc[table["psi"] > SEUIL_PSI_MODERE]
    verdict = {
        "variables clés au-dessus de 0,25": cles_hautes["variable"].tolist(),
        "variables au-dessus de 0,10": moderees["variable"].tolist(),
        "psi du score": psi_score,
        "déclenchée": bool(
            len(cles_hautes)
            or len(moderees) >= NB_VARIABLES_PSI_MODERE
            or psi_score > SEUIL_PSI_SCORE
        ),
    }
    return table, verdict


def manquants_relatifs(profil: dict, lot_recu: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """M8: missing share of each variable as received, against twice its training share.

    A variable never missing in training alerts on its first missing value: twice zero is
    zero, and a value that used to arrive and no longer does is a collection change.
    """
    lignes = []
    for colonne, part_reference in profil["manquants_a_l_entree"].items():
        if colonne not in lot_recu.columns:
            continue
        part = float(lot_recu[colonne].isna().mean())
        seuil = FACTEUR_MANQUANTS * part_reference
        lignes.append(
            {
                "variable": colonne,
                "part à l'entraînement": round(part_reference, 4),
                "part du lot": round(part, 4),
                "seuil": round(seuil, 4),
                "alerte": part > seuil,
            }
        )
    table = pd.DataFrame(lignes).sort_values("part du lot", ascending=False).reset_index(drop=True)
    verdict = {
        "variables en alerte": table.loc[table["alerte"], "variable"].tolist(),
        "déclenchée": bool(table["alerte"].any()),
    }
    return table, verdict


def ecart_volume(signales: int, signales_precedent: int | None) -> dict:
    """M9: gap in flagged accounts against the previous month; none without a previous one."""
    if not signales_precedent:
        return {
            "comptes signalés": signales,
            "mois précédent": None,
            "écart": None,
            "déclenchée": False,
        }
    ecart = abs(signales - signales_precedent) / signales_precedent
    return {
        "comptes signalés": int(signales),
        "mois précédent": int(signales_precedent),
        "écart": round(ecart, 4),
        "déclenchée": ecart > ECART_VOLUME_SIGNALES,
    }


def mesures_du_mois(derive: dict, manquants: dict, volume: dict) -> dict[str, bool]:
    """The verdicts as `evaluer_alertes` reads them: indicator -> triggered."""
    return {
        INDICATEUR_DERIVE: derive["déclenchée"],
        INDICATEUR_MANQUANTS: manquants["déclenchée"],
        INDICATEUR_VOLUME: volume["déclenchée"],
    }
