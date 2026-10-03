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
    tracer_ablation,
    tracer_baselines,
    tracer_calibration,
    tracer_charge_calcul,
    tracer_completude,
    tracer_compte_abandonne,
    tracer_concentration,
    tracer_courbe_validation,
    tracer_courbes_appariees,
    tracer_courbes_apprentissage,
    tracer_courbes_pr_roc,
    tracer_demonstration_fuite,
    tracer_facteurs_compares,
    tracer_fragmentation,
    tracer_importances,
    tracer_permutation,
    tracer_psi,
    tracer_risque_par_segment,
    tracer_tendances,
    tracer_valeur_vie_par_anciennete,
    tracer_validation_adverse,
)
from .materialisation import (
    charger_jeu_derive,
    descriptif_decoupage,
    materialiser,
    parties_du_decoupage,
    table_materialisation,
    verifier_decoupage,
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
from .selection import (
    GROUPES_DE_VARIABLES,
    LEURRES,
    VARIABLES_CONSTRUITES,
    ablation_par_groupe,
    candidates_au_retrait,
    comparer_jeux,
    confirmer_retraits,
    facteurs_inflation_variance,
    importances_par_permutation,
    parties_avant_selection,
    plancher_des_leurres,
    plis_repetes,
    resumer_apport,
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
    "tracer_psi",
    "tracer_validation_adverse",
    "tracer_permutation",
    "tracer_courbes_apprentissage",
    "tracer_valeur_vie_par_anciennete",
    "tracer_charge_calcul",
    "tracer_courbes_appariees",
    "tracer_courbe_validation",
    "tracer_ablation",
    "tracer_importances",
    "tracer_demonstration_fuite",
    "tracer_facteurs_compares",
    # Phase 6: baselines and evaluation protocol
    "tracer_courbes_pr_roc",
    "tracer_calibration",
    "tracer_baselines",
    # Variable selection, under rules fixed beforehand (phase 5, blocs B and C)
    "GROUPES_DE_VARIABLES",
    "LEURRES",
    "VARIABLES_CONSTRUITES",
    "comparer_jeux",
    "resumer_apport",
    "ablation_par_groupe",
    "importances_par_permutation",
    "parties_avant_selection",
    "plis_repetes",
    "plancher_des_leurres",
    "candidates_au_retrait",
    "confirmer_retraits",
    "facteurs_inflation_variance",
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
    "descriptif_decoupage",
    "verifier_decoupage",
    "parties_du_decoupage",
    "verifier_jeux_derives",
    "charger_jeu_derive",
    "version_code",
    "controler_schema",
    "detecter_fuite_suspecte",
    "verifier_leurres",
]
