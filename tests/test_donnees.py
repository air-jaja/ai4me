"""Activity 1 - cleaning and building the silver/gold levels."""

import pandas as pd
import pytest

from churn_saas.donnees.gold import construire_gold, separer_cible
from churn_saas.donnees.silver import (
    construire_silver,
    nettoyer_decimal_texte,
    normaliser_cle,
    parser_dates_multiformat,
)


def test_nombres_stockes_en_texte():
    """Numbers stored as text must become numbers, and junk must become NaN.

    A failed conversion raising no error would turn a numeric column into categories:
    "33,3" and "33,4" would lose any ordering relation."""
    serie = pd.Series(["33,3 %", "1 234,50 €", "12.5", None, "abc"])
    resultat = nettoyer_decimal_texte(serie)
    assert resultat.iloc[0] == pytest.approx(33.3)
    assert resultat.iloc[1] == pytest.approx(1234.50)
    assert resultat.iloc[2] == pytest.approx(12.5)
    assert pd.isna(resultat.iloc[4])  # unconvertible text -> NaN, never an exception


def test_dates_multiformats():
    """Mixed date formats must all parse, and DD/MM must win over MM/DD.

    Without an explicit dayfirst choice, pandas arbitrates alone and the result depends on
    row order - a non-reproducible parse."""
    serie = pd.Series(["31/01/2024", "2024-02-06", "03/04/2024"])
    resultat = parser_dates_multiformat(serie)
    assert resultat.notna().all()
    # dayfirst: 03/04/2024 is 3 April, not 4 March
    assert resultat.iloc[2].month == 4


def test_normalisation_de_la_cle_de_jointure():
    """The join key must collapse case and whitespace differences."""
    assert list(normaliser_cle(pd.Series([" STARTER", "Starter"]))) == ["starter", "starter"]


def test_jointure_catalogue_sans_perte_malgre_la_casse():
    """The catalogue join must lose no row despite STARTER/starter.

    This is the silent failure of the project: without normalisation nothing raises, the
    unmatched rows simply vanish from the result."""
    brut = pd.DataFrame({"plan": ["STARTER", "Pro"], "x": ["1", "2"]})
    catalogue = pd.DataFrame({"plan": ["starter", "pro"], "prix": [10, 20]})
    silver = construire_silver(brut, catalogue=catalogue)
    assert len(silver) == 2
    assert silver["prix"].notna().all()  # without normalisation everything would be NaN


def test_doublons_supprimes():
    """Strict duplicates must be removed.

    Duplicated accounts make the model learn the same example twice and flatter every
    metric computed afterwards."""
    brut = pd.DataFrame({"a": ["1", "1", "2"]})
    assert len(construire_silver(brut)) == 2


def test_gold_retire_les_colonnes_interdites():
    """Every forbidden column must be gone from the gold dataset.

    Guards the single most expensive defect of the project: a leaking variable silently
    reintroduced by a refactor would produce an excellent, meaningless model."""
    silver = pd.DataFrame(
        {
            "client_id": ["CLI-1"],
            "sante_compte_fin_periode": [80],
            "commentaire_csm": ["note"],
            "groupe_experimentation": ["A"],
            "valeur_vie_client_eur": [1000],
            "anciennete_mois": [12],
            "churn": [1],
        }
    )
    gold = construire_gold(silver)
    assert set(gold.columns) == {"anciennete_mois", "churn"}


def test_separation_de_la_cible():
    """The target must never remain among the explanatory variables."""
    gold = pd.DataFrame({"a": [1, 2], "churn": [0, 1]})
    X, y = separer_cible(gold)
    assert "churn" not in X.columns
    assert list(y) == [0, 1]


def test_les_variantes_de_casse_sont_fusionnees_en_une_seule_modalite():
    """`TPE` and `tpe` are one category written two ways, not two categories.

    Normalising the join key alone was not enough: the join worked while the stored values
    kept every spelling. One-hot encoding then turned each spelling into its own column, so
    the model saw several rare categories instead of one common one, split the signal
    between them, and made any importance reading misleading.
    """
    from churn_saas.donnees import normaliser_modalites

    serie = pd.Series(["TPE", "tpe", " TPE ", "PME", "pme", None])
    resultat = normaliser_modalites(serie)
    assert resultat.dropna().nunique() == 2
    # The canonical label is the most frequent original spelling, not a lowercase form:
    # a deliverable should show `TPE`, not `tpe`.
    assert resultat.iloc[0] == "TPE"
    assert pd.isna(resultat.iloc[5])


def test_le_silver_ne_conserve_aucune_variante_de_casse():
    """The whole chain must leave one label per business category."""
    brut = pd.DataFrame(
        {
            "secteur": ["Tech", "TECH", "tech", "Finance"],
            "taille_entreprise": ["PME", "pme", "PME", "ETI"],
        }
    )
    silver = construire_silver(brut)
    assert silver["secteur"].nunique() == 2
    assert silver["taille_entreprise"].nunique() == 2


# --- Phase 4 · Preparation and cleaning -------------------------------------------------
def test_un_suffixe_d_unite_est_converti():
    """A unit written in letters after the number must not turn the value into NaN.

    570 support delays arrived as "3.1 h". The symbol list removed spaces but not the
    letter, `to_numeric` coerced the rest to NaN, and the missing rate of the column went
    from 10 % to 21.4 % with no error anywhere.
    """
    serie = pd.Series(["3.1 h", "14,6 h", "2 j", "40 Go", "7.5h", "12"])
    resultat = nettoyer_decimal_texte(serie)
    assert list(resultat) == pytest.approx([3.1, 14.6, 2.0, 40.0, 7.5, 12.0])


def test_les_formats_deja_couverts_restent_convertis():
    """Handling units must not break the formats the primitive already covered."""
    serie = pd.Series(["33,3 %", "1 234,50 €", "1\u202f234,5", "-2,5", "1e3"])
    resultat = nettoyer_decimal_texte(serie)
    assert list(resultat) == pytest.approx([33.3, 1234.5, 1234.5, -2.5, 1000.0])


def test_une_perte_de_conversion_est_detectee_sans_cibler_de_colonne():
    """The guard compares presence before and after; it knows no column and no format.

    That is what makes it catch the next unexpected format, not only the one already met.
    """
    from churn_saas.donnees import pertes_de_conversion

    avant = pd.Series(["3.1", "abc", None, "", "nan", "4,2"])
    apres = nettoyer_decimal_texte(avant)
    assert list(pertes_de_conversion(avant, apres)) == [False, True, False, False, False, False]


def test_une_perte_de_conversion_bloque_la_chaine():
    """A value present in the source and lost on conversion stops the chain, by name."""
    brut = pd.DataFrame({"client_id": ["A", "B"], "delai": ["3.1", "trois heures"]})
    with pytest.raises(ValueError, match="delai : 1 valeurs"):
        construire_silver(brut, colonnes_decimales=["delai"])


def test_le_mode_non_strict_reproduit_le_defaut_en_connaissance_de_cause():
    """`strict=False` exists to show the defect, and only produces NaN where it lies."""
    brut = pd.DataFrame({"client_id": ["A", "B"], "delai": ["3.1", "trois heures"]})
    silver = construire_silver(brut, colonnes_decimales=["delai"], strict=False)
    assert silver["delai"].isna().tolist() == [False, True]


def test_une_date_illisible_bloque_la_chaine():
    """Dates go through the same guard: an unparsed date is a lost value too."""
    brut = pd.DataFrame({"client_id": ["A", "B"], "d": ["2024-01-31", "trente-et-un"]})
    with pytest.raises(ValueError, match="d : 1 valeurs"):
        construire_silver(brut, colonnes_dates=["d"])


def test_les_colonnes_du_catalogue_sont_typees():
    """Numeric catalogue columns become numbers; a genuinely textual one stays text.

    Read as text like every source, the prices and quotas reached the model as categories:
    "12" and "25" EUR with no ordering left between them.
    """
    from churn_saas.donnees import typer_colonnes_catalogue

    catalogue = pd.DataFrame(
        {
            "plan": ["Starter", "Pro"],
            "prix": ["12", "25"],
            "sla": ["2,5", "1"],
            "support": ["Non", "Oui"],
        }
    )
    type_ = typer_colonnes_catalogue(catalogue)
    assert pd.api.types.is_integer_dtype(type_["prix"])
    assert type_["sla"].tolist() == pytest.approx([2.5, 1.0])
    assert type_["support"].tolist() == ["Non", "Oui"]


def test_la_jointure_apporte_des_colonnes_numeriques():
    """End to end: after the join, a catalogue price is a number in silver."""
    brut = pd.DataFrame({"client_id": ["A", "B"], "plan": ["STARTER", "Pro"]})
    catalogue = pd.DataFrame({"plan": ["Starter", "Pro"], "prix": ["12", "25"]})
    silver = construire_silver(brut, catalogue=catalogue)
    assert pd.api.types.is_numeric_dtype(silver["prix"])


def test_un_doublon_au_format_different_est_retire():
    """Two rows describing one account, written differently, are one account.

    Deduplicating only the raw text kept them both: "12,5" and "12.5" differ as strings.
    """
    brut = pd.DataFrame(
        {
            "client_id": ["A", "A", "B"],
            "heures": ["12,5", "12.5", "3"],
            "secteur": ["Tech", "TECH", "Tech"],
        }
    )
    silver = construire_silver(brut, colonnes_decimales=["heures"])
    assert len(silver) == 2


def test_un_compte_en_conflit_bloque_la_chaine():
    """One account, two different values: no rule can tell which is right, so stop."""
    brut = pd.DataFrame({"client_id": ["A", "A", "B"], "heures": ["12", "40", "3"]})
    with pytest.raises(ValueError, match="valeurs différentes"):
        construire_silver(brut, colonnes_decimales=["heures"])


def test_la_cle_de_compte_peut_etre_desactivee():
    """Tables without an account key (a catalogue, a test frame) must still build."""
    brut = pd.DataFrame({"client_id": ["A", "A"], "x": ["1", "2"]})
    assert len(construire_silver(brut, cle_compte=None)) == 2


@pytest.mark.phase5
def test_gold_retire_la_date_brute_et_le_doublon_du_catalogue():
    """Each phase 4 exclusion is applied, and carries its own motive."""
    from churn_saas.donnees import MOTIFS_EXCLUSION

    silver = pd.DataFrame(
        {
            "date_souscription": pd.to_datetime(["2024-01-31"]),
            "fonctionnalites_incluses": [8],
            "fonctionnalites_total": [8],
            "anciennete_mois": [12],
            "churn": [0],
        }
    )
    gold = construire_gold(silver)
    # fonctionnalites_total itself goes in phase 5: one value per plan (arbitrage 2).
    assert set(gold.columns) == {"anciennete_mois", "churn"}
    assert MOTIFS_EXCLUSION["date_souscription"].startswith("date brute")
    assert MOTIFS_EXCLUSION["fonctionnalites_incluses"].startswith("doublon")


# --- Phase 4 · Data contract ------------------------------------------------------------
def _lot_sain() -> pd.DataFrame:
    """A small batch satisfying every rule of the contract."""
    return pd.DataFrame(
        {
            "client_id": ["A", "B", "C"],
            "utilisateurs_actifs": [5, 0, 10],
            "sieges_souscrits": [10, 4, 10],
            "taux_adoption_pct": [50.0, 0.0, 100.0],
            "fonctionnalites_utilisees": [3, 0, 8],
            "fonctionnalites_total": [8, 8, 16],
            "csat": [4, 1, 5],
            "secteur": ["Tech", "Retail", "Tech"],
            "churn": [0, 1, 0],
        }
    )


def _statut(contrat: pd.DataFrame, debut: str) -> str:
    return contrat.loc[contrat["contrôle"].str.startswith(debut), "statut"].iloc[0]


def test_le_contrat_passe_sur_un_lot_sain():
    from churn_saas.donnees import BLOQUANT, verifier_contrat

    contrat = verifier_contrat(_lot_sain())
    # Only the "documented columns" check fails here, the frame being a small extract.
    assert set(contrat.loc[contrat["statut"] == BLOQUANT, "contrôle"]) == {
        "Colonnes attendues présentes"
    }


@pytest.mark.parametrize(
    ("modification", "controle"),
    [
        ({"csat": [4, 1, 6]}, "Valeurs dans leur plage"),
        ({"taux_adoption_pct": [50.0, 0.0, 130.0]}, "Valeurs dans leur plage"),
        ({"utilisateurs_actifs": [5, 0, 12]}, "Invariants métier"),
        ({"taux_adoption_pct": [80.0, 0.0, 100.0]}, "Invariants métier"),
        ({"client_id": ["A", "A", "C"]}, "`client_id` unique"),
        ({"secteur": ["Tech", "Retail", "TECH"]}, "Une seule orthographe"),
        ({"churn": [0, 2, 0]}, "Cible `churn` binaire"),
    ],
)
def test_le_contrat_bloque_un_lot_defectueux(modification, controle):
    """Each blocking rule, broken alone, is reported under its own name."""
    from churn_saas.donnees import BLOQUANT, verifier_contrat

    lot = _lot_sain().assign(**modification)
    assert _statut(verifier_contrat(lot), controle) == BLOQUANT


def test_le_contrat_bloque_une_perte_de_conversion():
    """The conversion check reads the raw text: once typed, a lost value looks missing."""
    from churn_saas.donnees import BLOQUANT, verifier_contrat

    brut = pd.DataFrame({"client_id": ["A", "B"], "delai": ["3.1 h", "3.1h(est.)"]})
    contrat = verifier_contrat(_lot_sain(), brut=brut, colonnes_numeriques=["delai"])
    assert _statut(contrat, "Aucune valeur perdue") == BLOQUANT


def test_le_contrat_met_sous_surveillance_un_taux_de_manquants_eleve():
    """Between the watch and the blocking threshold, the batch passes but is flagged."""
    from churn_saas.donnees import SURVEILLANCE, verifier_contrat

    lot = _lot_sain().assign(csat=[4, None, 5])
    contrat = verifier_contrat(lot, seuil_surveillance=10, seuil_critique=50)
    assert _statut(contrat, "Taux de manquants") == SURVEILLANCE


def test_une_modalite_inconnue_est_a_surveiller_et_non_bloquante():
    """An unseen category degrades the score without corrupting it: watch, do not stop."""
    from churn_saas.donnees import SURVEILLANCE, referentiel_modalites, verifier_contrat

    reference = referentiel_modalites(_lot_sain())
    lot = _lot_sain().assign(secteur=["Tech", "Santé", "Tech"])
    contrat = verifier_contrat(lot, modalites_reference=reference)
    assert _statut(contrat, "Modalités connues") == SURVEILLANCE


def test_exiger_contrat_nomme_chaque_controle_en_echec():
    from churn_saas.donnees import exiger_contrat, verifier_contrat

    lot = _lot_sain().assign(csat=[4, 1, 6], client_id=["A", "A", "C"])
    with pytest.raises(ValueError) as erreur:
        exiger_contrat(verifier_contrat(lot))
    assert "Valeurs dans leur plage" in str(erreur.value)
    assert "`client_id` unique" in str(erreur.value)


def test_une_date_iso_n_est_jamais_inversee():
    """ "2024-02-06" is 6 February, whatever convention applies to slash dates.

    `format="mixed", dayfirst=True` read it as 2 June: 960 ISO dates were swapped until
    phase 4, while every one of them still parsed - nothing looked wrong.
    """
    resultat = parser_dates_multiformat(pd.Series(["2024-02-06", "2024-11-03", "03/04/2024"]))
    assert [(d.month, d.day) for d in resultat] == [(2, 6), (11, 3), (4, 3)]


def test_les_dates_textuelles_sont_lues():
    resultat = parser_dates_multiformat(pd.Series(["12 Jan 2024", "5 Mar 2023"]))
    assert [(d.year, d.month, d.day) for d in resultat] == [(2024, 1, 12), (2023, 3, 5)]


def test_un_format_de_date_non_declare_n_est_pas_devine():
    """An undeclared format becomes NaT - reported as a loss - rather than a guess."""
    assert parser_dates_multiformat(pd.Series(["2024.02.06", "06-02-2024"])).isna().all()


def test_le_contrat_bloque_une_date_inversee():
    """A date contradicting the stated weekday is reported, which is how the swap was found."""
    from churn_saas.donnees import BLOQUANT, verifier_contrat

    lot = pd.DataFrame(
        {
            "client_id": ["A", "B"],
            # 6 Feb 2024 is a Tuesday; read as 2 June 2024, it would be a Sunday.
            "date_souscription": pd.to_datetime(["2024-02-06", "2024-06-02"]),
            "jour_souscription": ["mardi", "mardi"],
        }
    )
    assert _statut(verifier_contrat(lot), "Date cohérente") == BLOQUANT


# --- Phase 4 · Deterministic reconstruction ---------------------------------------------
def _comptes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sieges_souscrits": [10, 4, 20, 5],
            "prix_mensuel_par_siege_eur": [12, 25, None, 45],
            "utilisateurs_actifs": [5, 1, 20, 0],
            "revenu_mensuel_recurrent_eur": [130.0, None, None, None],
            "taux_adoption_pct": [50.0, None, None, 0.0],
        }
    )


def test_une_valeur_observee_n_est_jamais_remplacee():
    """Reconstruction fills gaps only: an observed 130 EUR stays 130, not 10 x 12 = 120."""
    from churn_saas.donnees import reconstruire_valeurs_deterministes

    reconstruit, _ = reconstruire_valeurs_deterministes(_comptes())
    assert reconstruit.loc[0, "revenu_mensuel_recurrent_eur"] == 130.0
    assert reconstruit.loc[0, "taux_adoption_pct"] == 50.0


def test_le_revenu_est_reconstruit_par_sieges_fois_prix():
    from churn_saas.donnees import reconstruire_valeurs_deterministes

    reconstruit, _ = reconstruire_valeurs_deterministes(_comptes())
    assert reconstruit.loc[1, "revenu_mensuel_recurrent_eur"] == pytest.approx(100.0)
    assert reconstruit.loc[3, "revenu_mensuel_recurrent_eur"] == pytest.approx(225.0)


def test_le_taux_d_adoption_est_reconstruit_exactement():
    """Active users over seats, times 100, one decimal - the form of the source column."""
    from churn_saas.donnees import reconstruire_valeurs_deterministes

    reconstruit, _ = reconstruire_valeurs_deterministes(_comptes())
    assert reconstruit.loc[1, "taux_adoption_pct"] == pytest.approx(25.0)
    assert reconstruit.loc[2, "taux_adoption_pct"] == pytest.approx(100.0)


def test_un_ingredient_manquant_laisse_la_valeur_manquante():
    """No price, no revenue: the gap stays, for the median imputation to handle."""
    from churn_saas.donnees import reconstruire_valeurs_deterministes

    reconstruit, bilan = reconstruire_valeurs_deterministes(_comptes())
    assert pd.isna(reconstruit.loc[2, "revenu_mensuel_recurrent_eur"])
    ligne = bilan.set_index("colonne").loc["revenu_mensuel_recurrent_eur"]
    assert (ligne["manquants avant"], ligne["reconstruits"], ligne["manquants après"]) == (3, 2, 1)


def test_une_regle_inapplicable_est_signalee_et_non_ignoree():
    """A batch lacking an ingredient column says so in the report, it is not skipped quietly."""
    from churn_saas.donnees import reconstruire_valeurs_deterministes

    _, bilan = reconstruire_valeurs_deterministes(_comptes().drop(columns="sieges_souscrits"))
    assert bilan["statut"].str.startswith("non applicable").all()


# --- Phase 5 · Training / test split ------------------------------------------------------
def _jeu_a_decouper(n: int = 500) -> tuple[pd.DataFrame, pd.Series]:
    import numpy as np

    generateur = np.random.default_rng(0)
    X = pd.DataFrame({"a": generateur.normal(size=n), "b": generateur.choice(["x", "y"], n)})
    y = pd.Series((generateur.random(n) < 0.28).astype(int))
    return X, y


@pytest.mark.phase5
def test_le_decoupage_est_deterministe_disjoint_et_complet():
    """Same seed, same accounts in the test part; no account in both; none lost."""
    from churn_saas.donnees import decouper_entrainement_test

    X, y = _jeu_a_decouper()
    premier, second = decouper_entrainement_test(X, y), decouper_entrainement_test(X, y)
    assert list(premier.X_test.index) == list(second.X_test.index)
    assert set(premier.X_test.index).isdisjoint(premier.X_entrainement.index)
    assert len(premier.X_test) + len(premier.X_entrainement) == len(X)
    assert len(premier.X_test) == round(len(X) * premier.part_test)


@pytest.mark.phase5
def test_le_decoupage_est_stratifie_sur_la_cible():
    """Both parts keep the churn rate: the gap stays under the threshold fixed beforehand."""
    from churn_saas.config import ECART_STRATIFICATION_MAX_PTS
    from churn_saas.donnees import decouper_entrainement_test, resume_decoupage

    X, y = _jeu_a_decouper()
    resume = resume_decoupage(decouper_entrainement_test(X, y))
    ecart = resume.loc[resume["partie"] == "écart (points)", "taux de churn (%)"].iloc[0]
    assert ecart < ECART_STRATIFICATION_MAX_PTS


@pytest.mark.phase5
def test_une_autre_graine_change_le_jeu_de_test():
    """The seed matters: a change of seed must show in the recorded fingerprint."""
    from churn_saas.donnees import decouper_entrainement_test

    X, y = _jeu_a_decouper()
    a = decouper_entrainement_test(X, y, graine=1)
    b = decouper_entrainement_test(X, y, graine=2)
    assert set(a.X_test.index) != set(b.X_test.index)
