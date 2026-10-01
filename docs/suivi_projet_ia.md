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
| **Statut global** | 🟡 En cours — phases 1 à 3 terminées, 4 à 6 engagées, 7 à 9 à exécuter |
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
| 2 · Données — ingestion & gouvernance | 3, 5 | C1, C2, C3 |
| 3 · Exploration & profiling | 5, 6, 7 | C3, C4 |
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

## 2 · Données — ingestion & gouvernance *(🟢 terminé)*

> **De quoi s'agit-il ?** Rassembler les données, comprendre d'où elles viennent, qui en est propriétaire,
> combien de temps on a le droit de les garder. « Gouvernance » désigne l'ensemble de ces règles.
> « Versionner » signifie conserver une trace datée de chaque version, afin de pouvoir revenir en arrière
> et de reproduire à l'identique un résultat obtenu plusieurs mois plus tôt.

- [x] Lire et ingérer les sources, décrire le schéma des données
- [x] Documenter le cycle de vie des données (collecte → conservation → suppression)
- [x] Justifier le choix du mode de stockage
- [x] Mettre en place le versioning du code et des données
- [x] Identifier les données sensibles et le traitement associé

**Livrables produits :** `notebooks/02_donnees.ipynb` (exécuté, 3 figures, 13 tableaux) et
`docs/02.DONNEES_explications.md` (lecture sans prérequis technique, glossaire de 20 termes).

### Les trois fichiers sources

| Fichier | Contenu | Usage |
|---|---|---|
| `churn_saas_complet.csv` | 5 035 lignes, 29 colonnes | Apprentissage et évaluation |
| `churn_saas_echantillon.csv` | 50 lignes | Test du programme de bout en bout |
| `catalogue_plans.csv` | Caractéristiques des formules d'abonnement | Enrichissement par rapprochement |

### Le schéma : ce que chaque colonne a le droit de devenir

Le type d'une colonne dit comment elle est écrite ; son **rôle** dit ce qu'on a le droit d'en faire. Sur
29 colonnes, **six ne peuvent pas servir au programme**, et pour six raisons différentes — un identifiant,
deux cibles, une variable postérieure à la décision, un champ de texte libre, un artefact de process.

Ces motifs ne sont pas interchangeables : la certification distingue l'exclusion éthique de l'exclusion
technique, et une justification unique ne satisferait ni l'une ni l'autre.

### Quatre défauts mesurés, et ce qu'ils coûtent

| Défaut constaté | Ce qui se passerait si on ne le corrigeait pas |
|---|---|
| 35 lignes en double sur 5 035 | Le programme apprend deux fois les mêmes exemples et sa note est flattée |
| Un caractère invisible en tête de fichier | La première colonne devient introuvable par son nom |
| Des nombres écrits comme du texte | Chaque valeur devient une catégorie : « 33,3 » et « 33,4 » n'ont plus aucun rapport |
| Des majuscules incohérentes | Deux effets : le rapprochement échoue **sans message d'erreur**, et 26 catégories fantômes apparaissent |

**Le dernier est de loin le plus dangereux, et c'est contre-intuitif.** Les trois premiers provoquent une
erreur franche : on cherche, on corrige. Le quatrième ne provoque rien du tout. Nous l'avons mesuré : sans
harmonisation préalable, **2 302 lignes sur 5 035 ne sont pas rapprochées** — près d'une sur deux. Avec
harmonisation, toutes le sont.

Un échec total se remarquerait. Un échec à 46 % ne se remarque pas : les données restent plausibles et
l'analyse porte sur la moitié du portefeuille sans que rien ne le signale.

### Une hypothèse testée plutôt que tranchée

Entre 3 et 10 % des valeurs manquent. La réaction habituelle consiste à les remplacer par une estimation.
Mais une autre hypothèse était possible : et si **l'absence d'une donnée était elle-même un signal** ? Un
client désengagé pourrait cesser d'être suivi, et le vide dans ses données annoncerait son départ.

Nous avons vérifié, colonne par colonne. **L'écart maximal est de 4,5 points**, pour un taux de départ moyen
de 28 % — trop faible pour conclure. L'hypothèse est écartée sur la base d'une mesure, et c'est elle qui
légitime la méthode de remplacement retenue à l'étape suivante.

**Limite de cette conclusion, établie en phase 3.** Elle vaut pour les colonnes reçues, non pour celles que
le programme calcule. Une division par zéro y produit des trous qui encodent un compte abandonné, avec un
écart de 62 points. Généraliser aurait détruit le meilleur signal du jeu.

### Le cycle de vie : huit étapes, huit responsables

De la collecte à la purge, chaque étape porte sa fréquence, sa durée et **son responsable nommé**. Une étape
sans responsable est une étape que personne n'exécute — la purge en est l'exemple type : tout le monde
approuve le principe, personne ne la fait.

**Un point reste volontairement ouvert** : la durée de conservation des scores. Le suivi du programme demande
un historique long, la réglementation demande de ne pas garder plus que nécessaire. Cet arbitrage appartient
au délégué à la protection des données, pas à l'équipe technique.

### Le stockage : six options comparées, et un revirement

| Type de donnée | Support retenu | Motif |
|---|---|---|
| CSV sources (2 Mo) | **Git simple** | Sous 50 Mo, Git suffit et n'exige rien de particulier |
| Instantanés d'entraînement | **Parquet, suivi Git-LFS** | Fichiers volumineux et immuables : le cas où LFS est pertinent |
| Scores produits | **PostgreSQL** | On les interroge, on ne les versionne pas |
| Fiches de version | **Git simple** | Minuscules, textuelles, et ce sont elles le contrat |

**Le revirement mérite d'être raconté.** Le dépôt utilisait Git-LFS pour les CSV. Un clone réalisé depuis un
environnement dépourvu de l'extension a rapporté **trois fichiers de 128 octets au lieu de 700 000** — des
tickets, pas des données. Aucun message d'erreur.

C'est le même piège que la clé de rapprochement mal harmonisée : une défaillance qui ne dit pas son nom. Un
correcteur sans l'extension se retrouverait avec des fichiers illisibles et un programme qui échoue plus
loin, sur une cause sans rapport. La migration a été faite, puis **vérifiée par empreinte** : les fichiers
sont bit à bit identiques avant et après.

### Le versionnement des données

Versionner le programme est facile ; versionner les données est l'endroit où la reproductibilité se perd.
Rien dans Git ne signale qu'un fichier source a changé entre deux entraînements.

Une **empreinte** est une signature calculée à partir du contenu : si celui-ci change d'un seul caractère,
elle change entièrement. Une **fiche de version** enregistre l'empreinte de chaque fichier source, et se
vérifie avant tout entraînement. Elle est régénérée uniquement lorsque les empreintes ne tiennent plus — la
réécrire à chaque exécution produirait un diff à chaque commit, et une fiche que personne ne lit ne certifie
rien.

### Les données sensibles

« Sensible » ne veut pas dire uniquement « données personnelles ». Trois niveaux coexistent : donnée
personnelle (les notes libres), pseudonyme (le numéro de client, qui remonte à une entreprise identifiable),
et confidentiel commercial (le revenu d'un client).

Le champ de notes libres a été **analysé automatiquement** plutôt que présumé risqué, et les exemples
affichés sont masqués par le programme avant impression : la démonstration ne doit pas commettre l'infraction
qu'elle décrit.

**Les variables indirectes sont conservées, et c'est délibéré.** Pays, secteur et taille d'entreprise
pourraient approcher une caractéristique protégée. Les supprimer donnerait une illusion d'équité : le
programme reconstituerait l'information par d'autres colonnes, sans qu'aucun indicateur ne le détecte. Les
garder et les surveiller est plus honnête et plus efficace.

### Le code produit

| Module | Rôle |
|---|---|
| `donnees/ingestion.py` | Lecture brute, inventaire avant transformation |
| `donnees/silver.py` | Nettoyage, typage, normalisation, jointure catalogue |
| `donnees/gold.py` | Exclusions motivées, séparation de la cible |
| `donnees/schema.py` | Rôle déclaré de chaque colonne, audit de qualité, contrôle de jointure |
| `donnees/gouvernance.py` | Cycle de vie, sensibilité, scan de données personnelles, comparaison de stockage |
| `donnees/empreinte.py` | Empreintes, fiches de version, contrôle d'intégrité |

25 fonctions exposées, toutes couvertes par des tests.

🔧 **Outils** : Git *(historique du code et des CSV)* · pandas · SHA-256 *(empreintes)* ·
Parquet et Git-LFS *(instantanés d'entraînement)* · PostgreSQL *(scores produits)*
📦 **Artefacts** : `notebooks/02_donnees.ipynb` · `docs/02.DONNEES_explications.md` ·
`data/manifeste_v1.0.json` · sections 3, 4 et 5 du notebook de certification
**Statut** : **terminé** — décisions arrêtées, code couvert, carnet exécuté

---

## 3 · Exploration & profiling *(🟢 terminé)*

> **De quoi s'agit-il ?** Regarder les données avant de les utiliser : combien de valeurs manquent, y a-t-il
> des doublons, comment les chiffres se répartissent, quelles colonnes semblent liées au départ des clients.
> On y construit aussi la **chaîne de transformation** qui mène des fichiers bruts aux données exploitables
> par un programme.

- [x] Profiling : valeurs manquantes, doublons, distributions
- [x] Construire la chaîne bronze → silver → gold
- [x] Détecter le déséquilibre entre les catégories
- [x] Analyser les corrélations et les tendances
- [x] Vérifier si l'absence d'une donnée est elle-même un signal
- [x] Rédiger l'interprétation des observations

**Livrables produits :** `notebooks/03_exploration.ipynb` (exécuté, 6 figures, 18 tableaux) et
`docs/03.EXPLORATION_explications.md` (lecture sans prérequis technique, glossaire de 15 termes).

### La découverte qui a changé la préparation

Le programme calcule des **ratios d'usage** — les heures d'utilisation rapportées au nombre d'utilisateurs
actifs, par exemple. Quand ce nombre vaut zéro, la division est impossible et l'ordinateur inscrit « valeur
manquante ».

Le réflexe aurait été de combler ces trous comme les autres. **Ils ne sont pas des données manquantes :** ils
décrivent un compte que l'entreprise facture et que plus personne n'utilise.

| Constat | Valeur |
|---|---|
| Comptes sans aucun utilisateur actif | 297, soit 5,9 % du portefeuille |
| Leur taux de résiliation | **86,5 %** |
| Celui de tous les autres | 24,3 % |
| Revenu mensuel qu'ils représentent | ≈ 1,06 M€ |

Un écart de **62 points** — le signal le plus fort de tout le jeu de données. Le combler par une moyenne
l'aurait remplacé par la valeur d'un compte ordinaire, sans qu'aucune mesure ne signale la perte. Une
information explicite, « ce compte n'a aucun utilisateur actif », est donc déclarée avant le calcul des
ratios : elle survit au comblement, et un conseiller peut la lire.

### Le second défaut : vingt-six catégories fantômes

Un graphique de taux de départ par segment affichait **huit tailles d'entreprise** là où l'entreprise en a
quatre, et vingt-et-un secteurs pour sept. L'uniformisation des majuscules n'était appliquée qu'à la colonne
servant au rapprochement entre fichiers, pas aux valeurs enregistrées.

Le programme aurait vu plusieurs catégories rares là où le métier en a une seule, réparti le signal entre
elles, et toute explication fournie au conseiller serait devenue trompeuse.

**Ce défaut a invalidé trois chiffres publiés en phase 1**, corrigés depuis : les écarts entre segments
étaient surestimés d'un facteur deux. La correction renforce la conclusion du cadrage plutôt qu'elle ne la
fragilise — les segments se séparent encore moins qu'annoncé, ce qui justifie d'autant mieux un modèle
plutôt qu'une règle métier.

### Les trois niveaux de données

| Niveau | Contenu | Pour qui |
|---|---|---|
| **Bronze** | Brutes, telles que reçues, sans modification | Personne — c'est la référence |
| **Silver** | Nettoyées, corrigées, rapprochées, lisibles | Un humain, un outil de restitution |
| **Gold** | Informations calculées ajoutées, colonnes interdites retirées | Le programme |

Le programme tient un **journal** : à chaque étape, le nombre de lignes et de colonnes obtenues, et l'effet
produit. Une transformation que personne ne peut chiffrer est une transformation que personne ne peut
défendre.

**Où les trous sont comblés, et pourquoi pas dans la chaîne.** Un humain qui lit un tableau ne veut pas de
trous ; un programme, lui, en a besoin. Le comblement est donc calculé **à l'intérieur du programme
d'apprentissage**, sur les seules données d'entraînement — le faire avant la séparation laisserait l'examen
influencer la révision. Une version comblée du silver existe pour la lecture humaine, explicitement
interdite d'apprentissage.

### L'absence est-elle un signal ?

Question posée en phase 2, tranchée ici de façon plus fine.

| Type de colonne | Écart de taux de départ | Conclusion |
|---|---|---|
| Colonnes **reçues** | 4,5 points au plus | Hasard : le comblement statistique est légitime |
| Colonnes **calculées** | jusqu'à 62 points | Signal : à déclarer, jamais à combler |

Deux vérifications indépendantes soutiennent la première ligne : l'écart de taux de départ, et l'absence de
cause structurelle. Une absence peut être sans lien avec ce qu'on cherche à prédire tout en étant
structurelle, auquel cas la combler fabriquerait une valeur qui n'a jamais existé.

### Les données produites sont tracées

La chaîne calcule les trois niveaux en mémoire. Rien n'était conservé — et l'étape 4 du
cycle de vie décrite en phase 2, « instantané d'entraînement, jeu figé, horodaté et
empreinté », restait donc déclarative.

Elle est désormais effective. Les jeux nettoyé et prêt-pour-l'apprentissage sont enregistrés
au format Parquet, avec leur empreinte et la version du programme qui les a produits. Un
contrôle compare ces empreintes avant tout entraînement.

| Jeu | Support | Conservé dans l'historique |
|---|---|---|
| Fichiers de départ | `data/raw/*.csv` | **Oui** — 2 Mo, référence de tout le reste |
| Jeu nettoyé | `data/processed/*.parquet` | Non — recalculable |
| Jeu d'entraînement | `data/processed/*.parquet` | Non — recalculable |
| Fiche de version | `data/manifeste_v1.0.json` | **Oui** — c'est elle le contrat |

**Pourquoi enregistrer un résultat reproductible.** Parce que le supposer ne suffit pas.
Une mise à jour d'outil peut modifier le résultat sans que rien ne le signale, et le modèle
serait entraîné sur des données différentes de celles que sa fiche décrit. Le triangle
programme–données–modèle avait un sommet manquant : rien ne reliait une version de modèle au
jeu exact qui l'avait produite.

**Pourquoi pas en base de données.** Une base n'archive rien par nature : une mise à jour
efface l'état précédent. Elle reste le bon support pour les scores produits, qu'on
interroge, pas pour des données d'entraînement qu'on fige.

### Constats du profilage

| Observation | Valeur | Ce que cela implique |
|---|---|---|
| Doublons exacts | 35 sur 5 035 lignes | Supprimés — 5 000 comptes uniques restent |
| Doublons sur la clé client | Aucun | La suppression est sans risque |
| Taux de résiliation | **28 %** | Déséquilibre modéré, non sévère : le discours du cas rare serait faux |
| Données manquantes | 3 à 10 % selon les colonnes | Comblement légitime ; une colonne à 55 % reste écartée |
| Revenu moyen / revenu médian | **5,2×** | Comblement par la médiane, jamais par la moyenne |
| Valeurs extrêmes | 1 compte sur 8, la moitié du revenu | Conservées : ce sont les clients stratégiques |
| Écarts entre segments | 6 à 8 points | Aucun segment ne concentre le risque : un modèle se justifie |

### Le code produit

| Module | Rôle |
|---|---|
| `donnees/profilage.py` | Manquants, doublons, distributions, mécanisme des manquants |
| `features/pipeline.py` | Chaîne bronze → silver → gold, avec journal |
| `features/exploration.py` | Déséquilibre, corrélations, tendances par tranche |
| `features/materialisation.py` | Écriture des instantanés, empreintes, contrôle d'intégrité |

🔧 **Outils** : pandas · matplotlib *(production de graphiques)* · scipy *(tests statistiques)*
📦 **Artefacts** : `notebooks/03_exploration.ipynb` · `docs/03.EXPLORATION_explications.md` ·
`data/processed/*.parquet` *(instantanés datés)* · `data/manifeste_v1.0.json` *(étendu)* ·
sections 5, 6 et 7 du notebook de certification
**Statut** : **terminé** — 21 décisions arrêtées, code couvert par 52 cas de test, carnet exécuté

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
| Données | Git *(CSV et fiches de version)*, pandas, SHA-256, Parquet *(instantanés dérivés)*, PostgreSQL *(scores produits)* | DVC *(pertinent au-delà de quelques instantanés ; inutile à ce volume)* · Git-LFS sur les CSV *(dépendance côté client, échec silencieux sans l'extension)* |
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
| **Empreinte (hash)** | Signature calculée à partir du contenu d'un fichier ; change entièrement si le contenu change |
| **Git-LFS** | Extension de Git pour les gros fichiers ; nécessite une installation côté utilisateur |
| **Gouvernance** | Règles définissant qui fait quoi avec les données, et pendant combien de temps |
| **Instantané (snapshot)** | Photographie datée d'un jeu de données, figée pour référence |
| **Manifeste** | Fiche recensant les fichiers d'une version et leurs empreintes |
| **Pseudonyme** | Identifiant permettant de remonter à une personne ou entreprise via une autre source |
| **Variable indirecte (proxy)** | Colonne qui approche une caractéristique protégée sans la nommer |
| **Bronze / silver / gold** | Trois états successifs des données : brutes, nettoyées, prêtes pour l'apprentissage |
| **Corrélation** | Nombre entre −1 et +1 indiquant si deux informations varient ensemble |
| **Médiane** | Valeur partageant une population en deux moitiés égales ; insensible aux valeurs extrêmes |
| **Modalité** | Une des valeurs possibles d'une catégorie, par exemple « PME » |
| **Monotone** | Se dit d'une relation qui va toujours dans le même sens |
| **Profilage** | Mesure de ce que les données contiennent : trous, doublons, répartitions |
| **Quintile** | Un cinquième d'une population, classée par ordre croissant |
| **Ratio** | Rapport entre deux nombres, plus parlant que chacun pris seul |
| **Validation croisée** | Répétition de l'évaluation sur plusieurs découpages des données |

---

## Suivi d'avancement

| Phase | Statut | Échéance |
|---|---|---|
| 1 · Cadrage | 🟢 Terminé | — |
| 2 · Données | 🟢 Terminé | — |
| 3 · Exploration | 🟢 Terminé | — |
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
