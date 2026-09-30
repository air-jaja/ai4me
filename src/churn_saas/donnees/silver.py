"""SILVER level - cleaning and normalisation.

These functions are reused **unchanged** at scoring time (see `industrialisation.scoring`).
That is the safeguard against training-serving skew: data prepared differently during
training and in production produces errors that no alert will ever raise.
"""

from __future__ import annotations

import pandas as pd

SYMBOLES_A_RETIRER = ("\u20ac", "%", "\u202f", "\xa0", " ")


def nettoyer_decimal_texte(serie: pd.Series) -> pd.Series:
    """Convert a numeric column stored as text ("1 234,50 EUR", "33,3 %") into numbers."""
    texte = serie.astype(str)
    for symbole in SYMBOLES_A_RETIRER:
        texte = texte.str.replace(symbole, "", regex=False)
    return pd.to_numeric(texte.str.replace(",", ".", regex=False), errors="coerce")


def parser_dates_multiformat(serie: pd.Series) -> pd.Series:
    """Parse mixed date formats (DD/MM/YYYY, YYYY-MM-DD, "12 mars 2024").

    `dayfirst=True` resolves the 03/04/2024 ambiguity in favour of the French convention,
    consistent with where the data comes from. Without that explicit choice pandas would
    arbitrate on its own and the result would depend on row order.
    """
    return pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")


def normaliser_cle(serie: pd.Series) -> pd.Series:
    """Normalise a join key: strip whitespace, lowercase.

    `plan` appears as "STARTER" in one file and "Starter" in the other. Joining without
    normalisation would fail **without raising**: unmatched rows would simply vanish.
    """
    return serie.astype(str).str.strip().str.lower()


def construire_silver(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    colonnes_decimales: list[str] | None = None,
    colonnes_dates: list[str] | None = None,
    colonnes_entieres: list[str] | None = None,
) -> pd.DataFrame:
    """Apply the full chain: duplicates, typing, normalisation, catalogue join."""
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

    # Target text columns explicitly: select_dtypes(include="object") is ambiguous once
    # pandas string dtypes are in play.
    for col in [c for c in df.columns if df[c].dtype == object or str(df[c].dtype) == "str"]:
        df[col] = df[col].astype(str).str.strip().replace({"nan": None, "None": None})

    if catalogue is not None and "plan" in df.columns:
        cat = catalogue.copy()
        cat.columns = [c.lstrip("\ufeff") for c in cat.columns]
        df["_cle_plan"] = normaliser_cle(df["plan"])
        cat["_cle_plan"] = normaliser_cle(cat["plan"])
        avant = len(df)
        df = df.merge(cat.drop(columns=["plan"]), on="_cle_plan", how="left")
        # A row count change means the catalogue holds duplicate plans: fail loudly
        # rather than silently inflating the dataset.
        if len(df) != avant:
            raise ValueError(
                f"La jointure catalogue a changé le nombre de lignes ({avant} -> {len(df)}) : "
                "le catalogue contient vraisemblablement des doublons sur `plan`."
            )
        df = df.drop(columns=["_cle_plan"])

    return df
