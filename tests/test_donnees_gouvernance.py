"""Activity 1 (step 2) - schema, quality audit, governance and data fingerprinting."""

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
