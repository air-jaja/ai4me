"""Phase 11, A5 - the monthly monitoring, demonstrated on two SIMULATED batches.

    uv run python tools/suivi_simule.py                 # batches if absent, then the report
    uv run python tools/suivi_simule.py --forcer        # redo an identical report
    uv run python tools/suivi_simule.py --regenerer     # rebuild the batches (same seed)

Decision S1 to S8 (04/10/2026). The batches - raw CRM format, 5,000 accounts each - are
written to data/simulation/ with their manifest: the sample's 36 training accounts plus
rows drawn from the training part, month 1 as is, month 2 with the documented drift, month
3 with the strong one decided after month 2 left M5 silent (S8). The
report runs each batch through the production chain (silver, gold, the served model, the
operational list) and the rules M5, M8 and M9 against the reference profile, and writes
resultats/suivi_simule.json. It proves the mechanics, never the model's performance (S6).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "resultats" / "suivi_simule.json"
PROFIL = RACINE / "resultats" / "profil_reference.json"
# The first day of each simulated month: the list's date, so the report is reproducible.
DATES_DES_MOIS = ("2026-11-01", "2026-12-01", "2027-01-01")


def _outil_servi():
    specification = importlib.util.spec_from_file_location(
        "modele_servi", RACINE / "tools" / "modele_servi.py"
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _fichier(mois: str) -> str:
    return f"lot_simule_{mois}.csv"


def _mois(s) -> tuple[str, ...]:
    """S3 months, then the S8 one."""
    return (*s.MOIS_SIMULES, s.MOIS_DERIVE_FORTE)


def generer(regenerer: bool = False) -> dict:
    """S1-S4, S7: the two raw batches and their manifest, unless already there."""
    sys.path.insert(0, str(RACINE / "src"))
    import numpy as np
    import pandas as pd

    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage
    from churn_saas.monitoring import simulation as s

    manifeste = s.DOSSIER_SIMULATION / "manifeste_simulation.json"
    attendus = [_fichier(mois) for mois in _mois(s)]
    if manifeste.exists() and not regenerer:
        contenu = json.loads(manifeste.read_text(encoding="utf-8"))
        if list(contenu["fichiers"]) == attendus and all(
            (s.DOSSIER_SIMULATION / f).exists() for f in attendus
        ):
            return contenu

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    parties = parties_du_decoupage(resultat)
    ids_entrainement = set(resultat.silver.loc[parties.X_entrainement.index, "client_id"])
    ids_test = set(resultat.silver.loc[parties.X_test.index, "client_id"])
    brut = pd.read_csv(config.FICHIER_COMPLET, dtype=str, encoding="utf-8-sig")
    reservoir = brut[brut["client_id"].isin(ids_entrainement)].reset_index(drop=True)
    echantillon = pd.read_csv(config.FICHIER_ECHANTILLON, dtype=str, encoding="utf-8-sig")
    reels = s.comptes_reels(echantillon, ids_entrainement, ids_test)

    generateur = np.random.default_rng(s.GRAINE_SIMULATION)
    mois_1 = s.completer_lot(reels, reservoir, s.TAILLE_LOT_SIMULE, generateur)
    mois_2 = s.injecter_derive(
        s.completer_lot(reels, reservoir, s.TAILLE_LOT_SIMULE, generateur), generateur
    )
    # S8 comes after: drawn last from the same generator, months 1 and 2 stay identical.
    mois_3 = s.injecter_derive_forte(
        s.completer_lot(reels, reservoir, s.TAILLE_LOT_SIMULE, generateur), generateur
    )
    s.DOSSIER_SIMULATION.mkdir(parents=True, exist_ok=True)
    fichiers = {}
    for mois, lot in zip(_mois(s), (mois_1, mois_2, mois_3), strict=True):
        chemin = s.DOSSIER_SIMULATION / _fichier(mois)
        lot.to_csv(chemin, index=False, encoding="utf-8-sig", lineterminator="\n")
        fichiers[chemin.name] = {"lignes": len(lot), "sha256": _empreinte(chemin)}
    contenu = {
        "mention": s.MENTION,
        "decision": "S1 à S7, validées par le porteur le 04/10/2026",
        "graine": s.GRAINE_SIMULATION,
        "taille_lot": s.TAILLE_LOT_SIMULE,
        "comptes_reels": {
            "retenus (partie d'entraînement)": len(reels),
            "écartés (jeu de test)": int(echantillon["client_id"].isin(ids_test).sum()),
        },
        "derive_mois_2": {"M5": s.DERIVE_CONNEXION, "M8": s.DERIVE_MANQUANTS, "M9": "aucune"},
        "derive_mois_3": {"M5": s.DERIVE_CONNEXION_FORTE, "S8": "seule injection du mois"},
        "colonnes_retirees": list(s.COLONNES_POSTERIEURES),
        "fichiers": fichiers,
    }
    manifeste.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return contenu


def executer(forcer: bool = False, regenerer: bool = False, sortie: Path = DESTINATION) -> dict:
    lots = generer(regenerer)
    sys.path.insert(0, str(RACINE / "src"))
    warnings.simplefilter("ignore")
    import numpy as np
    import pandas as pd

    from churn_saas import config
    from churn_saas.donnees import charger_manifeste, typer_pour_modele
    from churn_saas.features import (
        construire_silver_standard,
        executer_pipeline,
        parties_du_decoupage,
        preparer_gold,
    )
    from churn_saas.industrialisation import construire_liste
    from churn_saas.modelisation import construire_baseline
    from churn_saas.monitoring import (
        couverture_revenu,
        derive_combinee,
        ecart_volume,
        evaluer_alertes,
        manquants_relatifs,
        mesures_du_mois,
        mesures_du_trimestre,
        pr_auc_en_production,
        rappel_segment,
        retention_contre_temoin,
        simuler_issues,
    )
    from churn_saas.monitoring import simulation as s
    from churn_saas.monitoring.alertes import SEGMENTS_SURVEILLES
    from churn_saas.packaging import etiquettes_tracabilite, identite_execution

    profil = json.loads(PROFIL.read_text(encoding="utf-8"))
    manifeste = charger_manifeste(RACINE / "data" / "manifeste_v1.0.json")
    etiquettes = etiquettes_tracabilite("11", "tools/suivi_simule.py", manifeste)
    identite = identite_execution(
        etiquettes,
        outil="suivi_simule",
        lots=",".join(f["sha256"] for f in lots["fichiers"].values()),
        profil=profil["identite_execution"],
    )
    if sortie.exists() and not forcer:
        existant = json.loads(sortie.read_text(encoding="utf-8"))
        if existant.get("identite_execution") == identite:
            print("Suivi simulé déjà calculé à l'identique : rien n'est recalculé.")
            return existant

    debut = time.perf_counter()
    parties = parties_du_decoupage(
        executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    )
    fond, y = parties.X_entrainement, parties.y_entrainement.astype(int)
    modele = _outil_servi().construire_servi(construire_baseline, "sigmoid", config)(fond)
    modele.fit(fond, y)
    catalogue = pd.read_csv(config.FICHIER_CATALOGUE, dtype=str, encoding="utf-8-sig")
    retenus = {"À contacter ce mois", "Groupe témoin (pas de contact)"}
    groupes = {"À contacter ce mois": "contact", "Groupe témoin (pas de contact)": "temoin"}
    # S5: the outcomes have their own stream, so the batches' draws stay as they are.
    generateur_issues = np.random.default_rng([s.GRAINE_SIMULATION, 5])

    mois_rapportes, issues_du_trimestre, fichiers_issues, precedent = [], [], {}, None
    for mois, date_liste in zip(_mois(s), DATES_DES_MOIS, strict=True):
        brut = pd.read_csv(s.DOSSIER_SIMULATION / _fichier(mois), dtype=str, encoding="utf-8-sig")
        silver = construire_silver_standard(brut, catalogue=catalogue)
        X = typer_pour_modele(preparer_gold(silver).gold.drop(columns=["churn"], errors="ignore"))
        score = pd.Series(modele.predict_proba(X)[:, 1], index=X.index)
        table_derive, derive = derive_combinee(profil, X, score)
        table_manquants, manquants = manquants_relatifs(profil, silver)
        liste = construire_liste(
            modele,
            X,
            brut["client_id"].set_axis(X.index),
            pd.to_numeric(brut["valeur_vie_client_eur"], errors="coerce").set_axis(X.index),
            pd.to_numeric(
                brut["revenu_mensuel_recurrent_eur"].str.replace(",", "."), errors="coerce"
            ).set_axis(X.index),
            fond,
            f"{profil['modele']['nom']} {profil['modele']['version']}",
            capacite=config.CAPACITE_MENSUELLE,
            genere_le=date_liste,
            graine=s.GRAINE_SIMULATION,
        )
        signales = int(liste["Action recommandée"].isin(retenus).sum())
        volume = ecart_volume(signales, precedent)
        action = liste.set_index("Compte")["Action recommandée"]
        issues = pd.DataFrame(
            {
                "client_id": brut["client_id"].to_numpy(),
                "mois_liste": date_liste,
                "groupe": action.reindex(brut["client_id"])
                .map(groupes)
                .fillna("non_retenu")
                .to_numpy(),
            },
            index=X.index,
        )
        issues["resultat_3_mois"] = simuler_issues(issues["groupe"], score, generateur_issues)
        chemin_issues = s.DOSSIER_SIMULATION / f"issues_simulees_{mois}.csv"
        issues.to_csv(chemin_issues, index=False, encoding="utf-8-sig", lineterminator="\n")
        fichiers_issues[chemin_issues.name] = {
            "lignes": len(issues),
            "sha256": _empreinte(chemin_issues),
        }
        issues_du_trimestre.append(
            issues.assign(
                parti=issues["resultat_3_mois"] == "parti",
                signale=issues["groupe"] != "non_retenu",
                score=score,
                mrr=X["revenu_mensuel_recurrent_eur"],
                pays=silver.loc[X.index, "pays"],
            )
        )
        alertes = evaluer_alertes(mesures_du_mois(derive, manquants, volume))
        mois_rapportes.append(
            {
                "mois": mois,
                "date_liste": date_liste,
                "comptes": int(len(X)),
                "M5_derive": {
                    "verdict": derive,
                    "psi": dict(zip(table_derive["variable"], table_derive["psi"], strict=True)),
                },
                "M8_manquants": {
                    "verdict": manquants,
                    "table": json.loads(
                        table_manquants.to_json(orient="records", force_ascii=False)
                    ),
                },
                "M9_volume": volume,
                "alertes": json.loads(alertes.to_json(orient="records", force_ascii=False)),
            }
        )
        precedent = signales

    # The quarterly review, on the three months' outcomes (part B; S5, S6).
    trimestre = pd.concat(issues_du_trimestre, ignore_index=True)
    generateur_revue = np.random.default_rng([s.GRAINE_SIMULATION, 6])
    reference = json.loads(
        (RACINE / "resultats" / "validation_phase9.json").read_text(encoding="utf-8")
    )["metriques"]["PR-AUC"]["valeur"]
    couverture = couverture_revenu(trimestre)
    colonne, modalite = SEGMENTS_SURVEILLES[0]
    suisse = rappel_segment(
        trimestre,
        colonne,
        modalite,
        config.RATIO_EQUITE,
        config.TAILLE_MIN_SEGMENT,
        config.DEPARTS_MIN_SEGMENT,
        generateur_revue,
    )
    retention = retention_contre_temoin(trimestre, generateur_revue)
    pr_auc = pr_auc_en_production(trimestre, reference)
    alertes_trimestre = evaluer_alertes(mesures_du_trimestre(couverture, suisse, retention, pr_auc))
    revue = {
        "mention": s.MENTION,
        "comptes": int(len(trimestre)),
        "issues": fichiers_issues,
        "M1_couverture": couverture,
        "M7_suisse": suisse,
        "retention_contre_temoin": retention,
        "pr_auc_en_production": pr_auc,
        "alertes": json.loads(alertes_trimestre.to_json(orient="records", force_ascii=False)),
    }

    bilan = {
        "identite_execution": identite,
        "mention": s.MENTION,
        "portee": "mécanique du suivi démontrée ; aucune conclusion sur la performance (S6)",
        "profil": {"modele": profil["modele"], "identite_execution": profil["identite_execution"]},
        "lots": lots["fichiers"],
        "mois": mois_rapportes,
        "revue_trimestrielle": revue,
        "duree_s": round(time.perf_counter() - debut, 1),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    sortie.write_text(
        json.dumps(bilan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return bilan


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Suivi mensuel sur lots simulés (phase 11).")
    analyseur.add_argument("--forcer", action="store_true", help="refaire un rapport identique")
    analyseur.add_argument("--regenerer", action="store_true", help="refaire les lots simulés")
    arguments = analyseur.parse_args(argv)
    bilan = executer(arguments.forcer, arguments.regenerer)
    print(bilan["mention"])
    for mois in bilan["mois"]:
        declenchees = [a["indicateur"] for a in mois["alertes"] if a["declenchee"]]
        print(f"{mois['mois']} : {', '.join(declenchees) or 'aucune alerte'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
