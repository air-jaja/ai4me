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
