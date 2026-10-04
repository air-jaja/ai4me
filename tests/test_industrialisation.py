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


# --- The monthly flow, run end to end (phase 11, point 9 of the certification review) ---------
@pytest.fixture(scope="module")
def modele_servi_temporaire(tmp_path_factory):
    """The served model, refitted as recorded (deterministic) into a temporary folder: the
    flow test needs no models/, so it runs in both CI jobs."""
    import importlib.util

    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import FicheModele, sauvegarder_modele

    specification = importlib.util.spec_from_file_location(
        "modele_servi", RACINE / "tools" / "modele_servi.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    parties = parties_du_decoupage(
        executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    )
    X, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    modele = outil.construire_servi(construire_baseline, "sigmoid", config)(X).fit(X, y)
    fiche = FicheModele(nom="churn_saas_servi", version="test", date_entrainement="2026-10-04")
    return sauvegarder_modele(
        modele, fiche, tmp_path_factory.mktemp("modele"), entrainement=(X, y), registre=None
    )


def test_le_flux_mensuel_tourne_de_bout_en_bout_et_rend_les_verdicts_du_suivi(
    modele_servi_temporaire,
):
    """The Prefect flow, called as production calls it, on the three simulated batches:
    data contract, scoring with the accounts' value and the catalogue, prioritisation, then
    the phase 11 verdicts. Month 1 raises no alert, month 2's collection incident is caught
    (M8), month 3's strong disengagement too (M5); the flagged volume is compared month to
    month (M9). Until 04/10/2026 this flow could not run at all, and nothing said so."""
    from churn_saas import config
    from churn_saas.industrialisation.flux import lot_mensuel

    simulation = RACINE / "data" / "simulation"
    precedent, verdicts = None, []
    for mois in ("mois_1_sans_derive", "mois_2_avec_derive", "mois_3_derive_forte"):
        table = lot_mensuel(
            str(simulation / f"lot_simule_{mois}.csv"),
            str(modele_servi_temporaire),
            chemin_catalogue=str(config.FICHIER_CATALOGUE),
            signales_precedents=precedent,
        )
        assert len(table) == 5_000 and int(table["a_traiter"].sum()) == config.CAPACITE_MENSUELLE
        assert table["client_id"].is_unique and table["proba_churn"].between(0, 1).all()
        suivi = table.attrs["suivi"]
        verdicts.append({a["indicateur"] for a in suivi["alertes"] if a["declenchee"]})
        precedent = suivi["M9_volume"]["comptes signalés"]
    assert verdicts[0] == set()
    assert verdicts[1] == {"Taux de manquants à l'entrée"}
    assert verdicts[2] == {"Dérive des entrées et du score (PSI)"}
