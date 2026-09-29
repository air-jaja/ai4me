"""Niveau SILVER — nettoyage et normalisation.

Ces fonctions sont **réutilisées à l'identique** au moment du scoring
(voir `industrialisation.scoring`). C'est la garantie contre le *training-serving skew* :
des données préparées différemment à l'entraînement et en production produisent des
erreurs qu'aucune alerte ne signale.
"""

from __future__ import annotations

import pandas as pd

SYMBOLES_A_RETIRER = ("\u20ac", "%", "\u202f", "\xa0", " ")


def nettoyer_decimal_texte(serie: pd.Series) -> pd.Series:
    """Convertit en nombre une colonne stockée en texte ("1 234,50 EUR", "33,3 %")."""
    texte = serie.astype(str)
    for symbole in SYMBOLES_A_RETIRER:
        texte = texte.str.replace(symbole, "", regex=False)
    return pd.to_numeric(texte.str.replace(",", ".", regex=False), errors="coerce")


def parser_dates_multiformat(serie: pd.Series) -> pd.Series:
    """Parse des dates de formats mêlés (JJ/MM/AAAA, AAAA-MM-JJ, "12 mars 2024").

    `dayfirst=True` tranche l'ambiguïté 03/04/2024 en faveur de la convention française,
    cohérente avec l'origine des données. Sans ce choix explicite, pandas arbitrerait seul
    et le résultat dépendrait de l'ordre des lignes.
    """
    return pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")


def normaliser_cle(serie: pd.Series) -> pd.Series:
    """Uniformise une clé de jointure : espaces retirés, casse abaissée.

    `plan` vaut tantôt "STARTER", tantôt "Starter". Une jointure sans normalisation
    échouerait **sans lever d'erreur** : les lignes non appariées disparaîtraient.
    """
    return serie.astype(str).str.strip().str.lower()


def construire_silver(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    colonnes_decimales: list[str] | None = None,
    colonnes_dates: list[str] | None = None,
    colonnes_entieres: list[str] | None = None,
) -> pd.DataFrame:
    """Applique la chaîne complète : doublons, types, normalisation, jointure catalogue."""
    df = brut.drop_duplicates().copy()

    for col in colonnes_decimales or []:
        if col in df.columns:
            df[col] = nettoyer_decimal_texte(df[col])
    for col in colonnes_entieres or []:
        if col in df.columns:
            df[col] = nettoyer_decimal_texte(df[col]).astype("Int64")
    for col in colonnes_dates or []:
        if col in df.columns:
            df[col] = parser_dates_multiformat(df[col])

    for col in [c for c in df.columns if df[c].dtype == object or str(df[c].dtype) == "str"]:
        df[col] = df[col].astype(str).str.strip().replace({"nan": None, "None": None})

    if catalogue is not None and "plan" in df.columns:
        cat = catalogue.copy()
        cat.columns = [c.lstrip("\ufeff") for c in cat.columns]
        df["_cle_plan"] = normaliser_cle(df["plan"])
        cat["_cle_plan"] = normaliser_cle(cat["plan"])
        avant = len(df)
        df = df.merge(cat.drop(columns=["plan"]), on="_cle_plan", how="left")
        if len(df) != avant:
            raise ValueError(
                f"La jointure catalogue a changé le nombre de lignes ({avant} -> {len(df)}) : "
                "le catalogue contient vraisemblablement des doublons sur `plan`."
            )
        df = df.drop(columns=["_cle_plan"])

    return df
