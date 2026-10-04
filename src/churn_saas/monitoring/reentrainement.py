"""Retraining: which data, and when (phase 11, part C; decisions M2, M3, M4).

    M2  contacted accounts are left out of the retraining data - the contact changed their
        outcome, the model would learn the action's effect instead of the risk; the control
        group and the accounts not contacted are kept;
    M4  a sliding window of twelve months;
    M3  every quarter, and earlier on an alert QUALIFIED as a real drift. An alert qualified
        as a collection incident sends back to the data, not to retraining (section 13).

The qualification is a person's decision: this module applies it, it never makes it.
"""

from __future__ import annotations

import pandas as pd

from .alertes import FENETRE_REENTRAINEMENT_MOIS, FREQUENCE_REENTRAINEMENT_MOIS

DERIVE_REELLE = "dérive réelle"
INCIDENT_DE_COLLECTE = "incident de collecte"


def selectionner_donnees_reentrainement(
    issues: pd.DataFrame, date_reference: str
) -> tuple[pd.DataFrame, dict]:
    """M2, M4: the accounts a retraining may learn from, and the count of each exclusion.

    `issues` carries one row per account and list: `mois_liste`, `groupe` (contact, temoin,
    non_retenu) and `resultat_3_mois` (reste, parti, inconnu).
    """
    reference = pd.Timestamp(date_reference)
    debut = reference - pd.DateOffset(months=FENETRE_REENTRAINEMENT_MOIS)
    dates = pd.to_datetime(issues["mois_liste"])
    dans_fenetre = (dates >= debut) & (dates < reference)
    contactes = issues["groupe"] == "contact"
    connus = issues["resultat_3_mois"].isin(("reste", "parti"))
    retenus = dans_fenetre & ~contactes & connus
    selection = issues[retenus]
    bilan = {
        "fenêtre": [debut.date().isoformat(), reference.date().isoformat()],
        "lignes reçues": int(len(issues)),
        "hors fenêtre": int((~dans_fenetre).sum()),
        "contactés, exclus (M2)": int((dans_fenetre & contactes).sum()),
        "issue inconnue, écartés": int((dans_fenetre & ~contactes & ~connus).sum()),
        "retenus": int(len(selection)),
        "dont témoins": int((selection["groupe"] == "temoin").sum()),
        "taux de départ des retenus": round(
            float((selection["resultat_3_mois"] == "parti").mean()), 4
        )
        if len(selection)
        else None,
    }
    return selection, bilan


def decider_reentrainement(
    date_dernier_entrainement: str, date_courante: str, alertes_qualifiees: list[dict]
) -> dict:
    """M3: retrain when the quarter is due, or earlier on an alert qualified as real drift.

    `alertes_qualifiees` lists {"indicateur", "qualification"} - the qualification written
    by the person who examined the alert.
    """
    ecart = pd.Timestamp(date_courante).to_period("M") - pd.Timestamp(
        date_dernier_entrainement
    ).to_period("M")
    mois_ecoules = int(ecart.n)
    reelles = [a["indicateur"] for a in alertes_qualifiees if a["qualification"] == DERIVE_REELLE]
    incidents = [
        a["indicateur"] for a in alertes_qualifiees if a["qualification"] == INCIDENT_DE_COLLECTE
    ]
    echeance = mois_ecoules >= FREQUENCE_REENTRAINEMENT_MOIS
    motifs = []
    if echeance:
        motifs.append(
            f"échéance trimestrielle ({mois_ecoules} mois depuis le dernier entraînement)"
        )
    if reelles:
        motifs.append(f"dérive réelle qualifiée : {', '.join(reelles)}")
    return {
        "mois écoulés": mois_ecoules,
        "réentraîner": bool(echeance or reelles),
        "motifs": motifs,
        "retour aux données (incidents de collecte)": incidents,
    }
