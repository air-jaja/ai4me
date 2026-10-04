# Champs de l'API — référence métier

> Document **généré** par `tools/documenter_champs.py` : ne pas le modifier à la main. Libellés et
> descriptions : dictionnaire des données (`industrialisation/dictionnaire.py`) ; réponse : schéma
> `ScoreSortie` (`industrialisation/api.py`) ; chiffres : les **4 000 comptes de la partie
> d'entraînement**. La partie de test n'est pas décrite. Guide d'appel : `docs/API.md`.

## 1. Entrées — `POST /score`

Les noms des champs sont les colonnes de l'export du CRM. Seul `valeur_vie_client_eur` est
obligatoire ; un champ absent ou `null` est traité comme à l'entraînement (colonne « Si absent »).

| Champ | Libellé | Description | Type | Unité | Exemple | Rôle | Sensibilité |
|---|---|---|---|---|---|---|---|
| `client_id` | Compte | Identifiant du compte dans le CRM, renvoyé tel quel. | texte | — | `CLI-004593` | Renvoyé tel quel | Pseudonyme |
| `jour_souscription` | Jour de souscription | Jour de la semaine de la souscription, en minuscules. | texte | — | `mardi` | Variable du modèle | — |
| `secteur` | Secteur | Secteur d'activité du client. | texte | — | `Santé` | Variable du modèle | Donnée d'entreprise |
| `taille_entreprise` | Taille d'entreprise | TPE, PME, ETI ou GE (grande entreprise). | texte | — | `PME` | Variable du modèle | Donnée d'entreprise |
| `plan` | Formule souscrite | Formule du catalogue (Starter, Pro, Business, Enterprise). | texte | — | `Starter` | Variable du modèle | — |
| `anciennete_mois` | Ancienneté | Mois depuis la souscription. | entier | mois | `8` | Variable du modèle | — |
| `sieges_souscrits` | Sièges souscrits | Nombre de licences payées. | entier | sièges | `12` | Variable du modèle | — |
| `utilisateurs_actifs` | Utilisateurs actifs | Utilisateurs connectés sur les 30 derniers jours. | entier | utilisateurs | `7` | Variable du modèle | — |
| `taux_adoption_pct` | Adoption des licences | Part des sièges réellement utilisés. | décimal | % | `58.3` | Variable du modèle | — |
| `connexions_30j` | Connexions (30 j) | Connexions sur les 30 derniers jours. | entier | connexions | `41` | Variable du modèle | — |
| `heures_usage_30j` | Heures d'usage (30 j) | Temps d'usage cumulé sur 30 jours. | décimal | heures | `63.5` | Variable du modèle | — |
| `fonctionnalites_utilisees` | Fonctionnalités utilisées | Fonctionnalités utilisées au moins une fois. | entier | fonctionnalités | `6` | Variable du modèle | — |
| `nb_integrations` | Intégrations actives | Connecteurs actifs vers d'autres outils du client. | entier | intégrations | `0` | Variable du modèle | — |
| `derniere_connexion_jours` | Jours depuis la dernière connexion | Jours écoulés depuis la dernière connexion d'un utilisateur. | entier | jours | `30` | Variable du modèle | — |
| `tickets_support_90j` | Tickets de support (90 j) | Tickets ouverts sur 90 jours. | entier | tickets | `6` | Variable du modèle | — |
| `delai_reponse_support_h` | Délai de réponse du support | Délai moyen de première réponse. | décimal | heures | `9.5` | Variable du modèle | — |
| `csat` | Satisfaction (CSAT) | Note de satisfaction de 1 à 5. | entier | sur 5 | `3` | Variable du modèle | — |
| `retards_paiement_12m` | Retards de paiement (12 mois) | Factures payées en retard sur 12 mois. | entier | retards | `1` | Variable du modèle | — |
| `revenu_mensuel_recurrent_eur` | Revenu mensuel | Revenu récurrent mensuel ; reconstruit depuis le catalogue s'il manque. | décimal | € par mois | `1188.0` | Variable du modèle | Donnée commerciale confidentielle |
| `valeur_vie_client_eur` | Valeur client estimée | Valeur vie du compte : nécessaire au gain attendu d'un contact. | décimal | € | `18400.0` | Calcul du gain attendu | Donnée commerciale confidentielle |

## 2. Valeurs numériques

« Plage admise » : ce qui vaut par définition ; une valeur hors plage est un défaut de la
source. Les autres colonnes décrivent les valeurs reçues sur les comptes d'entraînement.

| Champ | Plage admise | Minimum | Médiane | Maximum | Absents (source) | Si absent |
|---|---|---|---|---|---|---|
| `anciennete_mois` | ≥ 0 | 1 | 10 | 36 | 0 % | Médiane d'entraînement, 10 |
| `sieges_souscrits` | ≥ 0 | 1 | 27 | 897 | 0 % | Médiane d'entraînement, 27 |
| `utilisateurs_actifs` | ≥ 0 ; ≤ `sieges_souscrits` | 0 | 9 | 829 | 0 % | Médiane d'entraînement, 9 |
| `taux_adoption_pct` | 0 à 100 | 0 | 50 | 100 | 4,8 % | Recalculé : utilisateurs actifs ÷ sièges souscrits × 100, une décimale ; à défaut, médiane d'entraînement, 50 |
| `connexions_30j` | ≥ 0 | 0 | 16 | 156 | 0 % | Médiane d'entraînement, 16 |
| `heures_usage_30j` | ≥ 0 | 0 | 5,5 | 170,2 | 6,2 % | Médiane d'entraînement, 5,5 |
| `fonctionnalites_utilisees` | ≥ 0 | 0 | 5 | 40 | 0 % | Médiane d'entraînement, 5 |
| `nb_integrations` | ≥ 0 | 0 | 2 | 16 | 4,2 % | Médiane d'entraînement, 2 |
| `derniere_connexion_jours` | ≥ 0 | 0 | 2 | 200 | 0 % | Médiane d'entraînement, 2 |
| `tickets_support_90j` | ≥ 0 | 0 | 2 | 17 | 0 % | Médiane d'entraînement, 2 |
| `delai_reponse_support_h` | ≥ 0 | 0,5 | 10,6 | 56,5 | 9,6 % | Médiane d'entraînement, 10,6 |
| `csat` | 1 à 5 | 1 | 4 | 5 | 8,1 % | Médiane d'entraînement, 4 |
| `retards_paiement_12m` | ≥ 0 | 0 | 0 | 7 | 4,9 % | Médiane d'entraînement, 0 |
| `revenu_mensuel_recurrent_eur` | ≥ 0 | 9,11 | 676,69 | 76 511,23 | 2,7 % | Recalculé : sièges souscrits × prix mensuel par siège ; à défaut, médiane d'entraînement, 674,79 |
| `valeur_vie_client_eur` | ≥ 0 | 300 | 11 086,5 | 2 000 000 | 0 % | Appel refusé (422) |

## 3. Valeurs catégorielles

Modalités vues à l'entraînement, avec leur effectif. La casse et les espaces autour sont
ignorés (`PRO` vaut `Pro`) ; les accents comptent. Une valeur hors de cette liste n'est
reconnue par aucune modalité : le modèle n'en tient pas compte.

| Champ | Modalités (effectif) | Absents (source) | Si absent |
|---|---|---|---|
| `jour_souscription` | `lundi` (610), `mardi` (597), `samedi` (576), `vendredi` (570), `mercredi` (559), `dimanche` (545), `jeudi` (543) | 0 % | Modalité « Non renseigné » |
| `secteur` | `Commerce` (743), `Tech` (693), `Finance` (599), `Industrie` (516), `Éducation` (469), `Santé` (445), `Public` (339) | 4,9 % | Modalité « Non renseigné » |
| `taille_entreprise` | `PME` (1 672), `TPE` (1 353), `ETI` (696), `GE` (279) | 0 % | Modalité « Non renseigné » |
| `plan` | `Pro` (1 427), `Starter` (1 096), `Business` (1 030), `Enterprise` (447) | 0 % | Modalité « Non renseigné » |

## 4. Identifiant

`client_id` : 4 000 identifiants distincts pour 4 000 comptes, au format `CLI-999999` (9 : un chiffre).
Le modèle ne le lit pas ; l'API le renvoie tel quel pour rapprocher la réponse du compte.

## 5. Réponse — `POST /score`

| Champ | Libellé | Type | Description |
|---|---|---|---|
| `client_id` | Compte | texte | Identifiant reçu, renvoyé tel quel. |
| `risque_pct` | Risque (%) | entier | Probabilité calibrée de départ, en %. |
| `tranche_risque` | Risque de départ | texte | Très élevé, Élevé, Modéré ou Faible. |
| `probabilite` | Probabilité de départ | décimal | Valeur exacte, de 0 à 1. |
| `gain_attendu_contact_eur` | Gain attendu d'un contact (€) | décimal | Probabilité × valeur × efficacité − coût d'un contact. |
| `motif` | Pourquoi ce compte ? | texte | Les trois principaux facteurs, avec leur sens. |
| `modele` | Modèle | texte | Nom et version du modèle en service. |
| `avertissement` | Avertissement | texte | Rappel : le score éclaire, la liste mensuelle décide. |

**Tranches de risque** (`tranche_risque`, selon `probabilite`) :

| Tranche | Probabilité |
|---|---|
| Très élevé | ≥ 60 % |
| Élevé | ≥ 40 % et < 60 % |
| Modéré | ≥ 20 % et < 40 % |
| Faible | < 20 % |

**Gain attendu d'un contact** (`gain_attendu_contact_eur`) = probabilité × valeur client ×
efficacité de la rétention (25 %) − coût d'un contact (135 €).
Les deux paramètres sont des **hypothèses** du projet (`config.py`). Un gain négatif signifie
qu'un contact coûte plus qu'il ne rapporte en moyenne.
