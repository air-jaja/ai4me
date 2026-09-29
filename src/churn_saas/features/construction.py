"""Variables dérivées.

Un ratio est plus parlant qu'un couple de valeurs brutes : « 2 fonctionnalités utilisées
sur 10 disponibles » dit directement si le client exploite ce qu'il paie, là où les deux
nombres pris séparément ne le disent pas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _ratio(numerateur: pd.Series, denominateur: pd.Series) -> pd.Series:
    """Division protégée : un dénominateur nul donne NaN, jamais une erreur ni un infini."""
    num = pd.to_numeric(numerateur, errors="coerce")
    den = pd.to_numeric(denominateur, errors="coerce")
    return (num / den.replace(0, np.nan)).astype(float)


def ajouter_ratios_usage(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les ratios d'usage. Chaque variable ne repose que sur des données
    antérieures à l'échéance contractuelle.

    - `taux_activation`      part des licences réellement utilisées
    - `taux_couverture_fonc` part des fonctionnalités du plan effectivement employées
    - `usage_par_actif`      intensité d'usage rapportée au nombre d'utilisateurs
    - `tickets_par_actif`    pression sur le support, rapportée à la taille du compte
    """
    out = df.copy()
    if {"utilisateurs_actifs", "sieges_souscrits"} <= set(out.columns):
        out["taux_activation"] = _ratio(out["utilisateurs_actifs"], out["sieges_souscrits"])
    if {"fonctionnalites_utilisees", "fonctionnalites_total"} <= set(out.columns):
        out["taux_couverture_fonc"] = _ratio(
            out["fonctionnalites_utilisees"], out["fonctionnalites_total"]
        )
    if {"heures_usage_30j", "utilisateurs_actifs"} <= set(out.columns):
        out["usage_par_actif"] = _ratio(out["heures_usage_30j"], out["utilisateurs_actifs"])
    if {"tickets_support_90j", "utilisateurs_actifs"} <= set(out.columns):
        out["tickets_par_actif"] = _ratio(out["tickets_support_90j"], out["utilisateurs_actifs"])
    return out
