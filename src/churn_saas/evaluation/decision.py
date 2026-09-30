"""Business decision rule: expected-value prioritisation.

Rationale (notebook section 9): for an account with estimated probability p, acting is
rational as soon as

    p > C_FP / (C_FP + C_FN),   i.e.   p* = 1 / (1 + r)   with   r = C_FN / C_FP.

Since C_FN is proportional to account value, the optimal threshold varies by a factor of
130 between extreme deciles. A single global threshold implicitly assumes all accounts are
worth the same: on this portfolio that assumption is wrong by three orders of magnitude.
"""

from __future__ import annotations

import pandas as pd

from ..config import CAPACITE_MENSUELLE, COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION


def seuil_par_compte(
    valeur_vie_client: pd.Series,
    efficacite_retention: float = EFFICACITE_RETENTION,
    cout_faux_positif: float = COUT_CONTACT_CSM_EUR,
) -> pd.Series:
    """Probability threshold above which acting becomes profitable, account by account."""
    cout_faux_negatif = pd.to_numeric(valeur_vie_client, errors="coerce") * efficacite_retention
    return cout_faux_positif / (cout_faux_positif + cout_faux_negatif)


def prioriser(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
) -> pd.DataFrame:
    """Rank accounts by expected value and flag those the team can actually handle.

    The ranking is insensitive to `efficacite_retention`: being a factor common to every
    account, it shifts the absolute gain estimate but not the order. That is what makes
    the design robust to the project's most fragile assumption.
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
    """Empirically check ranking stability across retention-effectiveness values.

    Produces the evidence behind the sensitivity analysis promised in notebook section 9:
    the composition of the handled shortlist must not change.
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
