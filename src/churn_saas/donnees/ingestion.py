"""BRONZE level - read the sources, apply no transformation.

Everything is read as text. Letting pandas infer types would hide the very defects the
preparation step must handle: a number stored as "33,3" would silently become a string
and nobody could tell whether that was intended.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def charger_bronze(chemin: Path | str) -> pd.DataFrame:
    """Read a CSV keeping every column as text.

    `encoding="utf-8-sig"` strips the BOM found at the start of the supplied files.
    Without it the first column would be named "\ufeffclient_id" and any selection by
    name would fail in a confusing way.
    """
    return pd.read_csv(chemin, encoding="utf-8-sig", dtype=str)


def inventaire(df: pd.DataFrame) -> pd.DataFrame:
    """Baseline picture before any transformation: types, missing rates, cardinality.

    Produces the "before" snapshot without which the effect of cleaning cannot be
    demonstrated objectively to the jury (notebook section 5).
    """
    return pd.DataFrame(
        {
            "type": df.dtypes.astype(str),
            "manquants_pct": (df.isna().mean() * 100).round(2),
            "valeurs_distinctes": df.nunique(dropna=True),
            "exemple": df.apply(lambda s: s.dropna().iloc[0] if s.notna().any() else None),
        }
    )
