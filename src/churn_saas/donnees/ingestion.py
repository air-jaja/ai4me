"""Niveau BRONZE — lecture des sources, sans aucune transformation.

Tout est lu en texte. Laisser pandas deviner les types masquerait précisément les défauts
que la préparation doit traiter : un nombre écrit "33,3" serait silencieusement interprété
comme du texte, et l'on ne saurait pas si c'est voulu.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def charger_bronze(chemin: Path | str) -> pd.DataFrame:
    """Lit un CSV en conservant toutes les colonnes en texte.

    `encoding="utf-8-sig"` retire le BOM présent en tête des fichiers fournis. Sans lui,
    la première colonne s'appellerait "\ufeffclient_id" et toute sélection par nom
    échouerait de façon déroutante.
    """
    return pd.read_csv(chemin, encoding="utf-8-sig", dtype=str)


def inventaire(df: pd.DataFrame) -> pd.DataFrame:
    """État des lieux avant toute transformation : types, manquants, valeurs distinctes.

    Produit la photographie « avant » sans laquelle l'effet du nettoyage ne peut pas être
    démontré objectivement au jury (notebook § 5).
    """
    return pd.DataFrame(
        {
            "type": df.dtypes.astype(str),
            "manquants_pct": (df.isna().mean() * 100).round(2),
            "valeurs_distinctes": df.nunique(dropna=True),
            "exemple": df.apply(lambda s: s.dropna().iloc[0] if s.notna().any() else None),
        }
    )
