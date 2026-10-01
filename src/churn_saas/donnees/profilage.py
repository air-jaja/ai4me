"""Data profiling: missing values, duplicates, distributions, missingness mechanism.

Profiling is not a formality preceding the real work: it is what decides the real work.
The imputation strategy, the choice of metric and the handling of extreme values all
follow from what this step finds - or fail to follow from anything, if it is skipped.

Each function returns a table rather than printing one. The notebook decides how to show
it, and a test can assert on it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Reading grid for the missingness rate. The thresholds are conventions, stated here so
# the notebook does not restate them and so a test can rely on them.
SEUIL_MANQUANTS_SURVEILLANCE = 10.0
SEUIL_MANQUANTS_CRITIQUE = 50.0


def profil_manquants(df: pd.DataFrame) -> pd.DataFrame:
    """Missing rate per column, with a verdict drawn from the thresholds above."""
    taux = (df.isna().mean() * 100).round(2)
    lignes = [
        {
            "colonne": colonne,
            "manquants": int(df[colonne].isna().sum()),
            "manquants_pct": float(valeur),
            "verdict": (
                "écarter ou traiter à part"
                if valeur > SEUIL_MANQUANTS_CRITIQUE
                else "à surveiller"
                if valeur > SEUIL_MANQUANTS_SURVEILLANCE
                else "imputable"
                if valeur > 0
                else "complète"
            ),
        }
        for colonne, valeur in taux.items()
    ]
    profil = pd.DataFrame(lignes).sort_values("manquants_pct", ascending=False)
    return profil.reset_index(drop=True)


def profil_doublons(df: pd.DataFrame, cle: str | None = None) -> pd.DataFrame:
    """Strict duplicates, and duplicates on the business key when one is given.

    The two counts answer different questions. Strict duplicates are an export accident.
    Duplicates on the key alone mean the same account appears twice with differing values,
    which no deduplication can resolve without a business rule.
    """
    lignes = [
        {
            "contrôle": "Lignes strictement identiques",
            "nombre": int(df.duplicated().sum()),
            "conséquence": (
                "Le modèle apprend deux fois le même exemple et ses métriques sont flattées"
            ),
        }
    ]
    if cle and cle in df.columns:
        doublons_cle = int(df.duplicated(subset=[cle]).sum())
        lignes.append(
            {
                "contrôle": f"Doublons sur la clé `{cle}`",
                "nombre": doublons_cle,
                "conséquence": (
                    "Même compte présent plusieurs fois avec des valeurs différentes : "
                    "aucune déduplication automatique n'est possible"
                    if doublons_cle
                    else "Aucun : la clé identifie bien un compte unique"
                ),
            }
        )
    return pd.DataFrame(lignes)


def profil_distributions(df: pd.DataFrame, colonnes: list[str] | None = None) -> pd.DataFrame:
    """Shape of every numeric distribution, read through the mean/median gap.

    The ratio is the column that matters: a mean far above the median signals a heavy
    right tail, which changes both the imputation choice - median rather than mean - and
    the way the figures may be summarised in a deliverable.
    """
    numeriques = colonnes or df.select_dtypes(include="number").columns.tolist()
    lignes = []
    for colonne in numeriques:
        serie = pd.to_numeric(df[colonne], errors="coerce").dropna()
        if serie.empty:
            continue
        mediane = float(serie.median())
        moyenne = float(serie.mean())
        lignes.append(
            {
                "colonne": colonne,
                "min": round(float(serie.min()), 2),
                "médiane": round(mediane, 2),
                "moyenne": round(moyenne, 2),
                "max": round(float(serie.max()), 2),
                "moyenne/médiane": round(moyenne / mediane, 2) if mediane else float("nan"),
                "asymétrie": round(float(serie.skew()), 2),
            }
        )
    profil = pd.DataFrame(lignes)
    if not profil.empty:
        profil = profil.sort_values("asymétrie", ascending=False, key=abs).reset_index(drop=True)
    return profil


def mecanisme_manquants(
    df: pd.DataFrame,
    cible: str,
    colonnes: list[str] | None = None,
    effectif_minimal: int = 30,
) -> pd.DataFrame:
    """Test whether a value being absent is itself informative.

    Two readings, and both are needed:

    - the gap in target rate between rows where the column is present and where it is
      missing. A wide gap would mean the absence carries a signal, to be kept as an
      indicator rather than filled in;
    - the share of missing rows that also show the plausible structural cause. If a
      support delay were missing only when no ticket exists, the absence would be
      structural, not random - and imputing it would invent a delay that never occurred.

    When neither reading shows anything, the data are missing completely at random and a
    statistical imputation is both legitimate and sufficient.
    """
    valeurs_cible = pd.to_numeric(df[cible], errors="coerce")
    taux_global = float(valeurs_cible.mean())
    candidats = colonnes or [c for c in df.columns if c != cible and df[c].isna().any()]

    lignes = []
    for colonne in candidats:
        absent = df[colonne].isna()
        if int(absent.sum()) < effectif_minimal:
            continue
        taux_present = float(valeurs_cible[~absent].mean())
        taux_absent = float(valeurs_cible[absent].mean())
        lignes.append(
            {
                "colonne": colonne,
                "manquants": int(absent.sum()),
                "cible si renseignée": round(taux_present * 100, 1),
                "cible si absente": round(taux_absent * 100, 1),
                "écart (points)": round((taux_absent - taux_present) * 100, 1),
            }
        )
    profil = pd.DataFrame(lignes)
    if not profil.empty:
        profil["taux global (%)"] = round(taux_global * 100, 1)
        profil = profil.reindex(
            profil["écart (points)"].abs().sort_values(ascending=False).index
        ).reset_index(drop=True)
    return profil


def manquants_structurels(
    df: pd.DataFrame, couples: dict[str, str], valeur_neutre: float = 0
) -> pd.DataFrame:
    """Check whether a missing value coincides with a plausible structural cause.

    `couples` maps a column to the one that could explain its absence - a support delay
    to the ticket count, say. When the share of missing rows carrying the cause matches
    the base rate, the absence has nothing structural about it.
    """
    lignes = []
    for colonne, explicative in couples.items():
        if colonne not in df.columns or explicative not in df.columns:
            continue
        absent = df[colonne].isna()
        if not absent.any():
            continue
        cause = pd.to_numeric(df[explicative], errors="coerce") == valeur_neutre
        part_parmi_absents = float((absent & cause).sum() / absent.sum())
        part_de_base = float(cause.mean())
        lignes.append(
            {
                "colonne": colonne,
                "cause envisagée": f"{explicative} = {valeur_neutre:g}",
                "manquants": int(absent.sum()),
                "part portant la cause (%)": round(part_parmi_absents * 100, 1),
                "part de base (%)": round(part_de_base * 100, 1),
                "structurel": bool(part_parmi_absents > part_de_base * 1.5),
            }
        )
    return pd.DataFrame(lignes)


def resume_profilage(df: pd.DataFrame, cible: str, cle: str | None = None) -> pd.DataFrame:
    """One-line-per-finding summary, meant to open the exploration section."""
    manquants = profil_manquants(df)
    concernees = manquants.loc[manquants["manquants_pct"] > 0]
    numeriques = profil_distributions(df)
    asymetriques = (
        numeriques.loc[numeriques["moyenne/médiane"].abs() > 2]
        if not numeriques.empty
        else numeriques
    )
    return pd.DataFrame(
        [
            {"constat": "Lignes", "valeur": f"{len(df):,}".replace(",", " ")},
            {"constat": "Colonnes", "valeur": str(df.shape[1])},
            {"constat": "Lignes strictement dupliquées", "valeur": str(int(df.duplicated().sum()))},
            {"constat": "Colonnes incomplètes", "valeur": f"{len(concernees)} sur {df.shape[1]}"},
            {
                "constat": "Manquants les plus élevés",
                "valeur": (
                    f"{concernees.iloc[0]['colonne']} ({concernees.iloc[0]['manquants_pct']:.1f} %)"
                    if len(concernees)
                    else "aucun"
                ),
            },
            {
                "constat": "Distributions fortement asymétriques",
                "valeur": f"{len(asymetriques)} colonnes (moyenne > 2 × médiane)",
            },
            {
                "constat": "Taux de la cible",
                "valeur": f"{pd.to_numeric(df[cible], errors='coerce').mean():.1%}",
            },
            {
                "constat": "Clé métier unique",
                "valeur": (
                    "oui" if cle and cle in df.columns and not df[cle].duplicated().any() else "—"
                ),
            },
        ]
    )


def indice_asymetrie(serie: pd.Series) -> float:
    """Fisher skewness, exposed so the notebook does not import pandas internals."""
    return float(pd.to_numeric(serie, errors="coerce").dropna().skew())


def bornes_valeurs_extremes(serie: pd.Series, facteur: float = 1.5) -> tuple[float, float]:
    """Tukey bounds, given for reference only.

    They are deliberately not used to remove rows: on this portfolio the extreme values
    are real - the largest accounts - and dropping them would remove exactly the customers
    the project exists to protect.
    """
    valeurs = pd.to_numeric(serie, errors="coerce").dropna()
    q1, q3 = np.percentile(valeurs, [25, 75])
    ecart = q3 - q1
    return float(q1 - facteur * ecart), float(q3 + facteur * ecart)
