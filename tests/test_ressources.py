"""Compute resources: a project input, measured on the laptop, rendered and checked here.

`config/ressources_poste.toml` describes the machine that runs the project and the energy
hypotheses applied to it. These tests protect what would rot quietly: a hypothesis without
its source, a measurement missing from the file, a rendered document lagging behind its
input, a machine description that silently comes back empty.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ENTREE = RACINE / "config" / "ressources_poste.toml"
DOCUMENT = RACINE / "docs" / "06.SOBRIETE_calcul.md"
OUTIL = RACINE / "tools" / "ressources_calcul.py"


def _entree() -> dict:
    with open(ENTREE, "rb") as flux:
        return tomllib.load(flux)


def _outil():
    """The tool as a module, loaded from its path: it lives outside the package."""
    specification = importlib.util.spec_from_file_location("ressources_calcul", OUTIL)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_l_entree_porte_toutes_les_sections():
    entree = _entree()
    assert {"source", "poste", "mesures", "hypotheses"} <= set(entree)
    assert {"origine", "date"} <= set(entree["source"])


def test_chaque_hypothese_cite_sa_source():
    """A power or a carbon intensity without its source is an assertion, not an input."""
    h = _entree()["hypotheses"]
    assert h["source_puissance"].strip() and h["source_intensite"].strip()
    assert 0 < h["puissance_basse_w"] <= h["puissance_haute_w"]
    assert h["intensite_carbone_g_kwh"] > 0 and h["executions_developpement"] >= 1


def test_chaque_mesure_attendue_est_presente_et_positive():
    mesures = _entree()["mesures"]
    attendues = {
        "entrainement_lr_s",
        "entrainement_foret_s",
        "scoring_portefeuille_s",
        "importance_lr_s",
        "importance_foret_s",
        "lignes_entrainement",
        "memoire_pic_processus_mo",
    }
    assert attendues <= set(mesures)
    assert all(mesures[c] > 0 for c in attendues)


def test_le_poste_est_decrit():
    poste = _entree()["poste"]
    assert poste["processeur"].strip() and poste["coeurs_logiques"] >= 1
    assert poste["memoire_go"] > 0


def test_la_description_du_poste_fonctionne_sur_ce_systeme():
    """Each system has its own source; on the one running the suite, none may come back empty."""
    poste = _outil().collecter_poste()
    assert poste["processeur"] not in ("", "inconnu")
    assert poste["coeurs_logiques"] >= 1 and poste["memoire_go"] > 0


def test_le_document_de_sobriete_est_a_jour(tmp_path):
    """The document matches its input - otherwise it states a footprint nobody measured."""
    sortie = tmp_path / "sobriete.md"
    subprocess.run([sys.executable, str(OUTIL), "--sortie", str(sortie)], check=True, cwd=RACINE)
    assert sortie.read_text(encoding="utf-8") == DOCUMENT.read_text(encoding="utf-8"), (
        "docs/06.SOBRIETE_calcul.md est obsolète : lancer `make sobriete-doc`."
    )


def test_des_mesures_provisoires_sont_signalees_comme_telles():
    """Measures not taken on the development laptop must say so at the top of the document."""
    entree = _entree()
    contenu = DOCUMENT.read_text(encoding="utf-8")
    provisoire = entree["source"]["origine"] != _outil().ORIGINE_POSTE
    assert ("Mesures provisoires" in contenu) == provisoire


def test_l_ecriture_preserve_les_hypotheses_declarees(tmp_path):
    """Re-measuring the machine must never overwrite what a person declared."""
    outil = _outil()
    entree = _entree()
    copie = tmp_path / "ressources.toml"
    outil.ecrire_entree(entree, copie)
    with open(copie, "rb") as flux:
        relu = tomllib.load(flux)
    assert relu["hypotheses"] == entree["hypotheses"]
    assert relu["mesures"] == entree["mesures"]
