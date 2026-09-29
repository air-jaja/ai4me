"""Exposition des indicateurs à Prometheus.

Trois familles d'indicateurs, correspondant aux trois lectures du notebook § 12 :
technique, dérive, métier. Prometheus les collecte périodiquement ; Grafana les affiche.

Les seuils d'alerte ne sont pas codés ici : ils vivent dans `monitoring.alertes`, avec
leur action et leur responsable. Un exporteur expose, il ne décide pas.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - dépend de l'installation du groupe observabilite
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
    """Démarre le serveur HTTP de métriques sur /metrics."""
    if not _DISPONIBLE:
        raise RuntimeError(
            "prometheus-client absent : installer le groupe `observabilite` "
            "(uv sync --group observabilite)."
        )
    start_http_server(port)


def publier_lot(
    table_priorisee: Any, psi_max: float | None = None, pr_auc: float | None = None
) -> None:
    """Met à jour les jauges après un lot mensuel."""
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
