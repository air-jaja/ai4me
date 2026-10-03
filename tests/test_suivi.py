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


def _chaine_rapide(monkeypatch, forcer: bool = False) -> dict:
    """The chain, in this process, with a dummy protocol evaluation (optimisation A2).

    What these tests check is the RELAUNCH logic - identity, reuse, --forcer, registry -
    not the 25-fold evaluation, which the protocol's own tests and the non-regression
    figures cover. Run in-process, with an instant evaluation, a chain execution takes
    about a second instead of six in a subprocess.
    """
    import churn_saas.evaluation as evaluation
    from churn_saas.evaluation import ResultatProtocole

    def evaluation_factice(construire_modele, X, y, probabiliste=True):
        par_pli = pd.DataFrame(
            {
                "PR-AUC": [0.79] * 25,
                "ROC-AUC": [0.89] * 25,
                "rappel haut": [0.33] * 25,
                "précision haut": [0.92] * 25,
                "Brier": [0.13] * 25,
                "erreur de calibration": [0.11] * 25,
            }
        )
        return ResultatProtocole(par_pli, pd.Series(np.linspace(0, 1, len(X)), index=X.index))

    monkeypatch.setattr(evaluation, "evaluer_selon_protocole", evaluation_factice)
    return _outil_chaine().executer(avec_grille=False, rapide=True, forcer=forcer)


@exige_mlflow
def test_relancer_la_chaine_reutilise_l_execution_identique(monkeypatch):
    """Same code, data, protocol and options: the second execution computes and registers
    nothing - the same control as the replay tool (A1)."""
    pytest.importorskip("mlflow")
    from churn_saas.packaging import configurer_suivi

    mlflow = configurer_suivi()
    premiere, seconde = _chaine_rapide(monkeypatch), _chaine_rapide(monkeypatch)
    assert premiere["nouvelle_version"] and not premiere["reutilisee"]
    assert seconde["reutilisee"] and not seconde["nouvelle_version"]
    assert seconde["execution"] == premiere["execution"]
    runs = mlflow.search_runs(experiment_names=["churn-saas/phase7-chaine-mlflow"])
    assert len(runs) == 2  # one parent, one child: nothing added by the second execution

    forcee = _chaine_rapide(monkeypatch, forcer=True)
    assert forcee["execution"] != premiere["execution"] and not forcee["reutilisee"]
    runs = mlflow.search_runs(experiment_names=["churn-saas/phase7-chaine-mlflow"])
    assert len(runs) == 2 and forcee["version_registre"] == premiere["version_registre"]


@exige_mlflow
def test_la_chaine_rapide_tourne_de_bout_en_bout():
    """One real end-to-end run, in a subprocess, as a user launches it - the in-process
    tests above replace the computation, this one does not."""
    import json
    import subprocess

    from churn_saas.config import RACINE

    sortie = subprocess.run(
        [sys.executable, str(RACINE / "tools" / "pipeline_mlflow.py"), "--rapide"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RACINE,
        timeout=300,
    )
    assert sortie.returncode == 0, sortie.stderr[-800:]
    bilan = json.loads(sortie.stdout[sortie.stdout.index("{") :])
    assert bilan["registre_identique_au_modele_en_memoire"]


@exige_mlflow
def test_relancer_le_retracage_ne_cree_pas_de_doublon(monkeypatch):
    """The replay logic, with an instant reference computation (optimisation A2)."""
    mlflow = pytest.importorskip("mlflow")
    import types

    plis = {"PR-AUC": [0.79] * 25, "ROC-AUC": [0.89] * 25}
    factice = types.ModuleType("resultats_reference")
    factice.calculer = lambda: {
        "baselines": {
            n: {"par_pli": plis} for n in ("naïve", "règle métier", "régression logistique")
        }
    }
    monkeypatch.setitem(sys.modules, "resultats_reference", factice)

    from churn_saas.config import RACINE
    from churn_saas.packaging import configurer_suivi

    specification = importlib.util.spec_from_file_location(
        "retracer_mlflow", RACINE / "tools" / "retracer_mlflow.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    etiquettes = {"phase": "6", "empreinte_gold": "essai", "empreinte_code": "c1"}
    premier = outil.retracer_phase6(configurer_suivi(), etiquettes)
    second = outil.retracer_phase6(configurer_suivi(), etiquettes)
    assert premier == second
    assert len(mlflow.search_runs(experiment_names=["churn-saas/phase6-baselines"])) == 3

    # A change of code is a different identity: replayed, not kept in silence (A1).
    outil.retracer_phase6(configurer_suivi(), etiquettes | {"empreinte_code": "c2"})
    assert len(mlflow.search_runs(experiment_names=["churn-saas/phase6-baselines"])) == 6

    # --forcer replaces the identical runs without duplicating them.
    outil.retracer_phase6(configurer_suivi(), etiquettes | {"empreinte_code": "c2"}, forcer=True)
    assert len(mlflow.search_runs(experiment_names=["churn-saas/phase6-baselines"])) == 6


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


def test_l_identite_change_avec_le_code_les_donnees_le_protocole_ou_les_options():
    from churn_saas.packaging import identite_execution

    base = {"empreinte_code": "a", "empreinte_gold": "g", "empreinte_protocole": "p"}
    reference = identite_execution(base, outil="x", option=1)
    assert identite_execution(base, outil="x", option=1) == reference
    for cle in base:
        assert identite_execution(base | {cle: "autre"}, outil="x", option=1) != reference
    assert identite_execution(base, outil="x", option=2) != reference


def test_le_parallelisme_ne_change_pas_l_empreinte_du_protocole(monkeypatch):
    """N_JOBS changes durations, never results: it must not change the identity."""
    from churn_saas import config
    from churn_saas.packaging import empreinte_protocole

    avant = empreinte_protocole()
    monkeypatch.setattr(config, "N_JOBS", config.N_JOBS + 7)
    assert empreinte_protocole() == avant
    monkeypatch.setattr(config, "PART_HAUT_CLASSEMENT", 0.2)
    assert empreinte_protocole() != avant


# --- The traced runs: autolog for the traced fit only, one parallel layer -------------------
def _outil_chaine():
    from churn_saas.config import RACINE

    specification = importlib.util.spec_from_file_location(
        "pipeline_mlflow", RACINE / "tools" / "pipeline_mlflow.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    return outil


@exige_mlflow
def test_l_autolog_est_coupe_apres_l_entrainement_trace_meme_en_cas_d_erreur():
    """Left on, autolog patched the 25 fits of the protocol evaluation too, and on Windows
    its threads on top of the forests' exhausted the process ("can't start new thread")."""
    mlflow = pytest.importorskip("mlflow")
    autologging_is_disabled = pytest.importorskip(
        "mlflow.utils.autologging_utils"
    ).autologging_is_disabled

    outil = _outil_chaine()
    activer = lambda: mlflow.sklearn.autolog(log_models=False, silent=True)  # noqa: E731
    assert outil.ajuster_sous_autolog(mlflow, activer, lambda: "ajusté") == "ajusté"
    assert autologging_is_disabled("sklearn")

    def echoue():
        raise ValueError("entraînement en échec")

    with pytest.raises(ValueError):
        outil.ajuster_sous_autolog(mlflow, activer, echoue)
    assert autologging_is_disabled("sklearn")


def test_la_grille_de_la_chaine_n_a_qu_une_couche_parallele():
    """One layer, inside the forest and by threads: the search itself spawns no worker
    process. Worker processes broke on Windows under autolog (a task they could not
    unpickle: MemoryError, BrokenProcessPool)."""
    from churn_saas import config
    from churn_saas.modelisation import construire_candidat, grille_hyperparametres

    X = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": ["x", "y", "x"]})
    recherche = _outil_chaine().construire_recherche(
        X, config, construire_candidat, grille_hyperparametres
    )
    assert recherche.n_jobs == 1
    assert recherche.estimator.get_params()["modele__n_jobs"] == config.N_JOBS


def test_les_dependances_du_modele_sont_declarees_et_epinglees():
    """B2: declared rather than inferred by a uv export at every logged model."""
    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import dependances_du_modele

    X = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    dependances = dependances_du_modele(construire_baseline(X))
    assert any(d.startswith("scikit-learn==") for d in dependances)
    assert all("==" in d for d in dependances)
    assert not any(d.startswith("xgboost") for d in dependances)


@exige_mlflow
def test_journaliser_un_modele_ne_cherche_pas_la_version_de_pip(caplog):
    """The uv environment has no pip: inferring the conda file made MLflow look for it,
    slowly, with a warning at every logged model (B2, completed)."""
    import logging

    from churn_saas.modelisation import construire_baseline
    from churn_saas.packaging import experience, journaliser_modele

    X = pd.DataFrame({"a": np.linspace(0, 1, 60), "b": ["x", "y"] * 30})
    y = pd.Series([0, 1] * 30)
    modele = construire_baseline(X).fit(X, y)
    with caplog.at_level(logging.WARNING), experience("churn-saas/pip"):
        journaliser_modele(modele, X)
    assert not any("pip version" in r.getMessage() for r in caplog.records)


@exige_mlflow
def test_une_execution_incomplete_n_est_pas_reutilisee(monkeypatch):
    """Carnet 07, on the laptop: an execution interrupted earlier had been closed as
    FINISHED with no child run. Reused, it made the comparison read an empty table
    (KeyError). An incomplete execution is now replaced, and a failed one is FAILED."""
    from churn_saas.packaging import configurer_suivi

    mlflow = configurer_suivi()
    premiere = _chaine_rapide(monkeypatch)
    for run_id in mlflow.search_runs(
        experiment_names=["churn-saas/phase7-chaine-mlflow"],
        filter_string=f"tags.mlflow.parentRunId = '{premiere['execution']}'",
    )["run_id"]:
        mlflow.MlflowClient().delete_run(run_id)  # the parent stays, alone and FINISHED

    seconde = _chaine_rapide(monkeypatch)
    assert not seconde["reutilisee"] and seconde["execution"] != premiere["execution"]


@exige_mlflow
def test_une_execution_en_echec_est_marquee_failed(monkeypatch):
    import churn_saas.evaluation as evaluation
    from churn_saas.packaging import configurer_suivi

    mlflow = configurer_suivi()

    def echec(*args, **kwargs):
        raise RuntimeError("évaluation interrompue")

    monkeypatch.setattr(evaluation, "evaluer_selon_protocole", echec)
    with pytest.raises(RuntimeError):
        _outil_chaine().executer(avec_grille=False, rapide=True)
    parents = mlflow.search_runs(
        experiment_names=["churn-saas/phase7-chaine-mlflow"],
        filter_string="tags.execution = 'parent'",
    )
    assert set(parents["status"]) == {"FAILED"}


# --- Refined execution identity (03/10/2026): only the code that produces results ------------
def test_le_perimetre_de_l_identite_est_le_code_qui_produit_les_resultats():
    """Correcting MLflow logging, a figure or another tool invalidated every recorded
    result three times in a day (15 minutes of recomputation each, identical figures).
    The identity now covers the result-producing code and the producing tool only."""
    from churn_saas.config import RACINE
    from churn_saas.packaging import fichiers_du_perimetre

    perimetre = {
        f.relative_to(RACINE).as_posix() for f in fichiers_du_perimetre("tools/selection_modele.py")
    }
    for dedans in (
        "src/churn_saas/config.py",
        "src/churn_saas/modelisation/reglage.py",
        "src/churn_saas/evaluation/protocole.py",
        "src/churn_saas/features/pipeline.py",
        "src/churn_saas/donnees/gold.py",
        "tools/selection_modele.py",
    ):
        assert dedans in perimetre, dedans
    for dehors in (
        "src/churn_saas/packaging/suivi.py",
        "src/churn_saas/features/graphiques.py",
        "src/churn_saas/industrialisation/scoring.py",
        "tools/pipeline_mlflow.py",
        "tools/selection_variables.py",
    ):
        assert dehors not in perimetre, dehors


def test_l_empreinte_ne_bouge_qu_avec_le_code_du_perimetre(tmp_path, monkeypatch):
    """Same fingerprint after touching a file outside the perimeter; a new one after
    touching a file inside it."""
    import shutil

    import churn_saas.packaging.dependances as dependances
    import churn_saas.packaging.suivi as suivi
    from churn_saas.config import RACINE

    copie = tmp_path / "depot"
    shutil.copytree(RACINE / "src", copie / "src")
    shutil.copytree(RACINE / "tools", copie / "tools")
    monkeypatch.setattr(suivi, "RACINE", copie)
    monkeypatch.setattr(dependances, "RACINE", copie)
    monkeypatch.setattr(dependances, "PAQUET", copie / "src" / "churn_saas")
    avant = suivi.empreinte_code("tools/selection_modele.py")
    (copie / "src/churn_saas/packaging/suivi.py").write_text("# journalisation modifiée\n")
    (copie / "tools/pipeline_mlflow.py").write_text("# autre outil modifié\n")
    with open(copie / "src/churn_saas/features/__init__.py", "a", encoding="utf-8") as f:
        f.write("\n# nouvelle figure exportée\n")
    assert suivi.empreinte_code("tools/selection_modele.py") == avant
    with open(copie / "src/churn_saas/modelisation/reglage.py", "a", encoding="utf-8") as f:
        f.write("\n# réglage modifié\n")
    assert suivi.empreinte_code("tools/selection_modele.py") != avant


# --- Identity from the import graph, model descriptor (03/10/2026) -----------------------------
@pytest.mark.phase9
def test_le_perimetre_d_un_outil_suit_ses_imports_reels():
    """Phase 5's computations never import the decision rule: adding it to evaluation/
    invalidated them anyway, under the package-level perimeter. The import graph tells."""
    from churn_saas.config import RACINE
    from churn_saas.packaging import fichiers_du_perimetre

    def perimetre(outil):
        return {f.relative_to(RACINE).as_posix() for f in fichiers_du_perimetre(outil)}

    phase5 = perimetre("tools/selection_variables.py")
    assert "src/churn_saas/evaluation/decision.py" not in phase5
    assert {
        "src/churn_saas/features/selection.py",
        "src/churn_saas/modelisation/validation.py",
        "src/churn_saas/config.py",
    } <= phase5
    assert "src/churn_saas/evaluation/decision.py" in perimetre("tools/regle_decision.py")
    # a tool loaded dynamically is followed: the decision rule uses the served model's tool
    assert "tools/modele_servi.py" in perimetre("tools/regle_decision.py")
    assert not any("packaging" in f for f in phase5)


@pytest.mark.phase9
def test_l_empreinte_d_un_outil_ignore_les_modules_qu_il_n_importe_pas(tmp_path, monkeypatch):
    import shutil

    import churn_saas.packaging.dependances as dependances
    import churn_saas.packaging.suivi as suivi
    from churn_saas.config import RACINE

    copie = tmp_path / "depot"
    shutil.copytree(RACINE / "src", copie / "src")
    shutil.copytree(RACINE / "tools", copie / "tools")
    monkeypatch.setattr(suivi, "RACINE", copie)
    monkeypatch.setattr(dependances, "RACINE", copie)
    monkeypatch.setattr(dependances, "PAQUET", copie / "src" / "churn_saas")
    avant = suivi.empreinte_code("tools/selection_variables.py")
    with open(copie / "src/churn_saas/evaluation/decision.py", "a", encoding="utf-8") as f:
        f.write("\n# règle de décision modifiée\n")
    assert suivi.empreinte_code("tools/selection_variables.py") == avant
    with open(copie / "src/churn_saas/modelisation/validation.py", "a", encoding="utf-8") as f:
        f.write("\n# validation modifiée\n")
    assert suivi.empreinte_code("tools/selection_variables.py") != avant
