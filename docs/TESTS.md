# Catalogue des tests

> **Document généré.** Produit par `tools/catalogue_tests.py` à partir des fichiers de
> tests eux-mêmes. Un inventaire écrit à la main dérive dès le premier test ajouté, et
> un inventaire périmé est pire qu'aucun : il revendique une couverture qui n'existe
> plus. Régénérer avec :
>
> ```bash
> uv run python tools/catalogue_tests.py > docs/TESTS.md
> ```

**564 cas de test** issus de 306 fonctions, répartis sur 22 fichiers.

_Les deux nombres diffèrent parce qu'un test paramétré est une fonction unique exécutée plusieurs fois. Le décompte des cas provient de `pytest --collect-only`, non d'une lecture du code : une liste de paramètres calculée plutôt qu'écrite en dur échapperait à toute analyse statique._

## Principe : tester ce qui casse sans bruit

La suite ne vise pas la couverture de lignes. Elle vise les défauts qui ne lèvent
aucune erreur : une jointure qui perd des lignes en silence, une virgule décimale mal
convertie, une variable en fuite réintroduite, un infini qui se propage, un tableau
tronqué qui ampute un argument.

Un défaut bruyant se corrige en dix minutes. Un défaut silencieux se découvre en
soutenance.

## Vue d'ensemble

| Domaine | Fichier | Activité du cycle de vie | Compétences | Cas |
|---|---|---|---|---|
| [Structure du paquet](#structure-du-paquet) | `test_structure.py` | Transverse | C6 | 31 |
| [Nettoyage et niveaux de raffinage](#nettoyage-et-niveaux-de-raffinage) | `test_donnees.py` | 1 · Gestion des données | C3 | 46 |
| [Schéma, gouvernance et versionnement des données](#schéma-gouvernance-et-versionnement-des-données) | `test_donnees_gouvernance.py` | 1 · Gestion des données | C1, C2, C3 | 26 |
| [Construction et contrôle des variables](#construction-et-contrôle-des-variables) | `test_features.py` | 2 · Contrôle des features | C3, C5 | 15 |
| [Profilage et exploration](#profilage-et-exploration) | `test_exploration.py` | 1 · Données · 2 · Features | C3, C4 | 21 |
| [Matérialisation des jeux dérivés](#matérialisation-des-jeux-dérivés) | `test_materialisation.py` | 2 · Features | C3, C6 | 15 |
| [Métriques, décision et impact](#métriques-décision-et-impact) | `test_evaluation.py` | 4 · Évaluation | C5, C8 | 13 |
| [Artefacts et fiche modèle](#artefacts-et-fiche-modèle) | `test_packaging.py` | 5 · Packaging | C6 | 3 |
| [Dérive et règles d'alerte](#dérive-et-règles-dalerte) | `test_monitoring.py` | 7 · Monitoring | C8, C9 | 9 |
| [Contrat d'affichage des notebooks](#contrat-daffichage-des-notebooks) | `test_notebook.py` | Transverse | C3, C6 | 3 |
| [Conventions de travail](#conventions-de-travail) | `test_conventions.py` | Transverse | — | 182 |
| [Stockage et cache des figures](#stockage-et-cache-des-figures) | `test_figures.py` | Transverse | C3, C8 | 16 |
| [Récapitulatif de la suite](#récapitulatif-de-la-suite) | `test_recapitulatif.py` | Transverse | — | 19 |
| [Défaut de casse des modalités](#défaut-de-casse-des-modalités) | `test_regression_casse_modalites.py` | 1 · Données | C3 | 17 |
| [Non-régression des phases terminées](#non-régression-des-phases-terminées) | `test_non_regression.py` | Transverse | C1, C2, C3, C4, C5 | 88 |
| [test_campagnes.py](#test_campagnespy) | `test_campagnes.py` | — | — | 7 |
| [test_industrialisation.py](#test_industrialisationpy) | `test_industrialisation.py` | — | — | 4 |
| [test_modelisation.py](#test_modelisationpy) | `test_modelisation.py` | — | — | 14 |
| [test_registre.py](#test_registrepy) | `test_registre.py` | — | — | 8 |
| [test_ressources.py](#test_ressourcespy) | `test_ressources.py` | — | — | 8 |
| [test_resultats_reference.py](#test_resultats_referencepy) | `test_resultats_reference.py` | — | — | 5 |
| [test_suivi.py](#test_suivipy) | `test_suivi.py` | — | — | 14 |

---

## Détail par domaine

### Structure du paquet

**Fichier :** `tests/test_structure.py` — **Activité :** Transverse — **Compétences :** C6

**Ce que ce fichier protège :** L'organisation du code : aucun module ne doit masquer un paquet homonyme

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_les_sept_activites_existent` | Each lifecycle activity has its own package. | No activity, no separation. |
| 2 | `test_aucun_paquet_hors_des_sept_activites` | A package outside the agreed seven means an activity was invented along the way. | `stockage` lived here for a while before being folded into activity 6: the score warehouse holds what the batch *produces*, not what it consumes. |
| 3 | `test_chaque_activite_annonce_son_numero` _(×7)_ | The package docstring states which lifecycle activity it implements. | — |
| 4 | `test_chaque_activite_expose_une_interface` _(×7)_ | `__all__` is the activity's contract: what the other activities may rely on. | — |
| 5 | `test_aucun_module_ne_porte_le_nom_d_un_paquet` | A module and a package with the same name must never coexist. | Python resolves the package and the code keeps running, so the duplicate is invisible until someone edits the wrong file. |
| 6 | `test_seuls_les_modules_transverses_restent_a_la_racine` | Every module belongs to an activity, except those serving all of them. | — |
| 7 | `test_les_dependances_respectent_l_ordre_du_cycle_de_vie` | An activity may only rely on those the declaration allows. | Without this check the split survives on the filename alone: a backward dependency - data management calling the model, say - would make the two activities inseparable while the folders still suggest otherwise. |
| 8 | `test_les_activites_communiquent_par_leur_interface_publique` | Cross-activity imports target the package, never one of its submodules. | Reaching into `..donnees.gold` rather than `..donnees` ties the caller to an internal layout it does not own: any reorganisation inside the activity then breaks code elsewhere. `__all__` exists precisely to prevent that. |
| 9 | `test_tout_nom_utilise_hors_de_son_module_est_exporte` _(×7)_ | A function used outside its own module belongs to the activity's public surface. | Otherwise callers reach into a submodule they do not own, and `__all__` stops describing what the activity actually offers. The rule already applies between activities; this extends it to the notebooks and the test suite, which are the other consumers of that surface. |
| 10 | `test_le_lecteur_d_arborescence_reconstruit_les_chemins` | The parser itself: without this, an empty result would make the checks pass vacuously. | — |
| 11 | `test_l_arborescence_du_readme_est_lue` | The README tree yields the package modules. | a broken parse would return nothing. |
| 12 | `test_chaque_module_figure_dans_l_arborescence_du_readme` | A module the README does not list is a module a newcomer will not find. | — |
| 13 | `test_l_arborescence_du_readme_ne_cite_aucun_module_disparu` | A line left behind by a removed or renamed module describes code that does not exist. | — |

### Nettoyage et niveaux de raffinage

**Fichier :** `tests/test_donnees.py` — **Activité :** 1 · Gestion des données — **Compétences :** C3

**Ce que ce fichier protège :** La chaîne bronze → silver → gold et les exclusions anti-fuite

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_nombres_stockes_en_texte` | Numbers stored as text must become numbers, and junk must become NaN. | A failed conversion raising no error would turn a numeric column into categories: "33,3" and "33,4" would lose any ordering relation. |
| 2 | `test_dates_multiformats` | Mixed date formats must all parse, and DD/MM must win over MM/DD. | Without an explicit dayfirst choice, pandas arbitrates alone and the result depends on row order - a non-reproducible parse. |
| 3 | `test_normalisation_de_la_cle_de_jointure` | The join key must collapse case and whitespace differences. | — |
| 4 | `test_jointure_catalogue_sans_perte_malgre_la_casse` | The catalogue join must lose no row despite STARTER/starter. | This is the silent failure of the project: without normalisation nothing raises, the unmatched rows simply vanish from the result. |
| 5 | `test_doublons_supprimes` | Strict duplicates must be removed. | Duplicated accounts make the model learn the same example twice and flatter every metric computed afterwards. |
| 6 | `test_gold_retire_les_colonnes_interdites` | Every forbidden column must be gone from the gold dataset. | Guards the single most expensive defect of the project: a leaking variable silently reintroduced by a refactor would produce an excellent, meaningless model. |
| 7 | `test_separation_de_la_cible` | The target must never remain among the explanatory variables. | — |
| 8 | `test_les_variantes_de_casse_sont_fusionnees_en_une_seule_modalite` | `TPE` and `tpe` are one category written two ways, not two categories. | Normalising the join key alone was not enough: the join worked while the stored values kept every spelling. One-hot encoding then turned each spelling into its own column, so the model saw several rare categories instead of one common one, split the signal between them, and made any importance reading misleading. |
| 9 | `test_le_silver_ne_conserve_aucune_variante_de_casse` | The whole chain must leave one label per business category. | — |
| 10 | `test_un_suffixe_d_unite_est_converti` | A unit written in letters after the number must not turn the value into NaN. | 570 support delays arrived as "3.1 h". The symbol list removed spaces but not the letter, `to_numeric` coerced the rest to NaN, and the missing rate of the column went from 10 % to 21.4 % with no error anywhere. |
| 11 | `test_les_formats_deja_couverts_restent_convertis` | Handling units must not break the formats the primitive already covered. | — |
| 12 | `test_une_perte_de_conversion_est_detectee_sans_cibler_de_colonne` | The guard compares presence before and after; it knows no column and no format. | That is what makes it catch the next unexpected format, not only the one already met. |
| 13 | `test_une_perte_de_conversion_bloque_la_chaine` | A value present in the source and lost on conversion stops the chain, by name. | — |
| 14 | `test_le_mode_non_strict_reproduit_le_defaut_en_connaissance_de_cause` | `strict=False` exists to show the defect, and only produces NaN where it lies. | — |
| 15 | `test_une_date_illisible_bloque_la_chaine` | Dates go through the same guard: an unparsed date is a lost value too. | — |
| 16 | `test_les_colonnes_du_catalogue_sont_typees` | Numeric catalogue columns become numbers; a genuinely textual one stays text. | Read as text like every source, the prices and quotas reached the model as categories: "12" and "25" EUR with no ordering left between them. |
| 17 | `test_la_jointure_apporte_des_colonnes_numeriques` | End to end: after the join, a catalogue price is a number in silver. | — |
| 18 | `test_un_doublon_au_format_different_est_retire` | Two rows describing one account, written differently, are one account. | Deduplicating only the raw text kept them both: "12,5" and "12.5" differ as strings. |
| 19 | `test_un_compte_en_conflit_bloque_la_chaine` | One account, two different values: no rule can tell which is right, so stop. | — |
| 20 | `test_la_cle_de_compte_peut_etre_desactivee` | Tables without an account key (a catalogue, a test frame) must still build. | — |
| 21 | `test_gold_retire_la_date_brute_et_le_doublon_du_catalogue` | Each phase 4 exclusion is applied, and carries its own motive. | — |
| 22 | `test_le_contrat_passe_sur_un_lot_sain` | _(sans description)_ | — |
| 23 | `test_le_contrat_bloque_un_lot_defectueux` _(×7)_ | Each blocking rule, broken alone, is reported under its own name. | — |
| 24 | `test_le_contrat_bloque_une_perte_de_conversion` | The conversion check reads the raw text: once typed, a lost value looks missing. | — |
| 25 | `test_le_contrat_met_sous_surveillance_un_taux_de_manquants_eleve` | Between the watch and the blocking threshold, the batch passes but is flagged. | — |
| 26 | `test_une_modalite_inconnue_est_a_surveiller_et_non_bloquante` | An unseen category degrades the score without corrupting it: watch, do not stop. | — |
| 27 | `test_exiger_contrat_nomme_chaque_controle_en_echec` | _(sans description)_ | — |
| 28 | `test_une_date_iso_n_est_jamais_inversee` | "2024-02-06" is 6 February, whatever convention applies to slash dates. | `format="mixed", dayfirst=True` read it as 2 June: 960 ISO dates were swapped until phase 4, while every one of them still parsed - nothing looked wrong. |
| 29 | `test_les_dates_textuelles_sont_lues` | _(sans description)_ | — |
| 30 | `test_un_format_de_date_non_declare_n_est_pas_devine` | An undeclared format becomes NaT. | reported as a loss - rather than a guess. |
| 31 | `test_le_contrat_bloque_une_date_inversee` | A date contradicting the stated weekday is reported, which is how the swap was found. | — |
| 32 | `test_une_valeur_observee_n_est_jamais_remplacee` | Reconstruction fills gaps only: an observed 130 EUR stays 130, not 10 x 12 = 120. | — |
| 33 | `test_le_revenu_est_reconstruit_par_sieges_fois_prix` | _(sans description)_ | — |
| 34 | `test_le_taux_d_adoption_est_reconstruit_exactement` | Active users over seats, times 100, one decimal. | the form of the source column. |
| 35 | `test_un_ingredient_manquant_laisse_la_valeur_manquante` | No price, no revenue: the gap stays, for the median imputation to handle. | — |
| 36 | `test_une_regle_inapplicable_est_signalee_et_non_ignoree` | A batch lacking an ingredient column says so in the report, it is not skipped quietly. | — |
| 37 | `test_le_decoupage_est_deterministe_disjoint_et_complet` | Same seed, same accounts in the test part; no account in both; none lost. | — |
| 38 | `test_le_decoupage_est_stratifie_sur_la_cible` | Both parts keep the churn rate: the gap stays under the threshold fixed beforehand. | — |
| 39 | `test_une_autre_graine_change_le_jeu_de_test` | The seed matters: a change of seed must show in the recorded fingerprint. | — |
| 40 | `test_les_entiers_nullables_deviennent_decimaux_a_l_entree_du_modele` | A nullable integer column would make a model signature refuse missing values. | — |

### Schéma, gouvernance et versionnement des données

**Fichier :** `tests/test_donnees_gouvernance.py` — **Activité :** 1 · Gestion des données — **Compétences :** C1, C2, C3

**Ce que ce fichier protège :** Le contrat de schéma, le cycle de vie, la sensibilité et les empreintes

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_chaque_colonne_source_porte_un_role_documente` | An undocumented column is a column nobody decided what to do with. | — |
| 2 | `test_l_audit_qualite_detecte_les_doublons` | The quality audit must count duplicates, not merely mention them. | A defect stated without its scope cannot be arbitrated by anyone. |
| 3 | `test_la_jointure_normalisee_recupere_les_lignes_perdues` | Quantifies what normalisation buys, rather than asserting it helps. | — |
| 4 | `test_chaque_etape_du_cycle_de_vie_a_un_responsable` | A stage without an owner is a stage nobody performs. | — |
| 5 | `test_le_cycle_de_vie_va_de_la_collecte_a_la_purge` | The lifecycle must be complete end to end. | A lifecycle stopping before purge is the usual way personal data is kept for years without a legal basis. |
| 6 | `test_chaque_donnee_sensible_porte_un_traitement` | Identifying a sensitive column without stating its treatment protects nobody. | — |
| 7 | `test_le_scan_detecte_les_donnees_personnelles` | The scan must actually find personal data patterns. | Turns 'the field could contain personal data' from a comfortable, unverifiable claim into a measurement. |
| 8 | `test_les_exemples_affiches_sont_masques` | The demonstration must not commit the offence it describes. | — |
| 9 | `test_la_comparaison_de_stockage_tranche_chaque_option` | Every storage option must carry a decision, not just a description. | An option listed without a verdict is a comparison the jury will finish itself. |
| 10 | `test_l_empreinte_ignore_l_ordre_des_lignes_et_des_colonnes` | Two exports of the same content must yield the same fingerprint. | — |
| 11 | `test_l_empreinte_ne_depend_pas_du_systeme_d_exploitation` | The same data must fingerprint identically on Windows and on Linux. | `to_csv` ends lines with `os.linesep` by default. The phase 3 manifest, written on a Windows workstation, recorded a " " fingerprint the Linux CI could never reproduce; it surfaced only when phase 4 started comparing the manifest with the code. Simulating the Windows separator is enough: pandas reads it at call time. |
| 12 | `test_l_empreinte_change_si_une_valeur_change` | A single changed value must change the fingerprint. | Without this property the manifest would certify datasets it never verified. |
| 13 | `test_le_manifeste_detecte_une_source_modifiee` | Run before any training: a changed source means the run reproduces nothing. | — |
| 14 | `test_le_manifeste_signale_une_source_disparue` | A missing source must be reported, not silently ignored. | — |
| 15 | `test_les_tables_de_gouvernance_ne_sont_jamais_vides` _(×3)_ | An empty governance table would silently remove a section from the notebook. | — |
| 16 | `test_le_manifeste_n_est_pas_reecrit_sans_raison` | Two runs on unchanged sources must leave the manifest byte-identical. | Regenerating it each time would change `date_construction` and produce a diff on every commit for fingerprints that did not move. Noise of that kind trains readers to skip the file, and a manifest nobody reads certifies nothing. |
| 17 | `test_le_manifeste_est_reecrit_si_une_source_change` | A changed source must force a rewrite: silence there would certify a lie. | — |
| 18 | `test_l_inventaire_decrit_chaque_colonne` | The "before" snapshot must cover every column, including the empty ones. | Section 5 of the notebook compares this inventory to reference values. A column missing from it would silently escape the completeness check. |
| 19 | `test_la_table_des_exclusions_expose_chaque_motif` | Every excluded column appears with its own rationale. | The motives are not interchangeable: the grid separates ethics from technical preparation, so a single blanket justification would satisfy neither. |
| 20 | `test_l_empreinte_de_fichier_depend_du_contenu` | Identical bytes give the same fingerprint, a single changed byte gives another. | — |
| 21 | `test_l_empreinte_de_fichier_lit_par_blocs` | Block reading must give the same result as reading the file whole. | The block size bounds memory use on a large snapshot; a wrong implementation would only show up on files too big to notice during development. |
| 22 | `test_le_manifeste_se_relit_a_l_identique` | Writing then reading a manifest must return the same content. | The manifest is the contract between a data version and a model. A round-trip that loses a field would make the contract unverifiable without saying so. |
| 23 | `test_le_manifeste_enregistre_des_chemins_relatifs` | Paths are stored relative to the repository root, never absolute. | An absolute path ties the manifest to the machine that wrote it. Regenerated on a workstation and committed, it can no longer be verified anywhere else - CI included, where every source would be reported as missing. The check would then fail for a reason unrelated to the data it is meant to protect. |
| 24 | `test_le_manifeste_relatif_se_verifie_depuis_une_autre_racine` | A relative manifest verifies wherever the repository is cloned. | — |

### Construction et contrôle des variables

**Fichier :** `tests/test_features.py` — **Activité :** 2 · Contrôle des features — **Compétences :** C3, C5

**Ce que ce fichier protège :** Les ratios d'usage et la détection générique de fuite

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_ratio_protege_contre_la_division_par_zero` | A zero denominator must yield NaN, never an infinity. | An infinity propagates silently through the pipeline and only surfaces as an absurd model coefficient, far from its cause. |
| 2 | `test_controle_de_schema_signale_une_colonne_absente` | A missing expected column must be reported as non-compliant. | This is step 2 of the CI chain: it blocks a batch rather than scoring out-of-domain data, which would produce plausible but wrong probabilities. |
| 3 | `test_detection_generique_de_fuite` | The check targets no named column: it spots the abnormal correlation. | — |
| 4 | `test_confirmation_empirique_des_leurres` | Decoy variables must be confirmed as useless by measurement, not by assumption. | Dropping them upfront would forfeit the interpretability demonstration the brief asks for; keeping them without checking would be an unverified claim. |
| 5 | `test_les_ratios_structurels_valent_zero` | No active user: the per-user ratios are undefined, set to 0 by convention. | The indicator carries the meaning. Without the zero, these 297 accounts would be imputed with the median of ordinary accounts - mixed with genuinely unknown values. |
| 6 | `test_un_vrai_manquant_de_ratio_reste_manquant` | Users present, hours unknown: that gap is genuine and must reach the median imputation. | — |
| 7 | `test_la_chaine_partagee_produit_le_meme_gold_que_le_pipeline` | Training and monthly batch go through `preparer_gold`; it must match the pipeline. | The batch used to rebuild silver without the column lists and to skip what the pipeline did. This compares on a small frame; the non-regression suite compares on the full dataset. |
| 8 | `test_le_silver_garde_les_nan_que_l_exploration_lit` | The zeros apply on the way to gold; silver keeps the phase 3 NaN as they were. | — |
| 9 | `test_les_graphiques_se_tracent_a_partir_des_seules_donnees_recues` | Each drawing function works on its arguments alone: no global, no file written. | They were inline closures in the phase notebooks, reading notebook variables. Moved here so the certification notebook calls them instead of holding a second copy. |
| 10 | `test_les_jeux_sont_compares_sur_les_memes_plis` | Paired comparison: same folds for every set, so a difference is the variables'. | — |
| 11 | `test_un_apport_nul_n_est_pas_declare_significatif` | A redundant copy of a variable adds nothing: the one-std rule must say so. | — |
| 12 | `test_l_ablation_distingue_un_groupe_utile_d_un_groupe_inutile` | _(sans description)_ | — |
| 13 | `test_le_plancher_des_leurres_designe_les_variables_sans_information` | A variable carrying nothing falls under the decoy's floor; the signal stands above. | — |
| 14 | `test_une_variable_utile_a_un_seul_modele_est_gardee` | Removal needs the floor for every model: one model finding it useful is enough to keep. | — |
| 15 | `test_le_facteur_d_inflation_signale_une_quasi_copie` | _(sans description)_ | — |

### Profilage et exploration

**Fichier :** `tests/test_exploration.py` — **Activité :** 1 · Données · 2 · Features — **Compétences :** C3, C4

**Ce que ce fichier protège :** Le profilage qui décide la préparation, et le pipeline bronze → silver → gold

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_le_profil_des_manquants_classe_par_gravite` | A column missing over half its values is not treated like one missing 3%. | — |
| 2 | `test_le_profil_des_doublons_distingue_stricts_et_cle` | Two different questions: an export accident, or one account with two versions. | A strict duplicate can be dropped. A duplicate on the key alone cannot: the two rows disagree, and no automatic rule can decide which is right. |
| 3 | `test_le_profil_des_distributions_signale_l_asymetrie` | The mean-to-median ratio is what decides median imputation over mean imputation. | — |
| 4 | `test_le_mecanisme_des_manquants_mesure_l_ecart_a_la_cible` | An absence that predicts the target must be kept as a signal, not filled in. | — |
| 5 | `test_un_manquant_structurel_se_distingue_d_un_manquant_aleatoire` | A delay missing only when no ticket exists is structural: imputing would invent it. | — |
| 6 | `test_les_bornes_de_tukey_sont_informatives_et_non_appliquees` | Bounds are given for reference: on this portfolio the extremes are real accounts. | Removing them would drop exactly the customers the project exists to protect. |
| 7 | `test_le_pipeline_journalise_chacune_de_ses_etapes` | A transformation nobody can quantify is a transformation nobody can defend. | — |
| 8 | `test_le_pipeline_retire_les_colonnes_interdites` | The gold dataset carries no identifier, no leak, no free text, no secondary target. | — |
| 9 | `test_le_pipeline_peut_se_passer_des_variables_derivees` | Switching enrichment off is what makes the evaluation -> features loop measurable. | Without this parameter, the contribution of feature engineering could only be asserted, never compared. |
| 10 | `test_la_table_des_transformations_trace_chaque_colonne` | Every column says where it comes from and where it stops. | — |
| 11 | `test_le_silver_lisible_ne_sert_jamais_au_modele` | Readable silver fills every hole, which is exactly why it must not train a model. | The values are computed on the whole table: using them would let the test set influence what the model learns. The `_impute` flags make a reconstructed value distinguishable from an observed one. |
| 12 | `test_le_desequilibre_est_qualifie_et_non_seulement_chiffre` | Overstating the imbalance in a presentation invites a correction. | — |
| 13 | `test_le_desequilibre_des_categories_repere_les_modalites_rares` | A modality carrying a handful of rows produces an estimate nobody should trust. | — |
| 14 | `test_le_taux_par_segment_expose_l_ecart_au_global` | The gap is what matters: a segment at the average carries no information. | — |
| 15 | `test_les_correlations_sont_classees_par_force_absolue` | A strong negative driver matters as much as a strong positive one. | — |
| 16 | `test_les_variables_redondantes_sont_signalees` | Two equivalent variables share the credit, and both look half as useful as they are. | — |
| 17 | `test_la_tendance_par_tranche_revele_le_non_monotone` | A correlation coefficient hides a strong non-monotonic relationship. | — |
| 18 | `test_les_manquants_des_colonnes_SOURCE_sont_completement_aleatoires` | On source columns, neither the target nor a structural cause explains the holes. | Two independent readings agree, which is what legitimises a statistical imputation fitted inside the model pipeline. Should either move, the strategy would have to be reconsidered. |
| 19 | `test_les_manquants_des_ratios_sont_structurels_et_porteurs_de_signal` | The conclusion drawn on source columns does not carry over to derived ones. | Dividing by the number of active users yields NaN when that number is zero. Those NaN encode an abandoned account - still paid for, used by nobody - and separate the target more strongly than any other variable in the dataset. Imputing them with a median would replace the strongest available signal by the value of an ordinary account, and no metric would report the loss. |
| 20 | `test_l_indicateur_de_compte_abandonne_rend_le_signal_explicite` | The signal becomes a variable instead of a side effect of a division by zero. | A NaN survives no imputation; a declared indicator does. It is also readable by a CSM, which a missing value is not. |
| 21 | `test_le_resume_de_profilage_couvre_les_constats_cles` | _(sans description)_ | — |

### Matérialisation des jeux dérivés

**Fichier :** `tests/test_materialisation.py` — **Activité :** 2 · Features — **Compétences :** C3, C6

**Ce que ce fichier protège :** Le lien entre une version de modèle et le jeu exact qui l'a produite : écriture, empreinte, contrôle avant entraînement

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_silver_et_gold_sont_ecrits_en_parquet` | Parquet rather than CSV: types survive the round trip. | Reparsing decimals and dates on reload would undo the whole preparation step - the very defects phase 2 spent its time fixing. |
| 2 | `test_le_bronze_n_est_pas_reecrit` | Bronze already exists under `data/raw/`, versioned in Git. | Writing a second copy would create a file that can drift from the one the manifest fingerprints - two references instead of one. |
| 3 | `test_le_nom_du_fichier_porte_sa_version_et_sa_date` | A snapshot that cannot be dated cannot be matched to a model. | — |
| 4 | `test_le_manifeste_enregistre_l_empreinte_du_contenu` | The fingerprint is computed on the content, not on the file. | Two Parquet writes of the same rows can differ byte for byte - compression, metadata - while describing the same data. Fingerprinting the content is what makes the check meaningful. |
| 5 | `test_le_manifeste_enregistre_la_version_du_code` | Code, data and model are versioned together, or reproducibility is a claim. | A snapshot without the commit that produced it cannot be recomputed: the cleaning rules may have changed since. |
| 6 | `test_le_manifeste_conserve_les_sources` | Adding the derived datasets must not drop the source section. | — |
| 7 | `test_le_manifeste_se_relit_depuis_le_disque` | _(sans description)_ | — |
| 8 | `test_le_controle_confirme_un_instantane_intact` | _(sans description)_ | — |
| 9 | `test_le_controle_detecte_un_jeu_qui_a_derive` | A changed pipeline must be reported, not absorbed. | The run would otherwise produce a model whose card describes data it was not trained on - and no metric reports that. |
| 10 | `test_le_controle_detecte_un_fichier_disparu` | _(sans description)_ | — |
| 11 | `test_le_jeu_relu_est_identique_a_celui_ecrit` | The round trip preserves content and types, which is the point of Parquet. | — |
| 12 | `test_relire_un_instantane_modifie_leve_une_erreur` | Loading a snapshot without checking it defeats its purpose. | The error names both fingerprints: a message saying only "mismatch" leaves the reader unable to tell which side moved. |
| 13 | `test_le_controle_peut_etre_leve_explicitement` | Inspecting a snapshot known to have drifted stays possible, but never by default. | — |
| 14 | `test_la_table_de_materialisation_est_lisible` | _(sans description)_ | — |
| 15 | `test_l_outil_de_materialisation_ecrit_un_manifeste_conforme` | `make materialiser` refreshes the manifest without Jupyter, and checks what it wrote. | The phase 3 notebook used to be the only way to refresh it; when Jupyter failed (the orjson episode of 02/10), the manifest could not follow the code. |

### Métriques, décision et impact

**Fichier :** `tests/test_evaluation.py` — **Activité :** 4 · Évaluation — **Compétences :** C5, C8

**Ce que ce fichier protège :** La règle de priorisation par valeur espérée et sa robustesse

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_seuil_decroit_avec_la_valeur_du_compte` | The rational action threshold must fall as account value rises. | This monotonicity is the whole justification for abandoning a single global threshold: if it broke, the decision rule would lose its rationale. |
| 2 | `test_classement_insensible_a_l_efficacite_de_retention` | Core argument of section 9: u is a common factor, it does not change the order. | — |
| 3 | `test_sensibilite_confirme_la_stabilite_de_la_liste` | The handled shortlist must stay identical across retention-effectiveness values. | Produces the evidence behind the sensitivity analysis promised in section 9 - an analysis announced in the deliverable but never run would be worse than none. |
| 4 | `test_la_capacite_borne_le_nombre_de_comptes_traites` | The shortlist must never exceed team capacity. | A model flagging more accounts than the team can handle produces no additional action: the constraint is operational, not statistical. |
| 5 | `test_les_trois_niveaux_d_impact_sont_decroissants` | Exposed, covered and preserved revenue must decrease in that order. | An inversion would mean claiming to save more than what is at risk - the kind of figure that discredits an entire presentation. |
| 6 | `test_intervalle_de_confiance_sur_le_rappel` | The stated uncertainty on recall must remain around five points. | Section 9 tells the jury that two operating points at 70% and 74% are statistically indistinguishable. That statement must stay true. |
| 7 | `test_une_valeur_construite_sans_l_issue_n_est_pas_signalee` | Leavers are younger here, so their value is lower. | but the outcome adds nothing. |
| 8 | `test_une_valeur_qui_encode_l_issue_est_signalee` | A value cut short by the actual departure is caught: the outcome explains it. | — |
| 9 | `test_le_rappel_et_la_precision_du_haut_du_classement` | Top 20 % of ten accounts = two accounts; one of the two churners is among them. | — |
| 10 | `test_l_erreur_de_calibration_distingue_une_probabilite_juste_d_une_biaisee` | _(sans description)_ | — |
| 11 | `test_un_classement_n_a_ni_brier_ni_calibration` | A ranking rule is not a probability: its calibration is reported missing, not computed. | — |
| 12 | `test_le_protocole_couvre_25_plis_et_chaque_compte_une_fois_hors_pli` | _(sans description)_ | — |
| 13 | `test_le_protocole_et_la_selection_utilisent_les_memes_plis` | The baselines are measured on the very folds the phase 5 selection used. | — |

### Artefacts et fiche modèle

**Fichier :** `tests/test_packaging.py` — **Activité :** 5 · Packaging — **Compétences :** C6

**Ce que ce fichier protège :** La solidarité entre le modèle sérialisé et sa fiche

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_le_modele_et_sa_fiche_sont_enregistres_ensemble` | A model must never be written without its card. | A model shipped alone is an orphan artefact: nobody knows what data it learned from, nor what it cannot do. |
| 2 | `test_la_fiche_modele_est_remplie_depuis_le_contexte` | The card must be generated from training metadata, not hand-written. | Generation is what prevents the card and the artefact from drifting apart. |
| 3 | `test_les_champs_absents_prennent_leur_valeur_par_defaut` | A missing field must fall back to the template default, never to an empty slot. | An unsubstituted placeholder shipped to a jury reads as an unfinished deliverable. |

### Dérive et règles d'alerte

**Fichier :** `tests/test_monitoring.py` — **Activité :** 7 · Monitoring — **Compétences :** C8, C9

**Ce que ce fichier protège :** Le calcul de dérive et la boucle indicateur → seuil → action

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_psi_nul_sur_distributions_identiques` | Identical distributions must score near zero. | A drift indicator raising alerts on stable data would be switched off within a month. |
| 2 | `test_psi_detecte_un_decalage_franc` | A clear distribution shift must cross the alert threshold. | — |
| 3 | `test_ks_coherent_avec_le_psi` | The Kolmogorov-Smirnov test must agree with PSI on obvious cases. | The two indicators are read together: a disagreement on a clear-cut case would mean one of them is misconfigured. |
| 4 | `test_rapport_derive_marque_les_alertes` | The drift report must flag the drifting variable and only that one. | — |
| 5 | `test_chaque_regle_porte_une_action_et_un_responsable` | No rule may exist without a triggered action and a named owner. | A dashboard with no action owner produces no decision - it produces meetings. |
| 6 | `test_alerte_declenchee_expose_son_action` | A triggered alert must surface what to do and who does it. | — |
| 7 | `test_le_psi_categoriel_est_nul_sans_changement_et_positif_sinon` | _(sans description)_ | — |
| 8 | `test_une_hausse_des_manquants_categoriels_est_une_derive` | Missing values form their own category: more of them is a drift. | — |
| 9 | `test_une_derive_categorielle_declenche_une_alerte` | A sector mix moving from 50/50 to 95/5 must raise an alert. | Until phase 5 the numeric index was applied to every column: on text it returned NaN, and NaN compared to the threshold gave "no alert". The largest possible drift on a categorical variable was reported as none, without any error. |

### Contrat d'affichage des notebooks

**Fichier :** `tests/test_notebook.py` — **Activité :** Transverse — **Compétences :** C3, C6

**Ce que ce fichier protège :** L'unicité du code affiché et l'absence de troncature des tableaux

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_la_source_affichee_est_celle_du_module` | `afficher_source` reads the code from the module, so it cannot drift. | This is the invariant that allows a self-contained notebook with no duplicated code. |
| 2 | `test_le_tableau_affiche_ne_tronque_aucune_cellule` | A truncated table is a lost argument: the renderer must never elide content. | — |
| 3 | `test_le_rendu_ne_depend_pas_d_ipython` | The markup must be produced even without IPython installed. | Caught on a fresh clone installed with the `dev` group only: the function ignored `retourner_html` on the fallback path and returned None. The defect was invisible in a notebook environment, where IPython is always present - exactly the kind of gap a test run in the development environment alone never sees. |

### Conventions de travail

**Fichier :** `tests/test_conventions.py` — **Activité :** Transverse — **Compétences :** —

**Ce que ce fichier protège :** Les règles de langue : commentaires en anglais, contenu affiché en français

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_les_commentaires_sont_en_anglais` _(×80)_ | Comments stay in English across the whole source tree. | Mixed-language comments make a file harder to scan than either language alone: the reader switches context line by line. |
| 2 | `test_les_docstrings_sont_en_anglais` _(×80)_ | Docstrings stay in English: they document the implementation, not the deliverable. | — |
| 3 | `test_le_contenu_affiche_reste_en_francais` | Displayed labels stay in French: the deliverable is read by a French-speaking jury. | Checked on the governance and alerting tables, which are rendered as-is in the notebooks. An English column heading there would be a mistake, not a convention. |
| 4 | `test_les_carnets_respectent_le_format_notebook` _(×7)_ | Every notebook validates against the nbformat schema. | A markdown cell carrying an `outputs` field is accepted by Jupyter and rejected by stricter readers - the linter caught one that had survived several executions. A deliverable that some tools refuse to open is a risk not worth running the week of submission. |
| 5 | `test_le_notebook_de_certification_reste_sans_sorties` | The certification notebook ships without outputs until the freeze. | Committed outputs would make every run produce a diff, drowning the real changes. The notebook is executed at the freeze milestone, deliberately and once. |
| 6 | `test_les_dependances_des_tests_sont_declarees` | Every third-party module the tests import is declared in base or dev dependencies. | A dependency inherited transitively from another group works locally, where the full environment is installed, and fails in CI, which installs only `dev`. That is exactly how `nbformat` slipped through: imported by the tests, provided by `nbconvert` in the `notebook` group, absent from the pipeline. Declaring it where the tests run turns a pipeline failure into a static check. |
| 7 | `test_le_catalogue_s_ecrit_en_utf8_quel_que_soit_le_terminal` | The catalogue writes itself in UTF-8 rather than relying on shell redirection. | Redirecting the output tied the result to the terminal encoding: a Windows console opens `sys.stdout` in cp1252 and cannot represent the arrows the document contains, so `catalogue_tests.py > docs/TESTS.md` failed there while working on Linux. A tool whose success depends on the operating system of whoever runs it is a tool the CI cannot vouch for. |
| 8 | `test_chaque_outil_est_couvert_par_le_controle_d_encodage` | A new tool must join the check below; a forgotten one would escape it silently. | — |
| 9 | `test_chaque_outil_ecrit_sa_sortie_en_utf8_quel_que_soit_le_terminal` _(×9)_ | Every tool prints UTF-8, even when the terminal announces cp1252. | A Windows terminal hands a piped child process cp1252: "…" became byte 0x85, which a UTF-8 reader cannot decode. That is how the materialisation test failed on the development laptop while passing on Linux. The terminal is simulated here, so the CI reproduces what Windows does. |
| 10 | `test_les_fichiers_ecrits_par_le_code_se_terminent_par_un_saut_de_ligne` | Files our code writes and Git versions must end with a newline. | Without it, `end-of-file-fixer` rewrites the file at every commit: the hook fails, the CI fails, and the diff shows a single character on a file whose content never changed. The noise then trains everyone to run `--no-verify`, which is how a guardrail dies. Covers the three writers: the data manifest, the model card written next to the serialised model, and the generated model card. |

### Stockage et cache des figures

**Fichier :** `tests/test_figures.py` — **Activité :** Transverse — **Compétences :** C3, C8

**Ce que ce fichier protège :** Le cache des figures : une image périmée servie en silence serait pire qu'une régénération systématique

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_le_chemin_se_deduit_du_nom` | No caller writes a path: a hardcoded one breaks when the tree moves. | — |
| 2 | `test_la_figure_est_ecrite_dans_les_deux_formats` | PNG for documents and slides, SVG for anything that may be enlarged. | — |
| 3 | `test_la_cle_depend_des_donnees` | _(sans description)_ | — |
| 4 | `test_la_cle_depend_du_code_de_trace` | This is the property that makes the cache safe. | A key built on the data alone would keep serving an old image after the plotting code changed - exactly the situation a cache must never create. Hashing the source means a changed colour invalidates the stored figure, with nobody having to remember a version number. |
| 5 | `test_la_cle_est_stable_a_donnees_et_code_identiques` | _(sans description)_ | — |
| 6 | `test_une_figure_absente_doit_etre_tracee` | _(sans description)_ | — |
| 7 | `test_une_signature_illisible_force_le_trace` | A corrupted sidecar must not be read as agreement. | — |
| 8 | `test_une_figure_supprimee_est_retracee_malgre_sa_signature` | _(sans description)_ | — |
| 9 | `test_l_etat_du_cache_explique_sa_decision` | The reason is returned, not just a boolean: a cache that decides in silence is a cache nobody trusts, and the notebook prints the reason. | — |
| 10 | `test_la_figure_n_est_tracee_qu_une_fois` | Two runs on unchanged data and code must not redraw anything. | — |
| 11 | `test_un_changement_de_donnees_retrace_la_figure` | _(sans description)_ | — |
| 12 | `test_un_changement_de_code_retrace_la_figure` | Editing the plot must change the stored image, without touching the data. | — |
| 13 | `test_la_figure_rendue_est_bien_celle_du_dernier_trace` | Beyond the reason reported, the file on disk must have changed. | — |
| 14 | `test_l_inventaire_recense_les_figures_disponibles` | _(sans description)_ | — |
| 15 | `test_l_inventaire_d_un_dossier_absent_reste_lisible` | An empty inventory is a table with no row, never an exception. | — |
| 16 | `test_la_signature_enregistree_est_relisible` | _(sans description)_ | — |

### Récapitulatif de la suite

**Fichier :** `tests/test_recapitulatif.py` — **Activité :** Transverse — **Compétences :** —

**Ce que ce fichier protège :** Les taux affichés en fin de run : un taux faux donnerait confiance sans raison

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_un_test_ignore_fait_chuter_le_taux_d_execution` | A skipped test lowers the execution rate without touching the success rate. | This is the whole point of separating the two: a suite reported as "100% green" while half of it never ran proves nothing, and the success rate alone would say nothing about it. |
| 2 | `test_un_echec_fait_chuter_le_taux_de_reussite_pas_celui_d_execution` | _(sans description)_ | — |
| 3 | `test_une_erreur_de_fixture_compte_comme_un_echec` | A test that never started is not a neutral event: the guarantee is missing. | — |
| 4 | `test_un_echec_attendu_compte_comme_une_reussite` | An expected failure documents an observed behaviour: it is a verified guarantee. | — |
| 5 | `test_les_taux_restent_definis_sur_une_suite_vide` | No division by zero on an empty selection: `pytest -k` may match nothing. | — |
| 6 | `test_un_fichier_prend_la_couleur_de_son_issue_la_plus_grave` _(×5)_ | One failure among twenty passes must colour the file red, not green. | — |
| 7 | `test_chaque_issue_porte_un_symbole_distinct` | The symbol carries the meaning when colour is unavailable: CI logs, redirection. | — |
| 8 | `test_un_taux_arrondi_ne_pretend_jamais_atteindre_cent` _(×5)_ | 99.5% must never be displayed as "100%". | Announcing a flawless run while a test failed is the single most misleading thing a summary can do - and rounding does it silently. |
| 9 | `test_une_racine_temporaire_saine_est_conservee` | A working temp root must be left alone: the fallback is an exception, not a rule. | — |
| 10 | `test_un_dossier_pytest_illisible_est_detecte` | The exact failure seen on Windows: `pytest-of-<user>` unreadable. | pytest reuses that directory across runs, and `os.scandir` raises on it. Every test taking `tmp_path` then errors at setup - thirteen of them - for a reason unrelated to the code. Detecting it turns a wall of stack traces into one actionable line. |
| 11 | `test_une_racine_impossible_a_creer_est_detectee` | A temp root that cannot even be created is reported, not silently retried. | — |

### Défaut de casse des modalités

**Fichier :** `tests/test_regression_casse_modalites.py` — **Activité :** 1 · Données — **Compétences :** C3

**Ce que ce fichier protège :** Le défaut trouvé en phase 3 : ce qu'il produisait, et ce que la correction produit — les deux sont figés pour rester traçables

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_sans_normalisation_les_categories_sont_fragmentees` _(×3)_ | Without value normalisation, each spelling counts as its own category. | One-hot encoding would then produce a column per spelling: the model sees several rare categories where the business has one, splits the signal between them, and every importance reading becomes misleading. |
| 2 | `test_sans_normalisation_des_modalites_deviennent_trop_petites` | Fragmentation creates modalities too small for their rate to mean anything. | `tpe` carried 49 accounts against 1 435 for `TPE`. The small one, statistically unstable, then set the extreme of the segment table published in the framing notebook. |
| 3 | `test_sans_normalisation_les_ecarts_entre_segments_sont_surestimes` _(×3)_ | The fragmented spread is what the framing notebook published, and it was wrong. | Pinned here so the erroneous figures stay traceable: a reader of the git history must be able to tell which numbers were corrected, and by how much. |
| 4 | `test_apres_normalisation_une_seule_etiquette_par_categorie` _(×3)_ | One label per business category, and it is the most frequent spelling. | A deliverable read by a jury should show `TPE`, not `tpe`. |
| 5 | `test_apres_normalisation_les_ecarts_refletent_le_metier` _(×3)_ | The corrected spreads are those the framing notebook now publishes. | They are roughly half the previous ones - which **strengthens** the framing conclusion: no segment concentrates the risk, so a model is justified over a business rule. The argument held; the figure supporting it did not. |
| 6 | `test_apres_normalisation_aucune_modalite_n_est_marginale` | Every modality now carries enough accounts for its rate to be readable. | This is what makes grouping unnecessary, a decision stated in the exploration notebook. |
| 7 | `test_la_normalisation_est_desactivable_explicitement` | An empty list means "normalise nothing", it does not fall back to the default. | Written with `or` instead of `is None`, the parameter silently ignored an empty list - and the defect tests above would have measured the corrected behaviour while claiming to measure the broken one. |
| 8 | `test_l_audit_chiffre_les_modalites_en_trop` | The audit counts the surplus modalities instead of naming the columns. | Phase 2 reported "case and whitespace inconsistent" on three columns and stopped there. A defect stated without its scope cannot be arbitrated: 26 surplus modalities is a number a reader can act on, "inconsistent" is not. |
| 9 | `test_l_audit_signale_les_deux_consequences_de_la_casse` | Both effects are reported, not just the join failure. | Phase 2 mentioned only the silent join. The second - category fragmentation at encoding time - is the more damaging, and it is the one that actually invalidated published figures. |

### Non-régression des phases terminées

**Fichier :** `tests/test_non_regression.py` — **Activité :** Transverse — **Compétences :** C1, C2, C3, C4, C5

**Ce que ce fichier protège :** Les chiffres publiés dans les carnets, les documents et la soutenance — un fichier par projet, une section par phase close

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_les_chiffres_publies_sont_inchanges` _(×45)_ | A published figure must still be reproducible by the code that produced it. | When this fails, the code is not necessarily wrong: a source may legitimately have changed. What is certain is that the documents listed in `cite_dans` now contradict it, and must be updated in the same commit. |
| 2 | `test_l_ecart_de_seuil_entre_deciles_reste_superieur_a_cent` | The "factor over 100" argument justifies rejecting a single global threshold. | It is the central argument of the decision rule, quoted in the framing notebook, in the explanatory document and in the oral pitch. If the spread narrowed, a global threshold would become defensible and the whole design would need rethinking. |
| 3 | `test_le_seuil_du_dernier_decile_reste_tres_bas` | Acting on a top-decile account stays rational below 1% risk. | The 0.3% figure is the striking end of the argument presented to the jury. |
| 4 | `test_les_hypotheses_de_cadrage_sont_inchangees` | These values are quoted verbatim in the documents and in the oral pitch. | — |
| 5 | `test_la_precision_statistique_du_rappel_reste_autour_de_cinq_points` | The "±5 points" caveat stated in section 9 must remain true. | Saying it before the jury does is worth more than being told; but only while it holds. |
| 6 | `test_la_jointure_catalogue_apparie_tous_les_comptes` | A silent join failure would corrupt every downstream figure. | — |
| 7 | `test_la_normalisation_de_la_cle_reste_indispensable` | Without normalisation the join matches nothing, and raises nothing. | This measurement is the one quoted to justify the normalisation step. Should the sources become consistent on their own, the argument would need rewording - the code would still be right, the document would be misleading. |
| 8 | `test_chaque_colonne_source_porte_toujours_un_role` | A new column arriving undocumented is a column nobody decided what to do with. | — |
| 9 | `test_six_colonnes_restent_hors_du_modele` | Six columns cannot be explanatory variables, for six distinct reasons. | The count is quoted in the phase 2 notebook and in the explanatory document. The motives are not interchangeable: the grid separates the ethical exclusion from the technical one. |
| 10 | `test_les_sources_correspondent_toujours_au_manifeste` | The recorded fingerprints still match the files on disk. | This is the strongest non-regression guarantee of the project: it states that the data themselves have not moved. Every other figure here is computed from them, so a failure on this test explains all the others at once. |
| 11 | `test_les_modalites_ne_comportent_plus_de_variante_de_casse` | One label per business category, across every categorical column. | Normalising the join key alone left `TPE` and `tpe` as two categories in the dataset. One-hot encoding then produced a column per spelling: the model saw several rare categories where the business has one, split the signal between them, and every importance reading became misleading. |
| 12 | `test_les_nan_des_ratios_ont_une_cause_unique_et_connue` | Every NaN in `tickets_par_actif` comes from a zero denominator, nothing else. | The claim made in section 3.4 - that these NaN encode an abandoned account - only holds while this is true. Another cause appearing would make the explanatory indicator partly wrong without any metric saying so. |
| 13 | `test_les_trous_structurels_sont_combles_sur_le_chemin_du_gold` | Phase 4: in gold, the per-user ratios are 0 on abandoned accounts, and the only NaN left in `usage_par_actif` are hours genuinely unknown on accounts that have users. | the one kind of gap the median may fill. |
| 14 | `test_aucun_segment_ne_concentre_le_risque` | No segment stands out enough for a business rule to replace the model. | This is the framing conclusion of section 1.2: it justifies building a model rather than writing "watch sector X". It was published on overstated spreads - 13 to 17 points instead of 7 to 8 - which made it look weaker than it is. The threshold is set at 15 points: beyond that, a simple segmentation would start to compete with the model and the framing would need revisiting. |
| 15 | `test_la_chaine_produit_deux_fois_le_meme_jeu_gold` | Two runs on the same sources must give the same gold dataset, byte for byte. | This is the assumption the whole snapshot mechanism rests on. If it broke - a pandas upgrade, a change in join order - the fingerprint recorded in the manifest would no longer identify anything, and a model card would describe data the model never saw. The check is cheap: the chain runs in under a second on this volume. |
| 16 | `test_les_instantanes_derives_ne_sont_pas_versionnes` | Parquet snapshots stay out of Git; the manifest that describes them stays in. | Versioning the snapshots would produce a binary diff at every change to the cleaning rules, for information already held by the sources plus the code. The manifest is small, textual, and it is the contract. |
| 17 | `test_les_figures_produites_ne_sont_pas_versionnees` | Figures are outputs: regenerable, and a binary diff at every retouch otherwise. | The documents that reuse them get them by running the notebook, not from the history. |
| 18 | `test_le_cache_des_figures_depend_du_code_de_trace` | The property the whole figure cache rests on, pinned here as well. | If the key stopped covering the drawing code, every notebook would keep displaying figures from a previous version - and the deliverable would show pictures that no longer match the numbers beside them. |
| 19 | `test_le_contrat_de_donnees_est_respecte_sur_le_jeu_de_reference` | The reference data pass every check of the contract, without a single watch flag. | If a check turned to "to watch" here, either the data moved (the manifest test says so) or a cleaning rule regressed. |
| 20 | `test_aucune_colonne_numerique_n_entre_dans_le_modele_comme_categorie` | Every non-numeric explanatory column is genuinely textual. | Generic on purpose: it names no column. The catalogue prices reached the model as categories until phase 4; the next column read as text by mistake will fail here too. |
| 21 | `test_aucune_date_n_entre_dans_le_modele` | A raw date one-hot encoded is one category per day: noise, and unknown at scoring. | — |
| 22 | `test_aucune_colonne_du_gold_n_est_le_doublon_d_une_autre` | Two identical columns give the model the same information twice, under two names. | `fonctionnalites_incluses` was an exact copy of `fonctionnalites_total`, and `taux_activation` a rescaled copy of `taux_adoption_pct`, until phase 4. Generic: compares every pair, names none. |
| 23 | `test_les_manquants_du_delai_restent_au_hasard_apres_correction` | The phase 3 conclusion still holds on the corrected column. | Phase 3 concluded that support delays are missing at random, on a column where more than half the gaps were conversion losses. Corrected, the column must still show no structural cause (no ticket) and no churn signal - otherwise the imputation strategy built on that conclusion would rest on nothing. |
| 24 | `test_l_absence_d_une_valeur_source_n_est_toujours_pas_un_signal` | Phase 2 published a 4.5-point maximum churn gap on raw data; it holds after cleaning. | Measured on silver now, since the cleaning is what phase 4 changed. A gap growing past the published figure plus its tolerance would mean the cleaning creates a signal. |
| 25 | `test_le_manifeste_decrit_les_jeux_produits_par_le_code` | The derived datasets recorded in the manifest are the ones the code produces today. | Changing a cleaning rule changes silver and gold. Without this test the manifest kept describing the phase 3 gold - 34 columns, misread dates - while the code produced another one, and a model card would have cited a fingerprint nobody can reproduce. When it fails after a deliberate change: re-run the materialisation (README of the phase 4 delivery), then commit the manifest with the code. |
| 26 | `test_le_contrat_mesure_les_manquants_de_la_source` | The reconstruction runs after the contract, so the contract still sees real gaps. | Placed before, it would report 0 % missing revenue where the source has 3 %, and the monthly monitoring of incoming data quality would go blind. |
| 27 | `test_la_valeur_vie_client_n_encode_pas_l_issue` | Arbitrage 3 settled by measurement: the observed value may evaluate the rule. | The 18.9 against 15.6 months gap is a composition effect - leavers are younger accounts. Were the value to start encoding the outcome, the impact measured in phase 9 would be inflated, and this test would say so before the jury does. |
| 28 | `test_les_attributs_de_formule_ne_prennent_qu_une_valeur_par_plan` | The premise of arbitrage 2: if a plan ever had two prices, `plan` alone would lose it. | — |
| 29 | `test_le_decoupage_reste_celui_qui_a_ete_publie` | 4,000 / 1,000 accounts, the same 28 % churn rate in both parts. | — |
| 30 | `test_chaque_variable_est_stable_entre_entrainement_et_test` | Largest PSI published at 0.033 (utilisateurs_actifs), rule: below 0.10 everywhere. | — |
| 31 | `test_l_entrainement_et_le_test_sont_indiscernables` | Adversarial validation, published at 0.52 with the forest; checked here with the logistic regression, which reaches the same verdict in a second instead of fifteen. | — |
| 32 | `test_le_modele_bat_les_etiquettes_melangees` | Published with 100 shuffles: 0.789 against 0.285, p = 0.01. | Twenty shuffles here, the fewest that can reach p < 0.05, to keep the suite fast. |
| 33 | `test_la_regression_logistique_a_converge` | Learning curve: validation PR-AUC 0.789 at full size, 0.016 from the training score. | — |
| 34 | `test_le_manifeste_decrit_le_decoupage_produit_par_le_code` | The test part recorded is the one the code sets aside today. | When it fails after a deliberate change: re-run the materialisation (carnet 03), then commit the manifest with the code. Until then, no result on the test part is comparable. |
| 35 | `test_les_variables_retenues_sont_celles_de_la_selection` | The 18 variables the selection kept, and only them; no decoy reaches the model. | — |
| 36 | `test_les_familles_couvrent_exactement_le_jeu_candidat` | Every candidate variable belongs to one family, so the ablation misses none. | — |
| 37 | `test_les_variables_construites_n_apportent_toujours_rien` | Bloc B, logistic regression: gain -0.001, under one std between folds (0.020). | — |
| 38 | `test_les_retraits_combines_ne_coutent_rien` | Removals were confirmed one by one; together, the 18 variables lose nothing either (logistic regression: +0.003 over the 25 candidates, better on 23 folds out of 25). | — |
| 39 | `test_la_fuite_de_la_sante_du_compte_reste_demontree` | Bloc D: the same logistic regression goes from 0.891 to 0.999 AUC with the end-of-period health score. | the leak the notebook narrates, now measured. |
| 40 | `test_les_resultats_de_reference_sont_reproduits` | The code still yields, fold by fold, the baselines' results phase 7 must beat. | When it fails after a deliberate change to the data or the protocol: rerun `tools/resultats_reference.py`, then commit the file with the change. |
| 41 | `test_le_modele_bat_la_regle_metier_qui_bat_le_hasard` | PR-AUC 0.793 > 0.530 > 0.280: the model is worth more than what a CSM would do alone. | — |
| 42 | `test_la_regression_doit_etre_calibree_en_phase_7` | Calibration error 0.11, over the 0.05 threshold fixed beforehand: phase 7 calibrates. | The class weighting that helps ranking pushes the probabilities up. |
| 43 | `test_le_jeu_vu_par_mlflow_est_celui_du_manifeste` | The data run attaches the gold with the manifest's own fingerprint as digest. | — |
| 44 | `test_les_baselines_retracees_sont_les_references_figees` | Phase 6 replayed into MLflow gives back, to the digit, the recorded reference. | — |

### test_campagnes.py

**Fichier :** `tests/test_campagnes.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_l_activite_courante_a_une_campagne` | _(sans description)_ | — |
| 2 | `test_chaque_marqueur_de_campagne_est_declare` | With --strict-markers, an undeclared marker fails loudly instead of selecting nothing. | — |
| 3 | `test_chaque_fichier_de_non_regression_existe` | _(sans description)_ | — |
| 4 | `test_aucun_test_ne_tourne_deux_fois_dans_une_campagne` | A file listed for non-regression carries no activity marker, or it would run twice. | — |
| 5 | `test_les_tests_courants_selectionnent_des_tests` | A campaign whose current level selects nothing would pass without testing anything. | — |
| 6 | `test_un_test_ne_porte_qu_un_marqueur_d_activite` | Two activity markers on one test would run it in both the current and the earlier level of the same campaign. | — |
| 7 | `test_les_marqueurs_precedents_sont_declares` | _(sans description)_ | — |

### test_industrialisation.py

**Fichier :** `tests/test_industrialisation.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_le_lot_mensuel_appelle_la_chaine_partagee` | `preparer` must go through the shared chain, never rebuild silver on its own. | Until phase 4 it called `construire_silver` without the column lists: the batch would have been scored on numbers left as text while training used converted ones. |
| 2 | `test_le_lot_mensuel_passe_le_contrat_de_donnees` | _(sans description)_ | — |
| 3 | `test_le_lot_mensuel_prepare_comme_l_entrainement` | On the full dataset, the batch preparation yields the training gold, byte for byte. | — |
| 4 | `test_le_contrat_du_lot_n_exige_pas_les_colonnes_posterieures` | A monthly batch has no outcome yet: its contract must not demand `churn`. | — |

### test_modelisation.py

**Fichier :** `tests/test_modelisation.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_l_imputation_est_apprise_sur_le_pli_d_entrainement_seulement` | The median learnt is the training fold's, never the whole table's. | Training fold: 1, 2, 3 -> median 2. Whole table: median 3. Fitted on everything, the test rows (100, 200) would have pulled the value imputed into training rows. |
| 2 | `test_aucune_valeur_manquante_ne_sort_du_preprocesseur` | _(sans description)_ | — |
| 3 | `test_les_categories_manquantes_deviennent_non_renseigne` | An explicit category, not the most frequent one. | The mode would have turned the unknown sector into "Retail" here, inflating the dominant segment and biasing the per-segment fairness analysis. |
| 4 | `test_le_candidat_partage_le_preprocesseur_de_la_baseline` | One imputation strategy for both models: otherwise the comparison measures two. | — |
| 5 | `test_la_conversion_en_energie_et_en_emissions_est_exacte` | One hour at 10 W is 10 Wh; at 30.2 g/kWh, 0.302 g. | Ten runs, ten times as much. |
| 6 | `test_la_charge_se_deduit_des_temps_elementaires` | The workload is declared as data: each step costs its operations times their time. | — |
| 7 | `test_la_mesure_des_temps_renvoie_chaque_operation` | Smoke test on a small frame: every elementary time the document needs is measured. | — |
| 8 | `test_la_validation_adverse_ne_distingue_pas_deux_tirages_de_la_meme_source` | _(sans description)_ | — |
| 9 | `test_la_validation_adverse_detecte_un_decalage` | A test part drawn elsewhere is told apart. | The check can fail, which is what gives its passing a meaning. |
| 10 | `test_le_test_de_permutation_separe_signal_et_bruit` | Real signal beats every shuffle; pure noise does not. | — |
| 11 | `test_la_courbe_d_apprentissage_couvre_chaque_taille` | _(sans description)_ | — |
| 12 | `test_une_variable_connue_apres_l_issue_est_demontree_comme_fuite` | A variable built from the outcome lifts the AUC to near perfection: the symptom. | — |
| 13 | `test_la_regle_metier_classe_par_la_variable_choisie` | The longer since the last login, the higher the score; a gap gets the median. | — |
| 14 | `test_la_baseline_naive_annonce_le_taux_de_base` | _(sans description)_ | — |

### test_registre.py

**Fichier :** `tests/test_registre.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_chaque_entree_porte_les_champs_obligatoires` | An entry without a motive or a source is an assertion, not a trace. | — |
| 2 | `test_les_identifiants_sont_uniques` | _(sans description)_ | — |
| 3 | `test_chaque_element_differe_a_une_condition_de_reexamen` | A postponement without a criterion for coming back is an abandonment in disguise. | — |
| 4 | `test_les_preuves_citees_existent` | A motive citing a renamed test, or a moved file, silently loses its evidence. | — |
| 5 | `test_aucune_colonne_ne_disparait_sans_trace` | Every column of silver missing from the model carries a motive in the code. | Generic: it names no column. Dropping a variable is a decision; this makes sure the decision is written down where the register reads it. |
| 6 | `test_le_registre_reprend_chaque_exclusion_du_code` | The readable register lists every excluded column, read from the code. | — |
| 7 | `test_le_registre_genere_est_a_jour` | The document matches its source. | otherwise it describes decisions no longer made. |
| 8 | `test_le_document_s_ouvre_par_l_avertissement_de_generation` | A reader must know not to edit it, or the next generation erases the edit. | — |

### test_ressources.py

**Fichier :** `tests/test_ressources.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_l_entree_porte_toutes_les_sections` | _(sans description)_ | — |
| 2 | `test_chaque_hypothese_cite_sa_source` | A power or a carbon intensity without its source is an assertion, not an input. | — |
| 3 | `test_chaque_mesure_attendue_est_presente_et_positive` | _(sans description)_ | — |
| 4 | `test_le_poste_est_decrit` | _(sans description)_ | — |
| 5 | `test_la_description_du_poste_fonctionne_sur_ce_systeme` | Each system has its own source; on the one running the suite, none may come back empty. | — |
| 6 | `test_le_document_de_sobriete_est_a_jour` | The document matches its input. | otherwise it states a footprint nobody measured. |
| 7 | `test_des_mesures_provisoires_sont_signalees_comme_telles` | Measures not taken on the development laptop must say so at the top of the document. | — |
| 8 | `test_l_ecriture_preserve_les_hypotheses_declarees` | Re-measuring the machine must never overwrite what a person declared. | — |

### test_resultats_reference.py

**Fichier :** `tests/test_resultats_reference.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_un_ecart_sur_un_pli_est_detecte` | _(sans description)_ | — |
| 2 | `test_le_bruit_numerique_est_ignore` | _(sans description)_ | — |
| 3 | `test_une_metrique_qui_cesse_de_s_appliquer_est_detectee` | _(sans description)_ | — |
| 4 | `test_un_changement_de_donnees_est_detecte` | _(sans description)_ | — |
| 5 | `test_une_valeur_manquante_s_ecrit_null` | _(sans description)_ | — |

### test_suivi.py

**Fichier :** `tests/test_suivi.py` — **Activité :** — — **Compétences :** —

**Ce que ce fichier protège :** —

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_chaque_metrique_du_protocole_a_une_cle_ascii` | MLflow refuses accents in metric keys: every protocol metric needs its ASCII key. | — |
| 2 | `test_le_magasin_du_projet_est_un_chemin_absolu` | A relative store would differ between a notebook run in notebooks/ and a tool. | — |
| 3 | `test_les_tests_n_ecrivent_jamais_dans_le_magasin_du_projet` | _(sans description)_ | — |
| 4 | `test_sans_mlflow_le_suivi_ne_fait_rien_et_n_echoue_pas` | The CI has no MLflow: tracking must be a silent no-op, not an error. | — |
| 5 | `test_chaque_pli_est_journalise_comme_une_etape` | _(sans description)_ | — |
| 6 | `test_le_modele_du_registre_predit_comme_le_modele_en_memoire` | Registered, aliased, reloaded: same probabilities, on rows holding missing values. | the signature accepts them because nullable integers became floats. |
| 7 | `test_un_run_porte_le_commit_et_les_empreintes` | _(sans description)_ | — |
| 8 | `test_les_artefacts_vont_a_cote_du_magasin_en_usage` | Never in a `mlruns/` relative to the current directory: beside the store in use. | here the test's temporary one, so no test writes into the project. |
| 9 | `test_le_parallelisme_se_regle_par_la_configuration` | _(sans description)_ | — |
| 10 | `test_la_duree_est_estimee_a_partir_des_temps_mesures` | _(sans description)_ | — |
| 11 | `test_relancer_la_chaine_ne_cree_pas_de_nouvelle_version` | Same code, same data, same configuration: the second execution registers nothing. | — |
| 12 | `test_relancer_le_retracage_ne_cree_pas_de_doublon` | _(sans description)_ | — |
| 13 | `test_une_meme_version_des_donnees_n_a_qu_un_run` | _(sans description)_ | — |
| 14 | `test_la_matrice_de_confusion_ne_change_pas_le_moteur_graphique` | Built without pyplot: in a notebook it must not switch the inline backend, and in a script it must not open Tk. | whose figures, destroyed by another thread at exit, made pipeline_mlflow.py print "main thread is not in main loop" on Windows. |
