"""Activity 2 - Feature construction and control.

Two deliberately separate responsibilities:

    construction.py  builds derived variables
    controle.py      checks they are legitimate and usable

Control is not a formality. A derived variable can reintroduce leakage unnoticed: a ratio
computed from a column known only after the decision is itself known only after the
decision.
"""

from .construction import ajouter_ratios_usage
from .controle import controler_schema, detecter_fuite_suspecte, verifier_leurres

__all__ = [
    "ajouter_ratios_usage",
    "controler_schema",
    "detecter_fuite_suspecte",
    "verifier_leurres",
]
