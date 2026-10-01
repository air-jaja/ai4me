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
