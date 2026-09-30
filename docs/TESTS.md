# Catalogue des tests

> **Document généré.** Produit par `tools/catalogue_tests.py` à partir des fichiers de
> tests eux-mêmes. Un inventaire écrit à la main dérive dès le premier test ajouté, et
> un inventaire périmé est pire qu'aucun : il revendique une couverture qui n'existe
> plus. Régénérer avec :
>
> ```bash
> uv run python tools/catalogue_tests.py > docs/TESTS.md
> ```

**288 cas de test** issus de 122 fonctions, répartis sur 13 fichiers.

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
| [Structure du paquet](#structure-du-paquet) | `test_structure.py` | Transverse | C6 | 27 |
| [Nettoyage et niveaux de raffinage](#nettoyage-et-niveaux-de-raffinage) | `test_donnees.py` | 1 · Gestion des données | C3 | 9 |
| [Schéma, gouvernance et versionnement des données](#schéma-gouvernance-et-versionnement-des-données) | `test_donnees_gouvernance.py` | 1 · Gestion des données | C1, C2, C3 | 25 |
| [Construction et contrôle des variables](#construction-et-contrôle-des-variables) | `test_features.py` | 2 · Contrôle des features | C3, C5 | 4 |
| [Profilage et exploration](#profilage-et-exploration) | `test_exploration.py` | 1 · Données · 2 · Features | C3, C4 | 21 |
| [Métriques, décision et impact](#métriques-décision-et-impact) | `test_evaluation.py` | 4 · Évaluation | C5, C8 | 6 |
| [Artefacts et fiche modèle](#artefacts-et-fiche-modèle) | `test_packaging.py` | 5 · Packaging | C6 | 3 |
| [Dérive et règles d'alerte](#dérive-et-règles-dalerte) | `test_monitoring.py` | 7 · Monitoring | C8, C9 | 6 |
| [Contrat d'affichage des notebooks](#contrat-daffichage-des-notebooks) | `test_notebook.py` | Transverse | C3, C6 | 3 |
| [Conventions de travail](#conventions-de-travail) | `test_conventions.py` | Transverse | — | 117 |
| [Récapitulatif de la suite](#récapitulatif-de-la-suite) | `test_recapitulatif.py` | Transverse | — | 16 |
| [Défaut de casse des modalités](#défaut-de-casse-des-modalités) | `test_regression_casse_modalites.py` | 1 · Données | C3 | 17 |
| [Non-régression des phases terminées](#non-régression-des-phases-terminées) | `test_non_regression.py` | Transverse | C1, C2, C3, C4, C5 | 34 |

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
| 11 | `test_l_empreinte_change_si_une_valeur_change` | A single changed value must change the fingerprint. | Without this property the manifest would certify datasets it never verified. |
| 12 | `test_le_manifeste_detecte_une_source_modifiee` | Run before any training: a changed source means the run reproduces nothing. | — |
| 13 | `test_le_manifeste_signale_une_source_disparue` | A missing source must be reported, not silently ignored. | — |
| 14 | `test_les_tables_de_gouvernance_ne_sont_jamais_vides` _(×3)_ | An empty governance table would silently remove a section from the notebook. | — |
| 15 | `test_le_manifeste_n_est_pas_reecrit_sans_raison` | Two runs on unchanged sources must leave the manifest byte-identical. | Regenerating it each time would change `date_construction` and produce a diff on every commit for fingerprints that did not move. Noise of that kind trains readers to skip the file, and a manifest nobody reads certifies nothing. |
| 16 | `test_le_manifeste_est_reecrit_si_une_source_change` | A changed source must force a rewrite: silence there would certify a lie. | — |
| 17 | `test_l_inventaire_decrit_chaque_colonne` | The "before" snapshot must cover every column, including the empty ones. | Section 5 of the notebook compares this inventory to reference values. A column missing from it would silently escape the completeness check. |
| 18 | `test_la_table_des_exclusions_expose_chaque_motif` | Every excluded column appears with its own rationale. | The motives are not interchangeable: the grid separates ethics from technical preparation, so a single blanket justification would satisfy neither. |
| 19 | `test_l_empreinte_de_fichier_depend_du_contenu` | Identical bytes give the same fingerprint, a single changed byte gives another. | — |
| 20 | `test_l_empreinte_de_fichier_lit_par_blocs` | Block reading must give the same result as reading the file whole. | The block size bounds memory use on a large snapshot; a wrong implementation would only show up on files too big to notice during development. |
| 21 | `test_le_manifeste_se_relit_a_l_identique` | Writing then reading a manifest must return the same content. | The manifest is the contract between a data version and a model. A round-trip that loses a field would make the contract unverifiable without saying so. |
| 22 | `test_le_manifeste_enregistre_des_chemins_relatifs` | Paths are stored relative to the repository root, never absolute. | An absolute path ties the manifest to the machine that wrote it. Regenerated on a workstation and committed, it can no longer be verified anywhere else - CI included, where every source would be reported as missing. The check would then fail for a reason unrelated to the data it is meant to protect. |
| 23 | `test_le_manifeste_relatif_se_verifie_depuis_une_autre_racine` | A relative manifest verifies wherever the repository is cloned. | — |

### Construction et contrôle des variables

**Fichier :** `tests/test_features.py` — **Activité :** 2 · Contrôle des features — **Compétences :** C3, C5

**Ce que ce fichier protège :** Les ratios d'usage et la détection générique de fuite

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_ratio_protege_contre_la_division_par_zero` | A zero denominator must yield NaN, never an infinity. | An infinity propagates silently through the pipeline and only surfaces as an absurd model coefficient, far from its cause. |
| 2 | `test_controle_de_schema_signale_une_colonne_absente` | A missing expected column must be reported as non-compliant. | This is step 2 of the CI chain: it blocks a batch rather than scoring out-of-domain data, which would produce plausible but wrong probabilities. |
| 3 | `test_detection_generique_de_fuite` | The check targets no named column: it spots the abnormal correlation. | — |
| 4 | `test_confirmation_empirique_des_leurres` | Decoy variables must be confirmed as useless by measurement, not by assumption. | Dropping them upfront would forfeit the interpretability demonstration the brief asks for; keeping them without checking would be an unverified claim. |

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
| 1 | `test_les_commentaires_sont_en_anglais` _(×54)_ | Comments stay in English across the whole source tree. | Mixed-language comments make a file harder to scan than either language alone: the reader switches context line by line. |
| 2 | `test_les_docstrings_sont_en_anglais` _(×54)_ | Docstrings stay in English: they document the implementation, not the deliverable. | — |
| 3 | `test_le_contenu_affiche_reste_en_francais` | Displayed labels stay in French: the deliverable is read by a French-speaking jury. | Checked on the governance and alerting tables, which are rendered as-is in the notebooks. An English column heading there would be a mistake, not a convention. |
| 4 | `test_les_carnets_respectent_le_format_notebook` _(×4)_ | Every notebook validates against the nbformat schema. | A markdown cell carrying an `outputs` field is accepted by Jupyter and rejected by stricter readers - the linter caught one that had survived several executions. A deliverable that some tools refuse to open is a risk not worth running the week of submission. |
| 5 | `test_le_notebook_de_certification_reste_sans_sorties` | The certification notebook ships without outputs until the freeze. | Committed outputs would make every run produce a diff, drowning the real changes. The notebook is executed at the freeze milestone, deliberately and once. |
| 6 | `test_les_dependances_des_tests_sont_declarees` | Every third-party module the tests import is declared in base or dev dependencies. | A dependency inherited transitively from another group works locally, where the full environment is installed, and fails in CI, which installs only `dev`. That is exactly how `nbformat` slipped through: imported by the tests, provided by `nbconvert` in the `notebook` group, absent from the pipeline. Declaring it where the tests run turns a pipeline failure into a static check. |
| 7 | `test_le_catalogue_s_ecrit_en_utf8_quel_que_soit_le_terminal` | The catalogue writes itself in UTF-8 rather than relying on shell redirection. | Redirecting the output tied the result to the terminal encoding: a Windows console opens `sys.stdout` in cp1252 and cannot represent the arrows the document contains, so `catalogue_tests.py > docs/TESTS.md` failed there while working on Linux. A tool whose success depends on the operating system of whoever runs it is a tool the CI cannot vouch for. |
| 8 | `test_les_fichiers_ecrits_par_le_code_se_terminent_par_un_saut_de_ligne` | Files our code writes and Git versions must end with a newline. | Without it, `end-of-file-fixer` rewrites the file at every commit: the hook fails, the CI fails, and the diff shows a single character on a file whose content never changed. The noise then trains everyone to run `--no-verify`, which is how a guardrail dies. Covers the three writers: the data manifest, the model card written next to the serialised model, and the generated model card. |

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
| 1 | `test_les_chiffres_publies_sont_inchanges` _(×22)_ | A published figure must still be reproducible by the code that produced it. | When this fails, the code is not necessarily wrong: a source may legitimately have changed. What is certain is that the documents listed in `cite_dans` now contradict it, and must be updated in the same commit. |
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
| 13 | `test_aucun_segment_ne_concentre_le_risque` | No segment stands out enough for a business rule to replace the model. | This is the framing conclusion of section 1.2: it justifies building a model rather than writing "watch sector X". It was published on overstated spreads - 13 to 17 points instead of 7 to 8 - which made it look weaker than it is. The threshold is set at 15 points: beyond that, a simple segmentation would start to compete with the model and the framing would need revisiting. |
