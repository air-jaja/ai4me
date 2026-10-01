"""Non-regression tests for every completed phase.

**What this file pins, and what it does not.** Other test files check *behaviour*: a
function does what its contract says. This one pins *published figures* - the numbers
quoted in the phase notebooks, in the explanatory documents and in the oral presentation.

The distinction matters. A cleaning function can keep working perfectly while returning
different numbers, because a source changed or a rule was adjusted. Nothing would fail,
and three deliverables would silently become wrong at once.

**How to extend it.** One section per completed phase. Numeric figures go into
`CHIFFRES_PUBLIES`, which a single parametrised test walks through: adding a phase means
adding entries, not writing new tests. Structural guarantees that are not a number - a
join losing no row, a fingerprint matching - keep their own test.

Tolerances are deliberately loose. The aim is to catch a chain that broke, not to forbid a
rounding difference.

    Phase 1 - Framing                        notebooks/01_cadrage.ipynb
    Phase 2 - Ingestion and governance       notebooks/02_donnees.ipynb
    Phase 3 - Exploration and profiling      notebooks/03_exploration.ipynb
              materialisation                data/processed/*.parquet + manifest
    Phase 4 - ...                            (to be added)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn_saas.config import COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION
from churn_saas.donnees import (
    charger_bronze,
    construire_silver,
    controler_jointure,
    decrire_schema,
    verifier_manifeste,
)
from churn_saas.evaluation.decision import seuil_par_compte

RACINE = Path(__file__).resolve().parents[1]
DONNEES = RACINE / "data" / "raw"

COLONNES_DECIMALES = [
    "taux_adoption_pct",
    "heures_usage_30j",
    "delai_reponse_support_h",
    "revenu_mensuel_recurrent_eur",
    "valeur_vie_client_eur",
]
COLONNES_ENTIERES = [
    "anciennete_mois",
    "sieges_souscrits",
    "utilisateurs_actifs",
    "connexions_30j",
    "fonctionnalites_total",
    "fonctionnalites_utilisees",
    "nb_integrations",
    "derniere_connexion_jours",
    "tickets_support_90j",
    "csat",
    "retards_paiement_12m",
    "sante_compte_fin_periode",
    "churn",
]


# --- Fixtures shared by every phase ---------------------------------------------------
@pytest.fixture(scope="module")
def brut() -> pd.DataFrame:
    """Raw dataset, read exactly as the notebooks read it."""
    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip(
            "Jeu de données absent ou réduit à un pointeur Git-LFS. "
            "Exécuter `git lfs pull` ou replacer les CSV dans data/raw/."
        )
    return charger_bronze(fichier)


@pytest.fixture(scope="module")
def silver(brut: pd.DataFrame) -> pd.DataFrame:
    """Cleaned dataset, built exactly as the notebooks build it."""
    catalogue = charger_bronze(DONNEES / "catalogue_plans.csv")
    return construire_silver(
        brut,
        catalogue=catalogue,
        colonnes_decimales=COLONNES_DECIMALES,
        colonnes_dates=["date_souscription"],
        colonnes_entieres=COLONNES_ENTIERES,
    )


# --- Published figures, declared once -------------------------------------------------
@dataclass(frozen=True)
class ChiffrePublie:
    """One figure quoted in a deliverable, with how to recompute it.

    `cite_dans` is not decoration: it is what turns a failure into an action. Knowing a
    number moved is useless without knowing which documents now contradict the code.
    """

    phase: str
    libelle: str
    cite_dans: str
    attendu: float
    tolerance: float
    calcul: Callable[[pd.DataFrame, pd.DataFrame], float]


def _part_concentree(serie: pd.Series, part: float = 0.10) -> float:
    """Share of the total carried by the largest `part` of the values."""
    valeurs = pd.to_numeric(serie, errors="coerce").dropna().sort_values(ascending=False)
    return float(valeurs.head(int(len(valeurs) * part)).sum() / valeurs.sum())


def _gold(silver: pd.DataFrame) -> pd.DataFrame:
    """Gold dataset rebuilt from the cleaned data, target included."""
    from churn_saas.donnees import construire_gold
    from churn_saas.features import ajouter_ratios_usage

    return construire_gold(ajouter_ratios_usage(silver))


def _amplitude_segment(silver: pd.DataFrame, colonne: str, effectif_minimal: int = 30) -> float:
    """Spread in points between the highest and lowest churn rate across modalities.

    These three figures were published wrong until phase 3: computed on un-normalised
    modalities, they were overstated by roughly a factor of two, a marginal spelling
    variant setting the extreme.
    """
    churn = pd.to_numeric(silver["churn"], errors="coerce")
    groupes = churn.groupby(silver[colonne]).agg(["mean", "size"])
    retenus = groupes.loc[groupes["size"] >= effectif_minimal, "mean"]
    return float((retenus.max() - retenus.min()) * 100)


def _ecart_churn_selon_manquant(brut: pd.DataFrame, colonne: str) -> float:
    """Gap in churn rate between rows where a column is present and where it is missing."""
    cible = pd.to_numeric(brut["churn"], errors="coerce")
    absent = brut[colonne].isna()
    return float(abs(cible[absent].mean() - cible[~absent].mean()) * 100)


CHIFFRES_PUBLIES: tuple[ChiffrePublie, ...] = (
    # ---------------------------------------------------------------- Phase 1 - Cadrage
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Lignes du fichier source",
        cite_dans="01_cadrage § 1.1 · 02_donnees § 1.1 · suivi_projet_ia",
        attendu=5035,
        tolerance=0,
        calcul=lambda brut, silver: float(len(brut)),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Comptes uniques après retrait des doublons",
        cite_dans="01_cadrage § 1.1 · 02_donnees § 1.3 · README",
        attendu=5000,
        tolerance=0,
        calcul=lambda brut, silver: float(len(silver)),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Taux de résiliation",
        cite_dans="01_cadrage § 1.1 · notebook § 8 (déséquilibre modéré) · soutenance",
        attendu=0.28,
        tolerance=0.005,
        calcul=lambda brut, silver: float(silver["churn"].astype(float).mean()),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="MRR mensuel total du portefeuille (M€)",
        cite_dans="01_cadrage § 1.1 · notebook § 12 (assiette de référence)",
        attendu=17.2,
        tolerance=0.9,
        calcul=lambda brut, silver: float(
            pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").sum() / 1e6
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR portée par 10 % des comptes",
        cite_dans="01_cadrage § 1.2 · figure de concentration",
        attendu=0.68,
        tolerance=0.03,
        calcul=lambda brut, silver: _part_concentree(silver["revenu_mensuel_recurrent_eur"]),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR perdu portée par 10 % des churners",
        cite_dans="01_cadrage § 1.2 · 02.DONNEES_explications · README · soutenance",
        attendu=0.72,
        tolerance=0.03,
        calcul=lambda brut, silver: _part_concentree(
            silver.loc[silver["churn"].astype(float) == 1, "revenu_mensuel_recurrent_eur"]
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Part du MRR exposée au départ",
        cite_dans="01_cadrage § 1.1 · notebook § 12",
        attendu=0.23,
        tolerance=0.02,
        calcul=lambda brut, silver: float(
            pd.to_numeric(
                silver.loc[silver["churn"].astype(float) == 1, "revenu_mensuel_recurrent_eur"],
                errors="coerce",
            ).sum()
            / pd.to_numeric(silver["revenu_mensuel_recurrent_eur"], errors="coerce").sum()
        ),
    ),
    # ------------------------------------------- Phase 2 - Ingestion et gouvernance
    ChiffrePublie(
        phase="2 · Données",
        libelle="Colonnes du fichier source",
        cite_dans="02_donnees § 1.2 · dictionnaire de données",
        attendu=29,
        tolerance=0,
        calcul=lambda brut, silver: float(brut.shape[1]),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Doublons stricts retirés",
        cite_dans="02_donnees § 1.3 · 02.DONNEES_explications · suivi_projet_ia",
        attendu=35,
        tolerance=0,
        calcul=lambda brut, silver: float(len(brut) - len(silver)),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Manquants sur `commentaire_csm` (%)",
        cite_dans="02_donnees § 1.3 · notebook § 5 (valeurs de référence)",
        attendu=55.4,
        tolerance=0.5,
        calcul=lambda brut, silver: float(brut["commentaire_csm"].isna().mean() * 100),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Manquants les plus élevés hors texte libre (%)",
        cite_dans="02_donnees § 1.3 · notebook § 5 (seuil d'alerte à 10 %)",
        attendu=10.0,
        tolerance=0.5,
        calcul=lambda brut, silver: float(
            (brut.drop(columns=["commentaire_csm"]).isna().mean() * 100).max()
        ),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Écart de churn selon l'absence d'une valeur — colonnes SOURCE (points)",
        cite_dans="02_donnees § 1.3 · 02.DONNEES_explications · suivi_projet_ia",
        attendu=4.5,
        tolerance=1.0,
        calcul=lambda brut, silver: max(
            _ecart_churn_selon_manquant(brut, colonne)
            for colonne in brut.columns
            if colonne not in ("churn", "commentaire_csm") and brut[colonne].isna().sum() >= 30
        ),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Champs `commentaire_csm` renseignés (%)",
        cite_dans="02_donnees § 4.2",
        attendu=44.6,
        tolerance=0.5,
        calcul=lambda brut, silver: float(brut["commentaire_csm"].notna().mean() * 100),
    ),
    ChiffrePublie(
        phase="2 · Données",
        libelle="Modalités en trop dues à la casse, avant correction",
        cite_dans="02_donnees § 1.3 (audit qualité) · 03_exploration § 4.2",
        attendu=26,
        tolerance=0,
        calcul=lambda brut, silver: float(
            sum(
                brut[c].dropna().astype(str).str.strip().nunique()
                - brut[c].dropna().astype(str).str.strip().str.casefold().nunique()
                for c in ("secteur", "plan", "taille_entreprise", "pays", "code_datacenter")
            )
        ),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre tailles d'entreprise (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=8.3,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "taille_entreprise"),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre secteurs (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=7.0,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "secteur"),
    ),
    ChiffrePublie(
        phase="1 · Cadrage",
        libelle="Écart de churn entre pays (points)",
        cite_dans="01_cadrage § 1.2 · 01.CADRAGE_explications",
        attendu=6.1,
        tolerance=0.5,
        calcul=lambda brut, silver: _amplitude_segment(silver, "pays"),
    ),
    # ----------------------------------------- Phase 3 - Exploration et profilage
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Comptes sans aucun utilisateur actif",
        cite_dans="03_exploration § 3.4 · 03.EXPLORATION_explications · soutenance",
        attendu=297,
        tolerance=0,
        calcul=lambda brut, silver: float(
            (pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0).sum()
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Taux de churn des comptes abandonnés",
        cite_dans="03_exploration § 3.4 · figure « signal de 62 points »",
        attendu=0.865,
        tolerance=0.02,
        calcul=lambda brut, silver: float(
            silver.loc[pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0, "churn"]
            .astype(float)
            .mean()
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Écart de risque porté par l'abandon (points)",
        cite_dans="03_exploration § 3.4 · titre de figure · soutenance",
        attendu=62.2,
        tolerance=3.0,
        calcul=lambda brut, silver: float(
            (
                silver.loc[
                    pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") == 0, "churn"
                ]
                .astype(float)
                .mean()
                - silver.loc[
                    pd.to_numeric(silver["utilisateurs_actifs"], errors="coerce") != 0, "churn"
                ]
                .astype(float)
                .mean()
            )
            * 100
        ),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Modalités de `taille_entreprise` après normalisation",
        cite_dans="03_exploration § 4.2 (8 orthographes pour 4 catégories)",
        attendu=4,
        tolerance=0,
        calcul=lambda brut, silver: float(silver["taille_entreprise"].dropna().nunique()),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Colonnes du jeu gold livré au modèle",
        cite_dans="03_exploration § 3.6 · fiche modèle",
        attendu=34,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver).shape[1]),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Variables explicatives après séparation de la cible",
        cite_dans="03_exploration § 3.6 · suivi_projet_ia",
        attendu=33,
        tolerance=0,
        calcul=lambda brut, silver: float(_gold(silver).shape[1] - 1),
    ),
    ChiffrePublie(
        phase="3 · Exploration",
        libelle="Modalités de `secteur` après normalisation",
        cite_dans="03_exploration § 4.2 (21 orthographes pour 7 catégories)",
        attendu=7,
        tolerance=0,
        calcul=lambda brut, silver: float(silver["secteur"].dropna().nunique()),
    ),
)


@pytest.mark.parametrize(
    "chiffre",
    CHIFFRES_PUBLIES,
    ids=lambda c: f"{c.phase.split(' ')[0]}-{c.libelle[:45]}",
)
def test_les_chiffres_publies_sont_inchanges(
    chiffre: ChiffrePublie, brut: pd.DataFrame, silver: pd.DataFrame
):
    """A published figure must still be reproducible by the code that produced it.

    When this fails, the code is not necessarily wrong: a source may legitimately have
    changed. What is certain is that the documents listed in `cite_dans` now contradict
    it, and must be updated in the same commit.
    """
    obtenu = chiffre.calcul(brut, silver)
    assert obtenu == pytest.approx(chiffre.attendu, abs=chiffre.tolerance), (
        f"\n  Phase      : {chiffre.phase}"
        f"\n  Chiffre    : {chiffre.libelle}"
        f"\n  Publié     : {chiffre.attendu}"
        f"\n  Recalculé  : {obtenu:.4f}"
        f"\n  Cité dans  : {chiffre.cite_dans}"
        f"\n  → Corriger le code, ou mettre à jour ces documents dans le même commit."
    )


# --- Phase 1 · Cadrage : guarantees that are not a single figure -----------------------
def test_l_ecart_de_seuil_entre_deciles_reste_superieur_a_cent(silver: pd.DataFrame):
    """The "factor over 100" argument justifies rejecting a single global threshold.

    It is the central argument of the decision rule, quoted in the framing notebook, in
    the explanatory document and in the oral pitch. If the spread narrowed, a global
    threshold would become defensible and the whole design would need rethinking.
    """
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    seuils = seuil_par_compte(clv.quantile([0.10, 0.90]))
    facteur = float(seuils.iloc[0] / seuils.iloc[1])
    assert facteur > 100, (
        f"Écart tombé à {facteur:.0f} : l'argument central de la règle de décision ne tient plus"
    )


def test_le_seuil_du_dernier_decile_reste_tres_bas(silver: pd.DataFrame):
    """Acting on a top-decile account stays rational below 1% risk.

    The 0.3% figure is the striking end of the argument presented to the jury.
    """
    clv = pd.to_numeric(silver["valeur_vie_client_eur"], errors="coerce")
    assert float(seuil_par_compte(pd.Series([clv.quantile(0.90)])).iloc[0]) < 0.01


def test_les_hypotheses_de_cadrage_sont_inchangees():
    """These values are quoted verbatim in the documents and in the oral pitch."""
    assert EFFICACITE_RETENTION == 0.25
    assert COUT_CONTACT_CSM_EUR == 135.0


def test_la_precision_statistique_du_rappel_reste_autour_de_cinq_points(silver: pd.DataFrame):
    """The "±5 points" caveat stated in section 9 must remain true.

    Saying it before the jury does is worth more than being told; but only while it holds.
    """
    n_positifs = int(silver["churn"].astype(float).sum() * 0.20)
    demi_largeur = 1.96 * np.sqrt(0.70 * 0.30 / n_positifs)
    assert demi_largeur == pytest.approx(0.054, abs=0.01)


# --- Phase 2 · Ingestion et gouvernance : guarantees that are not a single figure -------
def test_la_jointure_catalogue_apparie_tous_les_comptes(silver: pd.DataFrame):
    """A silent join failure would corrupt every downstream figure."""
    assert "prix_mensuel_par_siege_eur" in silver.columns
    assert silver["prix_mensuel_par_siege_eur"].notna().all()


def test_la_normalisation_de_la_cle_reste_indispensable(brut: pd.DataFrame):
    """Without normalisation the join matches nothing, and raises nothing.

    This measurement is the one quoted to justify the normalisation step. Should the
    sources become consistent on their own, the argument would need rewording - the code
    would still be right, the document would be misleading.
    """
    catalogue = charger_bronze(DONNEES / "catalogue_plans.csv")
    controle = controler_jointure(brut, catalogue, cle="plan")
    assert controle.iloc[0]["taux d'appariement"] == "54.3%"
    assert controle.iloc[1]["taux d'appariement"] == "100.0%"


def test_chaque_colonne_source_porte_toujours_un_role(brut: pd.DataFrame):
    """A new column arriving undocumented is a column nobody decided what to do with."""
    schema = decrire_schema(brut)
    sans_role = sorted(schema.loc[schema["role"] == "non documenté", "colonne"])
    assert not sans_role, (
        f"Colonnes sans rôle déclaré : {sans_role}. "
        "Compléter ROLES_COLONNES avant de les laisser entrer dans la chaîne."
    )


def test_six_colonnes_restent_hors_du_modele(brut: pd.DataFrame):
    """Six columns cannot be explanatory variables, for six distinct reasons.

    The count is quoted in the phase 2 notebook and in the explanatory document. The
    motives are not interchangeable: the grid separates the ethical exclusion from the
    technical one.
    """
    non_modelisables = {
        "identifiant",
        "cible principale",
        "cible secondaire",
        "postérieur à la décision",
        "texte libre",
        "artefact de process",
    }
    schema = decrire_schema(brut)
    exclues = schema.loc[schema["role"].isin(non_modelisables)]
    assert len(exclues) == 6
    assert exclues["role"].nunique() == 6


def test_les_sources_correspondent_toujours_au_manifeste():
    """The recorded fingerprints still match the files on disk.

    This is the strongest non-regression guarantee of the project: it states that the data
    themselves have not moved. Every other figure here is computed from them, so a failure
    on this test explains all the others at once.
    """
    chemin = RACINE / "data" / "manifeste_v1.0.json"
    if not chemin.exists():
        pytest.skip("Manifeste absent : exécuter notebooks/02_donnees.ipynb.")

    manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    controle = verifier_manifeste(manifeste)
    non_conformes = controle.loc[~controle["conforme"], "source"].tolist()
    assert not non_conformes, (
        f"Sources modifiées depuis l'écriture du manifeste : {non_conformes}. "
        "Les chiffres publiés ne décrivent plus ces données."
    )


# --- Phase 3 · Exploration : guarantees that are not a single figure --------------------
def test_les_modalites_ne_comportent_plus_de_variante_de_casse(silver: pd.DataFrame):
    """One label per business category, across every categorical column.

    Normalising the join key alone left `TPE` and `tpe` as two categories in the dataset.
    One-hot encoding then produced a column per spelling: the model saw several rare
    categories where the business has one, split the signal between them, and every
    importance reading became misleading.
    """
    for colonne in ("secteur", "pays", "taille_entreprise", "plan", "code_datacenter"):
        valeurs = silver[colonne].dropna().astype(str)
        assert valeurs.nunique() == valeurs.str.strip().str.casefold().nunique(), (
            f"`{colonne}` conserve des variantes de casse : {sorted(valeurs.unique())[:6]}"
        )


def test_les_nan_des_ratios_ont_une_cause_unique_et_connue(silver: pd.DataFrame):
    """Every NaN in `tickets_par_actif` comes from a zero denominator, nothing else.

    The claim made in section 3.4 - that these NaN encode an abandoned account - only
    holds while this is true. Another cause appearing would make the explanatory indicator
    partly wrong without any metric saying so.
    """
    from churn_saas.features import ajouter_ratios_usage

    enrichi = ajouter_ratios_usage(silver)
    actifs = pd.to_numeric(enrichi["utilisateurs_actifs"], errors="coerce")
    assert (enrichi["tickets_par_actif"].isna() == (actifs == 0)).all()
    assert (
        pd.to_numeric(enrichi["compte_sans_utilisateur_actif"], errors="coerce") == (actifs == 0)
    ).all()


def test_aucun_segment_ne_concentre_le_risque(silver: pd.DataFrame):
    """No segment stands out enough for a business rule to replace the model.

    This is the framing conclusion of section 1.2: it justifies building a model rather
    than writing "watch sector X". It was published on overstated spreads - 13 to 17
    points instead of 7 to 8 - which made it look weaker than it is.

    The threshold is set at 15 points: beyond that, a simple segmentation would start to
    compete with the model and the framing would need revisiting.
    """
    for colonne in ("taille_entreprise", "secteur", "pays"):
        amplitude = _amplitude_segment(silver, colonne)
        assert amplitude < 15, (
            f"`{colonne}` sépare de {amplitude:.1f} points : une règle métier deviendrait "
            "compétitive et le cadrage serait à revoir."
        )


# --- Phase 3 · Materialisation: the chain stays reproducible --------------------------
def test_la_chaine_produit_deux_fois_le_meme_jeu_gold():
    """Two runs on the same sources must give the same gold dataset, byte for byte.

    This is the assumption the whole snapshot mechanism rests on. If it broke - a pandas
    upgrade, a change in join order - the fingerprint recorded in the manifest would no
    longer identify anything, and a model card would describe data the model never saw.

    The check is cheap: the chain runs in under a second on this volume.
    """
    from churn_saas.donnees import empreinte_donnees
    from churn_saas.features import executer_pipeline

    fichier = DONNEES / "churn_saas_complet.csv"
    if not fichier.exists() or fichier.stat().st_size < 10_000:
        pytest.skip("Jeu de données absent ou réduit à un pointeur Git-LFS.")

    catalogue = DONNEES / "catalogue_plans.csv"
    premier = executer_pipeline(fichier, catalogue)
    second = executer_pipeline(fichier, catalogue)

    assert empreinte_donnees(premier.silver) == empreinte_donnees(second.silver)
    assert empreinte_donnees(premier.gold) == empreinte_donnees(second.gold)


def test_les_instantanes_derives_ne_sont_pas_versionnes():
    """Parquet snapshots stay out of Git; the manifest that describes them stays in.

    Versioning the snapshots would produce a binary diff at every change to the cleaning
    rules, for information already held by the sources plus the code. The manifest is
    small, textual, and it is the contract.
    """
    import subprocess

    resultat = subprocess.run(
        ["git", "check-ignore", "data/processed/gold_v1.0_20260101.parquet"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    if resultat.returncode == 128:
        pytest.skip("Hors copie de travail Git.")
    assert resultat.returncode == 0, (
        "Les instantanés Parquet doivent rester hors de Git : vérifier `.gitignore`."
    )

    suivis = subprocess.run(
        ["git", "ls-files", "data/manifeste_v1.0.json"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    assert suivis.stdout.strip(), "Le manifeste doit, lui, être versionné."


def test_les_figures_produites_ne_sont_pas_versionnees():
    """Figures are outputs: regenerable, and a binary diff at every retouch otherwise.

    The documents that reuse them get them by running the notebook, not from the history.
    """
    import subprocess

    resultat = subprocess.run(
        ["git", "check-ignore", "reports/figures/03_correlations.png"],
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    if resultat.returncode == 128:
        pytest.skip("Hors copie de travail Git.")
    assert resultat.returncode == 0, "Les figures doivent rester hors de Git."


def test_le_cache_des_figures_depend_du_code_de_trace():
    """The property the whole figure cache rests on, pinned here as well.

    If the key stopped covering the drawing code, every notebook would keep displaying
    figures from a previous version - and the deliverable would show pictures that no
    longer match the numbers beside them.
    """
    from churn_saas.figures import cle_cache

    def tracer():
        return None

    def tracer_modifie():
        return None  # commentaire ajouté : le source change, donc la clé aussi

    assert cle_cache("signature", tracer) != cle_cache("signature", tracer_modifie)
