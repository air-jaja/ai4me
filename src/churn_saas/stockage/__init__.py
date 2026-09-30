"""Relational storage of scores and batch runs.

Implements the storage model chosen in notebook section 3: relational for day-to-day
operations, object storage for training snapshots.

The score table carries the **model version** that produced each row. Without that column,
a degradation observed after a retraining could not be traced back to its cause.
"""

from .entrepot import METADONNEES, creer_schema, ecrire_scores, lire_derniers_scores

__all__ = ["METADONNEES", "creer_schema", "ecrire_scores", "lire_derniers_scores"]
