"""Activity 5 - artefacts and model card."""

import pytest
from sklearn.dummy import DummyClassifier

from churn_saas.packaging.artefacts import FicheModele, charger_modele, sauvegarder_modele
from churn_saas.packaging.model_card import generer_model_card


def test_le_modele_et_sa_fiche_sont_enregistres_ensemble(tmp_path):
    """A model must never be written without its card.

    A model shipped alone is an orphan artefact: nobody knows what data it learned from,
    nor what it cannot do."""
    modele = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    fiche = FicheModele(nom="churn_model", version="1.0", empreinte_donnees="churn_train_20260928")
    import pandas as pd

    X, y = pd.DataFrame({"a": [0, 1]}), [0, 1]
    chemin = sauvegarder_modele(
        modele, fiche, dossier=tmp_path, entrainement=(X, y), registre=tmp_path / "registre.json"
    )
    assert chemin.exists()
    assert chemin.with_suffix(".json").exists()

    recharge, metadonnees = charger_modele(chemin)
    assert metadonnees["empreinte_donnees"] == "churn_train_20260928"
    assert recharge.predict([[0]]).shape == (1,)


def test_la_fiche_modele_est_remplie_depuis_le_contexte():
    """The card must be generated from training metadata, not hand-written.

    Generation is what prevents the card and the artefact from drifting apart."""
    carte = generer_model_card(
        {
            "model_id": "churn-saas-cisia",
            "model_summary": "Estimation du risque de résiliation.",
            "developers": "Haja RAKOTOVOALAVO PETERA",
        }
    )
    assert "churn-saas-cisia" in carte
    assert "Haja RAKOTOVOALAVO PETERA" in carte
    assert "{{" not in carte  # no unsubstituted template variable left


def test_les_champs_absents_prennent_leur_valeur_par_defaut():
    """A missing field must fall back to the template default, never to an empty slot.

    An unsubstituted placeholder shipped to a jury reads as an unfinished deliverable."""
    carte = generer_model_card({"model_id": "x"})
    assert "[More Information Needed]" in carte


@pytest.mark.phase9
def test_le_descriptif_est_lu_sur_l_objet_et_ecrit_dans_la_fiche(tmp_path):
    """What a card says about its model comes from the model: family, exact class,
    calibration and copies - for a calibrated regression as served in phase 8."""
    import json

    import numpy as np
    import pandas as pd

    from churn_saas.modelisation import construire_baseline, construire_calibre, construire_candidat
    from churn_saas.packaging import FicheModele, charger_modele, decrire_modele, sauvegarder_modele

    X = pd.DataFrame({"a": np.linspace(0, 1, 120), "b": ["x", "y", "z"] * 40})
    y = pd.Series([0, 1] * 60)
    calibre = construire_calibre(construire_baseline, "sigmoid")(X).fit(X, y)
    descriptif = decrire_modele(calibre)
    assert descriptif["famille"] == "regression_logistique"
    assert descriptif["estimateur"] == "sklearn.linear_model.LogisticRegression"
    assert (descriptif["calibration"], descriptif["copies"]) == ("sigmoid", 5)
    assert decrire_modele(construire_candidat(X))["famille"] == "foret_aleatoire"

    chemin = sauvegarder_modele(
        calibre,
        FicheModele(nom="essai", version="0.1"),
        tmp_path,
        entrainement=(X, y),
        registre=None,
    )
    fiche = json.loads(chemin.with_suffix(".json").read_text(encoding="utf-8"))
    recharge, _ = charger_modele(chemin)
    assert fiche["descriptif"]["famille"] == decrire_modele(recharge)["famille"]


@pytest.mark.phase10
def test_un_modele_ne_s_enregistre_pas_sans_sa_carte_d_identite(tmp_path):
    """Training rows are mandatory; the card holds the file's hash, the rows' fingerprint
    and the input contract; the registry keeps one line per model file."""
    import hashlib
    import json

    import pandas as pd

    modele = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    fiche = FicheModele(nom="essai", version="1.0.0")
    with pytest.raises(TypeError):
        sauvegarder_modele(modele, fiche, dossier=tmp_path)  # no training rows: refused
    X, y = pd.DataFrame({"a": [0.0, 1.0]}, index=[10, 11]), [0, 1]
    registre = tmp_path / "registre.json"
    chemin = sauvegarder_modele(
        modele,
        fiche,
        dossier=tmp_path,
        entrainement=(X, y),
        lignage={"commit": "abc1234"},
        registre=registre,
    )
    carte = json.loads(chemin.with_suffix(".json").read_text(encoding="utf-8"))
    assert carte["fichier_sha256"] == hashlib.sha256(chemin.read_bytes()).hexdigest()
    assert carte["entrainement"]["comptes"] == 2
    assert carte["entrainement"]["contrat_entree"] == [{"colonne": "a", "type": "float64"}]
    sauvegarder_modele(modele, fiche, dossier=tmp_path, entrainement=(X, y), registre=registre)
    assert len(json.loads(registre.read_text(encoding="utf-8"))) == 1  # same file: one line
