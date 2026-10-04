# Intégration CRM — valeurs par défaut (validées le 03/10/2026)

Réglages dans `src/churn_saas/industrialisation/liste.py`.

| Besoin | Règle | Réglage |
|---|---|---|
| **Format** | CSV UTF-8 avec BOM, séparateur `;`, une ligne par compte, libellés métier (`industrialisation/liste.py`, `LIBELLES`) | — |
| **Fréquence** | Lot **mensuel** : `tools/liste_operationnelle.py` ; score à la demande par l'API | — |
| **Compte déjà traité** | Règle prévue : écarté s'il a été contacté il y a moins de 2 mois, sauf hausse du gain attendu de plus de 50 % ou événement critique signalé par le CRM. **Codée dans `construire_liste`, pas encore appliquée** : l'outil de liste ne lui transmet pas l'historique des contacts (`--historique` accepté, non branché ; registre D-11) | `CARENCE_MOIS`, `HAUSSE_REINTEGRATION` |
| **Groupe témoin** | 10 % des comptes sélectionnés, tirés au sort (graine = mois de la liste), **non contactés** | `PART_GROUPE_TEMOIN` |
| **Boucle de retour** | Le CRM renvoie l'issue à 3 mois de chaque compte de la liste, contacté **et** témoin : `tools/retours_terrain.py` mesure l'efficacité réelle | — |

**Ce qui reste à confirmer avec le commanditaire** : le CRM (import de fichier ou API), la correspondance des
identifiants, qui saisit les retours et sous quel délai, et l'acceptation du groupe témoin (renoncer à contacter
quelques comptes rentables pour savoir si l'action sert vraiment).

## Fichiers échangés

| Sens | Fichier | Colonnes |
|---|---|---|
| CRM → projet | Historique des contacts | `client_id`, `date_contact`, `gain_au_contact_eur`, `evenement_critique` |
| Projet → CRM | Liste du mois | Priorité, Compte, Action recommandée, Risque de départ, Risque (%), Valeur client estimée (k€), Revenu mensuel (€), Gain attendu d'un contact (€), Pourquoi ce compte ?, Déjà contacté, Généré le, Modèle |
| CRM → projet | Retours à 3 mois | `client_id`, `mois_liste`, `groupe` (contact, temoin), `date_contact`, `action_menee`, `resultat_3_mois` (reste, parti, inconnu), `motif` (prix, fonctionnalites, support, concurrent, rachat_fusion, fin_de_projet, autre) |

Ces fichiers nomment des comptes réels : ils restent dans `sorties/`, jamais versionné.
