# Catalogue des tests

> **Document généré.** Produit par `tools/catalogue_tests.py` à partir des fichiers de
> tests eux-mêmes. Un inventaire écrit à la main dérive dès le premier test ajouté, et
> un inventaire périmé est pire qu'aucun : il revendique une couverture qui n'existe
> plus. Régénérer avec :
>
> ```bash
> uv run python tools/catalogue_tests.py > docs/TESTS.md
> ```

**175 cas de test** issus de 67 fonctions, répartis sur 10 fichiers.

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
| [Structure du paquet](#structure-du-paquet) | `test_structure.py` | Transverse | C6 | 20 |
| [Nettoyage et niveaux de raffinage](#nettoyage-et-niveaux-de-raffinage) | `test_donnees.py` | 1 · Gestion des données | C3 | 7 |
| [Schéma, gouvernance et versionnement des données](#schéma-gouvernance-et-versionnement-des-données) | `test_donnees_gouvernance.py` | 1 · Gestion des données | C1, C2, C3 | 18 |
| [Construction et contrôle des variables](#construction-et-contrôle-des-variables) | `test_features.py` | 2 · Contrôle des features | C3, C5 | 4 |
| [Métriques, décision et impact](#métriques-décision-et-impact) | `test_evaluation.py` | 4 · Évaluation | C5, C8 | 6 |
| [Artefacts et fiche modèle](#artefacts-et-fiche-modèle) | `test_packaging.py` | 5 · Packaging | C6 | 3 |
| [Dérive et règles d'alerte](#dérive-et-règles-dalerte) | `test_monitoring.py` | 7 · Monitoring | C8, C9 | 6 |
| [Contrat d'affichage des notebooks](#contrat-daffichage-des-notebooks) | `test_notebook.py` | Transverse | C3, C6 | 3 |
| [Conventions de travail](#conventions-de-travail) | `test_conventions.py` | Transverse | — | 99 |
| [Non-régression du cadrage](#non-régression-du-cadrage) | `test_non_regression_cadrage.py` | Transverse | C1, C4, C5 | 9 |

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

### Construction et contrôle des variables

**Fichier :** `tests/test_features.py` — **Activité :** 2 · Contrôle des features — **Compétences :** C3, C5

**Ce que ce fichier protège :** Les ratios d'usage et la détection générique de fuite

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_ratio_protege_contre_la_division_par_zero` | A zero denominator must yield NaN, never an infinity. | An infinity propagates silently through the pipeline and only surfaces as an absurd model coefficient, far from its cause. |
| 2 | `test_controle_de_schema_signale_une_colonne_absente` | A missing expected column must be reported as non-compliant. | This is step 2 of the CI chain: it blocks a batch rather than scoring out-of-domain data, which would produce plausible but wrong probabilities. |
| 3 | `test_detection_generique_de_fuite` | The check targets no named column: it spots the abnormal correlation. | — |
| 4 | `test_confirmation_empirique_des_leurres` | Decoy variables must be confirmed as useless by measurement, not by assumption. | Dropping them upfront would forfeit the interpretability demonstration the brief asks for; keeping them without checking would be an unverified claim. |

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
| 1 | `test_les_commentaires_sont_en_anglais` _(×47)_ | Comments stay in English across the whole source tree. | Mixed-language comments make a file harder to scan than either language alone: the reader switches context line by line. |
| 2 | `test_les_docstrings_sont_en_anglais` _(×47)_ | Docstrings stay in English: they document the implementation, not the deliverable. | — |
| 3 | `test_le_contenu_affiche_reste_en_francais` | Displayed labels stay in French: the deliverable is read by a French-speaking jury. | Checked on the governance and alerting tables, which are rendered as-is in the notebooks. An English column heading there would be a mistake, not a convention. |
| 4 | `test_les_carnets_respectent_le_format_notebook` _(×3)_ | Every notebook validates against the nbformat schema. | A markdown cell carrying an `outputs` field is accepted by Jupyter and rejected by stricter readers - the linter caught one that had survived several executions. A deliverable that some tools refuse to open is a risk not worth running the week of submission. |
| 5 | `test_le_notebook_de_certification_reste_sans_sorties` | The certification notebook ships without outputs until the freeze. | Committed outputs would make every run produce a diff, drowning the real changes. The notebook is executed at the freeze milestone, deliberately and once. |

### Non-régression du cadrage

**Fichier :** `tests/test_non_regression_cadrage.py` — **Activité :** Transverse — **Compétences :** C1, C4, C5

**Ce que ce fichier protège :** Les chiffres cités dans trois livrables et dans la soutenance

| # | Cas de test | Ce qu'il vérifie | Pourquoi il existe |
|---|---|---|---|
| 1 | `test_volumetrie_de_reference` | The source file and its duplicate count must be the ones the framing used. | Every figure downstream is computed on these 5,000 accounts: a changed source would invalidate the framing notebook, the explanatory document and the oral pitch at once. |
| 2 | `test_la_jointure_catalogue_apparie_tous_les_comptes` | A silent join failure would corrupt every downstream figure. | — |
| 3 | `test_taux_de_churn_de_reference` | The churn rate must stay at 28%. | It underpins the 'moderate imbalance' argument of section 8 and the 72% accuracy a trivial model would reach - both quoted verbatim in the deliverables. |
| 4 | `test_concentration_de_la_valeur` | 10% of accounts carry ~68% of revenue; 10% of churners carry ~72% of the loss. | This is the observation that turned exhaustive detection into prioritisation. |
| 5 | `test_mrr_total_de_reference` | Portfolio revenue must stay around 17.2 million euros. | This is the reference base against which exposed, covered and preserved revenue are expressed in section 12. |
| 6 | `test_l_ecart_de_seuil_entre_deciles_reste_superieur_a_cent` | The 'factor > 100' argument justifies rejecting a single global threshold. | — |
| 7 | `test_le_seuil_du_dernier_decile_reste_tres_bas` | Acting on a top-decile account must stay rational below 1% risk. | The 0.3% figure is the striking end of the argument presented to the jury. |
| 8 | `test_les_hypotheses_de_cadrage_sont_inchangees` | These three values are quoted verbatim in the documents and the oral pitch. | — |
| 9 | `test_precision_statistique_du_rappel_reste_autour_de_cinq_points` | The '+/- 5 points' caveat stated in section 9 must remain true. | — |
