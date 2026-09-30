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


COLONNES_A_NORMALISER = (
    "secteur",
    "pays",
    "taille_entreprise",
    "plan",
    "code_datacenter",
    "couleur_theme_interface",
    "jour_souscription",
)


def normaliser_modalites(serie: pd.Series) -> pd.Series:
    """Merge spellings of the same category, keeping the most frequent one as the label.

    `TPE`, `tpe` and ` TPE ` are one category written three ways. Left as they are, one-hot
    encoding turns each spelling into its own column: the model sees three rare categories
    instead of one common one, splits the signal between them, and any importance reading
    becomes misleading.

    The canonical label is the most frequent spelling rather than a lowercase form, so that
    `TPE` stays `TPE` and a reader is not handed `tpe` in a deliverable.
    """
    texte = serie.astype(str).str.strip()
    cle = texte.str.casefold()

    # Most frequent original spelling per normalised key.
    canonique = (
        pd.DataFrame({"cle": cle, "texte": texte})
        .loc[texte.ne("nan")]
        .groupby("cle")["texte"]
        .agg(lambda valeurs: valeurs.value_counts().index[0])
    )
    resultat = cle.map(canonique)
    return resultat.where(serie.notna() & texte.ne("nan"))


def construire_silver(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    colonnes_decimales: list[str] | None = None,
    colonnes_dates: list[str] | None = None,
    colonnes_entieres: list[str] | None = None,
    colonnes_categorielles: list[str] | None = None,
) -> pd.DataFrame:
    """Apply the full chain: duplicates, typing, normalisation, catalogue join.

    Case normalisation applies to the **stored values**, not only to the join key. Fixing
    the key alone leaves `TPE` and `tpe` as two categories in the dataset - the join works,
    and the model still sees twice as many categories as the business has.
    """
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

    # `is None` and not a truth test: an empty list must mean "normalise nothing", which
    # is what lets a test reproduce the defect this normalisation fixes. Written with
    # `or`, an empty list would silently fall back to the default and the test would
    # measure the corrected behaviour while claiming to measure the broken one.
    a_normaliser = (
        COLONNES_A_NORMALISER if colonnes_categorielles is None else colonnes_categorielles
    )
    for col in a_normaliser:
        if col in df.columns:
            df[col] = normaliser_modalites(df[col])

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


def silver_lisible(silver: pd.DataFrame, marquer: bool = True) -> pd.DataFrame:
    """Fill missing values for a human reader - never for the model.

    Silver has two consumers with opposite needs. A person reading the data, or a
    reporting tool, wants no holes. A model wants the holes left in place, because the
    imputation must be **fitted on training folds only**: filling before the split lets
    the test set influence the values the model learns from, which is leakage - quiet,
    and invisible in every metric.

    This function therefore serves the first consumer. The values it produces are
    deterministic - median for numbers, most frequent for categories, computed on the
    whole table - which is precisely what disqualifies them from any training use.

    `marquer` adds an `_impute` flag per filled column, so a reader can always tell an
    observed value from a reconstructed one.
    """
    lisible = silver.copy()
    for colonne in lisible.columns:
        manquants = lisible[colonne].isna()
        if not manquants.any():
            continue
        serie = lisible[colonne]
        if pd.api.types.is_numeric_dtype(serie):
            remplacement = serie.median()
        else:
            modes = serie.mode(dropna=True)
            remplacement = modes.iloc[0] if not modes.empty else "non renseigné"
        if marquer:
            lisible[f"{colonne}_impute"] = manquants
        lisible[colonne] = serie.fillna(remplacement)
    return lisible
