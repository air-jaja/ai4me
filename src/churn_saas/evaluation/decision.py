"""Règle de décision métier : priorisation par valeur espérée.

Fondement (notebook § 9) : pour un compte de probabilité p, agir est rationnel dès que

    p > C_FP / (C_FP + C_FN),   soit   p* = 1 / (1 + r)   avec   r = C_FN / C_FP.

C_FN étant proportionnel à la valeur du compte, le seuil optimal varie d'un facteur 130
entre déciles extrêmes. Un seuil global unique suppose implicitement que tous les comptes
se valent : sur ce portefeuille, l'hypothèse est fausse de trois ordres de grandeur.
"""

from __future__ import annotations

import pandas as pd

from ..config import CAPACITE_MENSUELLE, COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION


def seuil_par_compte(
    valeur_vie_client: pd.Series,
    efficacite_retention: float = EFFICACITE_RETENTION,
    cout_faux_positif: float = COUT_CONTACT_CSM_EUR,
) -> pd.Series:
    """Seuil de probabilité au-delà duquel agir devient rentable, compte par compte."""
    cout_faux_negatif = pd.to_numeric(valeur_vie_client, errors="coerce") * efficacite_retention
    return cout_faux_positif / (cout_faux_positif + cout_faux_negatif)


def prioriser(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
) -> pd.DataFrame:
    """Classe les comptes par valeur espérée et marque ceux que l'équipe peut traiter.

    Le classement est insensible à `efficacite_retention` : facteur commun à tous les
    comptes, elle ne modifie pas l'ordre, seulement l'estimation du gain absolu. C'est ce
    qui rend le dispositif robuste à l'hypothèse la plus fragile du projet.
    """
    table = pd.DataFrame(
        {
            "proba_churn": pd.Series(probabilites).astype(float),
            "valeur_vie_client_eur": pd.to_numeric(valeur_vie_client, errors="coerce"),
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


def sensibilite_classement(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    valeurs_efficacite: tuple[float, ...] = (0.15, 0.25, 0.40),
    capacite: int = CAPACITE_MENSUELLE,
) -> pd.DataFrame:
    """Vérifie empiriquement la stabilité du classement selon l'efficacité de rétention.

    Produit la preuve chiffrée de l'analyse de sensibilité annoncée au notebook § 9 :
    la composition de la liste des comptes traités ne doit pas varier.
    """
    reference = None
    lignes = []
    for u in valeurs_efficacite:
        table = prioriser(
            probabilites, valeur_vie_client, capacite=capacite, efficacite_retention=u
        )
        retenus = set(table.loc[table["a_traiter"]].index)
        if reference is None:
            reference = retenus
        lignes.append(
            {
                "efficacite_retention": u,
                "comptes_traites": len(retenus),
                "identiques_a_reference": len(retenus & reference),
                "part_commune_pct": round(
                    100 * len(retenus & reference) / max(len(reference), 1), 1
                ),
                "gain_espere_total_eur": round(
                    float(table.loc[table["a_traiter"], "valeur_esperee_eur"].sum()), 0
                ),
            }
        )
    return pd.DataFrame(lignes)
