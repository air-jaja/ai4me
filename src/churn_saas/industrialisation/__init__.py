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

try:  # the score store needs SQLAlchemy (group `stockage`), absent from the CI
    from .entrepot import construire_moteur, creer_schema, ecrire_scores, lire_derniers_scores
except ImportError:  # scoring, the list and the service must still import without it

    def _stockage_absent(*_args, **_kwargs):
        raise ImportError("SQLAlchemy absent : installer le groupe stockage.")

    construire_moteur = creer_schema = ecrire_scores = lire_derniers_scores = _stockage_absent
from .liste import FORMULATIONS, LIBELLES, construire_liste, motif, selectionner, tranche
from .scoring import controler_lot, preparer, scorer_lot_mensuel
from .service import reponse_scoring_unitaire

__all__ = [
    # Operational list for the account managers (phase 10)
    "construire_liste",
    "selectionner",
    "motif",
    "tranche",
    "LIBELLES",
    "FORMULATIONS",
    "preparer",
    "scorer_lot_mensuel",
    "controler_lot",
    "reponse_scoring_unitaire",
    "construire_moteur",
    "creer_schema",
    "ecrire_scores",
    "lire_derniers_scores",
]
