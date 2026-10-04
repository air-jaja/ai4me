"""The operational list handed to the account managers - business labels, plain reasons.

Technical columns are translated once, here (table `LIBELLES`, validated with the project
owner): the list is sorted by priority (net expected gain), carries the recommended action,
a risk band next to the calibrated percentage, and the three main reasons in plain words,
read from the exact linear contributions of the model in service.
"""

from __future__ import annotations

import pandas as pd

from ..config import CAPACITE_MENSUELLE
from ..evaluation import appliquer_regle, contributions_lineaires

# CRM integration defaults, validated by the project owner (03/10/2026). Kept here, not in
# config.py: config.py belongs to every tool's identity, and a serving setting must not
# invalidate the recorded results.
CARENCE_MOIS = 2  # an account contacted less than 2 months ago is not proposed again...
HAUSSE_REINTEGRATION = 0.5  # ...unless its expected gain rose by more than 50 %
PART_GROUPE_TEMOIN = 0.10  # share of selected accounts randomly NOT contacted (control group)

# Technical name -> label shown to the account manager (phase 10, point 3).
LIBELLES = {
    "rang": "Priorité",
    "client_id": "Compte",
    "action": "Action recommandée",
    "tranche_risque": "Risque de départ",
    "proba_pct": "Risque (%)",
    "valeur_keur": "Valeur client estimée (k€)",
    "mrr_eur": "Revenu mensuel (€)",
    "gain_eur": "Gain attendu d'un contact (€)",
    "motif": "Pourquoi ce compte ?",
    "deja_contacte": "Déjà contacté",
    "genere_le": "Généré le",
    "modele": "Modèle",
}

TRANCHES = ((0.60, "Très élevé"), (0.40, "Élevé"), (0.20, "Modéré"), (0.0, "Faible"))

# Variable -> sentence, from the account's own value.
FORMULATIONS = {
    "derniere_connexion_jours": lambda v: f"dernière connexion il y a {int(float(v))} jours",
    "nb_integrations": lambda v: (
        "aucune intégration active"
        if float(v) == 0
        else f"{int(float(v))} intégration(s) active(s)"
    ),
    "tickets_support_90j": lambda v: f"{int(float(v))} ticket(s) de support en 3 mois",
    "anciennete_mois": lambda v: f"client depuis {int(float(v))} mois",
    "taux_adoption_pct": lambda v: f"{float(v):.0f} % des licences utilisées",
    "csat": lambda v: f"satisfaction {int(float(v))} sur 5",
    "retards_paiement_12m": lambda v: f"{int(float(v))} retard(s) de paiement en 12 mois",
    "delai_reponse_support_h": lambda v: f"délai de réponse du support : {float(v):.0f} h",
    "utilisateurs_actifs": lambda v: f"{int(float(v))} utilisateurs actifs",
    "sieges_souscrits": lambda v: f"{int(float(v))} sièges souscrits",
    "revenu_mensuel_recurrent_eur": lambda v: f"revenu mensuel de {float(v):,.0f} €".replace(
        ",", " "
    ),
    "connexions_30j": lambda v: f"{int(float(v))} connexions en 30 jours",
    "heures_usage_30j": lambda v: f"{float(v):.0f} h d'usage en 30 jours",
    "fonctionnalites_utilisees": lambda v: f"{int(float(v))} fonctionnalités utilisées",
    "jour_souscription": lambda v: f"souscrit un {v}",
    "plan": lambda v: f"formule {v}",
    "secteur": lambda v: f"secteur {v}",
    "taille_entreprise": lambda v: f"entreprise {v}",
}


def tranche(probabilite: float) -> str:
    return next(nom for seuil, nom in TRANCHES if probabilite >= seuil)


def motif(contributions: pd.Series, valeurs: pd.Series, n: int = 3) -> str:
    """The n strongest reasons, in plain words, with their direction."""
    phrases = []
    for variable in contributions.abs().sort_values(ascending=False).index[:n]:
        valeur = valeurs[variable]
        if pd.isna(valeur):
            texte = f"{variable.replace('_', ' ')} non renseigné"
        else:
            formuler = FORMULATIONS.get(
                variable, lambda v, nom=variable: f"{nom.replace('_', ' ')} : {v}"
            )
            texte = formuler(valeur)
        sens = "augmente le risque" if contributions[variable] > 0 else "réduit le risque"
        phrases.append(f"{texte} ({sens})")
    return " ; ".join(phrases).capitalize()


def selectionner(
    regle: pd.DataFrame,
    identifiants: pd.Series,
    capacite: int,
    historique: pd.DataFrame | None,
    date_liste: pd.Timestamp,
    part_temoin: float,
    graine: int,
) -> tuple[pd.Series, pd.Series]:
    """Action per account, and when it was last contacted (point 5 defaults).

    1. Cool-down: an account contacted less than CARENCE_MOIS months ago is set aside,
       unless its expected gain rose by more than HAUSSE_REINTEGRATION since that contact
       or the CRM flags a critical event.
    2. Selection: the most valuable eligible profitable accounts, enough to fill the
       capacity once the control group is drawn.
    3. Control group: PART_GROUPE_TEMOIN of the selected accounts, drawn at random with a
       recorded seed, are NOT contacted - the only way to measure what contacting changes.
    """
    import numpy as np

    action = pd.Series("Pas d'action", index=regle.index)
    action[regle["rentable"]] = "En réserve (rentable, hors capacité)"
    deja = pd.Series("Nouveau", index=regle.index)
    eligibles = regle["rentable"].copy()
    if historique is not None and len(historique):
        dernier = (
            historique.sort_values("date_contact")
            .groupby("client_id")
            .tail(1)
            .set_index("client_id")
        )
        for indice, compte in identifiants.items():
            if compte not in dernier.index:
                continue
            contact = dernier.loc[compte]
            date_contact = pd.Timestamp(contact["date_contact"])
            deja[indice] = f"Contacté le {date_contact.date().isoformat()}"
            recent = date_contact > date_liste - pd.DateOffset(months=CARENCE_MOIS)
            hausse = regle.loc[indice, "valeur_nette_eur"] > (1 + HAUSSE_REINTEGRATION) * float(
                contact.get("gain_au_contact_eur", float("inf"))
            )
            evenement = bool(contact.get("evenement_critique", False))
            if recent and not (hausse or evenement) and eligibles[indice]:
                eligibles[indice] = False
                action[indice] = "En carence (contacté récemment)"
    candidats = regle.index[eligibles].tolist()  # regle is sorted by expected value
    retenus = candidats[: round(capacite / (1 - part_temoin))]
    generateur = np.random.default_rng(graine)
    temoins = (
        set(generateur.choice(retenus, size=round(part_temoin * len(retenus)), replace=False))
        if retenus
        else set()
    )
    for indice in retenus:
        action[indice] = (
            "Groupe témoin (pas de contact)" if indice in temoins else "À contacter ce mois"
        )
    return action, deja


def construire_liste(
    modele,
    X: pd.DataFrame,
    identifiants: pd.Series,
    valeur: pd.Series,
    mrr: pd.Series,
    fond: pd.DataFrame,
    version_modele: str,
    capacite: int = CAPACITE_MENSUELLE,
    genere_le: str | None = None,
    historique: pd.DataFrame | None = None,
    part_temoin: float = PART_GROUPE_TEMOIN,
    graine: int = 0,
) -> pd.DataFrame:
    """One row per account, business labels, sorted by priority."""
    proba = pd.Series(modele.predict_proba(X)[:, 1], index=X.index)
    regle = appliquer_regle(proba, valeur, capacite)
    contributions, _ = contributions_lineaires(modele, X, fond)
    date_liste = pd.Timestamp(genere_le or pd.Timestamp.today().date())
    action, deja = selectionner(
        regle, identifiants, capacite, historique, date_liste, part_temoin, graine
    )
    table = pd.DataFrame(
        {
            "rang": regle["rang"],
            "client_id": identifiants,
            "action": action,
            "tranche_risque": proba.map(tranche),
            "proba_pct": (100 * proba).round(0).astype(int),
            "valeur_keur": (valeur / 1000).round(1),
            "mrr_eur": mrr.round(0),
            "gain_eur": regle["valeur_nette_eur"].round(0),
            "motif": [motif(contributions.loc[i], X.loc[i]) for i in X.index],
            "deja_contacte": deja,
            "genere_le": date_liste.date().isoformat(),
            "modele": version_modele,
        }
    ).sort_values("rang")
    return table.rename(columns=LIBELLES).reset_index(drop=True)
