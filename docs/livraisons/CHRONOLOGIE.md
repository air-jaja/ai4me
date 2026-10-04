# Chronologie des commits livrés

Extraite des patchs de chaque livraison (`git format-patch`) : hachage, date et objet de chaque commit **tels que livrés**.
Les commits de **décision** (règles fixées avant les calculs) sont en gras. Les dates sont celles des commits de travail ;
la fusion dans `develop` a pu les regrouper, et les hachages livrés ne sont alors pas ceux de l'historique du dépôt.

| Date (UTC) | Commit | Objet | Livraison |
|---|---|---|---|
| 01/10 13:59 | `3c5f8f0` | feat(donnees): phase 4 — nettoyage sans perte et contrat de données | livraison_phase4_preparation |
| 01/10 13:59 | `715c841` | docs(phase 4): suivi, règles et éléments de soutenance | livraison_phase4_preparation |
| 01/10 14:12 | `5b6f8e9` | fix(donnees): empreinte de contenu indépendante du système d'exploitation | correctif_phase4_empreinte |
| 01/10 14:12 | `b7b754d` | fix(donnees): empreinte de contenu indépendante du système d'exploitation | livraison_phase4_imputation_registre |
| 01/10 15:36 | `e6270fb` | feat(phase 4): imputation en quatre familles et chaîne partagée avec le lot mensuel | livraison_phase4_imputation_registre |
| 01/10 15:36 | `df28928` | feat(regle 13): registre généré des éléments écartés, différés ou à arbitrer | livraison_phase4_imputation_registre |
| 01/10 15:36 | `e0fbf5f` | docs(phase 4): règles 9, 10, 13 ; suivi et éléments de soutenance | livraison_phase4_imputation_registre |
| 01/10 16:26 | `eaedf1e` | notebook(certification): sections 0 à 7 réalignées sur les phases 1 à 4 | livraison_notebook_sections_0_7 |
| 01/10 16:47 | `f742cce` | docs(readme): déplace « Démarrage sous Windows, et dépannage » dans docs/DEPANNAGE.md | livraison_depannage_arborescence |
| 01/10 16:47 | `0a8d698` | test(structure): l'arborescence du README décrit le paquet tel qu'il est | livraison_depannage_arborescence |
| 02/10 05:03 | `f856ff5` | docs(phase 5): arbitrages du 01/10 et règles de décision fixées avant les résultats | livraison_arbitrages_phase5, livraison_ressources_poste |
| 02/10 05:20 | `ef83114` | feat(sobriete): ressources du poste en entrée du projet, empreinte mesurée et générée | livraison_ressources_poste |
| 02/10 05:20 | `0214b15` | docs(sobriete): le chiffrage renvoie à l'entrée du projet et au document généré | livraison_ressources_poste |
| 02/10 06:12 | `f881adf` | feat(phase 5, bloc 0): catalogue réduit à plan, valeur vie client diagnostiquée | livraison_phase5_bloc0 |
| 02/10 06:13 | `c5a02cc` | docs(phase 5, bloc 0): résultats consignés dans les choix, le suivi et le notebook | livraison_phase5_bloc0 |
| 02/10 07:06 | `a9536fc` | feat(phase 5, bloc A): découpage enregistré, séparation et jeu validés | livraison_phase5_blocA, livraison_phase5_carnet |
| 02/10 07:06 | `77f94f1` | docs(phase 5, bloc A): résultats contre les règles fixées d'avance | livraison_phase5_blocA, livraison_phase5_carnet |
| 02/10 07:53 | `f6968bb` | feat(phase 5): carnet de travail 05 et matérialisation sans Jupyter | livraison_phase5_carnet |
| 02/10 07:53 | `ab96bb0` | notebook(certification): étape 5 reportée (§ 7.7 et § 8.A) ; règle 4 révisée | livraison_phase5_carnet |
| 02/10 11:05 | `8a567f5` | feat(phase 5, blocs B et C): sélection des variables et campagnes de tests | livraison_phase5_blocsBC |
| 02/10 11:05 | `92648c2` | notebooks et docs (phase 5, blocs B et C): résultats, report, phase terminée | livraison_phase5_blocsBC |
| 02/10 13:38 | `438c430` | feat(phase 5, bloc D): clôture — fuite démontrée, notebook réaligné, Annexe D | livraison_phase5_blocD |
| 02/10 14:55 | `02abb36` | feat(phase 6): protocole d'évaluation, trois références, résultats enregistrés | livraison_phase6_baseline |
| 02/10 15:05 | `017b4e0` | notebooks et docs (phase 6): carnet 06, § 8.D, phase terminée | livraison_phase6_baseline |
| 02/10 17:10 | `3d7febb` | feat(phase 7, bloc 7.0): suivi des expériences avec MLflow | livraison_phase7_bloc70_mlflow |
| 02/10 21:09 | `7646f6d` | feat(phase 7, bloc 7.0 bis): relances fiables et ressources du poste | correctif_notebook_tk, livraison_phase7_bloc70bis |
| 02/10 21:34 | `af5d242` | notebook(07): relance sans doublon et durées annoncées contre mesurées | correctif_notebook_tk, livraison_phase7_bloc70bis |
| 02/10 23:03 | `fb1d476` | fix: notebook final exécuté sur place, et erreurs Tk de pipeline_mlflow.py | correctif_notebook_tk |
| 03/10 00:10 | `fae785b` | **decision(phase 7): règles B1 à B5 validées avant toute comparaison** | livraison_phase7_regles_A1 |
| 03/10 00:16 | `19a30a2` | fix(mlflow, A1): un seul contrôle de relance pour le retraçage et la chaîne | livraison_phase7_regles_A1 |
| 03/10 00:28 | `4d836c4` | **decision(règle 3, voie B): notebook de certification versionné avec ses sorties** | correctif_regle3_voieB |
| 03/10 00:43 | `ac646c6` | feat(phase 7, C2-C4): réglage, comparaison à la référence, calibration | livraison_phase7 |
| 03/10 00:45 | `ac9c538` | feat(phase 7, C4): évaluation unique sur le jeu de test, modèle en service | livraison_phase7 |
| 03/10 00:49 | `7f3b9c8` | feat(phase 7, C5): modèle de valeur vie client pour les comptes récents | livraison_phase7 |
| 03/10 00:56 | `15d9edb` | docs(phase 7): résultats, registre, suivi, soutenance ; test des modèles hors de models/ | livraison_phase7 |
| 03/10 02:36 | `409b97e` | resultats(phase 7): identité d'exécution rafraîchie, chiffres inchangés | livraison_phase7 |
| 03/10 03:20 | `94ddd74` | notebook(certification): § 9 réaligné, § 10 sans chemin relatif, exécuté en entier | livraison_phase7 |
| 03/10 03:22 | `680f57f` | docs(readme): reglage.py et valeur_vie.py dans l'arborescence | livraison_phase7 |
| 03/10 03:45 | `33f141b` | fix(outils): erreurs (stderr) en UTF-8 aussi, et avertissement pandas 3 dans MLflow | correctif_stderr_utf8, correctifs_stderr_threads |
| 03/10 04:08 | `f547d0c` | fix(pipeline_mlflow): « can't start new thread » — autolog borné, une couche parallèle | correctifs_stderr_threads |
| 03/10 04:47 | `16ef923` | fix(grilles): plus de processus de calcul — parallélisme dans le modèle, par fils | correctif_grilles_fils |
| 03/10 05:20 | `80d9a88` | perf(tests): suite 120 s -> 77 s (A1, A2, A3), sans rien retirer de ce qui est vérifié | livraison_optimisation_temps |
| 03/10 05:21 | `786789c` | perf(mlflow, B2): dépendances du modèle déclarées, plus d'export uv à chaque modèle | livraison_optimisation_temps |
| 03/10 05:48 | `0e4643c` | perf(notebook, B1): calculs de la phase 5 enregistrés — notebook 790 s -> 78 s | livraison_optimisation_temps |
| 03/10 06:26 | `dd3c1a5` | perf(mlflow, B2 complété): environnement du modèle entièrement déclaré | correctif_b2_pip |
| 03/10 07:30 | `4bdeaee` | feat(B6, option C): contributions linéaires exactes en production, SHAP pour comparer les modèles | livraison_option_C_explicabilite |
| 03/10 07:49 | `391692a` | notebook(certification): § 9.F exécuté ; lecture des calculs de la phase 5 rétablie | livraison_option_C_explicabilite |
| 03/10 09:13 | `75a512f` | fix: configuration Docker testée et corrigée ; exécution MLflow incomplète jamais réutilisée | livraison_docker_identite |
| 03/10 09:37 | `67a9f3e` | perf(identité): l'empreinte ne porte que sur le code qui produit les résultats | livraison_docker_identite |
| 03/10 10:14 | `918e84a` | **decision(phase 8): grille et règles S1 à S5, P1 à P4 validées avant tout calcul** | livraison_phase8_intermediaire |
| 03/10 10:25 | `8477693` | feat(phase 8): réglage de la régression, surapprentissage surveillé, ressources mesurées | livraison_phase8_intermediaire |
| 03/10 11:10 | `d45db4e` | **decision(phase 8): P4 option c et jeu de test option i, décidées par le porteur** | livraison_phase8, livraison_phase8_correctif_tests |
| 03/10 11:22 | `240743f` | feat(phase 8, décision c): modèle servi en une copie calibrée, paramètres documentés | livraison_phase8, livraison_phase8_correctif_tests |
| 03/10 11:52 | `0f18342` | resultats(phase 8): recalcul sous l'identité affinée, notebook exécuté | livraison_phase8, livraison_phase8_correctif_tests |
| 03/10 12:31 | `3ac60c5` | fix(tests): chaque session a son propre dossier temporaire — campagnes KO sous Windows | livraison_phase8_correctif_tests |
| 03/10 12:59 | `0570fe4` | fix(docker): serveur MLflow aligné sur le client (3.16.1), écart D-06 soldé pour la version | correctif_mlflow_aligne |
| 03/10 13:08 | `c860aeb` | fix(docker): délai de grâce au premier démarrage de PostgreSQL | correctif_docker_demarrage |
| 03/10 13:27 | `81283d4` | **decision(phase 9): règles R1 à R12 consignées avant tout calcul et toute lecture du test** | livraison_phase9 |
| 03/10 13:30 | `86d69f1` | feat(phase 9, étapes 1-2): règle de décision nette et stabilité de la liste, sans le test | livraison_phase9 |
| 03/10 13:32 | `ea25291` | **feat(phase 9, étape 3): outil de la lecture unique de restitution (R6), committé avant la lecture** | livraison_phase9 |
| 03/10 13:32 | `65ab765` | **resultats(phase 9, R6): lecture unique de restitution du jeu de test** | livraison_phase9 |
| 03/10 15:16 | `7081a67` | feat(phase 9, étapes 4-7): analyses des scores enregistrés — métriques, MRR, équité | livraison_phase9 |
| 03/10 15:34 | `2dbec4f` | feat: identité par graphe d'imports, descriptif lu sur le modèle ; notebook § 9.E et § 12 réécrits | livraison_phase9 |
| 03/10 15:58 | `4909d5f` | phase 9 : résultats sous l'identité par imports, carnets 07b/08/09, documentation | livraison_phase9 |
