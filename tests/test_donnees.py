"""Activity 1 - cleaning and building the silver/gold levels."""

import pandas as pd
import pytest

from churn_saas.donnees.gold import construire_gold, separer_cible
from churn_saas.donnees.silver import (
    construire_silver,
    nettoyer_decimal_texte,
    normaliser_cle,
    parser_dates_multiformat,
)


def test_nombres_stockes_en_texte():
    """Numbers stored as text must become numbers, and junk must become NaN.

    A failed conversion raising no error would turn a numeric column into categories:
    "33,3" and "33,4" would lose any ordering relation."""
    serie = pd.Series(["33,3 %", "1 234,50 €", "12.5", None, "abc"])
    resultat = nettoyer_decimal_texte(serie)
    assert resultat.iloc[0] == pytest.approx(33.3)
    assert resultat.iloc[1] == pytest.approx(1234.50)
    assert resultat.iloc[2] == pytest.approx(12.5)
    assert pd.isna(resultat.iloc[4])  # unconvertible text -> NaN, never an exception


def test_dates_multiformats():
    """Mixed date formats must all parse, and DD/MM must win over MM/DD.

    Without an explicit dayfirst choice, pandas arbitrates alone and the result depends on
    row order - a non-reproducible parse."""
    serie = pd.Series(["31/01/2024", "2024-02-06", "03/04/2024"])
    resultat = parser_dates_multiformat(serie)
    assert resultat.notna().all()
    # dayfirst: 03/04/2024 is 3 April, not 4 March
    assert resultat.iloc[2].month == 4


def test_normalisation_de_la_cle_de_jointure():
    """The join key must collapse case and whitespace differences."""
    assert list(normaliser_cle(pd.Series([" STARTER", "Starter"]))) == ["starter", "starter"]


def test_jointure_catalogue_sans_perte_malgre_la_casse():
    """The catalogue join must lose no row despite STARTER/starter.

    This is the silent failure of the project: without normalisation nothing raises, the
    unmatched rows simply vanish from the result."""
    brut = pd.DataFrame({"plan": ["STARTER", "Pro"], "x": ["1", "2"]})
    catalogue = pd.DataFrame({"plan": ["starter", "pro"], "prix": [10, 20]})
    silver = construire_silver(brut, catalogue=catalogue)
    assert len(silver) == 2
    assert silver["prix"].notna().all()  # without normalisation everything would be NaN


def test_doublons_supprimes():
    """Strict duplicates must be removed.

    Duplicated accounts make the model learn the same example twice and flatter every
    metric computed afterwards."""
    brut = pd.DataFrame({"a": ["1", "1", "2"]})
    assert len(construire_silver(brut)) == 2


def test_gold_retire_les_colonnes_interdites():
    """Every forbidden column must be gone from the gold dataset.

    Guards the single most expensive defect of the project: a leaking variable silently
    reintroduced by a refactor would produce an excellent, meaningless model."""
    silver = pd.DataFrame(
        {
            "client_id": ["CLI-1"],
            "sante_compte_fin_periode": [80],
            "commentaire_csm": ["note"],
            "groupe_experimentation": ["A"],
            "valeur_vie_client_eur": [1000],
            "anciennete_mois": [12],
            "churn": [1],
        }
    )
    gold = construire_gold(silver)
    assert set(gold.columns) == {"anciennete_mois", "churn"}


def test_separation_de_la_cible():
    """The target must never remain among the explanatory variables."""
    gold = pd.DataFrame({"a": [1, 2], "churn": [0, 1]})
    X, y = separer_cible(gold)
    assert "churn" not in X.columns
    assert list(y) == [0, 1]
