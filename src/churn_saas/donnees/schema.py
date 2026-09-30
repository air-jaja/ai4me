"""Data schema description and quality report.

Two distinct questions, deliberately kept apart:

    schema      what the data claims to be - columns, types, roles
    qualite     what the data actually is - defects, gaps, inconsistencies

Comparing the two is the whole point of the ingestion step. A column declared as a
percentage but stored as "33,3 %" is not a typing accident: it is the gap between the
contract and the reality, and it must be measured before it is fixed.
"""

from __future__ import annotations

import pandas as pd

# Declared role of every source column. Roles - not types - drive what the pipeline is
# allowed to do with a column: a target must never become a feature, an identifier must
# never reach the model.
ROLES_COLONNES: dict[str, str] = {
    "client_id": "identifiant",
    "date_souscription": "contractuel",
    "jour_souscription": "contractuel",
    "secteur": "signalétique",
    "pays": "signalétique",
    "taille_entreprise": "signalétique",
    "plan": "contractuel",
    "anciennete_mois": "contractuel",
    "sieges_souscrits": "contractuel",
    "utilisateurs_actifs": "usage",
    "taux_adoption_pct": "usage",
    "connexions_30j": "usage",
    "heures_usage_30j": "usage",
    "fonctionnalites_total": "contractuel",
    "fonctionnalites_utilisees": "usage",
    "nb_integrations": "usage",
    "derniere_connexion_jours": "usage",
    "tickets_support_90j": "support",
    "delai_reponse_support_h": "support",
    "csat": "support",
    "retards_paiement_12m": "facturation",
    "revenu_mensuel_recurrent_eur": "facturation",
    "couleur_theme_interface": "leurre présumé",
    "code_datacenter": "leurre présumé",
    "groupe_experimentation": "artefact de process",
    "commentaire_csm": "texte libre",
    "sante_compte_fin_periode": "postérieur à la décision",
    "valeur_vie_client_eur": "cible secondaire",
    "churn": "cible principale",
}

# Expected storage form, as announced by the brief. Columns listed here are known to
# arrive as text even though they carry numbers or dates.
FORME_ATTENDUE: dict[str, str] = {
    "taux_adoption_pct": "décimal stocké en texte (virgule, %)",
    "heures_usage_30j": "décimal stocké en texte (virgule)",
    "delai_reponse_support_h": "décimal stocké en texte (virgule)",
    "revenu_mensuel_recurrent_eur": "décimal stocké en texte (virgule, €)",
    "valeur_vie_client_eur": "décimal stocké en texte (virgule)",
    "date_souscription": "date en formats mêlés",
}


def decrire_schema(brut: pd.DataFrame) -> pd.DataFrame:
    """Per-column schema view: declared role, observed form, completeness, cardinality."""
    lignes = []
    for colonne in brut.columns:
        serie = brut[colonne]
        lignes.append(
            {
                "colonne": colonne,
                "role": ROLES_COLONNES.get(colonne, "non documenté"),
                "forme attendue": FORME_ATTENDUE.get(colonne, "directement exploitable"),
                "manquants %": round(float(serie.isna().mean() * 100), 2),
                "valeurs distinctes": int(serie.nunique(dropna=True)),
                "exemple": (serie.dropna().iloc[0] if serie.notna().any() else None),
            }
        )
    return pd.DataFrame(lignes)


def auditer_qualite(brut: pd.DataFrame) -> pd.DataFrame:
    """Detected defects, each with its scope and the consequence of leaving it unfixed.

    The point is not to list problems but to make explicit what each one would cost. A
    silent failure - a join losing rows without raising - is worse than a loud one.
    """
    constats = []

    doublons = int(brut.duplicated().sum())
    constats.append(
        {
            "défaut": "Doublons stricts",
            "portée": f"{doublons} lignes sur {len(brut)}",
            "conséquence si non traité": (
                "Sur-représentation de comptes identiques : le modèle apprend deux fois "
                "les mêmes exemples et les métriques sont optimistes"
            ),
        }
    )

    bom = any(c.startswith("\ufeff") for c in brut.columns)
    constats.append(
        {
            "défaut": "BOM UTF-8 en tête de fichier",
            "portée": "1re colonne" if bom else "absent après lecture utf-8-sig",
            "conséquence si non traité": (
                "La première colonne s'appelle \ufeffclient_id : toute sélection par nom "
                "échoue sans message explicite"
            ),
        }
    )

    en_texte = [c for c in FORME_ATTENDUE if c in brut.columns and "décimal" in FORME_ATTENDUE[c]]
    constats.append(
        {
            "défaut": "Nombres stockés en texte",
            "portée": f"{len(en_texte)} colonnes : {', '.join(en_texte)}",
            "conséquence si non traité": (
                "Colonnes traitées comme catégorielles : une valeur = une modalité, "
                "toute relation d'ordre est perdue"
            ),
        }
    )

    if "date_souscription" in brut.columns:
        echantillon = brut["date_souscription"].dropna().astype(str)
        avec_slash = int(echantillon.str.contains("/").sum())
        avec_tiret = int(echantillon.str.contains("-").sum())
        constats.append(
            {
                "défaut": "Dates en formats mêlés",
                "portée": f"{avec_slash} en JJ/MM/AAAA, {avec_tiret} en AAAA-MM-JJ",
                "conséquence si non traité": (
                    "Parsing partiel : les formats non reconnus deviennent NaT sans alerte"
                ),
            }
        )

    casse = []
    for colonne in ("secteur", "plan", "pays", "taille_entreprise"):
        if colonne in brut.columns:
            valeurs = brut[colonne].dropna().astype(str)
            if valeurs.nunique() != valeurs.str.lower().str.strip().nunique():
                casse.append(colonne)
    constats.append(
        {
            "défaut": "Casse et espaces hétérogènes",
            "portée": ", ".join(casse) if casse else "aucune colonne concernée",
            "conséquence si non traité": (
                "Jointure sur `plan` silencieusement incomplète : les lignes non "
                "appariées disparaissent sans erreur"
            ),
        }
    )

    return pd.DataFrame(constats)


def controler_jointure(
    gauche: pd.DataFrame, droite: pd.DataFrame, cle: str = "plan"
) -> pd.DataFrame:
    """Compare join match rates with and without key normalisation.

    Quantifies what normalisation buys. Without this measurement, the decision to
    normalise rests on intuition rather than evidence.
    """
    valeurs_gauche = gauche[cle].dropna().astype(str)
    colonnes_droite = [c.lstrip("\ufeff") for c in droite.columns]
    droite = droite.copy()
    droite.columns = colonnes_droite
    valeurs_droite = droite[cle].dropna().astype(str)

    brut = valeurs_gauche.isin(set(valeurs_droite)).mean()
    normalise = (
        valeurs_gauche.str.strip()
        .str.lower()
        .isin(set(valeurs_droite.str.strip().str.lower()))
        .mean()
    )
    return pd.DataFrame(
        [
            {
                "méthode de jointure": "Sur la valeur brute",
                "taux d'appariement": f"{brut:.1%}",
                "lignes perdues": int(round((1 - brut) * len(valeurs_gauche))),
            },
            {
                "méthode de jointure": "Après normalisation (casse, espaces)",
                "taux d'appariement": f"{normalise:.1%}",
                "lignes perdues": int(round((1 - normalise) * len(valeurs_gauche))),
            },
        ]
    )
