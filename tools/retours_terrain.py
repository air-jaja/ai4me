"""Field feedback loop: measure what contacting an account actually changes.

    uv run python tools/retours_terrain.py --modele sorties/retours_modele.csv   # empty template
    uv run python tools/retours_terrain.py sorties/retours_2026-11.csv           # analysis

The CRM returns, for every account of a list - contacted AND control group - its outcome
three months later. Comparing the two groups measures the real retention efficacy, the
project's most fragile hypothesis (0.25): efficacy = (control churn - contacted churn) /
control churn, with a bootstrap interval. Without the control group, "contacted and
stayed" says nothing about what the contact changed. Feedback names real accounts: it
stays in `sorties/`, never versioned.
"""

from __future__ import annotations

import argparse
import sys

COLONNES = (
    "client_id",
    "mois_liste",
    "groupe",
    "date_contact",
    "action_menee",
    "resultat_3_mois",
    "motif",
)
GROUPES = ("contact", "temoin")
RESULTATS = ("reste", "parti", "inconnu")
MOTIFS = (
    "prix",
    "fonctionnalites",
    "support",
    "concurrent",
    "rachat_fusion",
    "fin_de_projet",
    "autre",
    "",
)


def efficacite_mesuree(retours, tirages: int = 1000, graine: int = 0) -> dict:
    """Efficacy = relative churn reduction of contacted accounts against the control group."""
    import numpy as np

    connus = retours[retours["resultat_3_mois"].isin(("reste", "parti"))]
    contact = (connus.loc[connus["groupe"] == "contact", "resultat_3_mois"] == "parti").to_numpy()
    temoin = (connus.loc[connus["groupe"] == "temoin", "resultat_3_mois"] == "parti").to_numpy()
    if len(contact) == 0 or len(temoin) == 0 or temoin.mean() == 0:
        return {
            "comptes contactés": len(contact),
            "comptes témoins": len(temoin),
            "efficacité mesurée": None,
            "note": "groupes insuffisants pour mesurer",
        }

    def mesure(c, t):
        return (t.mean() - c.mean()) / t.mean() if t.mean() else np.nan

    generateur = np.random.default_rng(graine)
    valeurs = [
        mesure(generateur.choice(contact, len(contact)), generateur.choice(temoin, len(temoin)))
        for _ in range(tirages)
    ]
    return {
        "comptes contactés": int(len(contact)),
        "comptes témoins": int(len(temoin)),
        "départs, contactés": round(float(contact.mean()), 4),
        "départs, témoins": round(float(temoin.mean()), 4),
        "efficacité mesurée": round(float(mesure(contact, temoin)), 4),
        "intervalle 95 %": [round(float(np.nanquantile(valeurs, q)), 4) for q in (0.025, 0.975)],
        "hypothèse du projet": 0.25,
    }


def controler(retours) -> list[str]:
    """Contract of the feedback file: columns and closed lists."""
    erreurs = [f"colonne absente : {c}" for c in COLONNES if c not in retours.columns]
    if erreurs:
        return erreurs
    for colonne, autorises in (
        ("groupe", GROUPES),
        ("resultat_3_mois", RESULTATS),
        ("motif", MOTIFS),
    ):
        hors = sorted(set(retours[colonne].fillna("")) - set(autorises))
        if hors:
            erreurs.append(f"{colonne} hors liste : {hors}")
    return erreurs


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    import json

    import pandas as pd

    analyseur = argparse.ArgumentParser(description="Boucle de retour du terrain.")
    analyseur.add_argument("retours", nargs="?")
    analyseur.add_argument("--modele", help="écrire un fichier de retours vide (gabarit)")
    arguments = analyseur.parse_args(argv)
    if arguments.modele:
        pd.DataFrame(columns=COLONNES).to_csv(
            arguments.modele, index=False, sep=";", encoding="utf-8-sig"
        )
        print(f"Gabarit : {arguments.modele}")
        return 0
    retours = pd.read_csv(arguments.retours, sep=";", dtype=str, encoding="utf-8-sig")
    erreurs = controler(retours)
    if erreurs:
        print("\n".join(erreurs), file=sys.stderr)
        return 1
    print(json.dumps(efficacite_mesuree(retours), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
