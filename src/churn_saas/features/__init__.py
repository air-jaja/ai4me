"""Activity 2 - Feature construction and control.

Two deliberately separate responsibilities:

    construction.py  builds derived variables
    controle.py      checks they are legitimate and usable
    exploration.py   reads what the data suggest, before any model is fitted
    pipeline.py      composes bronze -> silver -> gold and reports each step
    materialisation.py  writes the derived datasets and records their fingerprints

Control is not a formality. A derived variable can reintroduce leakage unnoticed: a ratio
computed from a column known only after the decision is itself known only after the
decision.
"""

from .construction import ajouter_ratios_usage
from .controle import controler_schema, detecter_fuite_suspecte, verifier_leurres
from .exploration import (
    correlations_cible,
    correlations_entre_variables,
    desequilibre_categories,
    desequilibre_cible,
    monotonie,
    taux_cible_par_segment,
    tendance_par_tranche,
)
from .materialisation import (
    charger_jeu_derive,
    materialiser,
    table_materialisation,
    verifier_jeux_derives,
    version_code,
)
from .pipeline import ResultatPipeline, executer_pipeline, table_transformations

__all__ = [
    "ajouter_ratios_usage",
    "desequilibre_cible",
    "desequilibre_categories",
    "taux_cible_par_segment",
    "correlations_cible",
    "correlations_entre_variables",
    "tendance_par_tranche",
    "monotonie",
    "executer_pipeline",
    "ResultatPipeline",
    "table_transformations",
    "materialiser",
    "table_materialisation",
    "verifier_jeux_derives",
    "charger_jeu_derive",
    "version_code",
    "controler_schema",
    "detecter_fuite_suspecte",
    "verifier_leurres",
]
