"""SILVER level - cleaning and normalisation.

These functions are reused **unchanged** at scoring time (see `industrialisation.scoring`).
That is the safeguard against training-serving skew: data prepared differently during
training and in production produces errors that no alert will ever raise.
"""

from __future__ import annotations

import pandas as pd

SYMBOLES_A_RETIRER = ("\u20ac", "%", "\u202f", "\xa0", " ")

# A unit written in letters right after the number: "3.1 h", "12 j", "40 Go". Matched
# generically rather than listed: a symbol list only covers the units someone thought of,
# and the one nobody thought of is turned into NaN without a word - which is how 570
# support delays written "3.1 h" were lost until phase 4.
UNITE_EN_LETTRES = r"(?<=\d)[^\W\d_]+\.?$"


def nettoyer_decimal_texte(serie: pd.Series) -> pd.Series:
    """Convert a numeric column stored as text ("1 234,50 EUR", "33,3 %", "3.1 h") into numbers.

    Unconvertible text still becomes NaN rather than raising: this primitive must never
    stop a batch on its own. Detecting what it lost is the job of `pertes_de_conversion`,
    which `construire_silver` runs on every converted column.
    """
    texte = serie.astype(str)
    for symbole in SYMBOLES_A_RETIRER:
        texte = texte.str.replace(symbole, "", regex=False)
    texte = texte.str.replace(UNITE_EN_LETTRES, "", regex=True)
    return pd.to_numeric(texte.str.replace(",", ".", regex=False), errors="coerce")


def pertes_de_conversion(avant: pd.Series, apres: pd.Series) -> pd.Series:
    """Rows holding a value before conversion and none after it.

    This is the generic guard against the defect `nettoyer_decimal_texte` can only
    mitigate: it targets no column name and no format, it compares presence before and
    after. A missing value that was already missing is not a loss.
    """
    texte = avant.astype("string").str.strip()
    present = avant.notna() & texte.notna() & texte.ne("") & texte.str.casefold().ne("nan")
    return present & apres.isna()


# Formats observed in the source, tried in this order. Declared explicitly because the
# implicit alternative is wrong in a way nothing reports: `format="mixed", dayfirst=True`
# reads "2024-02-06" as 2 June. Until phase 4 that swapped day and month on 960 of the
# 1,694 ISO dates - 19 % of the dataset - while every date still parsed.
FORMATS_DATE = ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y")


def parser_dates_multiformat(
    serie: pd.Series, formats: tuple[str, ...] = FORMATS_DATE
) -> pd.Series:
    """Parse mixed date formats (YYYY-MM-DD, DD/MM/YYYY, "12 Jan 2024"), one format at a time.

    Each value is read by the first declared format that fits it. A value matching none of
    them becomes NaT, which `construire_silver` reports as a conversion loss instead of
    guessing.

    Day-first for slash dates is a measured choice, not a convention. The source carries a
    witness: `jour_souscription`, the weekday of the subscription. Read this way, all 5,000
    dates agree with it; reading the 955 ambiguous slash dates month-first, only 15 % would
    (phase 4, pinned in the non-regression tests).
    """
    texte = serie.astype("string").str.strip()
    resultat = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    for format_ in formats:
        lues = pd.to_datetime(texte, format=format_, errors="coerce")
        resultat = resultat.where(resultat.notna(), lues)
    return resultat


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


def typer_colonnes_catalogue(catalogue: pd.DataFrame, cle: str = "plan") -> pd.DataFrame:
    """Give the catalogue columns their real type: numeric whenever the conversion is lossless.

    The catalogue is read as text like every source (bronze). Joined as is, its prices,
    SLA and quotas arrived in silver as strings, and the preprocessing then one-hot encoded
    them as categories - "12" and "25" EUR with no ordering left. The rule is generic: a
    column becomes numeric only if no value is lost on the way, so a genuinely textual
    column such as `support_dedie` ("Oui"/"Non") stays text.
    """
    out = catalogue.copy()
    out.columns = [c.lstrip("\ufeff") for c in out.columns]
    for colonne in [c for c in out.columns if c != cle]:
        converti = nettoyer_decimal_texte(out[colonne])
        if not pertes_de_conversion(out[colonne], converti).any():
            entier = converti.dropna().eq(converti.dropna().round()).all()
            out[colonne] = converti.astype("Int64") if entier else converti
    return out


def _signaler_pertes(pertes: dict[str, pd.Series], avant: pd.DataFrame) -> None:
    """Raise one readable error listing every column that lost values on conversion."""
    lignes = []
    for colonne, masque in pertes.items():
        exemples = ", ".join(repr(v) for v in avant.loc[masque, colonne].unique()[:3])
        lignes.append(f"  - {colonne} : {int(masque.sum())} valeurs (ex. {exemples})")
    raise ValueError(
        "Valeurs présentes dans la source et perdues à la conversion :\n"
        + "\n".join(lignes)
        + "\nCompléter la règle de conversion, ou appeler avec strict=False pour "
        "reproduire le défaut en connaissance de cause."
    )


def construire_silver(
    brut: pd.DataFrame,
    catalogue: pd.DataFrame | None = None,
    colonnes_decimales: list[str] | None = None,
    colonnes_dates: list[str] | None = None,
    colonnes_entieres: list[str] | None = None,
    colonnes_categorielles: list[str] | None = None,
    cle_compte: str | None = "client_id",
    strict: bool = True,
) -> pd.DataFrame:
    """Apply the full chain: duplicates, typing, normalisation, catalogue join.

    Case normalisation applies to the **stored values**, not only to the join key. Fixing
    the key alone leaves `TPE` and `tpe` as two categories in the dataset - the join works,
    and the model still sees twice as many categories as the business has.

    Three guards fail loudly instead of degrading quietly (phase 4):

    - `strict`: a value present in the source and lost on conversion raises. Until phase 4
      the conversion silently turned 570 support delays into NaN. `strict=False` exists
      only to reproduce that defect on purpose.
    - duplicates are removed twice: on the raw text, then again once values are typed and
      normalised, so that "12,5" and "12.5" describing the same account count as one.
    - `cle_compte`: an account still appearing twice after that carries conflicting
      values. No automatic rule can tell which row is right, so the chain stops.
    """
    df = brut.drop_duplicates().copy()
    reference = df.copy()

    pertes: dict[str, pd.Series] = {}
    for col in colonnes_decimales or []:
        if col in df.columns:
            df[col] = nettoyer_decimal_texte(df[col])
            pertes[col] = pertes_de_conversion(reference[col], df[col])
    for col in colonnes_entieres or []:
        if col in df.columns:
            df[col] = nettoyer_decimal_texte(df[col]).astype("Int64")
            pertes[col] = pertes_de_conversion(reference[col], df[col])
    for col in colonnes_dates or []:
        if col in df.columns:
            df[col] = parser_dates_multiformat(df[col])
            pertes[col] = pertes_de_conversion(reference[col], df[col])
    pertes = {col: masque for col, masque in pertes.items() if masque.any()}
    if strict and pertes:
        _signaler_pertes(pertes, reference)

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

    # Second pass, on typed and normalised values: duplicates differing only by their
    # written form ("12,5" / "12.5", "TPE" / "tpe") are only visible now.
    df = df.drop_duplicates()
    if cle_compte and cle_compte in df.columns:
        conflits = df[cle_compte].dropna().duplicated(keep=False)
        if conflits.any():
            exemples = ", ".join(df.loc[conflits[conflits].index, cle_compte].unique()[:3])
            raise ValueError(
                f"{int(df[cle_compte].duplicated().sum())} compte(s) en double avec des "
                f"valeurs différentes (ex. {exemples}). Aucune règle automatique ne peut "
                "décider quelle ligne est juste : arbitrer à la source avant de relancer."
            )

    if catalogue is not None and "plan" in df.columns:
        cat = typer_colonnes_catalogue(catalogue)
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
