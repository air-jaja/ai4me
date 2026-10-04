# ruff: noqa: E501  (prose of the generated document: long text lines on purpose)
"""Generate the API field reference (docs/API_champs.md) - dictionary and training data only.

    uv run python tools/documenter_champs.py

Every business field the API receives or returns, with its meaning, its unit, the range
that holds by definition, and what the training accounts actually contain: values seen,
spread, missing share, and what the service does when the field is absent. Labels and
descriptions come from the data dictionary, outputs from the response schema, figures from
the training part of the split - the test part is never described. Regenerated, never edited.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "docs" / "API_champs.md"
TYPES_JSON = {"integer": "entier", "number": "décimal", "string": "texte"}


def _nombre(valeur: float) -> str:
    """French rendering: space for thousands, comma for decimals, no useless zeros."""
    texte = f"{valeur:,.2f}".rstrip("0").rstrip(".")
    return texte.replace(",", " ").replace(".", ",")


def _pct(part: float) -> str:
    return f"{_nombre(round(100 * part, 1))} %"


def _cellule(texte: str) -> str:
    return str(texte).replace("|", "\\|").replace("\n", " ")


def _plage(colonne: str, plages: dict, coherences: tuple, champs: set) -> str:
    bas, haut = plages.get(colonne, (None, None))
    if bas is None and haut is None:
        texte = "—"
    elif haut is None:
        texte = f"≥ {_nombre(bas)}"
    else:
        texte = f"{_nombre(bas)} à {_nombre(haut)}"
    for gauche, droite in coherences:
        if colonne == gauche and droite in champs:  # only fields the API receives
            texte += f" ; ≤ `{droite}`"
    return texte


def mesurer() -> dict:
    """Facts about the training accounts only, as the model received them."""
    sys.path.insert(0, str(RACINE / "src"))
    import pandas as pd

    from churn_saas import config
    from churn_saas.features import executer_pipeline, parties_du_decoupage

    resultat = executer_pipeline(config.FICHIER_COMPLET, config.FICHIER_CATALOGUE)
    X = parties_du_decoupage(resultat).X_entrainement
    # Silver rows of the same accounts: the fields the model does not read (identifier,
    # customer value) and the gaps as received, before any reconstruction.
    recus = resultat.silver.loc[X.index]
    return {"X": X, "recus": recus, "pd": pd}


def contenu(mesures: dict) -> str:
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.config import COUT_CONTACT_CSM_EUR, EFFICACITE_RETENTION
    from churn_saas.donnees import REGLES_RECONSTRUCTION
    from churn_saas.donnees.gouvernance import SENSIBILITE
    from churn_saas.donnees.qualite import COHERENCES, PLAGES
    from churn_saas.industrialisation.api import ScoreSortie
    from churn_saas.industrialisation.dictionnaire import CATEGORIELLES, ENTREES
    from churn_saas.industrialisation.liste import TRANCHES
    from churn_saas.modelisation.baseline import MODALITE_MANQUANTE

    X, recus, pd = mesures["X"], mesures["recus"], mesures["pd"]
    reconstructions = {r.colonne: r.formule for r in REGLES_RECONSTRUCTION}
    n = len(X)
    champs = {v.colonne for v in ENTREES}

    def si_absent(v) -> str:
        if v.obligatoire:
            return "Appel refusé (422)"
        if v.colonne not in X.columns:
            return "Rien : le modèle ne lit pas ce champ"
        if v.colonne in CATEGORIELLES:
            return f"Modalité « {MODALITE_MANQUANTE} »"
        mediane = f"médiane d'entraînement, {_nombre(X[v.colonne].median())}"
        if v.colonne in reconstructions:
            return f"Recalculé : {reconstructions[v.colonne]} ; à défaut, {mediane}"
        return mediane[0].upper() + mediane[1:]

    def role(v) -> str:
        if v.colonne in X.columns:
            return "Variable du modèle"
        if v.obligatoire:
            return "Calcul du gain attendu"
        return "Renvoyé tel quel"

    lignes = [
        "# Champs de l'API — référence métier",
        "",
        "> Document **généré** par `tools/documenter_champs.py` : ne pas le modifier à la main. Libellés et",
        "> descriptions : dictionnaire des données (`industrialisation/dictionnaire.py`) ; réponse : schéma",
        f"> `ScoreSortie` (`industrialisation/api.py`) ; chiffres : les **{_nombre(n)} comptes de la partie",
        "> d'entraînement**. La partie de test n'est pas décrite. Guide d'appel : `docs/API.md`.",
        "",
        "## 1. Entrées — `POST /score`",
        "",
        "Les noms des champs sont les colonnes de l'export du CRM. Seul `valeur_vie_client_eur` est",
        "obligatoire ; un champ absent ou `null` est traité comme à l'entraînement (colonne « Si absent »).",
        "",
        "| Champ | Libellé | Description | Type | Unité | Exemple | Rôle | Sensibilité |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in ENTREES:
        sensibilite = SENSIBILITE.get(v.colonne, ("—",))[0]
        lignes.append(
            f"| `{v.colonne}` | {v.libelle} | {_cellule(v.description)} | {v.type} | "
            f"{v.unite or '—'} | `{_cellule(v.exemple)}` | {role(v)} | {sensibilite} |"
        )

    lignes += [
        "",
        "## 2. Valeurs numériques",
        "",
        "« Plage admise » : ce qui vaut par définition ; une valeur hors plage est un défaut de la",
        "source. Les autres colonnes décrivent les valeurs reçues sur les comptes d'entraînement.",
        "",
        "| Champ | Plage admise | Minimum | Médiane | Maximum | Absents (source) | Si absent |",
        "|---|---|---|---|---|---|---|",
    ]
    for v in ENTREES:
        if v.type == "texte":
            continue
        valeurs = pd.to_numeric(recus[v.colonne], errors="coerce")
        lignes.append(
            f"| `{v.colonne}` | {_plage(v.colonne, PLAGES, COHERENCES, champs)} | "
            f"{_nombre(valeurs.min())} | {_nombre(valeurs.median())} | {_nombre(valeurs.max())} | "
            f"{_pct(valeurs.isna().mean())} | {_cellule(si_absent(v))} |"
        )

    lignes += [
        "",
        "## 3. Valeurs catégorielles",
        "",
        "Modalités vues à l'entraînement, avec leur effectif. La casse et les espaces autour sont",
        "ignorés (`PRO` vaut `Pro`) ; les accents comptent. Une valeur hors de cette liste n'est",
        "reconnue par aucune modalité : le modèle n'en tient pas compte.",
        "",
        "| Champ | Modalités (effectif) | Absents (source) | Si absent |",
        "|---|---|---|---|",
    ]
    for v in ENTREES:
        if v.colonne not in CATEGORIELLES:
            continue
        effectifs = recus[v.colonne].value_counts()
        modalites = ", ".join(f"`{m}` ({_nombre(c)})" for m, c in effectifs.items())
        lignes.append(
            f"| `{v.colonne}` | {modalites} | {_pct(recus[v.colonne].isna().mean())} | "
            f"{_cellule(si_absent(v))} |"
        )

    identifiants = recus["client_id"].dropna()
    gabarit = identifiants.str.replace(r"[0-9]", "9", regex=True).mode().iloc[0]
    lignes += [
        "",
        "## 4. Identifiant",
        "",
        f"`client_id` : {_nombre(identifiants.nunique())} identifiants distincts pour {_nombre(n)} comptes,"
        f" au format `{gabarit}` (9 : un chiffre).",
        "Le modèle ne le lit pas ; l'API le renvoie tel quel pour rapprocher la réponse du compte.",
        "",
        "## 5. Réponse — `POST /score`",
        "",
        "| Champ | Libellé | Type | Description |",
        "|---|---|---|---|",
    ]
    for nom, propriete in ScoreSortie.model_json_schema()["properties"].items():
        types = [propriete.get("type")] + [t.get("type") for t in propriete.get("anyOf", [])]
        type_ = next(TYPES_JSON[t] for t in types if t in TYPES_JSON)
        lignes.append(
            f"| `{nom}` | {propriete.get('title', '—')} | {type_} | "
            f"{_cellule(propriete.get('description', '—'))} |"
        )
    bornes = [seuil for seuil, _ in TRANCHES]
    lignes += [
        "",
        "**Tranches de risque** (`tranche_risque`, selon `probabilite`) :",
        "",
        "| Tranche | Probabilité |",
        "|---|---|",
    ]
    for i, (seuil, nom) in enumerate(TRANCHES):
        bas = [f"≥ {_pct(seuil)}"] if seuil > 0 else []
        haut = [f"< {_pct(bornes[i - 1])}"] if i else []
        lignes.append(f"| {nom} | {' et '.join(bas + haut)} |")
    lignes += [
        "",
        "**Gain attendu d'un contact** (`gain_attendu_contact_eur`) = probabilité × valeur client ×",
        f"efficacité de la rétention ({_pct(EFFICACITE_RETENTION)}) − coût d'un contact"
        f" ({_nombre(COUT_CONTACT_CSM_EUR)} €).",
        "Les deux paramètres sont des **hypothèses** du projet (`config.py`). Un gain négatif signifie",
        "qu'un contact coûte plus qu'il ne rapporte en moyenne.",
        "",
    ]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(
        description="Génère la référence métier des champs de l'API (docs/API_champs.md)."
    )
    analyseur.add_argument("--sortie", default=str(DESTINATION))
    arguments = analyseur.parse_args(argv)
    texte = contenu(mesurer())
    Path(arguments.sortie).write_text(texte, encoding="utf-8", newline="\n")
    print(f"Référence des champs : {arguments.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
