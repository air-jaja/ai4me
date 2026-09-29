"""Activité 5 — artefacts et fiche modèle."""

from sklearn.dummy import DummyClassifier

from churn_saas.packaging.artefacts import FicheModele, charger_modele, sauvegarder_modele
from churn_saas.packaging.model_card import generer_model_card


def test_le_modele_et_sa_fiche_sont_enregistres_ensemble(tmp_path):
    modele = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    fiche = FicheModele(nom="churn_model", version="1.0", empreinte_donnees="churn_train_20260928")
    chemin = sauvegarder_modele(modele, fiche, dossier=tmp_path)
    assert chemin.exists()
    assert chemin.with_suffix(".json").exists()

    recharge, metadonnees = charger_modele(chemin)
    assert metadonnees["empreinte_donnees"] == "churn_train_20260928"
    assert recharge.predict([[0]]).shape == (1,)


def test_la_fiche_modele_est_remplie_depuis_le_contexte():
    carte = generer_model_card(
        {
            "model_id": "churn-saas-cisia",
            "model_summary": "Estimation du risque de résiliation.",
            "developers": "Haja RAKOTOVOALAVO PETERA",
        }
    )
    assert "churn-saas-cisia" in carte
    assert "Haja RAKOTOVOALAVO PETERA" in carte
    assert "{{" not in carte  # aucune variable de gabarit non substituée


def test_les_champs_absents_prennent_leur_valeur_par_defaut():
    carte = generer_model_card({"model_id": "x"})
    assert "[More Information Needed]" in carte
