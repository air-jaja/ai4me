"""Experiment tracking (MLflow): optional, isolated, and consistent with the sources of truth.

MLflow is a journal and a showcase, never the authority: these tests check that it stays
optional (a silent no-op without MLflow, as in the CI), that it writes where it should
(never into the project's store during tests), and that what it records matches the
manifest and the model it was given.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

from churn_saas import config
from churn_saas.packaging import CLES_MLFLOW

pytestmark = pytest.mark.phase7

AVEC_MLFLOW = importlib.util.find_spec("mlflow") is not None
exige_mlflow = pytest.mark.skipif(not AVEC_MLFLOW, reason="MLflow absent (groupe suivi)")


def test_chaque_metrique_du_protocole_a_une_cle_ascii():
    """MLflow refuses accents in metric keys: every protocol metric needs its ASCII key."""
    from churn_saas.evaluation import METRIQUES

    assert {m.nom for m in METRIQUES} == set(CLES_MLFLOW)
    assert all(cle.isascii() for cle in CLES_MLFLOW.values())


def test_le_magasin_du_projet_est_un_chemin_absolu():
    """A relative store would differ between a notebook run in notebooks/ and a tool."""
    from pathlib import Path

    chemin = config.URI_SUIVI.removeprefix("sqlite:///")
    assert config.URI_SUIVI.startswith("sqlite:///") and Path(chemin).is_absolute()


def test_les_tests_n_ecrivent_jamais_dans_le_magasin_du_projet():
    from churn_saas.packaging import uri_suivi

    assert uri_suivi() != config.URI_SUIVI


def test_sans_mlflow_le_suivi_ne_fait_rien_et_n_echoue_pas(monkeypatch):
    """The CI has no MLflow: tracking must be a silent no-op, not an error."""
    from churn_saas.packaging import configurer_suivi, experience, journaliser_protocole

    monkeypatch.setitem(sys.modules, "mlflow", None)
    assert configurer_suivi() is None
    with experience("churn-saas/essai") as run:
        assert run is None
    moyennes = journaliser_protocole(pd.DataFrame({"PR-AUC": [0.7, 0.8]}))
    assert moyennes == {"pr_auc_cv": pytest.approx(0.75)}


@exige_mlflow
def test_chaque_pli_est_journalise_comme_une_etape():
    mlflow = pytest.importorskip("mlflow")

    from churn_saas.packaging import experience, journaliser_protocole

    with experience("churn-saas/essai", run="plis") as run:
        journaliser_protocole(pd.DataFrame({"PR-AUC": [0.70, 0.75, 0.80]}))
    historique = mlflow.MlflowClient().get_metric_history(run.info.run_id, "pr_auc_cv_par_pli")
    assert [m.step for m in historique] == [0, 1, 2]
    assert [m.value for m in historique] == [0.70, 0.75, 0.80]


@exige_mlflow
def test_le_modele_du_registre_predit_comme_le_modele_en_memoire():
    """Registered, aliased, reloaded: same probabilities, on rows holding missing values -
    the signature accepts them because nullable integers became floats."""
    from churn_saas.donnees import typer_pour_modele
    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import charger, enregistrer, experience, journaliser_modele

    generateur = np.random.default_rng(0)
    X = pd.DataFrame(
        {
            "a": pd.array(generateur.integers(0, 10, 200), dtype="Int64"),
            "b": generateur.choice(["x", "y"], 200),
        }
    )
    X.loc[::7, "a"] = pd.NA
    X = typer_pour_modele(X)
    y = pd.Series((generateur.random(200) < 0.3).astype(int))
    modele = construire_baseline(X).fit(X, y)
    with experience("churn-saas/essai", run="registre") as run:
        journaliser_modele(modele, X)
    enregistrer(run.info.run_id, alias="challenger", nom_modele="essai")
    recharge = charger("challenger", nom_modele="essai")
    lignes = X[X.isna().any(axis=1)]
    assert np.allclose(recharge.predict_proba(lignes), modele.predict_proba(lignes))


@exige_mlflow
def test_un_run_porte_le_commit_et_les_empreintes():
    from churn_saas.packaging import etiquettes_tracabilite

    manifeste = {
        "jeux_derives": {"jeux": {"gold": {"empreinte_contenu": "abc"}}},
        "decoupage": {"empreinte_comptes_test": "def"},
    }
    etiquettes = etiquettes_tracabilite("7", "essai", manifeste)
    assert etiquettes["empreinte_gold"] == "abc" and etiquettes["empreinte_comptes_test"] == "def"
    assert etiquettes["commit"] and "modifications_non_committees" in etiquettes
