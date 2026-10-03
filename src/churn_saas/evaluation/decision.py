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


# --- Phase 9, rules R2 to R4 -----------------------------------------------------------------
def appliquer_regle(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    capacite: int = CAPACITE_MENSUELLE,
    efficacite_retention: float = EFFICACITE_RETENTION,
    cout_contact: float = COUT_CONTACT_CSM_EUR,
) -> pd.DataFrame:
    """Rule R3: net expected value, rational threshold, and the accounts actually treated.

    Net expected value = p x V x efficacy - cost of the contact. An account is profitable
    when it is positive - exactly when p exceeds its own threshold p* = cost / (cost +
    efficacy x V). The team treats the most valuable profitable accounts, within capacity.
    """
    table = prioriser(probabilites, valeur_vie_client, capacite, efficacite_retention)
    table["seuil_compte"] = seuil_par_compte(
        table["valeur_vie_client_eur"], efficacite_retention, cout_contact
    )
    table["valeur_nette_eur"] = table["valeur_esperee_eur"] - cout_contact
    table["rentable"] = table["proba_churn"] > table["seuil_compte"]
    table["a_traiter"] = table["a_traiter"] & table["rentable"]
    return table


def distribution_seuils(seuils: pd.Series) -> dict[str, float]:
    """R3: the per-account thresholds as a distribution - quantiles, not a variance.

    Values span orders of magnitude, so do the thresholds: a variance would be carried by a
    handful of accounts. Quantiles say what the typical account's threshold is."""
    quantiles = seuils.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "minimum": float(seuils.min()),
        **{f"quantile {int(q * 100)} %": float(v) for q, v in quantiles.items()},
        "maximum": float(seuils.max()),
        "rapport 95 % / 5 %": float(quantiles[0.95] / quantiles[0.05]),
    }


def part_rentable_selon_hypotheses(
    probabilites: pd.Series,
    valeur_vie_client: pd.Series,
    efficacites: tuple[float, ...],
    variation_cout: float,
    capacite: int,
) -> pd.DataFrame:
    """R3: how many accounts are worth contacting, under each economic hypothesis.

    The ORDER of the list does not depend on efficacy or cost (common factors); how far
    down the list contacting stays profitable does."""
    lignes = []
    for efficacite in efficacites:
        for facteur in (1 - variation_cout, 1.0, 1 + variation_cout):
            cout = COUT_CONTACT_CSM_EUR * facteur
            table = appliquer_regle(probabilites, valeur_vie_client, capacite, efficacite, cout)
            lignes.append(
                {
                    "efficacité": efficacite,
                    "coût d'un contact (€)": round(cout, 1),
                    "comptes rentables": int(table["rentable"].sum()),
                    "part rentable": round(float(table["rentable"].mean()), 4),
                    "comptes traités (capacité)": int(table["a_traiter"].sum()),
                    "valeur nette des comptes traités (€)": round(
                        float(table.loc[table["a_traiter"], "valeur_nette_eur"].sum()), 0
                    ),
                }
            )
    return pd.DataFrame(lignes)


def stabilite_liste(
    construire_modele,
    X: pd.DataFrame,
    y: pd.Series,
    valeur_vie_client: pd.Series,
    capacite: int,
    repetitions: int,
    graine: int,
) -> dict:
    """R4: does the treated list survive model uncertainty?

    The model is refitted on bootstrap resamples of the training rows; each refit ranks the
    same accounts, and its top-`capacite` list is compared with the reference model's by
    the Jaccard index (shared accounts / accounts in either list)."""
    import numpy as np

    y = pd.Series(y).astype(int)
    reference_modele = construire_modele(X).fit(X, y)

    def liste(modele):
        p = pd.Series(modele.predict_proba(X)[:, 1], index=X.index)
        table = prioriser(p, valeur_vie_client, capacite)
        return set(table.index[table["a_traiter"]])

    reference = liste(reference_modele)
    generateur = np.random.default_rng(graine)
    indices = []
    for _ in range(repetitions):
        tirage = generateur.integers(0, len(X), len(X))
        modele = construire_modele(X).fit(X.iloc[tirage], y.iloc[tirage])
        autre = liste(modele)
        indices.append(len(reference & autre) / len(reference | autre))
    indices = np.asarray(indices)
    return {
        "jaccard_moyen": float(indices.mean()),
        "jaccard_minimum": float(indices.min()),
        "jaccard_quantile_5": float(np.quantile(indices, 0.05)),
        "indices": [round(float(i), 4) for i in indices],
        "taille_liste": len(reference),
    }
