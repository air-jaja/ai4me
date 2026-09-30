"""Activity 1 (step 2) - schema, quality audit, governance and data fingerprinting."""

from pathlib import Path

import pandas as pd
import pytest

from churn_saas.donnees.empreinte import (
    construire_manifeste,
    empreinte_donnees,
    verifier_manifeste,
)
from churn_saas.donnees.gouvernance import (
    comparer_stockage,
    exemples_anonymises,
    scanner_texte_libre,
    table_cycle_de_vie,
    table_sensibilite,
)
from churn_saas.donnees.schema import (
    ROLES_COLONNES,
    auditer_qualite,
    controler_jointure,
    decrire_schema,
)


# --- Schema -------------------------------------------------------------------------
def test_chaque_colonne_source_porte_un_role_documente():
    """An undocumented column is a column nobody decided what to do with."""
    brut = pd.DataFrame(columns=list(ROLES_COLONNES))
    schema = decrire_schema(brut)
    assert (schema["role"] != "non documenté").all()


def test_l_audit_qualite_detecte_les_doublons():
    """The quality audit must count duplicates, not merely mention them.

    A defect stated without its scope cannot be arbitrated by anyone."""
    brut = pd.DataFrame({"a": ["1", "1", "2"]})
    audit = auditer_qualite(brut)
    ligne = audit.loc[audit["défaut"] == "Doublons stricts"].iloc[0]
    assert "1 lignes" in ligne["portée"]


def test_la_jointure_normalisee_recupere_les_lignes_perdues():
    """Quantifies what normalisation buys, rather than asserting it helps."""
    gauche = pd.DataFrame({"plan": ["STARTER", "Pro", " business "]})
    droite = pd.DataFrame({"plan": ["starter", "pro", "business"]})
    controle = controler_jointure(gauche, droite)
    assert controle.iloc[0]["taux d'appariement"] == "0.0%"
    assert controle.iloc[1]["taux d'appariement"] == "100.0%"


# --- Governance ---------------------------------------------------------------------
def test_chaque_etape_du_cycle_de_vie_a_un_responsable():
    """A stage without an owner is a stage nobody performs."""
    cycle = table_cycle_de_vie()
    assert (cycle["Responsable"].str.len() > 0).all()
    assert len(cycle) >= 8


def test_le_cycle_de_vie_va_de_la_collecte_a_la_purge():
    """The lifecycle must be complete end to end.

    A lifecycle stopping before purge is the usual way personal data is kept for years
    without a legal basis."""
    cycle = table_cycle_de_vie()
    assert "Collecte" in cycle["Étape"].iloc[0]
    assert "Purge" in cycle["Étape"].iloc[-1]


def test_chaque_donnee_sensible_porte_un_traitement():
    """Identifying a sensitive column without stating its treatment protects nobody."""
    sensibilite = table_sensibilite()
    assert (sensibilite["Traitement retenu"].str.len() > 10).all()
    assert "commentaire_csm" in set(sensibilite["Colonne"])


def test_le_scan_detecte_les_donnees_personnelles():
    """The scan must actually find personal data patterns.

    Turns 'the field could contain personal data' from a comfortable, unverifiable claim
    into a measurement."""
    serie = pd.Series(
        [
            "Relance envoyée à jean.dupont@exemple.fr",
            "Appel au 06 12 34 56 78 sans réponse",
            "Compte satisfait, rien à signaler",
        ]
    )
    scan = scanner_texte_libre(serie)
    assert int(scan.loc[scan["Motif recherché"] == "adresse e-mail", "Occurrences"].iloc[0]) == 1
    assert (
        int(scan.loc[scan["Motif recherché"] == "numéro de téléphone", "Occurrences"].iloc[0]) == 1
    )


def test_les_exemples_affiches_sont_masques():
    """The demonstration must not commit the offence it describes."""
    serie = pd.Series(["Contact : jean.dupont@exemple.fr pour le renouvellement"])
    exemples = exemples_anonymises(serie)
    assert "jean.dupont@exemple.fr" not in exemples[0]
    assert "[masqué]" in exemples[0]


def test_la_comparaison_de_stockage_tranche_chaque_option():
    """Every storage option must carry a decision, not just a description.

    An option listed without a verdict is a comparison the jury will finish itself."""
    options = comparer_stockage()
    assert len(options) >= 6
    assert (options["Retenu"].str.len() > 0).all()


# --- Data fingerprinting ------------------------------------------------------------
def test_l_empreinte_ignore_l_ordre_des_lignes_et_des_colonnes():
    """Two exports of the same content must yield the same fingerprint."""
    a = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    b = a.iloc[::-1][["y", "x"]].reset_index(drop=True)
    assert empreinte_donnees(a) == empreinte_donnees(b)


def test_l_empreinte_change_si_une_valeur_change():
    """A single changed value must change the fingerprint.

    Without this property the manifest would certify datasets it never verified."""
    a = pd.DataFrame({"x": [1, 2, 3]})
    b = pd.DataFrame({"x": [1, 2, 4]})
    assert empreinte_donnees(a) != empreinte_donnees(b)


def test_le_manifeste_detecte_une_source_modifiee(tmp_path):
    """Run before any training: a changed source means the run reproduces nothing."""
    source = tmp_path / "donnees.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    manifeste = construire_manifeste({"source": source}, version_donnees="v1")
    assert bool(verifier_manifeste(manifeste)["conforme"].iloc[0])

    source.write_text("a,b\n1,3\n", encoding="utf-8")
    assert not bool(verifier_manifeste(manifeste)["conforme"].iloc[0])


def test_le_manifeste_signale_une_source_disparue(tmp_path):
    """A missing source must be reported, not silently ignored."""
    source = tmp_path / "donnees.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    manifeste = construire_manifeste({"source": source}, version_donnees="v1")
    source.unlink()
    controle = verifier_manifeste(manifeste)
    assert not bool(controle["présent"].iloc[0])
    assert not bool(controle["conforme"].iloc[0])


@pytest.mark.parametrize("fonction", [table_cycle_de_vie, table_sensibilite, comparer_stockage])
def test_les_tables_de_gouvernance_ne_sont_jamais_vides(fonction):
    """An empty governance table would silently remove a section from the notebook."""
    assert not fonction().empty


def test_le_manifeste_n_est_pas_reecrit_sans_raison(tmp_path):
    """Two runs on unchanged sources must leave the manifest byte-identical.

    Regenerating it each time would change `date_construction` and produce a diff on every
    commit for fingerprints that did not move. Noise of that kind trains readers to skip
    the file, and a manifest nobody reads certifies nothing.
    """
    from churn_saas.donnees.empreinte import manifeste_stable

    source = tmp_path / "donnees.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    chemin = tmp_path / "manifeste.json"

    _, reecrit = manifeste_stable({"source": source}, chemin, version_donnees="v1")
    assert reecrit, "Le premier appel doit écrire le manifeste"
    contenu = chemin.read_bytes()

    _, reecrit = manifeste_stable({"source": source}, chemin, version_donnees="v1")
    assert not reecrit
    assert chemin.read_bytes() == contenu


def test_le_manifeste_est_reecrit_si_une_source_change(tmp_path):
    """A changed source must force a rewrite: silence there would certify a lie."""
    from churn_saas.donnees.empreinte import manifeste_stable

    source = tmp_path / "donnees.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    chemin = tmp_path / "manifeste.json"
    manifeste_stable({"source": source}, chemin, version_donnees="v1")

    source.write_text("a,b\n1,3\n", encoding="utf-8")
    _, reecrit = manifeste_stable({"source": source}, chemin, version_donnees="v1")
    assert reecrit


# --- Public functions that had no coverage until the activity 1 review ---------------
def test_l_inventaire_decrit_chaque_colonne(tmp_path):
    """The "before" snapshot must cover every column, including the empty ones.

    Section 5 of the notebook compares this inventory to reference values. A column
    missing from it would silently escape the completeness check.
    """
    from churn_saas.donnees import inventaire

    df = pd.DataFrame({"a": ["1", None, "3"], "vide": [None, None, None]})
    resume = inventaire(df)
    assert list(resume.index) == ["a", "vide"]
    assert resume.loc["vide", "manquants_pct"] == 100.0
    assert resume.loc["vide", "exemple"] is None  # no example, and no exception either


def test_la_table_des_exclusions_expose_chaque_motif():
    """Every excluded column appears with its own rationale.

    The motives are not interchangeable: the grid separates ethics from technical
    preparation, so a single blanket justification would satisfy neither.
    """
    from churn_saas.donnees import MOTIFS_EXCLUSION, table_exclusions

    table = table_exclusions()
    assert len(table) == len(MOTIFS_EXCLUSION)
    assert set(table["colonne"]) == set(MOTIFS_EXCLUSION)
    assert table["motif d'exclusion"].str.len().min() > 15


def test_l_empreinte_de_fichier_depend_du_contenu(tmp_path):
    """Identical bytes give the same fingerprint, a single changed byte gives another."""
    from churn_saas.donnees import empreinte_fichier

    a, b, c = tmp_path / "a.csv", tmp_path / "b.csv", tmp_path / "c.csv"
    a.write_text("x,y\n1,2\n", encoding="utf-8")
    b.write_text("x,y\n1,2\n", encoding="utf-8")
    c.write_text("x,y\n1,3\n", encoding="utf-8")
    assert empreinte_fichier(a) == empreinte_fichier(b)
    assert empreinte_fichier(a) != empreinte_fichier(c)


def test_l_empreinte_de_fichier_lit_par_blocs(tmp_path):
    """Block reading must give the same result as reading the file whole.

    The block size bounds memory use on a large snapshot; a wrong implementation would
    only show up on files too big to notice during development.
    """
    import hashlib

    from churn_saas.donnees import empreinte_fichier

    fichier = tmp_path / "gros.csv"
    fichier.write_bytes(b"ligne\n" * 50_000)
    attendu = hashlib.sha256(fichier.read_bytes()).hexdigest()
    assert empreinte_fichier(fichier, taille_bloc=512) == attendu


def test_le_manifeste_se_relit_a_l_identique(tmp_path):
    """Writing then reading a manifest must return the same content.

    The manifest is the contract between a data version and a model. A round-trip that
    loses a field would make the contract unverifiable without saying so.
    """
    from churn_saas.donnees import charger_manifeste, construire_manifeste, ecrire_manifeste

    source = tmp_path / "donnees.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    manifeste = construire_manifeste({"source": source}, version_donnees="v1", commentaire="essai")

    chemin = ecrire_manifeste(manifeste, tmp_path / "manifeste.json")
    assert charger_manifeste(chemin) == manifeste


def test_le_manifeste_enregistre_des_chemins_relatifs(tmp_path, monkeypatch):
    """Paths are stored relative to the repository root, never absolute.

    An absolute path ties the manifest to the machine that wrote it. Regenerated on a
    workstation and committed, it can no longer be verified anywhere else - CI included,
    where every source would be reported as missing. The check would then fail for a
    reason unrelated to the data it is meant to protect.
    """
    from churn_saas.donnees import construire_manifeste

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    dossier = tmp_path / "data" / "raw"
    dossier.mkdir(parents=True)
    source = dossier / "donnees.csv"
    source.write_text("a\n1\n", encoding="utf-8")

    manifeste = construire_manifeste({"source": source}, version_donnees="v1", racine=tmp_path)
    chemin = manifeste["fichiers"]["source"]["chemin"]
    assert chemin == "data/raw/donnees.csv"
    assert not Path(chemin).is_absolute()


def test_le_manifeste_relatif_se_verifie_depuis_une_autre_racine(tmp_path):
    """A relative manifest verifies wherever the repository is cloned."""
    from churn_saas.donnees import construire_manifeste, verifier_manifeste

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    dossier = tmp_path / "data"
    dossier.mkdir()
    source = dossier / "donnees.csv"
    source.write_text("a\n1\n", encoding="utf-8")

    manifeste = construire_manifeste({"source": source}, version_donnees="v1", racine=tmp_path)
    assert bool(verifier_manifeste(manifeste, racine=tmp_path)["conforme"].all())
