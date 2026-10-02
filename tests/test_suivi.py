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


# --- Bloc 7.0 bis: one artefact location, reruns that add nothing --------------------------
@exige_mlflow
def test_les_artefacts_vont_a_cote_du_magasin_en_usage(tmp_path):
    """Never in a `mlruns/` relative to the current directory: beside the store in use -
    here the test's temporary one, so no test writes into the project."""
    from churn_saas.packaging import emplacement_artefacts, experience, uri_suivi

    attendu = emplacement_artefacts(uri_suivi())
    assert attendu.startswith("file://") and str(tmp_path.as_posix()) in attendu
    with experience("churn-saas/emplacement") as run:
        pass
    assert run.info.artifact_uri.startswith(attendu)


def test_le_parallelisme_se_regle_par_la_configuration(monkeypatch):
    from churn_saas import config

    monkeypatch.setenv("CHURN_N_JOBS", "2")
    assert config._coeurs_paralleles() == 2
    monkeypatch.delenv("CHURN_N_JOBS")
    assert config._coeurs_paralleles() >= 1


def test_la_duree_est_estimee_a_partir_des_temps_mesures():
    from churn_saas.modelisation import annoncer_duree, estimer_duree

    temps = {"entrainement_lr_s": 0.1, "entrainement_foret_s": 1.0}
    assert estimer_duree(temps, entrainements_lr=10, entrainements_foret=5) == pytest.approx(6.0)
    assert annoncer_duree(10, 5).startswith("Durée estimée")


@exige_mlflow
def test_relancer_la_chaine_ne_cree_pas_de_nouvelle_version():
    """Same code, same data, same configuration: the second execution registers nothing."""
    import json
    import subprocess

    from churn_saas.config import RACINE

    bilans = []
    for _ in range(2):
        sortie = subprocess.run(
            [sys.executable, str(RACINE / "tools" / "pipeline_mlflow.py"), "--rapide"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=RACINE,
            timeout=300,
        )
        assert sortie.returncode == 0, sortie.stderr[-800:]
        bilans.append(json.loads(sortie.stdout[sortie.stdout.index("{") :]))
    assert bilans[0]["nouvelle_version"] and not bilans[1]["nouvelle_version"]
    assert bilans[0]["version_registre"] == bilans[1]["version_registre"]
    assert bilans[0]["execution"] != bilans[1]["execution"]


@exige_mlflow
def test_relancer_le_retracage_ne_cree_pas_de_doublon():
    mlflow = pytest.importorskip("mlflow")

    from churn_saas.config import RACINE
    from churn_saas.packaging import configurer_suivi

    specification = importlib.util.spec_from_file_location(
        "retracer_mlflow", RACINE / "tools" / "retracer_mlflow.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    etiquettes = {"phase": "6", "empreinte_gold": "essai"}
    premier = outil.retracer_phase6(configurer_suivi(), etiquettes)
    second = outil.retracer_phase6(configurer_suivi(), etiquettes)
    assert premier == second
    runs = mlflow.search_runs(experiment_names=["churn-saas/phase6-baselines"])
    assert len(runs) == 3


@exige_mlflow
def test_une_meme_version_des_donnees_n_a_qu_un_run():
    from churn_saas.packaging import tracer_donnees

    gold = pd.DataFrame({"a": [1, 2], "churn": [0, 1]})
    journal = pd.DataFrame({"niveau": ["gold"], "lignes": [2], "colonnes": [2]})
    manifeste = {"jeux_derives": {"jeux": {"gold": {"empreinte_contenu": "f" * 64}}}}
    assert tracer_donnees(gold, journal, manifeste) == tracer_donnees(gold, journal, manifeste)


def test_la_matrice_de_confusion_ne_change_pas_le_moteur_graphique():
    """Built without pyplot: in a notebook it must not switch the inline backend, and in a
    script it must not open Tk - whose figures, destroyed by another thread at exit, made
    pipeline_mlflow.py print "main thread is not in main loop" on Windows."""
    import matplotlib
    from matplotlib.figure import Figure

    from churn_saas.config import RACINE

    specification = importlib.util.spec_from_file_location(
        "pipeline_mlflow", RACINE / "tools" / "pipeline_mlflow.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    avant = matplotlib.get_backend()
    figure, seuil = outil._matrice_confusion(
        pd.Series([0, 1, 0, 1, 1, 0, 0, 0, 1, 0]), np.linspace(0.1, 0.9, 10), part=0.2
    )
    assert isinstance(figure, Figure) and 0 < seuil < 1
    assert matplotlib.get_backend() == avant
