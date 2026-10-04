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
    """S1 to S8, validated by the project owner on 04/10/2026 before any simulation (rule 8):
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
    # S8, decided after month 2 left M5 silent - month 2 itself unchanged.
    assert simulation.MOIS_DERIVE_FORTE == "mois_3_derive_forte"
    assert simulation.DERIVE_CONNEXION_FORTE == {
        "variable": "derniere_connexion_jours",
        "part": 0.30,
        "ajout_jours": 30,
    }


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


# --- Phase 11 · Simulated batches (A5) ----------------------------------------------------
@pytest.mark.phase11
def test_un_compte_du_jeu_de_test_est_refuse_dans_un_lot_simule():
    """S1: the test part is never read a third time - a test account is refused, loudly."""
    from churn_saas.monitoring.simulation import comptes_reels

    echantillon = pd.DataFrame({"client_id": ["A", "B", "C"]})
    assert comptes_reels(echantillon, {"A", "B"}, {"C"})["client_id"].tolist() == ["A", "B"]
    with pytest.raises(ValueError, match="S1"):
        comptes_reels(echantillon, {"A", "C"}, {"C"})


@pytest.mark.phase11
def test_un_lot_simule_a_sa_taille_ses_identifiants_et_aucune_issue():
    """S2: the real accounts first, drawn rows renamed SIM-..., no outcome column."""
    from churn_saas.monitoring.simulation import completer_lot

    reels = pd.DataFrame({"client_id": ["CLI-1"], "x": ["1"], "churn": ["0"]})
    reservoir = pd.DataFrame(
        {"client_id": ["CLI-2", "CLI-3"], "x": ["2", "3"], "churn": ["1", "0"]}
    )
    lot = completer_lot(reels, reservoir, 50, np.random.default_rng(0))
    assert len(lot) == 50 and lot["client_id"].is_unique
    assert (
        lot["client_id"].iloc[0] == "CLI-1"
        and lot["client_id"].iloc[1:].str.startswith("SIM-").all()
    )
    assert "churn" not in lot.columns


@pytest.mark.phase11
def test_la_derive_injectee_touche_les_parts_decidees():
    """S4: last login doubled on 30 % of the accounts, support delay blanked on 25 %."""
    from churn_saas.monitoring.simulation import injecter_derive

    lot = pd.DataFrame(
        {"derniere_connexion_jours": ["10"] * 1_000, "delai_reponse_support_h": ["5.0"] * 1_000}
    )
    derive = injecter_derive(lot, np.random.default_rng(0))
    assert (derive["derniere_connexion_jours"] == "20").sum() == 300
    assert derive["delai_reponse_support_h"].isna().sum() == 250


@pytest.mark.phase11
def test_la_derive_forte_ajoute_trente_jours_a_trente_pour_cent_des_comptes():
    """S8: 30 days added to the last login of 30 % of the accounts, nothing else touched."""
    from churn_saas.monitoring import injecter_derive_forte

    lot = pd.DataFrame(
        {"derniere_connexion_jours": ["2"] * 1_000, "delai_reponse_support_h": ["5.0"] * 1_000}
    )
    derive = injecter_derive_forte(lot, np.random.default_rng(0))
    assert (derive["derniere_connexion_jours"] == "32").sum() == 300
    assert derive["delai_reponse_support_h"].equals(lot["delai_reponse_support_h"])


@pytest.mark.phase11
def test_le_rapport_simule_est_marque_et_le_mois_temoin_est_muet():
    """S3, S6, S7, S8: the report says it is simulated and what it proves; the drift-free
    month raises no alert, month 2's collection incident is caught (M8), month 3's strong
    disengagement too (M5)."""
    import json
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    rapport = json.loads((racine / "resultats" / "suivi_simule.json").read_text(encoding="utf-8"))
    assert rapport["mention"] == "SIMULÉ — démonstration" and "performance" in rapport["portee"]
    mois_1, mois_2, mois_3 = rapport["mois"]
    assert not any(a["declenchee"] for a in mois_1["alertes"])
    assert mois_2["M8_manquants"]["verdict"]["variables en alerte"] == ["delai_reponse_support_h"]
    # The month 2 finding, kept as is: doubling the last login left M5 silent.
    assert not mois_2["M5_derive"]["verdict"]["déclenchée"]
    # S8: the strong disengagement is caught on its key variable; M8 is silent again.
    assert mois_3["M5_derive"]["verdict"]["variables clés au-dessus de 0,25"] == [
        "derniere_connexion_jours"
    ]
    assert not mois_3["M8_manquants"]["verdict"]["déclenchée"]
    manifeste = json.loads(
        (racine / "data" / "simulation" / "manifeste_simulation.json").read_text(encoding="utf-8")
    )
    assert manifeste["mention"] == rapport["mention"]
    assert manifeste["fichiers"] == rapport["lots"]


@pytest.mark.phase11
def test_les_figures_du_suivi_se_tracent_depuis_le_rapport_et_disent_simule():
    """The working notebook's figures come from the recorded report, and each title carries
    the simulated mark: a monitoring chart lifted out of the notebook must not pass for
    production data."""
    import json
    from pathlib import Path

    import matplotlib

    matplotlib.use("Agg")
    from churn_saas.features import tracer_carte_psi, tracer_evolution_psi, tracer_manquants

    racine = Path(__file__).resolve().parents[1]
    rapport = json.loads((racine / "resultats" / "suivi_simule.json").read_text(encoding="utf-8"))
    profil = json.loads(
        (racine / "resultats" / "profil_reference.json").read_text(encoding="utf-8")
    )
    figures = [
        tracer_evolution_psi(
            rapport["mois"], profil["variables_cles"], "derniere_connexion_jours", (0.10, 0.25)
        ),
        tracer_carte_psi(rapport["mois"]),
        tracer_manquants(rapport["mois"], 2.0),
    ]
    for figure in figures:
        assert "SIMULÉ" in figure.axes[0].get_title()


# --- Phase 11 · Quarterly review on simulated outcomes (part B) ----------------------------
@pytest.mark.phase11
def test_les_issues_simulees_reduisent_le_risque_des_seuls_comptes_contactes():
    """S5: a contacted account's risk is lowered by the efficacy hypothesis; nobody else's."""
    from churn_saas.monitoring import simuler_issues

    groupes = pd.Series(["contact"] * 20_000 + ["temoin"] * 20_000)
    issues = simuler_issues(groupes, np.full(40_000, 0.8), np.random.default_rng(0))
    parti = issues == "parti"
    assert parti[groupes == "contact"].mean() == pytest.approx(0.8 * 0.75, abs=0.01)
    assert parti[groupes == "temoin"].mean() == pytest.approx(0.8, abs=0.01)


def _issues(n_partis_signales, n_partis_non_signales, mrr=100.0, pays="France"):
    lignes = [(True, True)] * n_partis_signales + [(True, False)] * n_partis_non_signales
    return pd.DataFrame(
        {
            "parti": [p for p, _ in lignes],
            "signale": [s for _, s in lignes],
            "mrr": mrr,
            "pays": pays,
        }
    )


@pytest.mark.phase11
def test_la_couverture_du_revenu_se_compare_a_la_cible():
    """M1: covered MRR over exposed MRR, against 50 %."""
    from churn_saas.monitoring import couverture_revenu

    assert couverture_revenu(_issues(6, 4))["part couverte"] == 0.6
    assert not couverture_revenu(_issues(6, 4))["déclenchée"]
    assert couverture_revenu(_issues(4, 6))["déclenchée"]


@pytest.mark.phase11
def test_le_segment_surveille_suit_le_critere_r9():
    """M7: triggered only when conclusive, under 0.8 x the global recall AND its interval
    excludes the global recall; a small segment is never conclusive."""
    from churn_saas.monitoring import rappel_segment

    issues = pd.concat([_issues(300, 300), _issues(10, 190, pays="Suisse")], ignore_index=True)
    verdict = rappel_segment(issues, "pays", "Suisse", 0.8, 50, 10, np.random.default_rng(0))
    assert verdict["concluant"] and verdict["déclenchée"]
    pareil = pd.concat([_issues(300, 300), _issues(100, 100, pays="Suisse")], ignore_index=True)
    assert not rappel_segment(pareil, "pays", "Suisse", 0.8, 50, 10, np.random.default_rng(0))[
        "déclenchée"
    ]
    petit = pd.concat([_issues(300, 300), _issues(0, 8, pays="Suisse")], ignore_index=True)
    assert not rappel_segment(petit, "pays", "Suisse", 0.8, 50, 10, np.random.default_rng(0))[
        "concluant"
    ]


@pytest.mark.phase11
def test_la_retention_contre_temoin_exige_un_effet_significatif():
    """A clear effect on large groups passes; the same effect on a handful of control
    accounts is not significant - the rule triggers."""
    from churn_saas.monitoring import retention_contre_temoin

    def groupes(n_contact, n_temoin):
        return pd.DataFrame(
            {
                "groupe": ["contact"] * n_contact + ["temoin"] * n_temoin,
                "parti": [i % 10 < 3 for i in range(n_contact)]
                + [i % 10 < 6 for i in range(n_temoin)],
            }
        )

    assert not retention_contre_temoin(groupes(2_000, 2_000), np.random.default_rng(0))[
        "déclenchée"
    ]
    assert retention_contre_temoin(groupes(400, 10), np.random.default_rng(0))["déclenchée"]


@pytest.mark.phase11
def test_le_pr_auc_en_production_ignore_les_comptes_contactes():
    """A contact changes the outcome it would score: contacted accounts are left out."""
    from churn_saas.monitoring import pr_auc_en_production

    issues = pd.DataFrame(
        {
            "groupe": ["non_retenu"] * 4 + ["contact"] * 2,
            "parti": [True, True, False, False, False, False],
            "score": [0.9, 0.8, 0.2, 0.1, 0.99, 0.98],
        }
    )
    verdict = pr_auc_en_production(issues, reference=0.8)
    assert verdict["comptes"] == 4 and verdict["PR-AUC"] == 1.0 and not verdict["déclenchée"]


@pytest.mark.phase11
def test_la_revue_trimestrielle_simulee_est_enregistree_et_marquee():
    """Part B in the recorded report: simulated outcomes on file (hashes match), the four
    quarterly verdicts tied to existing rules, the simulated mark."""
    import hashlib
    import json
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    revue = json.loads((racine / "resultats" / "suivi_simule.json").read_text(encoding="utf-8"))[
        "revue_trimestrielle"
    ]
    assert revue["mention"] == "SIMULÉ — démonstration"
    for nom, fichier in revue["issues"].items():
        contenu = (racine / "data" / "simulation" / nom).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(contenu).hexdigest() == fichier["sha256"], nom
    indicateurs = {a["indicateur"] for a in revue["alertes"]}
    assert (
        {
            "Couverture du revenu à risque",
            "Rappel sur le segment Suisse",
            "Rétention des comptes traités",
            "PR-AUC en production",
        }
        <= indicateurs
        == set(table_regles()["indicateur"])
    )


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
