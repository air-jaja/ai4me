"""Indicator exposure to Prometheus.

Three families of indicators, matching the three readings of notebook section 12:
technical, drift, business. Prometheus scrapes them; Grafana displays them.

Alert thresholds are not coded here: they live in `monitoring.alertes`, together with
their action and owner. An exporter exposes, it does not decide.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - depends on the `observabilite` group being installed
    from prometheus_client import Gauge, start_http_server

    _DISPONIBLE = True
except ImportError:  # pragma: no cover
    _DISPONIBLE = False

if _DISPONIBLE:
    COMPTES_SCORES = Gauge("churn_comptes_scores", "Comptes scorés lors du dernier lot")
    COMPTES_A_TRAITER = Gauge("churn_comptes_a_traiter", "Comptes retenus pour action")
    VALEUR_ESPEREE_TOTALE = Gauge(
        "churn_valeur_esperee_totale_eur", "Valeur espérée cumulée des comptes retenus"
    )
    PSI_MAX = Gauge("churn_psi_max", "PSI le plus élevé observé sur les variables suivies")
    PR_AUC = Gauge("churn_pr_auc", "PR-AUC de la dernière évaluation disponible")
    # Phase 11: the monthly verdicts (M5, M8, M9) and the alerts they raise.
    PSI_SCORE = Gauge("churn_psi_score", "PSI de la distribution du score contre le profil")
    VARIABLES_PSI_MODERE = Gauge(
        "churn_variables_psi_au_dessus_de_0_10", "Variables du modèle au-dessus de 0,10 (M5)"
    )
    VARIABLES_MANQUANTS_EN_ALERTE = Gauge(
        "churn_variables_manquants_en_alerte",
        "Variables au-dessus du double de l'entraînement (M8)",
    )
    COMPTES_SIGNALES = Gauge("churn_comptes_signales", "Comptes retenus par la liste (M9)")
    ALERTE = Gauge("churn_alerte", "Règle d'alerte déclenchée (1) ou non (0)", ["indicateur"])
    TAUX_MANQUANTS_MAX = Gauge(
        "churn_taux_manquants_max", "Taux de manquants le plus élevé à l'entrée"
    )


def demarrer_exporteur(port: int = 9109) -> None:
    """Start the metrics HTTP server on /metrics."""
    if not _DISPONIBLE:
        raise RuntimeError(
            "prometheus-client absent : installer le groupe `observabilite` "
            "(uv sync --group observabilite)."
        )
    start_http_server(port)


def publier_lot(
    table_priorisee: Any, psi_max: float | None = None, pr_auc: float | None = None
) -> None:
    """Refresh the gauges after a monthly batch."""
    # Silent no-op without the group installed: publishing metrics must never break a
    # batch that is otherwise complete.
    if not _DISPONIBLE:
        return
    COMPTES_SCORES.set(len(table_priorisee))
    retenus = table_priorisee[table_priorisee["a_traiter"]]
    COMPTES_A_TRAITER.set(len(retenus))
    VALEUR_ESPEREE_TOTALE.set(float(retenus["valeur_esperee_eur"].sum()))
    if psi_max is not None:
        PSI_MAX.set(float(psi_max))
    if pr_auc is not None:
        PR_AUC.set(float(pr_auc))


def publier_suivi(derive: dict, manquants: dict, volume: dict, alertes: Any) -> None:
    """Refresh the phase 11 gauges after the monthly verdicts (`monitoring.suivi`).

    Exposes, does not decide: the thresholds and their actions stay in `monitoring.alertes`.
    """
    if not _DISPONIBLE:
        return
    PSI_SCORE.set(float(derive["psi du score"]))
    VARIABLES_PSI_MODERE.set(len(derive["variables au-dessus de 0,10"]))
    VARIABLES_MANQUANTS_EN_ALERTE.set(len(manquants["variables en alerte"]))
    COMPTES_SIGNALES.set(int(volume["comptes signalés"]))
    for _, ligne in alertes.iterrows():
        ALERTE.labels(indicateur=ligne["indicateur"]).set(int(bool(ligne["declenchee"])))
