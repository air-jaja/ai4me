"""Figures of the certification notebook, drawn from the same functions everywhere.

The phase notebooks drew their figures with functions written inline. That was acceptable
while they were working documents; the certification notebook is the deliverable, and
copying those functions into it would create a second version of each (rule 7). They live
here instead: the notebook calls them, and can display their source next to the figure.

Each function takes data and returns a matplotlib figure. None reads a global, none saves
anything: storing a figure is the caller's decision (`figures.enregistrer_figure`).

Labels and titles are in French, as everything the reader sees (rule 1).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

PALETTE = {
    "principal": "#2a6f9e",
    "accent": "#b03030",
    "attention": "#d08a1e",
    "neutre": "#8a8a8a",
}


def _part_cumulee(valeurs: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative share of accounts and of value, accounts sorted by decreasing value."""
    v = pd.to_numeric(valeurs, errors="coerce").dropna().sort_values(ascending=False).to_numpy()
    return np.arange(1, len(v) + 1) / len(v), np.cumsum(v) / v.sum()


def tracer_concentration(valeur: pd.Series, cible: pd.Series, part: float = 0.10) -> Figure:
    """Lorenz-type curves: how much value the largest accounts carry, churners apart."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    courbes = (
        ("Tous les comptes", valeur, PALETTE["principal"], "-"),
        ("Comptes qui résilient", valeur[cible == 1], PALETTE["accent"], "--"),
    )
    for libelle, serie, couleur, style in courbes:
        x, y = _part_cumulee(serie)
        ax.plot(x * 100, y * 100, color=couleur, lw=2, ls=style, label=libelle)
        y_ref = np.interp(part, x, y) * 100
        ax.scatter([part * 100], [y_ref], color=couleur, zorder=5, s=40)
        ax.annotate(
            f"{y_ref:.0f} %",
            (part * 100, y_ref),
            textcoords="offset points",
            xytext=(10, -4),
            color=couleur,
            fontweight="bold",
        )
    ax.plot([0, 100], [0, 100], color=PALETTE["neutre"], lw=1, ls=":", label="Répartition égale")
    ax.axvline(part * 100, color=PALETTE["neutre"], lw=0.8, ls="--")
    ax.set_xlabel("Part des comptes, du plus important au moins important (%)")
    ax.set_ylabel("Part du revenu mensuel cumulé (%)")
    ax.set_title("La valeur est concentrée sur une minorité de comptes")
    ax.legend(loc="lower right", fontsize=8.5)
    fig.tight_layout()
    return fig


def tracer_completude(
    profil: pd.DataFrame, seuil_surveillance: float, seuil_critique: float
) -> Figure:
    """Missing rate per column, read against the watch and blocking thresholds.

    `profil` is the output of `donnees.profil_manquants`.
    """
    incompletes = profil.loc[profil["manquants_pct"] > 0].sort_values("manquants_pct")
    couleurs = [
        PALETTE["accent"]
        if v > seuil_critique
        else PALETTE["attention"]
        if v > seuil_surveillance
        else PALETTE["principal"]
        for v in incompletes["manquants_pct"]
    ]
    fig, ax = plt.subplots(figsize=(8.6, 0.42 * len(incompletes) + 1.6))
    ax.barh(range(len(incompletes)), incompletes["manquants_pct"], color=couleurs)
    ax.set_yticks(range(len(incompletes)))
    ax.set_yticklabels(incompletes["colonne"], fontsize=8.5)
    for i, v in enumerate(incompletes["manquants_pct"]):
        ax.text(v + 0.6, i, f"{v:.1f} %", va="center", fontsize=8)
    for seuil, libelle, couleur in (
        (seuil_surveillance, "surveillance", PALETTE["attention"]),
        (seuil_critique, "blocage", PALETTE["accent"]),
    ):
        ax.axvline(seuil, color=couleur, ls="--", lw=1)
        ax.text(seuil + 0.5, len(incompletes) - 0.4, libelle, fontsize=8, color=couleur)
    ax.set_xlabel("Taux de valeurs manquantes (%)")
    ax.set_title("Complétude des colonnes reçues, lue à travers les seuils du contrat")
    ax.set_xlim(0, max(float(incompletes["manquants_pct"].max()) * 1.15, seuil_critique + 5))
    fig.tight_layout()
    return fig


def tracer_compte_abandonne(df: pd.DataFrame, cible: str = "churn") -> Figure:
    """Churn rate of accounts without any active user, against all the others."""
    actifs = pd.to_numeric(df["utilisateurs_actifs"], errors="coerce")
    y = pd.to_numeric(df[cible], errors="coerce")
    groupes = {
        "Au moins un utilisateur actif": y[actifs > 0],
        "Aucun utilisateur actif": y[actifs == 0],
    }
    taux = [g.mean() * 100 for g in groupes.values()]
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    barres = ax.bar(
        list(groupes), taux, color=[PALETTE["principal"], PALETTE["accent"]], width=0.55
    )
    for barre, valeur, groupe in zip(barres, taux, groupes.values(), strict=True):
        ax.text(
            barre.get_x() + barre.get_width() / 2,
            valeur + 1.5,
            f"{valeur:.1f} %\n({len(groupe)} comptes)",
            ha="center",
            fontsize=9,
        )
    ax.axhline(y.mean() * 100, color=PALETTE["neutre"], ls=":", lw=1)
    ax.text(1.32, y.mean() * 100 + 1, "taux global", fontsize=8, color=PALETTE["neutre"])
    ax.set_ylabel("Taux de résiliation (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Un compte payé que personne n'utilise : le signal le plus fort du jeu")
    fig.tight_layout()
    return fig


def tracer_fragmentation(comparaison: pd.DataFrame) -> Figure:
    """Number of categories per column, before and after case normalisation.

    `comparaison` has one row per column: its name, then the counts before and after.
    """
    x = np.arange(len(comparaison))
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.bar(x - 0.2, comparaison["avant"], 0.4, color=PALETTE["accent"], label="Avant")
    ax.bar(x + 0.2, comparaison["après"], 0.4, color=PALETTE["principal"], label="Après")
    for i, (avant, apres) in enumerate(
        zip(comparaison["avant"], comparaison["après"], strict=True)
    ):
        ax.text(i - 0.2, avant + 0.3, str(avant), ha="center", fontsize=8)
        ax.text(i + 0.2, apres + 0.3, str(apres), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(comparaison["colonne"], fontsize=8.5)
    ax.set_ylabel("Nombre de catégories")
    ax.set_title("Une seule orthographe par catégorie : avant et après normalisation")
    ax.legend(fontsize=8.5)
    fig.tight_layout()
    return fig


def tracer_risque_par_segment(
    df: pd.DataFrame, colonnes: list[str], cible: str = "churn"
) -> Figure:
    """Churn rate per category, against the global rate, one panel per column."""
    y = pd.to_numeric(df[cible], errors="coerce")
    fig, axes = plt.subplots(1, len(colonnes), figsize=(4.0 * len(colonnes), 3.8))
    for ax, colonne in zip(np.atleast_1d(axes), colonnes, strict=True):
        taux = (y.groupby(df[colonne]).mean() * 100).sort_values()
        ax.barh(taux.index.astype(str), taux.to_numpy(), color=PALETTE["principal"])
        ax.axvline(y.mean() * 100, color=PALETTE["accent"], ls="--", lw=1)
        ax.set_title(colonne, fontsize=10)
        ax.set_xlabel("Taux de résiliation (%)")
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle("Aucun segment ne concentre le risque (pointillés : taux global)", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_tendances(profils: dict[str, pd.DataFrame], taux_global: float) -> Figure:
    """Churn rate per quantile bucket, one line per variable.

    `profils` maps a variable to the output of `features.tendance_par_tranche`. A line that
    jumps in one extreme bucket and stays flat elsewhere is a threshold effect: monotonic,
    yet poorly described by a straight line.
    """
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    for nom, profil in profils.items():
        ax.plot(range(1, len(profil) + 1), profil["taux (%)"], marker="o", lw=1.8, label=nom)
    ax.axhline(taux_global, color=PALETTE["neutre"], ls=":", lw=1)
    ax.set_xticks(range(1, max(len(p) for p in profils.values()) + 1))
    ax.set_xlabel("Tranche de la variable (1 = valeurs les plus basses)")
    ax.set_ylabel("Taux de résiliation (%)")
    ax.set_title("Des effets de seuil plutôt que des droites")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


# --- Phase 5 · Validating the split and the dataset ---------------------------------------
def tracer_psi(rapport: pd.DataFrame, seuil: float) -> Figure:
    """Per-variable stability index between training and test parts, against its threshold.

    Titles here describe, they do not conclude: the reading belongs to the notebook text,
    which states it against the rule fixed beforehand.

    `rapport` is the output of `monitoring.rapport_derive`.
    """
    donnees = rapport.sort_values("psi")
    couleurs = [PALETTE["accent"] if v > seuil else PALETTE["principal"] for v in donnees["psi"]]
    fig, ax = plt.subplots(figsize=(7.6, 0.28 * len(donnees) + 1.4))
    ax.barh(donnees["variable"], donnees["psi"], color=couleurs)
    ax.axvline(seuil, color=PALETTE["accent"], ls="--", lw=1)
    ax.text(seuil, len(donnees) - 0.5, f" seuil {seuil:.2f}", color=PALETTE["accent"], fontsize=8)
    ax.set_xlim(0, max(seuil * 1.4, float(donnees["psi"].max()) * 1.2))
    ax.set_xlabel("Indice de stabilité (PSI) entre entraînement et test")
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("Stabilité de chaque variable entre entraînement et test")
    fig.tight_layout()
    return fig


def tracer_validation_adverse(taux_faux: np.ndarray, taux_vrais: np.ndarray, auc: float) -> Figure:
    """ROC curve of a classifier asked to tell training rows from test rows."""
    fig, ax = plt.subplots(figsize=(5.0, 4.4))
    ax.plot(taux_faux, taux_vrais, color=PALETTE["principal"], lw=2, label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], color=PALETTE["neutre"], ls=":", lw=1, label="Hasard (0,5)")
    ax.set_xlabel("Taux de faux positifs")
    ax.set_ylabel("Taux de vrais positifs")
    ax.set_title("Validation adverse : distinguer l'entraînement du test")
    ax.legend(loc="lower right", fontsize=8.5)
    fig.tight_layout()
    return fig


def tracer_permutation(scores_permutes: np.ndarray, score: float, taux_base: float) -> Figure:
    """Scores obtained on shuffled labels, against the score on the real labels."""
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.hist(
        scores_permutes, bins=20, color=PALETTE["neutre"], alpha=0.8, label="Étiquettes mélangées"
    )
    ax.axvline(score, color=PALETTE["accent"], lw=2, label=f"Étiquettes réelles : {score:.3f}")
    ax.axvline(
        taux_base,
        color=PALETTE["principal"],
        ls=":",
        lw=1.2,
        label=f"Taux de base : {taux_base:.2f}",
    )
    ax.set_xlabel("PR-AUC en validation croisée")
    ax.set_ylabel("Nombre de mélanges")
    ax.set_title("Test de permutation des étiquettes")
    ax.legend(fontsize=8.5)
    fig.tight_layout()
    return fig


def tracer_courbes_apprentissage(courbes: dict[str, pd.DataFrame]) -> Figure:
    """Training and validation PR-AUC by training size, one panel per model.

    `courbes` maps a model name to the output of `modelisation.courbe_apprentissage`.
    """
    fig, axes = plt.subplots(1, len(courbes), figsize=(5.2 * len(courbes), 3.9), sharey=True)
    for ax, (nom, courbe) in zip(np.atleast_1d(axes), courbes.items(), strict=True):
        effectifs = courbe["comptes d'entraînement"]
        ax.plot(
            effectifs,
            courbe["PR-AUC entraînement"],
            marker="o",
            color=PALETTE["neutre"],
            label="Entraînement",
        )
        ax.plot(
            effectifs,
            courbe["PR-AUC validation"],
            marker="o",
            color=PALETTE["principal"],
            label="Validation",
        )
        ax.fill_between(
            effectifs,
            courbe["PR-AUC validation"] - courbe["écart-type validation"],
            courbe["PR-AUC validation"] + courbe["écart-type validation"],
            color=PALETTE["principal"],
            alpha=0.15,
        )
        ax.set_title(nom, fontsize=10)
        ax.set_xlabel("Comptes d'entraînement")
        ax.legend(fontsize=8)
    np.atleast_1d(axes)[0].set_ylabel("PR-AUC")
    fig.suptitle("Courbes d'apprentissage (PR-AUC, validation croisée à 5 plis)", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_valeur_vie_par_anciennete(
    df: pd.DataFrame, tranches: int = 5, cible: str = "churn"
) -> Figure:
    """Lifetime value in months of revenue, by seniority bucket, leavers against stayers.

    If the value encoded the outcome, leavers would sit below stayers within every bucket.
    If the overall gap is a composition effect, the two lines merge once seniority is fixed.
    """
    mois = pd.to_numeric(df["valeur_vie_client_eur"], errors="coerce") / pd.to_numeric(
        df["revenu_mensuel_recurrent_eur"], errors="coerce"
    )
    anciennete = pd.to_numeric(df["anciennete_mois"], errors="coerce")
    tranche = pd.qcut(anciennete, tranches, labels=False, duplicates="drop") + 1
    issue = pd.to_numeric(df[cible], errors="coerce")
    medianes = mois.groupby([tranche, issue]).median().unstack()
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.plot(medianes.index, medianes[0], marker="o", color=PALETTE["principal"], label="Restent")
    ax.plot(medianes.index, medianes[1], marker="o", color=PALETTE["accent"], label="Partent")
    ax.set_xticks(list(medianes.index))
    ax.set_xlabel("Tranche d'ancienneté (1 = comptes les plus récents)")
    ax.set_ylabel("Valeur vie client, en mois de revenu (médiane)")
    ax.set_title("Valeur vie client par ancienneté, selon l'issue")
    ax.legend(fontsize=8.5)
    fig.tight_layout()
    return fig


def tracer_charge_calcul(charge: pd.DataFrame) -> Figure:
    """Seconds of computation per planned step, from `modelisation.estimer_charge`."""
    donnees = charge.sort_values("secondes")
    fig, ax = plt.subplots(figsize=(7.6, 0.42 * len(donnees) + 1.4))
    ax.barh(donnees["étape"], donnees["secondes"] / 60, color=PALETTE["principal"])
    for i, v in enumerate(donnees["secondes"] / 60):
        ax.text(v, i, f" {v:.1f}", va="center", fontsize=8)
    ax.set_xlabel("Minutes de calcul sur le poste de développement")
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("Charge de calcul de la phase 5, étape par étape")
    fig.tight_layout()
    return fig


# --- Phase 5 · Blocs B and C: what the variables bring ---------------------------------------
def tracer_courbes_appariees(
    scores: dict[str, pd.DataFrame], reference: str, candidat: str
) -> Figure:
    """One line per fold, from the reference set to the candidate set, one panel per model.

    Lines going up everywhere mean a systematic gain; lines crossing mean the difference is
    the split's, not the variables'. `scores` maps a model to `selection.comparer_jeux`.
    """
    fig, axes = plt.subplots(1, len(scores), figsize=(4.6 * len(scores), 4.0), sharey=True)
    for ax, (nom, table) in zip(np.atleast_1d(axes), scores.items(), strict=True):
        for _, ligne in table.iterrows():
            couleur = (
                PALETTE["principal"] if ligne[candidat] > ligne[reference] else PALETTE["accent"]
            )
            ax.plot([0, 1], [ligne[reference], ligne[candidat]], color=couleur, alpha=0.5, lw=1)
        ax.plot(
            [0, 1],
            [table[reference].mean(), table[candidat].mean()],
            color="black",
            lw=2.5,
            marker="o",
            label="Moyenne",
        )
        ax.set_xticks([0, 1])
        ax.set_xticklabels([reference, candidat], fontsize=8.5)
        ax.set_xlim(-0.2, 1.2)
        ax.set_title(nom, fontsize=10)
        ax.legend(fontsize=8)
    np.atleast_1d(axes)[0].set_ylabel("PR-AUC du pli")
    fig.suptitle("Comparaison appariée, pli par pli (bleu : le candidat gagne)", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_ablation(tables: dict[str, pd.DataFrame]) -> Figure:
    """PR-AUC lost when each family is removed, with its spread, one panel per model."""
    fig, axes = plt.subplots(1, len(tables), figsize=(4.8 * len(tables), 3.8), sharey=True)
    for ax, (nom, table) in zip(np.atleast_1d(axes), tables.items(), strict=True):
        donnees = table.sort_values("perte moyenne")
        couleurs = [
            PALETTE["accent"] if s else PALETTE["neutre"] for s in donnees["perte significative"]
        ]
        ax.barh(
            donnees["groupe"],
            donnees["perte moyenne"],
            xerr=donnees["écart-type de la perte"],
            color=couleurs,
            capsize=3,
        )
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(nom, fontsize=10)
        ax.set_xlabel("PR-AUC perdue sans la famille")
    fig.suptitle("Ablation par famille de variables (rouge : perte significative)", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_importances(importances: pd.DataFrame, leurres: list[str], titre: str) -> Figure:
    """Permutation importance per variable across folds, decoys and their floor highlighted.

    `importances` is the long table of `selection.importances_par_permutation`.
    """
    ordre = importances.groupby("variable")["importance"].mean().sort_values().index
    plancher = (
        importances[importances["variable"].isin(leurres)]
        .groupby("variable")["importance"]
        .mean()
        .max()
    )
    fig, ax = plt.subplots(figsize=(7.6, 0.3 * len(ordre) + 1.4))
    donnees = [importances.loc[importances["variable"] == v, "importance"] for v in ordre]
    boites = ax.boxplot(donnees, orientation="horizontal", patch_artist=True, showfliers=False)
    for boite, variable in zip(boites["boxes"], ordre, strict=True):
        boite.set_facecolor(PALETTE["accent"] if variable in leurres else PALETTE["principal"])
        boite.set_alpha(0.7)
    ax.set_yticks(range(1, len(ordre) + 1))
    ax.set_yticklabels(ordre, fontsize=8)
    ax.axvline(plancher, color=PALETTE["accent"], ls="--", lw=1)
    ax.text(
        plancher, len(ordre) + 0.3, " plancher des leurres", color=PALETTE["accent"], fontsize=8
    )
    ax.set_xlabel("Perte de PR-AUC quand la variable est mélangée")
    ax.set_title(titre)
    fig.tight_layout()
    return fig


def tracer_demonstration_fuite(tables: dict[str, pd.DataFrame]) -> Figure:
    """AUC and PR-AUC without, then with, the leaking variable, one panel per model.

    `tables` maps a model to the output of `modelisation.demontrer_fuite`.
    """
    fig, axes = plt.subplots(1, len(tables), figsize=(4.6 * len(tables), 3.8), sharey=True)
    for ax, (nom, table) in zip(np.atleast_1d(axes), tables.items(), strict=True):
        x = np.arange(len(table))
        for decalage, metrique, couleur in (
            (-0.2, "AUC", PALETTE["principal"]),
            (0.2, "PR-AUC", PALETTE["attention"]),
        ):
            barres = ax.bar(x + decalage, table[metrique], 0.4, color=couleur, label=metrique)
            for barre, valeur in zip(barres, table[metrique], strict=True):
                ax.text(
                    barre.get_x() + barre.get_width() / 2,
                    valeur + 0.01,
                    f"{valeur:.3f}",
                    ha="center",
                    fontsize=8,
                )
        ax.set_xticks(x)
        ax.set_xticklabels(table["jeu"], fontsize=8)
        ax.set_ylim(0.5, 1.08)
        ax.set_title(nom, fontsize=10)
        ax.legend(fontsize=8, loc="lower right")
    fig.suptitle(
        "Avec une variable connue après la décision, le modèle « devine » l'issue", fontsize=11
    )
    fig.tight_layout()
    return fig


# --- Phase 6: baselines and evaluation protocol ---------------------------------------------
def tracer_courbes_pr_roc(predictions: dict[str, tuple[pd.Series, pd.Series]]) -> Figure:
    """Precision-recall and ROC curves, one line per model, from out-of-fold predictions."""
    from sklearn.metrics import average_precision_score, precision_recall_curve, roc_curve

    fig, (ax_pr, ax_roc) = plt.subplots(1, 2, figsize=(10.4, 4.2))
    couleurs = [PALETTE["neutre"], PALETTE["attention"], PALETTE["principal"], PALETTE["accent"]]
    for (nom, (y, score)), couleur in zip(predictions.items(), couleurs, strict=False):
        libelle = f"{nom} ({average_precision_score(y, score):.3f})"
        if pd.Series(score).nunique() == 1:
            # A constant score has a single operating point; joining it to (0, 1) would draw a
            # diagonal no threshold reaches. Its true curve is flat at the base rate.
            ax_pr.hlines(float(np.mean(y)), 0, 1, color=couleur, lw=2, label=libelle)
        else:
            precision, rappel, _ = precision_recall_curve(y, score)
            ax_pr.plot(rappel, precision, color=couleur, lw=2, label=libelle)
        faux, vrais, _ = roc_curve(y, score)
        ax_roc.plot(faux, vrais, color=couleur, lw=2, label=nom)
    ax_roc.plot([0, 1], [0, 1], color=PALETTE["neutre"], ls=":", lw=1)
    ax_pr.set_xlabel("Rappel")
    ax_pr.set_ylabel("Précision")
    ax_pr.set_title("Courbe précision-rappel (PR-AUC entre parenthèses)")
    ax_roc.set_xlabel("Taux de faux positifs")
    ax_roc.set_ylabel("Taux de vrais positifs")
    ax_roc.set_title("Courbe ROC")
    ax_pr.legend(fontsize=8)
    ax_roc.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    return fig


def tracer_calibration(
    predictions: dict[str, tuple[pd.Series, pd.Series]], tranches: int = 10
) -> Figure:
    """Observed churn rate against announced probability, by probability bucket."""
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    ax.plot([0, 1], [0, 1], color=PALETTE["neutre"], ls=":", lw=1, label="Calibration parfaite")
    couleurs = [PALETTE["principal"], PALETTE["accent"], PALETTE["attention"]]
    for (nom, (y, proba)), couleur in zip(predictions.items(), couleurs, strict=False):
        donnees = pd.DataFrame(
            {"y": np.asarray(y, dtype=float), "p": np.asarray(proba, dtype=float)}
        )
        donnees["tranche"] = pd.cut(
            donnees["p"], np.linspace(0, 1, tranches + 1), include_lowest=True
        )
        points = donnees.groupby("tranche", observed=True).agg(p=("p", "mean"), y=("y", "mean"))
        ax.plot(points["p"], points["y"], marker="o", color=couleur, lw=1.8, label=nom)
    ax.set_xlabel("Probabilité annoncée (moyenne de la tranche)")
    ax.set_ylabel("Taux de churn observé")
    ax.set_title("Calibration des probabilités")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def tracer_baselines(par_pli: dict[str, pd.DataFrame], metrique: str = "PR-AUC") -> Figure:
    """Distribution of one metric over the 25 folds, one box per baseline."""
    noms = list(par_pli)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    boites = ax.boxplot(
        [par_pli[n][metrique] for n in noms],
        orientation="horizontal",
        patch_artist=True,
        showfliers=False,
    )
    for boite in boites["boxes"]:
        boite.set_facecolor(PALETTE["principal"])
        boite.set_alpha(0.6)
    ax.set_yticks(range(1, len(noms) + 1))
    ax.set_yticklabels(noms)
    ax.set_xlabel(f"{metrique} sur les 25 plis")
    ax.set_title(f"Les trois références : {metrique}")
    fig.tight_layout()
    return fig


def tracer_facteurs_compares(parts: pd.DataFrame, n: int = 10) -> Figure:
    """Share of each model's attribution per variable, for the n most important on average.

    `parts` has one column per model (SHAP shares summing to 1). Shares rather than raw
    SHAP values: the families explain on different scales (log-odds, probability).
    """
    ordre = parts.mean(axis=1).sort_values(ascending=False).head(n).index[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 0.45 * n + 1.2))
    hauteur = 0.8 / len(parts.columns)
    couleurs = [PALETTE["principal"], PALETTE["accent"], PALETTE.get("neutre", "#7a7a7a")]
    for k, modele in enumerate(parts.columns):
        positions = [i + (k - (len(parts.columns) - 1) / 2) * hauteur for i in range(len(ordre))]
        ax.barh(
            positions,
            parts.loc[ordre, modele],
            height=hauteur,
            color=couleurs[k % len(couleurs)],
            label=modele,
        )
    ax.set_yticks(range(len(ordre)), ordre)
    ax.set_xlabel("Part de l'attribution totale du modèle (SHAP)")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Sur quoi chaque modèle s'appuie-t-il ?", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_courbe_validation(points: pd.DataFrame, retenu: float) -> Figure:
    """Training and validation PR-AUC along the regularisation C (rule S2).

    `points` holds one row per value of C, with its training and validation PR-AUC. The
    gap between the two curves is what overfitting would widen; a flat validation curve
    says the regularisation hardly matters.
    """
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(
        points["C"],
        points["PR-AUC entraînement"],
        marker="o",
        color=PALETTE["accent"],
        label="entraînement",
    )
    ax.plot(
        points["C"],
        points["PR-AUC validation"],
        marker="o",
        color=PALETTE["principal"],
        label="validation (25 plis)",
    )
    ax.axvline(retenu, color="#7a7a7a", linestyle=":", label=f"retenu par P1 (C = {retenu:g})")
    ax.set_xscale("log")
    ax.set_xlabel("C (plus petit = plus régularisé)")
    ax.set_ylabel("PR-AUC")
    ax.legend(frameon=False)
    ax.set_title("Courbe de validation de la régression logistique", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_seuils(seuils: list[float] | pd.Series) -> Figure:
    """Distribution of the per-account rational thresholds (rule R3), on a log scale."""
    import numpy as np

    seuils = np.asarray(seuils, dtype=float)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(
        seuils,
        bins=np.logspace(np.log10(seuils.min()), np.log10(seuils.max()), 40),
        color=PALETTE["principal"],
    )
    ax.axvline(
        float(np.median(seuils)),
        color=PALETTE["accent"],
        linestyle="--",
        label=f"médiane {np.median(seuils):.3f}",
    )
    ax.set_xscale("log")
    ax.set_xlabel("Seuil de probabilité au-delà duquel contacter le compte est rentable")
    ax.set_ylabel("Comptes")
    ax.legend(frameon=False)
    ax.set_title("Un seuil par compte : il dépend de ce que le compte rapporte", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_niveaux_mrr(mrr: dict) -> Figure:
    """Exposed, covered and preserved monthly recurring revenue (rule R8), with intervals,
    for each operating point. `mrr` maps a point to its three levels."""
    niveaux = ("exposé", "couvert", "préservé")
    points = [p for p in mrr if isinstance(mrr[p], dict)]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    largeur = 0.8 / len(points)
    couleurs = [PALETTE["principal"], PALETTE["accent"]]
    for k, point in enumerate(points):
        valeurs = [mrr[point][n]["€ par mois (test)"] / 1000 for n in niveaux]
        bas = [
            v - mrr[point][n]["intervalle_95"][0] / 1000
            for v, n in zip(valeurs, niveaux, strict=True)
        ]
        haut = [
            mrr[point][n]["intervalle_95"][1] / 1000 - v
            for v, n in zip(valeurs, niveaux, strict=True)
        ]
        positions = [i + (k - (len(points) - 1) / 2) * largeur for i in range(len(niveaux))]
        ax.bar(
            positions,
            valeurs,
            width=largeur,
            yerr=[bas, haut],
            capsize=3,
            color=couleurs[k % 2],
            label=point,
        )
    ax.set_xticks(range(len(niveaux)), niveaux)
    ax.set_ylabel("k€ de revenu récurrent par mois (jeu de test)")
    ax.legend(frameon=False)
    ax.set_title("Revenu exposé, couvert par la liste, préservé par l'action", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_equite(lignes: list[dict], rappel_global: float, ratio: float) -> Figure:
    """Recall by segment with its interval, against the global recall and the fairness
    threshold (rule R9). Inconclusive segments are drawn hollow."""
    table = pd.DataFrame(lignes)
    table = table[table["intervalle du rappel"].notna()].reset_index(drop=True)
    etiquettes = table["segment"] + " · " + table["modalité"]
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(table) + 1.4))
    for i, ligne in table.iterrows():
        bas, haut = ligne["intervalle du rappel"]
        couleur = (
            PALETTE["principal"] if ligne["critère respecté"] is not False else PALETTE["accent"]
        )
        ax.plot([bas, haut], [i, i], color=couleur)
        ax.plot(
            ligne["rappel"],
            i,
            "o",
            color=couleur,
            markerfacecolor=couleur if ligne["concluant"] else "white",
        )
    ax.axvline(rappel_global, color="#555555", label=f"rappel global {rappel_global:.2f}")
    ax.axvline(
        ratio * rappel_global,
        color="#999999",
        linestyle=":",
        label=f"seuil d'équité ({ratio:g} × global)",
    )
    ax.set_yticks(range(len(table)), etiquettes)
    ax.set_xlabel("Rappel au point protocole (intervalle à 95 %)")
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Le modèle détecte-t-il les départs aussi bien dans chaque segment ?", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_importance_test(importances: list[dict]) -> Figure:
    """Permutation importance on the test part (rule R10): mean drop of PR-AUC and its
    interval; variables whose interval reaches zero are drawn hollow."""
    table = pd.DataFrame(importances).sort_values("baisse moyenne de PR-AUC")
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(table) + 1.2))
    for i, (_, ligne) in enumerate(table.iterrows()):
        ax.plot(
            [ligne["borne basse 95 %"], ligne["borne haute 95 %"]],
            [i, i],
            color=PALETTE["principal"],
        )
        ax.plot(
            ligne["baisse moyenne de PR-AUC"],
            i,
            "o",
            color=PALETTE["principal"],
            markerfacecolor=PALETTE["principal"]
            if ligne["apport démontré sur le test"]
            else "white",
        )
    ax.axvline(0, color="#999999", linestyle=":")
    ax.set_yticks(range(len(table)), table["variable"])
    ax.set_xlabel("Baisse de PR-AUC quand la variable est mélangée (test, 30 répétitions)")
    ax.set_title("Importance par permutation sur le jeu de test", fontsize=11)
    fig.tight_layout()
    return fig


# --- Phase 11 · Monthly monitoring --------------------------------------------------------
# Three months, three categorical slots in fixed order: the reference palette's first three
# hues, validated all-pairs (colour-vision deficiencies included). Red and orange status
# colours stay reserved for alerts: thresholds are drawn in grey ink and labelled.
SERIES_MOIS = ("#2a78d6", "#eb6834", "#1baf7a")
ENCRE, ENCRE_SECONDAIRE, CONTEXTE = "#0b0b0b", "#52514e", "#c3c2b7"


def _mois(identifiant: str) -> str:
    """Month identifier as the reader sees it: underscores to spaces, French accent restored."""
    return identifiant.replace("_", " ").replace("derive", "dérive")


def _virgule(valeur: float, decimales: int = 3) -> str:
    return f"{valeur:.{decimales}f}".replace(".", ",")


_AXE_VIRGULE = plt.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


def _seuil(ax, valeur: float, texte: str, horizontal: bool = True) -> None:
    trace = ax.axhline if horizontal else ax.axvline
    trace(valeur, color=ENCRE_SECONDAIRE, ls="--", lw=1)
    if horizontal:
        ax.text(
            1.0,
            valeur,
            f" {texte}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=8,
            color=ENCRE_SECONDAIRE,
        )
    else:
        ax.text(
            valeur,
            1.0,
            f" {texte}",
            transform=ax.get_xaxis_transform(),
            va="bottom",
            fontsize=8,
            color=ENCRE_SECONDAIRE,
        )


def tracer_evolution_psi(
    mois: list[dict], variables_cles: list[str], suivie: str, seuils: tuple[float, float]
) -> Figure:
    """M5 month after month: the PSI of the key variables and of the score, with the two
    thresholds. `mois` is `resultats/suivi_simule.json`'s list; `suivie` is highlighted."""
    etiquettes = [_mois(m["mois"]) for m in mois]
    x = np.arange(len(mois))
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    for variable in variables_cles:
        valeurs = [m["M5_derive"]["psi"][variable] for m in mois]
        mise_en_avant = variable == suivie
        ax.plot(
            x,
            valeurs,
            marker="o",
            ms=8 if mise_en_avant else 5,
            lw=2 if mise_en_avant else 1.2,
            color=SERIES_MOIS[0] if mise_en_avant else CONTEXTE,
            zorder=3 if mise_en_avant else 2,
            label=variable,
        )
        if mise_en_avant:
            ax.annotate(
                _virgule(valeurs[-1]),
                (x[-1], valeurs[-1]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
                color=ENCRE,
            )
    score = [m["M5_derive"]["verdict"]["psi du score"] for m in mois]
    ax.plot(x, score, marker="s", ms=7, lw=2, ls="-", color=SERIES_MOIS[1], label="score", zorder=3)
    ax.annotate(
        f"score {_virgule(score[-1])}",
        (x[-1], score[-1]),
        xytext=(6, -10),
        textcoords="offset points",
        fontsize=9,
        color=ENCRE,
    )
    modere, cle = seuils
    _seuil(ax, modere, f"{_virgule(modere, 2)} : trois variables, ou le score")
    _seuil(ax, cle, f"{_virgule(cle, 2)} : une variable clé")
    ax.yaxis.set_major_formatter(_AXE_VIRGULE)
    ax.set_xticks(x, etiquettes)
    ax.set_ylim(0, max(cle * 1.3, max(score) * 1.2, ax.get_ylim()[1]))
    ax.set_ylabel("PSI contre le profil de référence")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e6e3", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title(
        "Dérive des variables clés et du score, mois après mois (M5) — SIMULÉ", fontsize=11
    )
    fig.tight_layout()
    return fig


def tracer_carte_psi(mois: list[dict]) -> Figure:
    """Every model variable's PSI, one column per month: one hue, light to dark."""
    table = pd.DataFrame({_mois(m["mois"]): m["M5_derive"]["psi"] for m in mois})
    table = table.loc[table.max(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(6.4, 0.3 * len(table) + 1.4))
    image = ax.imshow(
        table.to_numpy(),
        cmap="Blues",
        vmin=0,
        vmax=max(0.25, float(table.max().max())),
        aspect="auto",
    )
    for (i, j), valeur in np.ndenumerate(table.to_numpy()):
        ax.text(
            j,
            i,
            _virgule(valeur),
            ha="center",
            va="center",
            fontsize=7,
            color="white" if valeur > 0.15 else ENCRE,
        )
    ax.set_xticks(range(table.shape[1]), table.columns, fontsize=8)
    ax.set_yticks(range(len(table)), table.index, fontsize=8)
    fig.colorbar(image, ax=ax, shrink=0.6, label="PSI")
    ax.set_title("PSI de chaque variable, par mois — SIMULÉ", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_deciles(bornes: list[float], parts: dict[str, list[float]], variable: str) -> Figure:
    """Shares of one variable in the reference profile's bins: the reference, then each
    batch - what the PSI compares, drawn. `parts` maps a label to its shares, in order."""
    etiquettes = (
        [f"≤ {bornes[0]:g}"]
        + [f"{a:g} – {b:g}" for a, b in zip(bornes[:-1], bornes[1:], strict=True)]
        + [f"> {bornes[-1]:g}"]
    )
    x = np.arange(len(etiquettes))
    largeur = 0.8 / len(parts)
    couleurs = [CONTEXTE, *SERIES_MOIS]
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    for k, (nom, valeurs) in enumerate(parts.items()):
        ax.bar(
            x + (k - (len(parts) - 1) / 2) * largeur,
            valeurs,
            width=largeur * 0.92,
            color=couleurs[k],
            label=nom,
        )
    ax.set_xticks(x, etiquettes, fontsize=8)
    ax.set_xlabel(f"{variable} — tranches du profil de référence (jours)")
    ax.set_ylabel("Part des comptes")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e6e3", lw=0.6)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"Répartition de {variable} : référence et lots — SIMULÉ", fontsize=11)
    fig.tight_layout()
    return fig


def tracer_manquants(mois: list[dict], facteur: float) -> Figure:
    """M8: each variable's missing share per month, against its threshold (twice training)."""
    lignes = {
        m["mois"]: pd.DataFrame(m["M8_manquants"]["table"]).set_index("variable") for m in mois
    }
    reference = next(iter(lignes.values()))
    variables = reference.index[reference["part à l'entraînement"] > 0].tolist()
    variables += [v for t in lignes.values() for v in t.index[t["alerte"]] if v not in variables]
    fig, ax = plt.subplots(figsize=(8.4, 0.42 * len(variables) + 1.6))
    y = np.arange(len(variables))
    seuils = reference.loc[variables, "seuil"]
    ax.scatter(
        seuils,
        y,
        marker="|",
        s=260,
        color=ENCRE,
        label=f"seuil ({facteur:g} × entraînement)",
        zorder=2,
    )
    for k, (nom, table) in enumerate(lignes.items()):
        ax.scatter(
            table.loc[variables, "part du lot"],
            y + (k - 1) * 0.18,
            s=40,
            color=SERIES_MOIS[k],
            label=_mois(nom),
            zorder=3,
            edgecolors="white",
            linewidths=1,
        )
    ax.set_yticks(y, variables, fontsize=8)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Part d'absents à l'entrée")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#e6e6e3", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Manquants à l'entrée contre leur seuil (M8) — SIMULÉ", fontsize=11)
    fig.tight_layout()
    return fig
