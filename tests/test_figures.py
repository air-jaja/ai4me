"""Figure storage and its cache.

A cache that serves a stale image is worse than no cache: the reader sees a picture that no
longer matches the code or the data, and nothing says so. These tests pin the property that
prevents it - the key includes the source of the drawing function, so editing the plot
invalidates the stored image on its own.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from churn_saas.figures import (  # noqa: E402
    chemin_figure,
    cle_cache,
    enregistrer_figure,
    etat_cache,
    figure_en_cache,
    inventaire_figures,
)


def _tracer_simple():
    fig, ax = plt.subplots(figsize=(2, 1.5))
    ax.plot([1, 2, 3], [1, 4, 9])
    return fig


def _tracer_modifie():
    fig, ax = plt.subplots(figsize=(2, 1.5))
    ax.plot([1, 2, 3], [1, 4, 9], color="red")  # une seule ligne change
    return fig


# --- Paths ----------------------------------------------------------------------------
def test_le_chemin_se_deduit_du_nom(tmp_path):
    """No caller writes a path: a hardcoded one breaks when the tree moves."""
    assert chemin_figure("03_essai", "png", tmp_path) == tmp_path / "03_essai.png"
    assert chemin_figure("03_essai", "svg", tmp_path) == tmp_path / "03_essai.svg"


def test_la_figure_est_ecrite_dans_les_deux_formats(tmp_path):
    """PNG for documents and slides, SVG for anything that may be enlarged."""
    ecrits = enregistrer_figure(_tracer_simple(), "03_essai", "cle", tmp_path)
    assert {p.suffix for p in ecrits} == {".png", ".svg"}
    assert all(p.exists() and p.stat().st_size > 0 for p in ecrits)


# --- The cache key --------------------------------------------------------------------
def test_la_cle_depend_des_donnees():
    assert cle_cache("signature-a", _tracer_simple) != cle_cache("signature-b", _tracer_simple)


def test_la_cle_depend_du_code_de_trace():
    """This is the property that makes the cache safe.

    A key built on the data alone would keep serving an old image after the plotting code
    changed - exactly the situation a cache must never create. Hashing the source means a
    changed colour invalidates the stored figure, with nobody having to remember a version
    number.
    """
    assert cle_cache("signature", _tracer_simple) != cle_cache("signature", _tracer_modifie)


def test_la_cle_est_stable_a_donnees_et_code_identiques():
    assert cle_cache("signature", _tracer_simple) == cle_cache("signature", _tracer_simple)


# --- Cache state ----------------------------------------------------------------------
def test_une_figure_absente_doit_etre_tracee(tmp_path):
    obsolete, raison = etat_cache("03_essai", "cle", tmp_path)
    assert obsolete and raison == "figure absente"


def test_une_signature_illisible_force_le_trace(tmp_path):
    """A corrupted sidecar must not be read as agreement."""
    enregistrer_figure(_tracer_simple(), "03_essai", "cle", tmp_path)
    (tmp_path / "03_essai.signature.json").write_text("{ pas du json", encoding="utf-8")
    obsolete, raison = etat_cache("03_essai", "cle", tmp_path)
    assert obsolete and raison == "signature illisible"


def test_une_figure_supprimee_est_retracee_malgre_sa_signature(tmp_path):
    enregistrer_figure(_tracer_simple(), "03_essai", "cle", tmp_path)
    chemin_figure("03_essai", "png", tmp_path).unlink()
    obsolete, raison = etat_cache("03_essai", "cle", tmp_path)
    assert obsolete and raison == "figure absente"


def test_l_etat_du_cache_explique_sa_decision(tmp_path):
    """The reason is returned, not just a boolean: a cache that decides in silence is a
    cache nobody trusts, and the notebook prints the reason."""
    enregistrer_figure(_tracer_simple(), "03_essai", "cle", tmp_path)
    assert etat_cache("03_essai", "cle", tmp_path) == (False, "inchangée")
    assert etat_cache("03_essai", "autre", tmp_path)[1] == "données ou code de tracé modifiés"


# --- End to end -----------------------------------------------------------------------
def test_la_figure_n_est_tracee_qu_une_fois(tmp_path):
    """Two runs on unchanged data and code must not redraw anything."""
    _, premiere = figure_en_cache("03_essai", "signature", _tracer_simple, tmp_path)
    _, seconde = figure_en_cache("03_essai", "signature", _tracer_simple, tmp_path)
    assert premiere == "figure absente"
    assert seconde == "inchangée"


def test_un_changement_de_donnees_retrace_la_figure(tmp_path):
    figure_en_cache("03_essai", "signature-a", _tracer_simple, tmp_path)
    _, raison = figure_en_cache("03_essai", "signature-b", _tracer_simple, tmp_path)
    assert raison == "données ou code de tracé modifiés"


def test_un_changement_de_code_retrace_la_figure(tmp_path):
    """Editing the plot must change the stored image, without touching the data."""
    figure_en_cache("03_essai", "signature", _tracer_simple, tmp_path)
    _, raison = figure_en_cache("03_essai", "signature", _tracer_modifie, tmp_path)
    assert raison == "données ou code de tracé modifiés"


def test_la_figure_rendue_est_bien_celle_du_dernier_trace(tmp_path):
    """Beyond the reason reported, the file on disk must have changed."""
    chemin, _ = figure_en_cache("03_essai", "signature", _tracer_simple, tmp_path)
    avant = chemin.read_bytes()
    figure_en_cache("03_essai", "signature", _tracer_modifie, tmp_path)
    assert chemin.read_bytes() != avant


# --- Inventory ------------------------------------------------------------------------
def test_l_inventaire_recense_les_figures_disponibles(tmp_path):
    figure_en_cache("03_une", "signature", _tracer_simple, tmp_path)
    figure_en_cache("01_autre", "signature", _tracer_simple, tmp_path)
    inventaire = inventaire_figures(tmp_path)
    assert set(inventaire["figure"]) == {"03_une", "01_autre"}
    assert set(inventaire["phase"]) == {"03", "01"}
    assert (inventaire["formats"] == "png, svg").all()


def test_l_inventaire_d_un_dossier_absent_reste_lisible(tmp_path):
    """An empty inventory is a table with no row, never an exception."""
    assert inventaire_figures(tmp_path / "inexistant").empty


def test_la_signature_enregistree_est_relisible(tmp_path):
    enregistrer_figure(_tracer_simple(), "03_essai", "cle-connue", tmp_path)
    contenu = json.loads((tmp_path / "03_essai.signature.json").read_text(encoding="utf-8"))
    assert contenu["cle"] == "cle-connue"
    assert contenu["nom"] == "03_essai"


@pytest.fixture(autouse=True)
def _fermer_les_figures():
    """Close every figure after each test: matplotlib keeps them open and warns at 20."""
    yield
    plt.close("all")
