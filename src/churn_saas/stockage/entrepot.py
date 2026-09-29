"""Schéma et accès à l'entrepôt de scores (SQLAlchemy Core).

SQLAlchemy Core plutôt que l'ORM : les objets manipulés sont des lignes de résultats,
pas des entités métier avec un cycle de vie. L'ORM ajouterait une couche sans bénéfice.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine

METADONNEES = MetaData()

scores_churn = Table(
    "scores_churn",
    METADONNEES,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date_scoring", DateTime(timezone=True), nullable=False, index=True),
    Column("client_id", String(32), nullable=False, index=True),
    Column("proba_churn", Float, nullable=False),
    Column("valeur_vie_client_eur", Float),
    Column("valeur_esperee_eur", Float),
    Column("rang", Integer),
    Column("a_traiter", Boolean, nullable=False, default=False),
    # Rattache le score au modèle qui l'a produit : indispensable pour diagnostiquer
    # une dégradation après réentraînement (notebook § 13).
    Column("version_modele", String(64), nullable=False),
)

executions = Table(
    "executions",
    METADONNEES,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date_execution", DateTime(timezone=True), nullable=False),
    Column("version_modele", String(64), nullable=False),
    Column("empreinte_donnees", String(128)),
    Column("nb_comptes_scores", Integer),
    Column("nb_comptes_a_traiter", Integer),
    Column("statut", String(32), nullable=False),
)


def construire_moteur(url: str | None = None) -> Engine:
    """Moteur SQLAlchemy. L'URL vient de l'environnement, jamais du code.

    `postgresql+psycopg://` : sans le suffixe `+psycopg`, SQLAlchemy chercherait
    psycopg2, absent du verrou.
    """
    url = url or os.environ.get(
        "CHURN_DB_URL", "postgresql+psycopg://churn:churn@localhost:5432/churn"
    )
    return create_engine(url, pool_pre_ping=True, future=True)


def creer_schema(moteur: Engine) -> None:
    """Crée les tables si elles n'existent pas. Idempotent."""
    METADONNEES.create_all(moteur)


def ecrire_scores(moteur: Engine, table_priorisee: pd.DataFrame, version_modele: str) -> int:
    """Écrit un lot de scores. Renvoie le nombre de lignes insérées."""
    horodatage = datetime.now(UTC)
    lignes = [
        {
            "date_scoring": horodatage,
            "client_id": str(ligne.get("client_id", "")),
            "proba_churn": float(ligne["proba_churn"]),
            "valeur_vie_client_eur": float(ligne.get("valeur_vie_client_eur", float("nan"))),
            "valeur_esperee_eur": float(ligne.get("valeur_esperee_eur", float("nan"))),
            "rang": int(ligne.get("rang", 0)),
            "a_traiter": bool(ligne.get("a_traiter", False)),
            "version_modele": version_modele,
        }
        for _, ligne in table_priorisee.iterrows()
    ]
    if not lignes:
        return 0
    with moteur.begin() as connexion:
        connexion.execute(scores_churn.insert(), lignes)
    return len(lignes)


def lire_derniers_scores(moteur: Engine, limite: int = 500) -> pd.DataFrame:
    """Relit les scores les plus récents, pour contrôle ou restitution CRM."""
    requete = (
        select(scores_churn)
        .order_by(scores_churn.c.date_scoring.desc(), scores_churn.c.rang.asc())
        .limit(limite)
    )
    with moteur.connect() as connexion:
        return pd.DataFrame(connexion.execute(requete).mappings().all())
