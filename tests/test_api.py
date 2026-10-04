"""The HTTP service: key, champion by alias, parity with the batch, contract, latency.

Needs FastAPI (group `api`) and the served model's file (models/, rebuilt in the complete
CI job): skipped otherwise - the complete job tolerates no skip.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

RACINE = Path(__file__).resolve().parents[1]
CLE = "cle-de-test"


@pytest.fixture(scope="module")
def client():
    import os

    from fastapi.testclient import TestClient

    from churn_saas.industrialisation.api import app

    os.environ["CHURN_API_KEY"] = f"autre-cle,{CLE}"
    with TestClient(app) as c:
        if c.get("/ready").status_code != 200:
            pytest.skip("Modèle servi absent de models/ (modele_servi.py --reconstruire-seulement)")
        yield c


def _comptes():
    from churn_saas import config
    from churn_saas.donnees.silver import nettoyer_decimal_texte
    from churn_saas.industrialisation.dictionnaire import ENTREES

    brut = pd.read_csv(config.FICHIER_ECHANTILLON, dtype=str, encoding="utf-8-sig")
    for colonne in (
        "taux_adoption_pct",
        "heures_usage_30j",
        "delai_reponse_support_h",
        "revenu_mensuel_recurrent_eur",
        "valeur_vie_client_eur",
    ):
        brut[colonne] = nettoyer_decimal_texte(brut[colonne])
    champs = [v.colonne for v in ENTREES]
    return [
        {k: (None if pd.isna(v) else v) for k, v in ligne.items()}
        for _, ligne in brut[champs].iterrows()
    ]


@pytest.mark.phase10
def test_l_api_donne_les_scores_du_lot(client):
    """Parity: the 50 sample accounts, one by one through HTTP, get the batch's scores to
    1e-9 - catalogue loaded, types applied, categories spelt as in training (D-09)."""
    reference = pd.read_csv(RACINE / "resultats" / "scores_echantillon_reference.csv")
    for i, compte in enumerate(_comptes()):
        reponse = client.post("/score", json=compte, headers={"X-API-Key": CLE})
        assert reponse.status_code == 200, reponse.text
        assert reponse.json()["probabilite"] == pytest.approx(reference["proba"][i], abs=1e-9)


@pytest.mark.phase10
def test_sans_cle_valide_pas_de_score(client):
    compte = _comptes()[0]
    assert client.post("/score", json=compte).status_code == 401
    assert client.post("/score", json=compte, headers={"X-API-Key": "faux"}).status_code == 401
    assert client.get("/health").status_code == 200  # health checks stay open


@pytest.mark.phase10
def test_la_reponse_parle_metier_et_ne_decide_pas(client):
    corps = client.post("/score", json=_comptes()[0], headers={"X-API-Key": CLE}).json()
    assert corps["tranche_risque"] in ("Très élevé", "Élevé", "Modéré", "Faible")
    assert corps["motif"] and "_" not in corps["motif"]
    assert "decision" not in corps and "action" not in corps  # E-102
    assert (
        client.get("/ready").json()["descriptif"]["estimateur"]
        == "sklearn.linear_model.LogisticRegression"
    )


@pytest.mark.phase10
def test_le_modele_tient_le_budget_de_latence_dans_l_api(client):
    """P4 (phase 8) budgets the MODEL: under 50 ms per account - met here. The whole HTTP
    call also prepares the raw record (silver cleaning, about 80 ms in this environment):
    an end-to-end budget is the project owner's decision, pending (docs/API.md)."""
    from churn_saas.config import BUDGET_COMPTE_MS
    from churn_saas.donnees import typer_pour_modele
    from churn_saas.evaluation import contributions_lineaires
    from churn_saas.industrialisation.api import etat
    from churn_saas.industrialisation.scoring import preparer

    brut = pd.DataFrame([{k: (None if v is None else str(v)) for k, v in _comptes()[0].items()}])
    X = typer_pour_modele(
        preparer(brut, catalogue=etat["catalogue"]).drop(columns=["churn"], errors="ignore")
    )
    durees = []
    for _ in range(30):
        debut = time.perf_counter()
        etat["modele"].predict_proba(X)
        contributions_lineaires(etat["modele"], X, moyennes=etat["moyennes"])
        durees.append(time.perf_counter() - debut)
    assert 1000 * statistics.median(durees) < BUDGET_COMPTE_MS


@pytest.mark.phase10
def test_le_contrat_est_documente_et_a_jour(tmp_path):
    """Every input field has a business title, a description and an example (generated
    from the data dictionary); docs/openapi.json is the current contract."""
    import importlib.util

    from churn_saas.industrialisation.api import app

    schema = app.openapi()["components"]["schemas"]["CompteEntree"]
    for nom, champ in schema["properties"].items():
        assert champ.get("title") and champ.get("description") and champ.get("examples"), nom
    assert schema["required"] == ["valeur_vie_client_eur"]
    specification = importlib.util.spec_from_file_location(
        "exporter", RACINE / "tools" / "exporter_openapi.py"
    )
    outil = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outil)
    outil.main(["--sortie", str(tmp_path / "openapi.json")])
    assert json.loads((tmp_path / "openapi.json").read_text(encoding="utf-8")) == json.loads(
        (RACINE / "docs" / "openapi.json").read_text(encoding="utf-8")
    )


@pytest.mark.phase10
def test_le_dictionnaire_couvre_les_entrees_du_modele(chaine_x_entrainement):
    from churn_saas.industrialisation.dictionnaire import par_colonne

    assert set(chaine_x_entrainement.columns) <= set(par_colonne())


@pytest.fixture(scope="module")
def chaine_x_entrainement():
    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage

    return parties_du_decoupage(
        executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    ).X_entrainement
