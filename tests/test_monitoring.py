"""Activity 7 - drift detection and alert rules."""

import numpy as np
import pandas as pd
import pytest

from churn_saas.monitoring.alertes import evaluer_alertes, table_regles
from churn_saas.monitoring.derive import ks_deux_echantillons, psi, rapport_derive


def test_psi_nul_sur_distributions_identiques():
    """Identical distributions must score near zero.

    A drift indicator raising alerts on stable data would be switched off within a month."""
    serie = pd.Series(np.random.default_rng(0).normal(size=5_000))
    assert psi(serie, serie) < 0.01


def test_psi_detecte_un_decalage_franc():
    """A clear distribution shift must cross the alert threshold."""
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(0, size=5_000)), pd.Series(rng.normal(2, size=5_000))) > 0.25


def test_ks_coherent_avec_le_psi():
    """The Kolmogorov-Smirnov test must agree with PSI on obvious cases.

    The two indicators are read together: a disagreement on a clear-cut case would mean one
    of them is misconfigured."""
    rng = np.random.default_rng(1)
    _, p_identique = ks_deux_echantillons(
        pd.Series(rng.normal(size=2_000)), pd.Series(rng.normal(size=2_000))
    )
    _, p_decale = ks_deux_echantillons(
        pd.Series(rng.normal(0, size=2_000)), pd.Series(rng.normal(2, size=2_000))
    )
    assert p_identique > 0.01
    assert p_decale < 0.01


def test_rapport_derive_marque_les_alertes():
    """The drift report must flag the drifting variable and only that one."""
    rng = np.random.default_rng(2)
    ref = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(size=2_000)})
    cur = pd.DataFrame({"a": rng.normal(size=2_000), "b": rng.normal(3, size=2_000)})
    rapport = rapport_derive(ref, cur, ["a", "b"])
    assert bool(rapport.loc[rapport["variable"] == "b", "alerte"].iloc[0]) is True


@pytest.mark.phase11
def test_chaque_regle_porte_une_action_et_un_responsable():
    """No rule may exist without a triggered action and a named owner.

    A dashboard with no action owner produces no decision - it produces meetings."""
    regles = table_regles()
    assert (regles["action"].str.len() > 0).all()
    assert (regles["responsable"].str.len() > 0).all()


@pytest.mark.phase11
def test_alerte_declenchee_expose_son_action():
    """A triggered alert must surface what to do and who does it."""
    resultat = evaluer_alertes({"Dérive des entrées et du score (PSI)": True})
    ligne = resultat.loc[resultat["indicateur"] == "Dérive des entrées et du score (PSI)"].iloc[0]
    assert ligne["declenchee"]
    assert ligne["responsable"] != "—"


# --- Phase 11 · Defaults validated before any implementation ----------------------------
@pytest.mark.phase11
def test_les_valeurs_par_defaut_de_la_phase_11_sont_figees():
    """M1 to M9, validated by the project owner on 04/10/2026 (rule 8): changing one is a new
    decision, committed alone - not an edit slipped into an implementation commit."""
    from churn_saas.monitoring import alertes

    assert alertes.CIBLE_COUVERTURE_REVENU == 0.50
    assert alertes.FREQUENCE_REENTRAINEMENT_MOIS == 3
    assert alertes.FENETRE_REENTRAINEMENT_MOIS == 12
    assert (alertes.SEUIL_PSI_VARIABLE_CLE, alertes.SEUIL_PSI_MODERE) == (0.25, 0.10)
    assert (alertes.NB_VARIABLES_PSI_MODERE, alertes.SEUIL_PSI_SCORE) == (3, 0.10)
    assert alertes.FACTEUR_MANQUANTS == 2.0
    assert alertes.ECART_VOLUME_SIGNALES == 0.30
    assert alertes.SEGMENTS_SURVEILLES == (("pays", "Suisse"),)


@pytest.mark.phase11
def test_le_tableau_des_regles_reprend_les_valeurs_validees():
    """The rule table is what people read; the constants are what the code will use. Each
    validated value must appear in its rule, so the two cannot tell different stories."""
    from churn_saas.monitoring import alertes

    seuils = dict(zip(table_regles()["indicateur"], table_regles()["seuil"], strict=True))
    assert (
        f"{alertes.CIBLE_COUVERTURE_REVENU:.0%}".replace("%", " %")
        in seuils["Couverture du revenu à risque"]
    )
    derive = seuils["Dérive des entrées et du score (PSI)"]
    assert "0,25" in derive and derive.count("0,10") == 2 and "trois" in derive
    assert f"{alertes.FACTEUR_MANQUANTS:.0f} ×" in seuils["Taux de manquants à l'entrée"]
    assert (
        f"{alertes.ECART_VOLUME_SIGNALES:.0%}".replace("%", " %")
        in seuils["Volume de comptes signalés"]
    )
    assert "Rappel sur le segment Suisse" in seuils


@pytest.mark.phase11
def test_les_variables_cles_sont_les_quatre_premieres_de_la_phase_9():
    """M5 names the key variables after the recorded permutation importance (R10), so the
    list cannot silently drift from the result it claims to follow."""
    import json
    from pathlib import Path

    from churn_saas.monitoring import alertes

    restitution = json.loads(
        (Path(__file__).resolve().parents[1] / "resultats" / "restitution_test.json").read_text(
            encoding="utf-8"
        )
    )
    premieres = tuple(i["variable"] for i in restitution["importance_permutation"][:4])
    assert alertes.VARIABLES_CLES == premieres


@pytest.mark.phase11
def test_les_donnees_de_demonstration_sont_figees():
    """S1 to S7, validated by the project owner on 04/10/2026 before any simulation (rule 8):
    the simulated batches cannot be resized or re-drifted without a new decision."""
    from churn_saas import config
    from churn_saas.monitoring import simulation

    assert simulation.TAILLE_LOT_SIMULE == 5_000
    assert simulation.GRAINE_SIMULATION == config.GRAINE == 42
    assert simulation.MOIS_SIMULES == ("mois_1_sans_derive", "mois_2_avec_derive")
    assert simulation.DERIVE_CONNEXION == {
        "variable": "derniere_connexion_jours",
        "part": 0.30,
        "facteur": 2.0,
    }
    assert simulation.DERIVE_MANQUANTS == {"variable": "delai_reponse_support_h", "part": 0.25}
    assert simulation.REDUCTION_RISQUE_CONTACT == config.EFFICACITE_RETENTION
    assert simulation.PART_TEMOIN_SIMULE == 0.10
    assert simulation.DOSSIER_SIMULATION == config.RACINE / "data" / "simulation"
    assert simulation.MENTION == "SIMULÉ — démonstration"


# --- Phase 11 · Reference profile (A1) -----------------------------------------------------
@pytest.mark.phase11
def test_le_psi_lu_sur_le_profil_est_celui_des_donnees():
    """The profile replaces the training rows: read from it - after a JSON round trip, as the
    service reads it - the PSI must be the one computed on the rows themselves."""
    import json

    from churn_saas.monitoring import profil_variable, psi_categoriel, psi_contre_profil

    rng = np.random.default_rng(11)
    reference = pd.Series(rng.normal(size=3_000))
    courant = pd.Series(rng.normal(0.4, size=2_000))
    courant[:150] = np.nan
    profil = json.loads(json.dumps(profil_variable(reference)))
    assert psi_contre_profil(profil, courant) == pytest.approx(psi(reference, courant), abs=1e-12)

    reference = pd.Series(["a"] * 600 + ["b"] * 300 + [None] * 100)
    courant = pd.Series(["a"] * 300 + ["b"] * 500 + ["c"] * 200)
    profil = json.loads(json.dumps(profil_variable(reference)))
    assert psi_contre_profil(profil, courant) == pytest.approx(
        psi_categoriel(reference, courant), abs=1e-12
    )


@pytest.fixture(scope="module")
def profil_enregistre():
    import json
    from pathlib import Path

    chemin = Path(__file__).resolve().parents[1] / "resultats" / "profil_reference.json"
    return json.loads(chemin.read_text(encoding="utf-8"))


@pytest.mark.phase11
def test_le_profil_de_reference_appartient_au_champion(profil_enregistre):
    """Section 13: a reference left behind by a retraining compares the present to an old
    state. The profile names its model; a new champion without a new profile fails here."""
    from pathlib import Path

    from churn_saas.packaging import lire_aliases

    champion = lire_aliases(
        Path(__file__).resolve().parents[1] / "resultats" / "aliases_modeles.json"
    )["champion"]
    assert profil_enregistre["modele"]["fichier_sha256"] == champion["fichier_sha256"]


@pytest.mark.phase11
def test_le_profil_de_reference_decrit_la_partie_d_entrainement(profil_enregistre):
    """Every model variable, as the training part holds it - recomputed now from the
    manifest's data and the frozen split; missing shares as received (M8)."""
    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.monitoring import profil_variable
    from churn_saas.monitoring.alertes import VARIABLES_CLES

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    X = parties_du_decoupage(resultat).X_entrainement
    assert profil_enregistre["comptes"] == len(X)
    assert set(VARIABLES_CLES) <= set(profil_enregistre["variables"]) == set(X.columns)
    for colonne in X.columns:
        assert profil_enregistre["variables"][colonne] == profil_variable(X[colonne]), colonne
    recus = resultat.silver.loc[X.index]
    for colonne, part in profil_enregistre["manquants_a_l_entree"].items():
        assert part == pytest.approx(recus[colonne].isna().mean(), abs=1e-6), colonne


# --- Phase 11 · Monthly verdicts (A2-A4) ------------------------------------------------
def _profil_synthetique():
    from churn_saas.monitoring import profil_variable

    rng = np.random.default_rng(5)
    reference = pd.DataFrame({f"v{i}": rng.normal(size=4_000) for i in range(6)})
    reference.loc[:399, "v5"] = np.nan  # 10 % missing in training
    score = pd.Series(rng.uniform(size=4_000))
    profil = {
        "variables_cles": ["v0", "v1"],
        "variables": {c: profil_variable(reference[c]) for c in reference},
        "score": profil_variable(score),
        "manquants_a_l_entree": {c: float(reference[c].isna().mean()) for c in reference},
    }
    return profil, reference, score


@pytest.mark.phase11
def test_la_derive_combinee_suit_ses_trois_conditions():
    """M5: silent on a stable batch; triggered by one key variable over 0.25, by three
    variables over 0.10, or by the score over 0.10 - and by nothing weaker."""
    from churn_saas.monitoring import derive_combinee

    profil, reference, score = _profil_synthetique()
    rng = np.random.default_rng(6)
    stable = pd.DataFrame({c: rng.normal(size=5_000) for c in reference})
    score_stable = pd.Series(rng.uniform(size=5_000))
    assert not derive_combinee(profil, stable, score_stable)[1]["déclenchée"]

    cle = stable.assign(v0=stable["v0"] + 1.5)
    assert derive_combinee(profil, cle, score_stable)[1]["variables clés au-dessus de 0,25"] == [
        "v0"
    ]
    une_seule = stable.assign(v2=stable["v2"] + 0.45)
    verdict = derive_combinee(profil, une_seule, score_stable)[1]
    assert verdict["variables au-dessus de 0,10"] == ["v2"] and not verdict["déclenchée"]
    trois = stable.assign(**{c: stable[c] + 0.45 for c in ("v2", "v3", "v4")})
    assert derive_combinee(profil, trois, score_stable)[1]["déclenchée"]
    score_decale = pd.Series(rng.uniform(0.3, 1.0, size=5_000))
    verdict = derive_combinee(profil, stable, score_decale)[1]
    assert verdict["psi du score"] > 0.10 and verdict["déclenchée"]


@pytest.mark.phase11
def test_les_manquants_sont_juges_contre_le_double_de_l_entrainement():
    """M8: 10 % in training tolerates up to 20 %; a variable never missing alerts at once."""
    from churn_saas.monitoring import manquants_relatifs

    profil, reference, _ = _profil_synthetique()
    lot = reference.copy()
    lot.loc[:599, "v5"] = np.nan  # 15 %: under twice 10 %
    assert not manquants_relatifs(profil, lot)[1]["déclenchée"]
    lot.loc[:899, "v5"] = np.nan  # 22.5 %: over
    assert manquants_relatifs(profil, lot)[1]["variables en alerte"] == ["v5"]
    lot = reference.copy()
    lot.loc[0, "v1"] = np.nan  # one missing value where there never was any
    assert manquants_relatifs(profil, lot)[1]["variables en alerte"] == ["v1"]


@pytest.mark.phase11
def test_le_volume_de_comptes_signales_compare_au_mois_precedent():
    """M9: over 30 % either way triggers; no previous month, no verdict."""
    from churn_saas.monitoring import ecart_volume

    assert not ecart_volume(140, 140)["déclenchée"]
    assert not ecart_volume(110, 140)["déclenchée"]
    assert ecart_volume(90, 140)["déclenchée"]
    assert ecart_volume(190, 140)["déclenchée"]
    assert ecart_volume(140, None) == {
        "comptes signalés": 140,
        "mois précédent": None,
        "écart": None,
        "déclenchée": False,
    }


@pytest.mark.phase11
def test_les_verdicts_du_mois_designent_des_regles_existantes():
    """A verdict whose indicator no rule carries would trigger nothing, silently."""
    from churn_saas.monitoring import mesures_du_mois

    mesures = mesures_du_mois({"déclenchée": True}, {"déclenchée": False}, {"déclenchée": True})
    resultat = evaluer_alertes(mesures)
    declenchees = set(resultat.loc[resultat["declenchee"], "indicateur"])
    assert set(mesures) <= set(table_regles()["indicateur"])
    assert declenchees == {k for k, v in mesures.items() if v}


# --- Phase 5 · Categorical stability ------------------------------------------------------
@pytest.mark.phase5
def test_le_psi_categoriel_est_nul_sans_changement_et_positif_sinon():
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a"] * 50 + ["b"] * 50)
    assert psi_categoriel(reference, reference) == pytest.approx(0, abs=1e-9)
    assert psi_categoriel(reference, pd.Series(["a"] * 90 + ["b"] * 10)) > 0.25


@pytest.mark.phase5
def test_une_hausse_des_manquants_categoriels_est_une_derive():
    """Missing values form their own category: more of them is a drift."""
    from churn_saas.monitoring import psi_categoriel

    reference = pd.Series(["a", "b"] * 50)
    courant = pd.Series(["a", "b"] * 25 + [None] * 50)
    assert psi_categoriel(reference, courant) > 0.25


@pytest.mark.phase5
def test_une_derive_categorielle_declenche_une_alerte():
    """A sector mix moving from 50/50 to 95/5 must raise an alert.

    Until phase 5 the numeric index was applied to every column: on text it returned NaN,
    and NaN compared to the threshold gave "no alert". The largest possible drift on a
    categorical variable was reported as none, without any error.
    """
    from churn_saas.monitoring import rapport_derive

    reference = pd.DataFrame({"x": range(100), "c": ["a", "b"] * 50})
    courant = pd.DataFrame({"x": range(100), "c": ["a"] * 95 + ["b"] * 5})
    rapport = rapport_derive(reference, courant, ["x", "c"]).set_index("variable")
    assert rapport.loc["c", "alerte"] and not pd.isna(rapport.loc["c", "psi"])
    assert not rapport.loc["x", "alerte"]
