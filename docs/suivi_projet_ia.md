# Suivi de projet IA — Prédiction de résiliation client (churn) SaaS

> Document de suivi calé sur le cycle de vie d'un projet d'intelligence artificielle.
> **Rédigé pour être compris sans connaissance préalable du sujet** : chaque phase explique d'abord *de quoi
> il s'agit*, avant de dire *ce qui a été fait*.

---

## En deux minutes : de quoi parle ce projet ?

Une entreprise vend un logiciel par abonnement à d'autres entreprises. Chaque mois, ses clients paient pour
continuer à l'utiliser. Le problème : certains arrêtent leur abonnement à l'échéance du contrat. C'est ce
qu'on appelle la **résiliation**, ou *churn*. Chaque départ fait perdre un revenu régulier, et en retrouver
un nouveau coûte plus cher que de conserver l'existant.

L'objectif du projet est de **repérer à l'avance les clients susceptibles de partir**, pour que les équipes
chargées de la relation client puissent les contacter avant qu'il ne soit trop tard.

Le principe est le suivant : on dispose de l'historique de 5 000 comptes clients, dont on sait lesquels sont
partis et lesquels sont restés. On y ajoute ce qu'on sait de chacun — depuis combien de temps il est client,
à quel point il utilise le logiciel, combien il paie, combien de fois il a contacté le support. Un programme
apprend alors à reconnaître les signaux qui précèdent un départ, puis applique ce qu'il a appris aux clients
actuels pour estimer, pour chacun, un **risque de départ**.

**Ce que le projet n'est pas.** Le programme ne décide rien. Il produit une liste de comptes classés par
priorité ; ce sont des humains qui décident quoi faire. C'est un outil d'aide à la décision, et cette limite
est volontaire.

### Le cadre : une certification professionnelle

Ce travail est réalisé dans le cadre d'une **certification** attestant la capacité à concevoir et implémenter
une solution d'intelligence artificielle. Le candidat doit démontrer **neuf compétences** (notées C1 à C9),
depuis la compréhension du besoin métier jusqu'au suivi de la solution une fois en service.

L'évaluation repose sur deux documents remis à un jury, puis sur un oral d'une heure. Le premier document est
un **notebook** — un fichier qui mélange du texte explicatif, du code informatique et les résultats obtenus,
de sorte qu'un lecteur puisse suivre le raisonnement de bout en bout. Le second est un support de
présentation.

**Une particularité à connaître :** le jury attend autant le *raisonnement* que le *résultat*. Un modèle
performant mais dont les choix ne sont pas justifiés vaut moins qu'un modèle modeste dont chaque décision est
argumentée. C'est pourquoi ce document insiste autant sur les *pourquoi*.

---

## Fiche projet

| Champ | Valeur |
|---|---|
| **Nom du projet** | Prédiction de résiliation client (churn) — éditeur de logiciel SaaS B2B |
| **Responsable** | Candidat à la certification |
| **Client / commanditaire** | Direction Customer Success de l'éditeur *(cas d'usage pédagogique)* |
| **Date de début** | 08/08/2026 |
| **Échéance cible** | **30/09/2026** (gel des livrables) — remise 01/10/2026 |
| **Statut global** | 🟡 En cours — phases 1 à 6 engagées, 7 à 9 à exécuter |
| **Nature** | Exercice de certification. **Aucun déploiement réel** : les phases 10 et 11 sont conçues et documentées, pas mises en service. |

**Légende statut** : `[ ]` à faire · `[~]` en cours · `[x]` terminé · `[—]` sans objet ici

---

## Comment lire ce document

Trois découpages coexistent. Ils décrivent la même chose sous trois angles.

| Découpage | À quoi il sert |
|---|---|
| **Les 11 phases** de ce suivi | L'ordre réel du travail — c'est le cycle de vie d'un projet IA |
| **Les 16 sections** du notebook | L'ordre imposé par le règlement de la certification pour le document remis |
| **Les 9 compétences** C1 à C9 | Ce que le jury évalue |

| Phase de suivi | Sections du notebook | Compétences |
|---|---|---|
| 1 · Cadrage | 2, 4 | C1, C2 |
| 2 · Données — ingestion & gouvernance | 3, 5 | C1, C3 |
| 3 · Exploration & profiling | 5, 6 | C3 |
| 4 · Préparation & nettoyage | 7 | C3 |
| 5 · Feature engineering | 7 | C3, C5 |
| 6 · Baseline & protocole d'évaluation | 8 | C4 |
| 7 · Choix & entraînement du modèle | 8, 9 | C4, C5 |
| 8 · Optimisation & fine-tuning | 9 | C4, C5 |
| 9 · Validation & explicabilité | 9, 12 | C5, C8 |
| 10 · Déploiement | 10, 11 | C6, C7 |
| 11 · Suivi & ré-entraînement | 13 | C9 |

---

## 1 · Cadrage *(🔵 terminé)*

> **De quoi s'agit-il ?** Avant d'écrire la moindre ligne de code, on définit le problème : que cherche-t-on
> à résoudre, pour qui, et comment saura-t-on qu'on a réussi ? C'est la phase la plus souvent bâclée et
> celle qui coûte le plus cher quand elle est ratée — un modèle qui répond parfaitement à la mauvaise
> question ne sert à rien.

- [x] Cadrer le besoin métier et les critères de succès
- [x] Cartographier les parties prenantes et les impacts
- [x] Identifier les risques éthiques et le cadre réglementaire
- [x] Définir les critères d'acceptation
- [x] Fixer la périodicité de révision des indicateurs *(exigence de la compétence C9, à poser dès le cadrage)*

**Décisions structurantes prises**

| Décision | Explication accessible |
|---|---|
| Cibler la résiliation **à l'échéance du contrat** | On ne cherche pas à prédire un départ « à n'importe quel moment », mais au moment précis où le client peut ne pas renouveler. C'est la seule fenêtre où une action est possible. |
| Objectif de **priorisation**, pas de détection exhaustive | Les données montrent que 10 % des clients qui partent représentent 72 % du revenu perdu. Mieux vaut bien traiter ceux-là que d'en signaler beaucoup sans pouvoir tous les traiter. |
| La **capacité de l'équipe** est une contrainte, pas un réglage | Si l'équipe peut contacter 140 clients par mois, signaler 800 comptes ne sert à rien. Le modèle doit produire une liste actionnable. |
| **Décision humaine obligatoire** | Le programme classe, il ne décide pas. Choix éthique assumé, pas une limite technique. |

**Parties prenantes identifiées**

| Acteur | Rôle |
|---|---|
| Direction Customer Success | Commanditaire — arbitre la politique de priorisation |
| Équipes CSM *(Customer Success Manager)* | Utilisateurs finaux — reçoivent la liste de comptes |
| DPO / juriste | Valide la conformité à la réglementation sur les données personnelles |
| Équipe technique | Met en œuvre et exploite la solution |

**Cadre réglementaire retenu :** RGPD (protection des données personnelles), AI Act (règlement européen sur
l'intelligence artificielle — le système relève de la catégorie « risque minimal »), lignes directrices
européennes pour une IA digne de confiance, recommandations de la CNIL.

**Deux dilemmes éthiques documentés**, avec la position retenue : contacter un client identifié à risque peut
paradoxalement précipiter son départ ; et prioriser les clients à forte valeur revient à délaisser les
petits.

🔧 **Outils** : cadre RGPD · AI Act · dictionnaire de données documenté *(équivalent d'une « datasheet »,
c'est-à-dire une fiche décrivant l'origine, le contenu et les limites d'un jeu de données)*
📦 **Artefacts** : sections 2 et 4 du notebook · tableau des parties prenantes · liste des critères de succès
**Statut** : **terminé** — décisions arrêtées, à ne rouvrir que si l'exécution les invalide

---

## 2 · Données — ingestion & gouvernance *(🟡 en cours)*

> **De quoi s'agit-il ?** Rassembler les données, comprendre d'où elles viennent, qui en est propriétaire,
> combien de temps on a le droit de les garder. « Gouvernance » désigne l'ensemble de ces règles.
> « Versionner » signifie conserver une trace datée de chaque version, afin de pouvoir revenir en arrière
> et de reproduire à l'identique un résultat obtenu plusieurs mois plus tôt.

- [x] Lire et ingérer les sources, décrire le schéma des données
- [x] Documenter le cycle de vie des données (collecte → conservation → suppression)
- [x] Justifier le choix du mode de stockage
- [~] Mettre en place le versioning du code et des données
- [x] Identifier les données sensibles et le traitement associé

**Les trois fichiers sources**

| Fichier | Contenu | Usage |
|---|---|---|
| `churn_saas_complet.csv` | 5 035 lignes, 29 colonnes | Apprentissage et évaluation |
| `churn_saas_echantillon.csv` | 50 lignes | Test du programme de bout en bout |
| `catalogue_plans.csv` | Caractéristiques des formules d'abonnement | Enrichissement par rapprochement |

**Un piège identifié.** Le rapprochement entre les deux premiers fichiers se fait sur le nom de la formule
d'abonnement. Or celle-ci est écrite tantôt `STARTER`, tantôt `Starter`. Un rapprochement sans
uniformisation préalable échouerait **sans produire d'erreur visible** : les lignes non appariées
disparaîtraient silencieusement. C'est un défaut classique et redoutable, car rien ne signale le problème.

**Données sensibles.** La colonne `commentaire_csm` contient des notes rédigées librement par les
conseillers, pouvant mentionner des personnes ou porter des jugements. Elle est exclue du modèle pour des
motifs de protection des données, et non parce qu'elle serait inutile.

🔧 **Outils** : Git *(historique du code)* · pandas *(manipulation de tableaux de données en Python)* ·
fichiers CSV · DVC *(versioning de données — documenté comme cible, non installé)*
📦 **Artefacts** : sections 3 et 5 du notebook · dictionnaire de données · tableau du cycle de vie
**Statut** : **en cours** — documentation faite, mise en œuvre du versioning à confirmer

---

## 3 · Exploration & profiling *(🟡 en cours)*

> **De quoi s'agit-il ?** Regarder les données avant de les utiliser : combien de valeurs manquent, y a-t-il
> des doublons, comment les chiffres se répartissent, quelles colonnes semblent liées au départ des clients.
> On y détecte aussi les **biais** — par exemple si un secteur d'activité est surreprésenté, le modèle
> risque d'être plus juste pour lui que pour les autres.

- [x] Profiling : valeurs manquantes, doublons, distributions
- [x] Détecter le déséquilibre entre les catégories
- [~] Analyser les corrélations et les tendances
- [ ] Rédiger l'interprétation des observations
- [ ] Vérifier si l'absence d'une donnée est elle-même un signal

**Constats établis**

| Observation | Valeur | Ce que cela implique |
|---|---|---|
| Doublons exacts | 35 sur 5 035 lignes | À supprimer — 5 000 comptes uniques restent |
| Taux de résiliation | **28 %** | Déséquilibre modéré : environ un client sur quatre part |
| Données manquantes | 3 à 10 % selon les colonnes | Gérable ; une colonne à 55 % est écartée |
| Concentration du chiffre d'affaires | 10 % des comptes = 68 % du revenu | Tous les clients ne se valent pas, loin de là |
| Défauts de format | Nombres écrits en texte, dates en formats mélangés, majuscules incohérentes | Introduits volontairement dans l'exercice — à corriger et à documenter |

**Une question ouverte importante.** Les taux de données manquantes sont étonnamment réguliers, ce qui
suggère une absence purement aléatoire. Mais si l'absence d'une donnée était liée au départ du client — par
exemple parce qu'un client désengagé cesse d'être suivi — alors **le manque serait lui-même un signal**, à
conserver plutôt qu'à combler. À vérifier avant de décider comment traiter ces trous.

🔧 **Outils** : pandas · matplotlib *(production de graphiques)*
📦 **Artefacts** : section 6 du notebook · graphiques de distribution
**Statut** : **en cours** — graphiques préparés, interprétation écrite à produire

---

## 4 · Préparation & nettoyage *(🟡 en cours)*

> **De quoi s'agit-il ?** Corriger les défauts repérés à l'étape précédente. Convertir les nombres stockés
> comme du texte, unifier les dates, supprimer les doublons, décider quoi faire des valeurs manquantes.
> **Imputer** signifie remplacer une valeur absente par une estimation — par exemple la valeur moyenne des
> autres clients.

- [x] Fonctions de nettoyage réutilisables (nombres en texte, dates multi-formats, uniformisation de la casse)
- [x] Suppression des doublons
- [~] Traitement des valeurs manquantes, colonne par colonne
- [ ] Tests de qualité automatisés sur les données d'entrée

**Un choix technique important.** Les fonctions de nettoyage sont écrites une fois et **réutilisées à
l'identique** au moment d'appliquer le modèle à de nouveaux clients. Si l'on nettoyait différemment les
données d'apprentissage et les données réelles, le modèle recevrait des informations dans un format qu'il ne
reconnaît pas et se tromperait sans que rien ne l'indique. Ce défaut classique porte un nom en anglais :
*training-serving skew*, littéralement « décalage entre l'entraînement et le service ».

🔧 **Outils** : pandas · imputation par la médiane ou par la dernière valeur connue
*(Outils du modèle générique non retenus ici : détection d'outliers par Z-score ou IQR — les valeurs extrêmes
observées, comme un chiffre d'affaires très élevé, sont réelles et non des erreurs ; les supprimer
retirerait précisément les clients les plus importants.)*
📦 **Artefacts** : section 7 du notebook · fonctions de nettoyage
**Statut** : **en cours** — stratégie d'imputation à finaliser colonne par colonne

---

## 5 · Feature engineering *(🟡 en cours)*

> **De quoi s'agit-il ?** Une *feature*, ou **variable explicative**, est une information fournie au modèle
> pour l'aider à prédire. Le *feature engineering* consiste à en construire de nouvelles à partir des
> existantes, parce qu'elles sont plus parlantes. Exemple : plutôt que de donner séparément « 10
> fonctionnalités disponibles » et « 2 fonctionnalités utilisées », on fournit le rapport — 20 % — qui dit
> directement si le client exploite ce qu'il paie.

- [x] Construire des ratios d'usage
- [x] Vérifier l'absence de **fuite de données**
- [~] Sélectionner les variables à conserver
- [ ] Mesurer l'apport réel des variables construites

**La fuite de données, point central de cet exercice.** Une *fuite* survient lorsqu'une information donnée
au modèle n'était en réalité pas disponible au moment où la prédiction aurait dû être faite. Le modèle
obtient alors d'excellents résultats en apprentissage, puis s'effondre en situation réelle — il avait
littéralement la réponse sous les yeux.

Ici, la colonne `sante_compte_fin_periode` est un score de santé du compte calculé **en fin de période**,
donc après la décision du client. Elle est écartée. **Une performance anormalement élevée est traitée comme
une alerte, pas comme un succès.**

**Variables « leurres ».** Certaines colonnes, comme la couleur du thème d'interface choisi par le client,
n'ont aucune raison d'influencer un départ. Elles sont **conservées volontairement** afin de démontrer,
chiffres à l'appui, qu'elles n'apportent rien — plutôt que de les écarter par intuition.

🔧 **Outils** : pandas · `train_test_split` *(séparation entre données d'apprentissage et données de test)* ·
mise à l'échelle des variables numériques
*(Outils du modèle générique non retenus : **SMOTE / ADASYN**, techniques qui fabriquent des exemples
artificiels pour rééquilibrer les catégories — écartées car elles inventent des clients qui n'existent pas,
sur des données comportant beaucoup de catégories ; **PCA**, technique de compression des variables — écartée
car elle rend le modèle inexplicable, alors que les conseillers doivent comprendre pourquoi un compte est
signalé ; **TimeSeriesSplit** — sans objet, les données ne forment pas une série chronologique.)*
📦 **Artefacts** : section 7 du notebook · jeu de données préparé
**Statut** : **en cours**

---

## 6 · Baseline & protocole d'évaluation *(🟡 en cours)*

> **De quoi s'agit-il ?** Une **baseline** est un modèle simple servant de point de comparaison. Sans elle,
> impossible de dire si un modèle sophistiqué apporte quoi que ce soit. Le **protocole d'évaluation** fixe à
> l'avance comment on mesurera la réussite — décider après coup reviendrait à choisir la règle du jeu une
> fois la partie jouée.

- [x] Définir une séparation reproductible entre données d'apprentissage et de test
- [x] Choisir la baseline : régression logistique
- [x] Fixer les critères de performance **avant** l'entraînement
- [ ] Exécuter la baseline et relever les résultats de référence

**Comment on mesure.** Plusieurs indicateurs coexistent, chacun répondant à une question différente.

| Indicateur | Ce qu'il mesure, en clair |
|---|---|
| **Rappel** | Parmi les clients qui sont réellement partis, quelle proportion avait été repérée ? |
| **Précision** | Parmi les clients signalés comme à risque, quelle proportion est réellement partie ? |
| **PR-AUC** | Résume l'équilibre entre les deux précédents, en un seul chiffre |
| **ROC-AUC** | Capacité générale à distinguer un partant d'un restant |

**Pourquoi pas le simple « taux de bonnes réponses » ?** Parce que 72 % des clients restent. Un programme
répondant systématiquement « ce client va rester » aurait 72 % de bonnes réponses tout en étant parfaitement
inutile.

🔧 **Outils** : scikit-learn *(bibliothèque Python de référence pour l'apprentissage automatique)* ·
séparation stratifiée · graine aléatoire fixée *(pour que les résultats soient reproductibles à l'identique)*
📦 **Artefacts** : section 8 du notebook · protocole d'évaluation
**Statut** : **en cours** — protocole défini, exécution à faire

---

## 7 · Choix & entraînement du modèle *(à faire)*

> **De quoi s'agit-il ?** « Entraîner » un modèle, c'est lui présenter des milliers d'exemples passés dont
> on connaît l'issue, afin qu'il repère les régularités. La **validation croisée** consiste à répéter
> l'opération plusieurs fois sur des découpages différents des données, pour vérifier que le résultat ne
> tient pas au hasard d'un découpage favorable.

- [ ] Entraîner la baseline (régression logistique)
- [ ] Entraîner le modèle candidat (forêt aléatoire)
- [ ] Comparer par validation croisée en 5 découpages
- [ ] Sélectionner le modèle final et justifier le choix
- [ ] Entraîner le modèle secondaire d'estimation de la valeur client

**Les deux modèles comparés**

| Modèle | Principe | Avantage | Inconvénient |
|---|---|---|---|
| **Régression logistique** | Combine les variables de façon linéaire pour produire une probabilité | Très explicable, rapide | Ne capte pas les effets combinés complexes |
| **Forêt aléatoire** | Combine des centaines d'arbres de décision | Capte les interactions entre variables | Moins directement lisible |

**Modèles écartés d'emblée, et pourquoi.** Les réseaux de neurones profonds nécessitent des volumes de
données bien supérieurs ; sur 5 000 lignes, leur coût de calcul serait engagé sans bénéfice attendu. Les
outils de vision par ordinateur (CNN, YOLO) sont sans objet : il n'y a pas d'images ici.

🔧 **Outils** : scikit-learn · validation croisée stratifiée
*(MLflow, outil de traçabilité des expérimentations, n'est pas utilisé : le projet tient dans un notebook
unique, et les paramètres sont consignés directement dans le document.)*
📦 **Artefacts** : sections 8 et 9 du notebook · modèle entraîné
**Statut** : **à faire** — prévu les 24 et 25 septembre

---

## 8 · Optimisation & fine-tuning *(à faire)*

> **De quoi s'agit-il ?** Un modèle comporte des **hyperparamètres** : des réglages fixés avant
> l'entraînement, comme le nombre d'arbres d'une forêt. Les optimiser consiste à essayer plusieurs
> combinaisons pour retenir la meilleure. Le **surapprentissage** est le risque associé : à force d'ajuster,
> le modèle finit par mémoriser les exemples d'apprentissage au lieu d'en tirer des règles générales.

- [ ] Explorer la grille d'hyperparamètres définie
- [ ] Surveiller le surapprentissage
- [ ] Documenter les paramètres retenus
- [~] Arbitrer entre performance et consommation de ressources

**Un choix volontairement sobre.** La grille de recherche est **restreinte** plutôt qu'exhaustive. Explorer
des milliers de combinaisons consommerait beaucoup de calcul — donc d'énergie — pour un gain marginal. Cette
démarche d'**éco-conception** est une exigence explicite de la certification, et elle est ici assumée comme
un arbitrage documenté plutôt que subie.

Dans le même esprit : à performance équivalente, le modèle le plus léger est retenu ; et le
ré-entraînement est prévu tous les trois mois plutôt que tous les mois, ce qui divise par quatre la
consommation associée.

🔧 **Outils** : `GridSearchCV` *(exploration systématique d'une grille de réglages)*
*(Optuna, outil d'optimisation plus avancé, n'est pas retenu : son intérêt apparaît sur de grands espaces de
recherche, ce qui contredirait la démarche de sobriété adoptée. CodeCarbon, qui mesure l'empreinte carbone
d'un calcul, serait un ajout pertinent et peu coûteux — **option ouverte**, non tranchée.)*
📦 **Artefacts** : section 9 du notebook · tableau des hyperparamètres
**Statut** : **à faire**

---

## 9 · Validation & explicabilité *(à faire — phase la plus différenciante)*

> **De quoi s'agit-il ?** Vérifier ce que vaut le modèle sur des données qu'il n'a jamais vues, traduire sa
> performance en termes financiers, et rendre ses décisions compréhensibles. **L'explicabilité** est la
> capacité à dire *pourquoi* un client précis a été signalé — sans elle, un conseiller ne peut pas agir de
> façon pertinente.

- [ ] Évaluer sur le jeu de test
- [ ] Appliquer la règle de décision économique
- [ ] Produire l'analyse d'importance des variables
- [ ] Vérifier l'absence de traitement défavorable par secteur, pays et taille d'entreprise
- [ ] Traduire la performance en euros

### Le raisonnement central du projet

**Deux types d'erreurs sont possibles**, et elles ne coûtent pas la même chose.

| Erreur | Ce qui se passe | Coût |
|---|---|---|
| **Faux négatif** | Un client allait partir, on ne l'a pas repéré | On perd le client et son revenu futur |
| **Faux positif** | On contacte un client qui n'allait pas partir | Du temps d'équipe, environ 135 € |

Intuitivement, on en conclut qu'il vaut mieux trop signaler que pas assez. **Les données montrent que c'est
plus subtil.**

Le coût d'un client perdu dépend de sa valeur. Pour un petit compte, perdre le client coûte environ 200 € —
à peine plus qu'un contact inutile. Pour un gros compte, plus de 44 000 €. Le rapport entre les deux coûts
varie donc **d'un facteur supérieur à 200 selon le client**.

**Conséquence :** il n'existe pas de seuil unique. Le niveau de risque à partir duquel il devient rentable
d'agir vaut 40 % pour un petit compte et 0,3 % pour un gros. Les comptes sont donc classés par **valeur
espérée** — le risque de départ multiplié par ce que représente le client — et l'équipe traite les premiers
de la liste, dans la limite de sa capacité.

**Une conséquence à assumer.** Cette règle rend les petits comptes structurellement moins prioritaires. Ce
n'est pas illégal — la valeur d'un client est un critère commercial légitime — mais c'est un arbitrage qui
doit être exposé plutôt que dissimulé. Des mesures de compensation sont prévues : un quota d'actions réservé
aux petits comptes, et un suivi du taux de départ **par segment** et non seulement en moyenne globale.

🔧 **Outils** : matrice de confusion *(tableau croisant prédictions et réalité)* · courbe ROC ·
courbe précision-rappel · importance par permutation · SHAP *(méthode expliquant la contribution de chaque
variable à une prédiction individuelle — **option ouverte**)*
📦 **Artefacts** : sections 9 et 12 du notebook · analyse d'équité · liste de comptes priorisée
**Statut** : **à faire** — prévu le 26 septembre

---

## 10 · Déploiement *(conçu, non mis en service)*

> **De quoi s'agit-il ?** Faire passer le modèle du fichier d'expérimentation à un usage réel et régulier.
> Cela suppose de l'**empaqueter** (l'enregistrer dans un format rechargeable), de définir comment il sera
> appelé, et de garder trace de la version utilisée à chaque instant.

- [~] Enregistrer le modèle dans un fichier rechargeable
- [ ] Recharger le modèle et l'appliquer à l'échantillon de test
- [ ] Produire la liste opérationnelle destinée aux conseillers
- [x] Décrire la chaîne de livraison automatisée
- [x] Définir les règles de versioning
- [x] Documenter les besoins d'intégration

**Une décision d'architecture qui mérite explication.** Le service de calcul ne renvoie **pas** de décision
binaire du type « à contacter / à ne pas contacter ». Il renvoie une probabilité et une valeur espérée. La
raison est directe : puisque la décision dépend du classement de l'ensemble du portefeuille et de la
capacité disponible, elle **ne peut pas** être calculée pour un client isolé. La coupure est appliquée
mensuellement, quand on dispose de la vue d'ensemble.

**Versioning : trois éléments, pas un seul.** On conserve la version du code, celle des données
d'apprentissage et celle du modèle. Conserver le seul code ne suffit pas : si les données ont changé
entre-temps, le résultat n'est pas reproductible.

**Le flux le plus souvent oublié** est le retour d'information : ce que le conseiller a fait, et si le
client est finalement parti. Sans lui, on ne peut jamais mesurer si le dispositif fonctionne réellement.

🔧 **Outils** : joblib *(enregistrement d'un modèle Python dans un fichier)* · esquisse d'interface de
service · chaîne d'intégration continue décrite
*(MLflow Model Registry, qui gère le passage d'un modèle du test à la production, est décrit comme cible mais
non installé — le cas d'usage ne comporte pas d'environnement réel.)*
📦 **Artefacts** : sections 10 et 11 du notebook · modèle enregistré · schéma d'architecture *(à produire)*
**Statut** : **partiel** — conception faite, trois éléments techniques à produire

---

## 11 · Suivi & ré-entraînement *(conçu, non mis en service)*

> **De quoi s'agit-il ?** Un modèle se dégrade avec le temps, parce que la réalité évolue. La **dérive**
> désigne ce décalage progressif entre les données d'aujourd'hui et celles sur lesquelles le modèle a
> appris. Le suivi consiste à la détecter avant qu'elle ne produise des erreurs coûteuses.

- [x] Définir les indicateurs, leurs seuils d'alerte et l'action associée
- [x] Définir la fréquence de ré-entraînement
- [x] Formaliser le retour vers la phase Données en cas d'alerte
- [ ] Implémenter le calcul de dérive

**Chaque indicateur est associé à un seuil, une action et un responsable nommé.** Un indicateur sans seuil
ne se surveille pas ; un seuil sans action associée ne sert à rien.

**Une étape que l'on oublie souvent.** Lorsqu'une alerte se déclenche, on ne ré-entraîne pas immédiatement.
On qualifie d'abord l'alerte : s'agit-il d'une vraie évolution du comportement des clients, ou d'un simple
incident technique de collecte ? Les deux produisent la même alerte mais appellent des réponses opposées.

**Le piège technique du dispositif.** L'indicateur de dérive compare les données actuelles à une
distribution de référence. Si cette référence n'est pas mise à jour lors d'un ré-entraînement, le système
compare indéfiniment le présent à un état ancien : il signale une dérive déjà corrigée, ou cesse d'en
détecter de nouvelles. Cette référence doit donc être versionnée au même titre que le modèle.

🔧 **Outils** : PSI *(Population Stability Index — indicateur mesurant l'écart entre deux distributions)* ·
test de Kolmogorov-Smirnov · tableau de bord de suivi
📦 **Artefacts** : section 13 du notebook · tableau indicateur / seuil / action / responsable
**Statut** : **partiel** — dispositif conçu, calcul à implémenter

---

## Récapitulatif des outils par phase

| Phase | Outils retenus | Écartés, et pourquoi |
|---|---|---|
| Cadrage | RGPD, AI Act, dictionnaire de données | — |
| Données | Git, pandas, CSV | DVC *(décrit comme cible, non installé)* |
| Exploration | pandas, matplotlib | — |
| Préparation | pandas, imputation médiane | Z-score, IQR *(les valeurs extrêmes sont réelles, pas des erreurs)* |
| Feature engineering | ratios d'usage, `train_test_split`, mise à l'échelle | SMOTE/ADASYN *(fabriquent de faux clients)*, PCA *(détruit l'explicabilité)*, TimeSeriesSplit *(pas de série chronologique)* |
| Baseline | scikit-learn, séparation stratifiée | — |
| Entraînement | régression logistique, forêt aléatoire, validation croisée | CNN, YOLO, autoencodeur *(pas d'images)*, réseaux profonds *(trop peu de données)*, MLflow *(surdimensionné pour un notebook)* |
| Optimisation | `GridSearchCV`, grille restreinte | Optuna *(contraire à la démarche de sobriété)* · CodeCarbon *(option ouverte)* |
| Validation | matrice de confusion, ROC, précision-rappel, importance par permutation | SHAP *(option ouverte)* · exactitude *(trompeuse ici)* |
| Déploiement | joblib, esquisse d'API, CI/CD décrite | MLflow Model Registry *(pas d'environnement réel)* |
| Suivi | PSI, Kolmogorov-Smirnov | — |

**Un mot sur les outils écartés.** Un projet réussi n'est pas celui qui emploie le plus d'outils, mais celui
qui justifie ceux qu'il emploie **et** ceux qu'il écarte. Chaque ligne de la colonne de droite est un
argument défendable devant un jury.

---

## Glossaire

| Terme | Définition |
|---|---|
| **Baseline** | Modèle simple servant de point de comparaison obligatoire |
| **Churn** | Résiliation d'un abonnement par un client |
| **CSM** | *Customer Success Manager* — conseiller chargé de la relation client |
| **Dérive** | Décalage progressif entre les données actuelles et celles d'apprentissage |
| **Faux négatif** | Un départ non repéré |
| **Faux positif** | Une alerte sur un client qui n'allait pas partir |
| **Feature / variable explicative** | Information fournie au modèle pour l'aider à prédire |
| **Fuite de données** | Information utilisée par le modèle alors qu'elle n'était pas disponible au moment de la prédiction |
| **Hyperparamètre** | Réglage du modèle fixé avant l'entraînement |
| **Imputation** | Remplacement d'une valeur manquante par une estimation |
| **MRR** | *Monthly Recurring Revenue* — revenu mensuel récurrent |
| **Notebook** | Document mêlant texte, code et résultats |
| **Précision** | Part de bonnes alertes parmi les alertes émises |
| **Rappel** | Part des départs réels effectivement repérés |
| **Seuil de décision** | Niveau de risque à partir duquel on décide d'agir |
| **Surapprentissage** | Le modèle mémorise les exemples au lieu d'en tirer des règles générales |
| **Valeur espérée** | Risque de départ multiplié par la valeur du client |
| **Valeur vie client (CLV)** | Revenu total qu'un client devrait générer sur toute sa durée de vie |
| **Validation croisée** | Répétition de l'évaluation sur plusieurs découpages des données |

---

## Suivi d'avancement

| Phase | Statut | Échéance |
|---|---|---|
| 1 · Cadrage | 🟢 Terminé | — |
| 2 · Données | 🟡 En cours | 23/09 |
| 3 · Exploration | 🟡 En cours | 23/09 |
| 4 · Préparation | 🟡 En cours | 23/09 |
| 5 · Feature engineering | 🟡 En cours | 24/09 |
| 6 · Baseline | 🟡 En cours | 25/09 |
| 7 · Entraînement | 🔴 À faire | 25/09 |
| 8 · Optimisation | 🔴 À faire | 25/09 |
| 9 · Validation | 🔴 À faire | 26/09 |
| 10 · Déploiement | 🟠 Partiel | 27/09 |
| 11 · Suivi | 🟠 Partiel | 28/09 |
| **Gel des livrables** | — | **28/09 au soir** |
| Support de présentation | 🔴 À faire | 29–30/09 |
| **Remise** | — | **01/10** |
