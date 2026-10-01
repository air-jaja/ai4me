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

from .construction import ajouter_ratios_usage, combler_ratios_structurels
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
from .graphiques import (
    tracer_completude,
    tracer_compte_abandonne,
    tracer_concentration,
    tracer_fragmentation,
    tracer_risque_par_segment,
    tracer_tendances,
)
from .materialisation import (
    charger_jeu_derive,
    materialiser,
    table_materialisation,
    verifier_jeux_derives,
    version_code,
)
from .pipeline import (
    COLONNES_DATES,
    COLONNES_DECIMALES,
    COLONNES_ENTIERES,
    PreparationGold,
    ResultatPipeline,
    construire_silver_standard,
    executer_pipeline,
    preparer_gold,
    table_transformations,
)

__all__ = [
    "ajouter_ratios_usage",
    # Figures of the certification notebook (single source, rule 7)
    "tracer_concentration",
    "tracer_completude",
    "tracer_compte_abandonne",
    "tracer_fragmentation",
    "tracer_risque_par_segment",
    "tracer_tendances",
    "combler_ratios_structurels",
    "desequilibre_cible",
    "desequilibre_categories",
    "taux_cible_par_segment",
    "correlations_cible",
    "correlations_entre_variables",
    "tendance_par_tranche",
    "monotonie",
    "executer_pipeline",
    "construire_silver_standard",
    "preparer_gold",
    "PreparationGold",
    "COLONNES_DECIMALES",
    "COLONNES_ENTIERES",
    "COLONNES_DATES",
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
