# Audit du notebook de certification — chaque cellule, justifiable en 30 secondes ?

Notebook de 9367c8e : **130 cellules**, dont 54 de code (les deux cellules de captures du 04/10 portent le total de 128 à 130).
Aucune modification n'est faite : ce rapport attend l'arbitrage du porteur.

## Synthèse

| Verdict | Cellules | Sens |
|---|---|---|
| ✅ tient | 106 | Un seul propos, suivi de sa lecture |
| ✂️ à découper ou alléger | 10 | Trop long ou trop dense pour 30 secondes ; découpage sans réécriture |
| 🔁 redondance | 10 | Même information affichée deux fois (détail ci-dessous) |
| ↕️ ordre | 3 | La lecture est séparée de ce qu'elle commente |
| ⚠️ affichage | 1 | Affichage qu'un jury lira de travers |

## Redondances entre graphiques et tableaux

| # | Cellules | Ce qui est affiché deux fois | Proposition |
|---|---|---|---|
| R1 | 26 | Figure et tableau : churn des comptes sans utilisateur actif contre les autres | Garder la figure ; les deux taux dans la lecture |
| R2 | 28 | Figure et tableau : nombre de catégories avant/après normalisation | Garder la figure |
| R3 | 86 | Histogramme et tableau des quantiles des seuils par compte | Garder l'histogramme ; le facteur 356 est déjà dans la lecture. Garder le tableau des hypothèses (autre information) |
| R4 | 94 | Courbe de validation et grille de 14 lignes (mêmes PR-AUC) | Garder la courbe et les tableaux S1-S5 et P2 |
| R5 | 113 | Figure et tableau : exposé, couvert, préservé | Garder la figure (intervalles) ; l'extrapolation au portefeuille dans la lecture |
| R6 | 81 et 109 | Les métriques du test, deux fois, avec deux intervalles ([0,712 ; 0,806] puis [0,710 ; 0,807]) | **Recommandé** : le § 12.A renvoie au § 9.C et ne garde que l'écart validation/test et la calibration. Une seule évaluation, un seul intervalle dans tout le livrable (résumé, conclusion et tests alignés sur le § 9.C) |
| R7 | 41, 50, 67 | Les exclusions : le § 7 liste déjà les 20 exclusions finales, dont celles décidées aux § 7.7 et 8.C | Le § 7 ne liste que les exclusions de la phase 4 ; chaque décision ultérieure garde son propre tableau |

**Répétitions assumées, à garder** (même objet, étape différente, preuve différente) :
- calibration : avant (70), dans les plis (79), sur le test (109) ;
- explicabilité : SHAP comparé (89), permutation sur le test (117), contributions exactes (91, 119) ;
- comparaison appariée : variables construites (65), réglage (77), modèle servi (96) ;
- PSI : découpage (57), suivi mensuel (124).

## Effet des propositions

- **Texte seul** (✂️ découpages, ↕️ déplacement) : aucune réexécution, aucun recalcul.
- **Code** (R1 à R7, ⚠️ 91) : les cellules concernées affichent moins ; réexécution du notebook, **sans recalcul** (aucun outil de `tools/` ni module de `src/` ne change).
- Chaque correction reçoit son test de non-régression, comme les précédentes.

## Cellule par cellule

| # | § | Type | Rôle | Verdict | Action proposée |
|---|---|---|---|---|---|
| 0 | 0 | texte | Cas d'usage 01 — Résiliation client SaaS (churn) | ✅ |  |
| 1 | 0 | code | Environnement : versions et chemins, pour la reproductibilité | ✅ |  |
| 2 | 1 | texte | 1. Résumé exécutif | ✅ |  |
| 3 | 2 | texte | 2. Cadrage métier et cas d'usage — journal de bord [C1] | ✂️ | Découper : cadrage / hypothèses et critères / ordres de grandeur (déjà sous-titré) |
| 4 | 2 | code | Ordres de grandeur métier calculés (concentration de la valeur) | ✅ |  |
| 5 | 2 | texte | Conséquence de cadrage. La valeur est très concentrée : traiter les 10 % de churners les plus i | ✂️ | Découper en trois cellules : conséquence de cadrage et capacité / cycle de vie / boucles |
| 6 | 2 | code | Figure du cycle de vie (rendu du Mermaid) | ✅ |  |
| 7 | 3 | texte | 3. Données : disponibilité, gouvernance et alternatives — journal de bord [C1] [C3] | ✅ |  |
| 8 | 3 | code | Jointure au catalogue et intégrité des fichiers contre le manifeste | ✅ |  |
| 9 | 3 | texte | Solutions alternatives en cas d'indisponibilité des données. Ces scénarios sont anticipés car i | ✂️ | Découper : alternatives et stockage / empreinte et cycle de vie / journal |
| 10 | 4 | texte | 4. Enjeux éthiques, sociétaux et conformité — journal de bord [C2] | ✂️ | Découper : risques et RGPD / cadres et dilemmes / conséquence éthique de la priorisation |
| 11 | 4 | texte | Vérifications mesurées | ✅ |  |
| 12 | 4 | code | Classement des colonnes sensibles et recherche de données personnelles dans le texte libre | ✅ |  |
| 13 | 4 | texte | Décision. Aucun motif de donnée personnelle n'est détecté, mais le champ reste exclu : le motif | ✅ |  |
| 14 | 4 | code | Écart de churn entre segments sensibles (seuil de 15 points) | ✅ |  |
| 15 | 4 | texte | Lecture. Aucun segment n'écarte de plus de 15 points : aucune règle métier simple (« surveiller | ✅ |  |
| 16 | 5 | texte | 5. Chargement et compréhension des données [C3] | ✅ |  |
| 17 | 5 | code | Niveau bronze : schéma déclaré et défauts détectés | ✅ |  |
| 18 | 5 | texte | Ce que montre l'audit. | ✅ |  |
| 19 | 5 | code | Chaîne complète et contrat de données sur le jeu de référence | ✅ |  |
| 20 | 5 | texte | Lecture. Les neuf contrôles sont conformes sur le jeu de référence. Deux d'entre eux méritent d | ✅ |  |
| 21 | 6 | texte | 6. Analyse exploratoire (EDA) : visualisations et interprétation — journal de bord [C3] | ✅ |  |
| 22 | 6 | code | Doublons et manquants : l'absence d'une valeur est-elle un signal ? | ✅ |  |
| 23 | 6 | texte | Lecture. Les 35 doublons sont tous stricts : la clé client_id identifie bien un compte unique,  | ✅ |  |
| 24 | 6 | code | Distributions et valeurs extrêmes des variables clés | ✅ |  |
| 25 | 6 | texte | Lecture. Le revenu mensuel moyen vaut plus de cinq fois le revenu médian : une minorité de très | ✅ |  |
| 26 | 6 | code | Comptes sans utilisateur actif : écart de churn | 🔁 | R1 : le tableau redit la figure (deux taux de churn) |
| 27 | 6 | texte | Lecture. Ces valeurs manquantes ne sont pas des données manquantes. Elles décrivent un compte q | ✅ |  |
| 28 | 6 | code | Catégories fantômes avant et après normalisation | 🔁 | R2 : le tableau redit la figure (catégories avant/après) |
| 29 | 6 | texte | Lecture. Le jeu reçu compte 21 secteurs pour 7, 12 formules d'abonnement pour 4, 8 tailles | ✅ |  |
| 30 | 6 | code | Déséquilibre de la cible et des catégories ; churn par segment | ✅ |  |
| 31 | 6 | texte | Lecture. Le déséquilibre de la cible est modéré (28 %, 2,6 négatifs pour 1 positif), pas sévère | ✅ |  |
| 32 | 6 | code | Corrélations, redondances, formes de relation, contrôle de fuite | ✅ |  |
| 33 | 6 | texte | Lecture, en quatre constats. | ✅ |  |
| 34 | 7 | texte | 7. Préparation des données (nettoyage, manquants, transformations, features) — journal de bord  | ✅ |  |
| 35 | 7 | code | Affiche le code de la chaîne partagée (silver, gold) | ✅ |  |
| 36 | 7 | texte | 7.1 Deux défauts silencieux, trouvés en mesurant | ✅ |  |
| 37 | 7 | code | Premier défaut silencieux : conversion des délais (unité « h ») | ✅ |  |
| 38 | 7 | texte | Second défaut : 960 dates lues jour et mois inversés. Les dates arrivaient sous trois formats.  | ✅ |  |
| 39 | 7 | code | Second défaut silencieux : dates lues jour/mois inversés | ✅ |  |
| 40 | 7 | texte | Lecture. Avec l'ancienne lecture, moins de la moitié des dates internationales tombaient le jou | ✅ |  |
| 41 | 7 | code | Colonnes exclues des variables explicatives, avec motif | 🔁 | R7 : liste les 20 exclusions finales, y compris celles décidées plus tard (cellules 50, 67) |
| 42 | 7 | texte | Les motifs ne sont pas interchangeables : la grille sépare l'exclusion éthique (C2 — texte libr | ✅ |  |
| 43 | 7 | code | Zéros structurels et reconstruction ligne à ligne | ✅ |  |
| 44 | 7 | texte | Lecture. La reconstruction n'est pas affirmée, elle est vérifiée là où la vérité est connue : | ✅ |  |
| 45 | 7 | code | Manquants imputés dans chaque pli d'entraînement | ✅ |  |
| 46 | 7 | texte | 7.5 Variables construites | ✅ |  |
| 47 | 7 | code | Jeu gold figé, vérifié contre le manifeste | ✅ |  |
| 48 | 7 | texte | Le jeu d'apprentissage est figé : son empreinte est enregistrée au manifeste et un test vérifie | ✅ |  |
| 49 | 7 | texte | 7.7 Feature engineering (phase 5) — préalables | ✅ |  |
| 50 | 7 | code | Attributs du plan (une valeur par formule) ; exclusions de la phase 5 | 🔁 | R7 : le second tableau est un sous-ensemble de la cellule 41 |
| 51 | 7 | texte | Lecture. Chaque attribut ne prend qu'une valeur par formule : gardées, ces cinq colonnes répéta | ✅ |  |
| 52 | 7 | code | Diagnostic de la valeur vie client (expliquée sans puis avec l'issue) | ✅ |  |
| 53 | 7 | texte | Lecture. Sans l'issue, les variables connues avant la décision expliquent près de 90 % de la va | ✅ |  |
| 54 | 8 | texte | 8. Choix du modèle et démarche scientifique (baseline, modèles, comparaison) — journal de bord  | ✂️ | Découper (11 000 car.) : démarche et métriques / performance attendue / familles et sobriété / déséquilibre et règle de décision / boucle |
| 55 | 8 | texte | 8.A Avant tout modèle : découpage et validation du jeu (phase 5) | ✅ |  |
| 56 | 8 | code | Découpage entraînement/test, vérifié contre le manifeste | ✅ |  |
| 57 | 8 | code | Stabilité des variables (PSI) et validation adverse | ↕️ | Quatre figures (57-58) sans lecture avant la cellule 63, après la démonstration de la fuite |
| 58 | 8 | code | Test de permutation des étiquettes et courbes d'apprentissage | ↕️ | Voir 57 |
| 59 | 8 | code | Contrôles du découpage contre les règles fixées le 01/10 | ✅ |  |
| 60 | 8 | texte | La fuite, démontrée. L'itération 1 du projet (ci-dessus) raconte qu'un premier modèle « devinai | ✅ |  |
| 61 | 8 | code | Démonstration chiffrée de la fuite | ✅ |  |
| 62 | 8 | texte | Lecture. Avec la variable, les deux modèles atteignent une AUC de 0,996 à 0,999 : une performan | ✅ |  |
| 63 | 8 | texte | Lecture. La séparation est représentative : 28,0 % de churn dans chaque partie, aucune variable | ↕️ | Déplacer avant la cellule 60 : elle commente 56 à 59, pas la fuite |
| 64 | 8 | texte | 8.B Les variables construites apportent-elles quelque chose ? (phase 5) | ✅ |  |
| 65 | 8 | code | Apport des variables construites : comparaison appariée et ablation | ✅ |  |
| 66 | 8 | texte | Lecture. Les variables construites ne font rien gagner, à aucun des deux modèles : le gain moye | ✅ |  |
| 67 | 8 | code | Importance contre le plancher des leurres ; sélection finale | 🔁 | R7 : le tableau des retraits est un sous-ensemble de la cellule 41 ; cinq sorties, à alléger |
| 68 | 8 | texte | Lecture. Deux variables passent sous le plancher des leurres pour les deux modèles, usage_par_a | ✅ |  |
| 69 | 8 | texte | 8.D Les références : protocole d'évaluation et baselines (phase 6) | ✅ |  |
| 70 | 8 | code | Les trois baselines sous le protocole (25 plis) | ✅ |  |
| 71 | 8 | texte | Lecture. | ✅ |  |
| 72 | 8 | texte | 8.E Traçabilité des expériences : MLflow (phase 7, bloc 7.0) | ✅ |  |
| 73 | 8 | code | Chaîne MLflow : trois exécutions tracées, comparées hors pli | ✅ |  |
| 74 | 8 | texte | Lecture. La régression logistique reste en tête (0,793), les modèles d'arbres se groupent autou | ✅ |  |
| 75 | 9 | texte | 9. Entraînement, validation et ajustement (sélection du modèle final) — journal de bord [C5] | ✅ |  |
| 76 | 9 | texte | 9.A Réglage et comparaison à la référence figée (B1, B3) | ✅ |  |
| 77 | 9 | code | Réglage des modèles d'arbres et comparaison appariée (B1, B3) | ✅ |  |
| 78 | 9 | texte | Lecture. Même réglés, la forêt (0,774) et XGBoost (0,780) font moins bien que la régression log | ✅ |  |
| 79 | 9 | code | Calibration choisie dans les plis (B2) | ✅ |  |
| 80 | 9 | texte | Lecture. Après calibration sigmoïde, les points rejoignent la diagonale : l'erreur passe de 0,1 | ✅ |  |
| 81 | 9 | code | Évaluation unique sur le test, lue et non recalculée (B4) | 🔁 | R6 : mêmes métriques du test que la cellule 109, avec un autre intervalle |
| 82 | 9 | texte | Lecture. Sur 1 000 comptes jamais vus, la PR-AUC est de 0,761 [0,712 ; 0,806] : la valeur de va | ✅ |  |
| 83 | 9 | code | Modèle de valeur vie client pour les comptes trop récents (B5) | ✅ |  |
| 84 | 9 | texte | Lecture. La forêt de régression explique 89 % de la variance du logarithme de la valeur, contre | ✅ |  |
| 85 | 9 | texte | 9.E Règle de décision économique (phase 9 — règles R1 à R5) | ✅ |  |
| 86 | 9 | code | Règle de décision : seuils par compte et sensibilité aux hypothèses | 🔁 | R3 : le tableau des seuils redit l'histogramme |
| 87 | 9 | texte | Lecture. Les seuils varient d'un facteur 356 entre les comptes (quantiles 5 % et 95 %) : un seu | ✅ |  |
| 88 | 9 | texte | 9.F Explicabilité du modèle retenu (B6, option C) | ✅ |  |
| 89 | 9 | code | Les trois modèles s'appuient-ils sur les mêmes facteurs ? (SHAP) | ✅ |  |
| 90 | 9 | texte | Lecture. Les intégrations, l'ancienneté et les tickets de support figurent parmi les cinq premi | ✅ |  |
| 91 | 9 | code | Explication pour le conseiller par contributions exactes | ⚠️ | Affiche « risque 100 % » (arrondi de 0,99…) : un jury lira une certitude |
| 92 | 9 | texte | Journal de bord [C4] [C8] — explicabilité : | ✅ |  |
| 93 | 9 | texte | 9.G Réglage, surapprentissage et ressources (phase 8) | ✅ |  |
| 94 | 9 | code | Grille de la régression et contrôles de surapprentissage (S1 à S5) | 🔁 | R4 : la grille de 14 lignes redit la courbe de validation |
| 95 | 9 | texte | Lecture. La grille est plate : moins de 0,002 entre toutes les combinaisons, pour un écart-type | ✅ |  |
| 96 | 9 | code | Ressources (P4) et équivalence du modèle servi | ✂️ | Quatre tableaux denses : les paramètres du modèle servi sont dans la model card |
| 97 | 9 | texte | Lecture. Appliquée à la lettre, P4 désignait XGBoost : sa moyenne (0,780) tombe dans l'écart-ty | ✅ |  |
| 98 | 10 | texte | 10. Implémentation et mise en exploitation (déploiement, exemple d'usage) — journal de bord [C6 | ✂️ | Découper : API et exemple / chaîne CI / versioning et intégration / mise en œuvre outillée |
| 99 | 10 | texte | La chaîne en fonctionnement (04/10/2026). | ✅ |  |
| 100 | 10 | code | Bout en bout sur l'échantillon : fichier brut → chaîne → modèle en service | ✅ |  |
| 101 | 10 | texte | 10.A Mise en exploitation réalisée (phase 10) | ✅ |  |
| 102 | 10 | code | Liste opérationnelle sur l'échantillon, avec groupe témoin | ✅ |  |
| 103 | 10 | texte | Journal de bord [C6] — phase 10 : carence de 2 mois et groupe témoin de 10 % (valeurs par défau | ✅ |  |
| 104 | 11 | texte | 11. Architecture cible et contraintes [C7] | ✂️ | Découper : architecture cible et contraintes / chiffrage et acteurs / mise en œuvre / schéma |
| 105 | 11 | code | Figure du schéma d'architecture | ✅ |  |
| 106 | 11 | texte | Plateforme vérifiée en fonctionnement (04/10/2026) | ✅ |  |
| 107 | 12 | texte | 12. Mesure de performance et impacts (métriques techniques + métier) — journal de bord [C8] | ✅ |  |
| 108 | 12 | texte | 12.A Métriques globales, écart validation croisée / test, calibration (R7) | ✅ |  |
| 109 | 12 | code | Métriques du test avec intervalles, écart validation/test, calibration (R7) | 🔁 | R6 : redit le tableau du § 9.C ; garder l'écart validation/test et la calibration |
| 110 | 12 | texte | Lecture. PR-AUC 0,761 [0,710 ; 0,807] sur le test (le § 9.C donne [0,712 ; 0,806] : mêmes score | ✅ |  |
| 111 | 12 | code | Matrices de confusion aux points métier et protocole (R5) | ✅ |  |
| 112 | 12 | texte | Lecture. Au point métier, l'équipe contacte 28 comptes (la capacité mensuelle ramenée au test)  | ✅ |  |
| 113 | 12 | code | Revenu exposé, couvert, préservé (R8) | 🔁 | R5 : la figure redit les trois montants du tableau |
| 114 | 12 | texte | Lecture. Sur le jeu de test, 814 k€ de revenu mensuel partent avec les clients perdus (exposé). | ✅ |  |
| 115 | 12 | code | Rappel par segment, critère d'équité (R9) | ✅ |  |
| 116 | 12 | texte | Lecture. Sur 18 segments concluants, un seul sort du critère : la Suisse — rappel 0,15 [0,03 ;  | ✅ |  |
| 117 | 12 | code | Importance par permutation sur le test (R10) | ✅ |  |
| 118 | 12 | texte | Lecture. La dernière connexion, l'ancienneté, les intégrations et les tickets de support porten | ✅ |  |
| 119 | 12 | code | Contributions exactes de trois comptes types (R11) | ✅ |  |
| 120 | 12 | texte | Lecture. Pour chaque compte, la base (le score moyen, en cotes logarithmiques) plus la somme de | ✅ |  |
| 121 | 13 | texte | 13. Amélioration continue (ré-entraînement, suivi, versioning) [C9] | ✂️ | Découper : plan théorique (dérive, réentraînement, versioning) / CI et métriques / boucle monitoring → données |
| 122 | 13 | code | Règles d'alerte M1 à M10, lues dans le code | ✅ |  |
| 123 | 13 | texte | Suivi mensuel sur lots simulés. Mois 1 sans dérive (témoin), mois 2 avec un désengagement modes | ✅ |  |
| 124 | 13 | code | Suivi mensuel simulé : verdicts et évolution du PSI | ✅ |  |
| 125 | 13 | texte | Revue trimestrielle et réentraînement. Trois mois après chaque liste, l'issue de chaque compte  | ✅ |  |
| 126 | 13 | code | Revue trimestrielle simulée et décision de réentraînement | ✅ |  |
| 127 | 14 | texte | 14. Conclusion (synthèse et recommandations) | ✅ |  |
| 128 | 15 | texte | 15. Annexes (versions, paramètres, dépendances, fonctions utilitaires) | ✂️ | Une cellule par annexe (A à E) : navigation et lecture en 30 secondes |
| 129 | 15 | code | Annexe A : versions des dépendances | ✅ |  |
