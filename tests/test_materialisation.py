"""Writing the derived datasets, and the contract that makes them trustworthy.

A snapshot nobody verifies is a file, not a reference. What matters here is less that the
Parquet is written than that its fingerprint is recorded, checked on reload, and that a
drift is reported instead of being absorbed silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from churn_saas.donnees import charger_manifeste, empreinte_donnees
from churn_saas.features import (
    charger_jeu_derive,
    executer_pipeline,
    materialiser,
    table_materialisation,
    verifier_jeux_derives,
    version_code,
)

RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "data" / "raw"


@pytest.fixture(scope="module")
def resultat():
    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    return executer_pipeline(fichier, DONNEES / "catalogue_plans.csv")


@pytest.fixture
def materialise(resultat, tmp_path):
    """Materialise into a temporary directory, never over the repository's snapshots."""
    manifeste = materialiser(
        resultat,
        version_donnees="test",
        dossier=tmp_path / "processed",
        chemin_manifeste=tmp_path / "manifeste.json",
        date="20260101",
    )
    return manifeste, tmp_path


# --- What is written ------------------------------------------------------------------
def test_silver_et_gold_sont_ecrits_en_parquet(materialise):
    """Parquet rather than CSV: types survive the round trip.

    Reparsing decimals and dates on reload would undo the whole preparation step - the
    very defects phase 2 spent its time fixing.
    """
    _, racine = materialise
    fichiers = sorted(p.name for p in (racine / "processed").glob("*.parquet"))
    assert fichiers == ["gold_test_20260101.parquet", "silver_test_20260101.parquet"]


def test_le_bronze_n_est_pas_reecrit(materialise):
    """Bronze already exists under `data/raw/`, versioned in Git.

    Writing a second copy would create a file that can drift from the one the manifest
    fingerprints - two references instead of one.
    """
    _, racine = materialise
    assert not list((racine / "processed").glob("bronze*"))


def test_le_nom_du_fichier_porte_sa_version_et_sa_date(materialise):
    """A snapshot that cannot be dated cannot be matched to a model."""
    manifeste, _ = materialise
    for nom in ("silver", "gold"):
        chemin = manifeste["jeux_derives"]["jeux"][nom]["chemin"]
        assert "test" in chemin and "20260101" in chemin


# --- What is recorded -----------------------------------------------------------------
def test_le_manifeste_enregistre_l_empreinte_du_contenu(materialise, resultat):
    """The fingerprint is computed on the content, not on the file.

    Two Parquet writes of the same rows can differ byte for byte - compression, metadata -
    while describing the same data. Fingerprinting the content is what makes the check
    meaningful.
    """
    manifeste, _ = materialise
    assert manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"] == empreinte_donnees(
        resultat.gold
    )


def test_le_manifeste_enregistre_la_version_du_code(materialise):
    """Code, data and model are versioned together, or reproducibility is a claim.

    A snapshot without the commit that produced it cannot be recomputed: the cleaning rules
    may have changed since.
    """
    manifeste, _ = materialise
    version = manifeste["jeux_derives"]["jeux"]["gold"]["version_code"]
    assert version and version == version_code()


def test_le_manifeste_conserve_les_sources(materialise):
    """Adding the derived datasets must not drop the source section."""
    manifeste, _ = materialise
    assert "fichiers" in manifeste
    assert manifeste["version_donnees"] == "test"


def test_le_manifeste_se_relit_depuis_le_disque(materialise):
    manifeste, racine = materialise
    assert charger_manifeste(racine / "manifeste.json") == manifeste


# --- What is verified -----------------------------------------------------------------
def test_le_controle_confirme_un_instantane_intact(materialise, resultat):
    manifeste, _ = materialise
    assert bool(verifier_jeux_derives(resultat, manifeste)["conforme"].all())


def test_le_controle_detecte_un_jeu_qui_a_derive(materialise, resultat):
    """A changed pipeline must be reported, not absorbed.

    The run would otherwise produce a model whose card describes data it was not trained
    on - and no metric reports that.
    """
    manifeste, _ = materialise
    manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"] = "0" * 64
    controle = verifier_jeux_derives(resultat, manifeste)
    assert not bool(controle.loc[controle["jeu"] == "gold", "conforme"].iloc[0])


def test_le_controle_detecte_un_fichier_disparu(materialise, resultat):
    manifeste, racine = materialise
    (racine / "processed" / "gold_test_20260101.parquet").unlink()
    controle = verifier_jeux_derives(resultat, manifeste)
    assert not bool(controle.loc[controle["jeu"] == "gold", "fichier présent"].iloc[0])


# --- What is reloaded -----------------------------------------------------------------
def test_le_jeu_relu_est_identique_a_celui_ecrit(materialise, resultat, monkeypatch):
    """The round trip preserves content and types, which is the point of Parquet."""
    manifeste, racine = materialise
    monkeypatch.setattr("churn_saas.features.materialisation.racine_projet", lambda *a, **k: racine)
    relu = charger_jeu_derive(manifeste, "gold")
    assert empreinte_donnees(relu) == empreinte_donnees(resultat.gold)
    assert list(relu.dtypes.astype(str)) == list(resultat.gold.dtypes.astype(str))


def test_relire_un_instantane_modifie_leve_une_erreur(materialise):
    """Loading a snapshot without checking it defeats its purpose.

    The error names both fingerprints: a message saying only "mismatch" leaves the reader
    unable to tell which side moved.
    """
    manifeste, _ = materialise
    manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"] = "0" * 64
    with pytest.raises(ValueError, match="ne correspond pas au manifeste"):
        charger_jeu_derive(manifeste, "gold")


def test_le_controle_peut_etre_leve_explicitement(materialise, resultat, monkeypatch):
    """Inspecting a snapshot known to have drifted stays possible, but never by default."""
    manifeste, racine = materialise
    monkeypatch.setattr("churn_saas.features.materialisation.racine_projet", lambda *a, **k: racine)
    manifeste["jeux_derives"]["jeux"]["gold"]["empreinte_contenu"] = "0" * 64
    assert isinstance(charger_jeu_derive(manifeste, "gold", controler=False), pd.DataFrame)


# --- What is displayed ----------------------------------------------------------------
def test_la_table_de_materialisation_est_lisible(materialise):
    manifeste, _ = materialise
    table = table_materialisation(manifeste)
    assert set(table["Jeu"]) == {"silver", "gold"}
    assert (table["Empreinte du contenu"].str.len() > 10).all()


def test_l_outil_de_materialisation_ecrit_un_manifeste_conforme(tmp_path):
    """`make materialiser` refreshes the manifest without Jupyter, and checks what it wrote.

    The phase 3 notebook used to be the only way to refresh it; when Jupyter failed (the
    orjson episode of 02/10), the manifest could not follow the code.
    """
    import subprocess
    import sys

    racine = Path(__file__).resolve().parents[1]
    if (racine / "data" / "raw" / "churn_saas_complet.csv").stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")
    manifeste = tmp_path / "manifeste.json"
    manifeste.write_text(
        (racine / "data" / "manifeste_v1.0.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    sortie = subprocess.run(
        [
            sys.executable,
            str(racine / "tools" / "materialiser.py"),
            "--manifeste",
            str(manifeste),
            "--dossier",
            str(tmp_path / "processed"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=racine,
    )
    assert sortie.returncode == 0, sortie.stdout + sortie.stderr
    assert "Manifeste conforme au code." in sortie.stdout
    assert "decoupage" in json.loads(manifeste.read_text(encoding="utf-8"))
