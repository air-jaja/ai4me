"""Activity 6 - the monthly batch prepares data exactly as training does.

`industrialisation` imports SQLAlchemy, which the CI does not install (it only installs the
`dev` group). The first test therefore reads the source instead of importing it, so the
guarantee holds in CI; the behavioural ones run wherever the platform group is installed.
"""

import ast
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SCORING = RACINE / "src" / "churn_saas" / "industrialisation" / "scoring.py"
DONNEES = RACINE / "data" / "raw"


def _appels(fonction: str) -> set[str]:
    arbre = ast.parse(SCORING.read_text(encoding="utf-8"))
    corps = next(
        n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == fonction
    )
    return {
        n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        for n in ast.walk(corps)
        if isinstance(n, ast.Call)
    }


def test_le_lot_mensuel_appelle_la_chaine_partagee():
    """`preparer` must go through the shared chain, never rebuild silver on its own.

    Until phase 4 it called `construire_silver` without the column lists: the batch would
    have been scored on numbers left as text while training used converted ones.
    """
    appels = _appels("preparer")
    assert {"construire_silver_standard", "preparer_gold"} <= appels
    assert "construire_silver" not in appels


def test_le_lot_mensuel_passe_le_contrat_de_donnees():
    assert {"exiger_contrat", "controler_lot"} <= _appels("scorer_lot_mensuel")


def test_le_lot_mensuel_prepare_comme_l_entrainement():
    """On the full dataset, the batch preparation yields the training gold, byte for byte."""
    pytest.importorskip("sqlalchemy")
    from churn_saas.donnees import charger_bronze, empreinte_donnees
    from churn_saas.features import executer_pipeline
    from churn_saas.industrialisation import preparer

    fichier, catalogue = DONNEES / "churn_saas_complet.csv", DONNEES / "catalogue_plans.csv"
    entrainement = executer_pipeline(fichier, catalogue).gold
    lot = preparer(charger_bronze(fichier), catalogue=charger_bronze(catalogue))
    assert empreinte_donnees(lot) == empreinte_donnees(entrainement)


def test_le_contrat_du_lot_n_exige_pas_les_colonnes_posterieures():
    """A monthly batch has no outcome yet: its contract must not demand `churn`."""
    pytest.importorskip("sqlalchemy")
    from churn_saas.donnees import CONFORME, charger_bronze
    from churn_saas.industrialisation import controler_lot

    lot = charger_bronze(DONNEES / "churn_saas_echantillon.csv").drop(
        columns=["churn", "sante_compte_fin_periode"]
    )
    contrat = controler_lot(lot, catalogue=charger_bronze(DONNEES / "catalogue_plans.csv"))
    assert (contrat["statut"] == CONFORME).all(), contrat.to_string()
