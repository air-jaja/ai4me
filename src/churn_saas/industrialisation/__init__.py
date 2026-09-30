"""Activity 6 - Industrialisation services.

    scoring.py  the MONTHLY BATCH, which decides. It sees the whole portfolio.
    entrepot.py the score warehouse: what the batch produces, not what it consumes.
    service.py  the UNIT response, which does not decide. It sees one account.
    api.py      the HTTP service exposing that response.
    flux.py     the Prefect orchestration of the monthly batch.

The service cannot decide: the prioritisation rule depends on an account's rank within
the whole ranking and on available capacity. Returning a binary decision from a unit call
would be wrong (notebook section 10).
"""

from .entrepot import construire_moteur, creer_schema, ecrire_scores, lire_derniers_scores
from .scoring import preparer, scorer_lot_mensuel
from .service import reponse_scoring_unitaire

__all__ = [
    "preparer",
    "scorer_lot_mensuel",
    "reponse_scoring_unitaire",
    "construire_moteur",
    "creer_schema",
    "ecrire_scores",
    "lire_derniers_scores",
]
