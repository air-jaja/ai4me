"""Activité 6 — Services d'industrialisation.

    scoring.py  le LOT MENSUEL, qui décide. Il voit tout le portefeuille.
    service.py  la réponse UNITAIRE, qui ne décide pas. Elle voit un compte à la fois.
    api.py      le service HTTP exposant cette réponse.
    flux.py     l'orchestration Prefect du lot mensuel.

Le service ne peut pas trancher : la règle de priorisation dépend du rang d'un compte
dans le classement de l'ensemble et de la capacité disponible. Renvoyer une décision
binaire depuis un appel unitaire serait faux (notebook § 10).
"""

from .scoring import preparer, scorer_lot_mensuel
from .service import reponse_scoring_unitaire

__all__ = ["preparer", "scorer_lot_mensuel", "reponse_scoring_unitaire"]
