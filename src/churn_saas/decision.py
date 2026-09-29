"""Règle de décision métier : priorisation par valeur espérée.

Fondement (notebook § 9) : pour un compte de probabilité p, agir est rationnel dès que
    p > C_FP / (C_FP + C_FN),  soit  p* = 1 / (1 + r)  avec  r = C_FN / C_FP.

Comme C_FN est proportionnel à la valeur du compte, le seuil optimal varie d'un facteur
130 entre déciles extrêmes. Un seuil global unique est donc économiquement incohérent :
les comptes sont classés par valeur espérée et coupés à la capacité de traitement.
"""

from __future__ import annotations

import pandas as pd

from .config import CAPACITE_MENSUELLE, COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION


def seuil_par_compte(
    valeur_vie_client: pd.Series,
    efficacite_retention: float = EFFICACITE_RETENTION,
    cout_faux_positif: float = COUT_CONTACT_CSM_EUR,
) -> pd.Series:
    """Seuil de probabilité au-delà duquel agir devient rentable, compte par compte."""
    cout_faux_negatif = valeur_vie_client * efficacite_retention
    return cout_faux_positif / (cout_faux_positif + cout_faux_negatif)


def prioriser(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
) -> pd.DataFrame:
    """Classe les comptes par valeur espérée et marque ceux que l'équipe peut traiter.

    Le classement est insensible à `efficacite_retention` : facteur commun à tous les
    comptes, elle ne modifie pas l'ordre, seulement l'estimation du gain absolu.
    """
    table = pd.DataFrame(
        {
            "proba_churn": probabilites,
            "valeur_vie_client_eur": valeur_vie_client,
        }
    )
    table["valeur_esperee_eur"] = (
        table["proba_churn"] * table["valeur_vie_client_eur"] * efficacite_retention
    )
    table["seuil_compte"] = seuil_par_compte(table["valeur_vie_client_eur"], efficacite_retention)
    table = table.sort_values("valeur_esperee_eur", ascending=False)
    table["rang"] = range(1, len(table) + 1)
    table["a_traiter"] = table["rang"] <= capacite
    return table
