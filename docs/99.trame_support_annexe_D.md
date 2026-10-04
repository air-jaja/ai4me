# Support de soutenance — première trame (approche par l'Annexe D)

**Statut : première approche, non finalisée.** Format, gabarit et découpage définitifs à arbitrer par le porteur.

## Le parti pris

Raconter le projet **par ses retours en arrière** : chaque bloc part d'une itération de l'Annexe D (le
constat, le retour, l'effet mesuré). Le jury voit une démarche qui se corrige sur preuve, pas une suite
d'étapes cochées. Les 15 itérations couvrent les neuf compétences ; la colonne « C » le vérifie.

Durée cible : **29 minutes**, une minute de marge. Les chiffres viennent du notebook ; la colonne « Preuve »
indique où les retrouver en cas de question.

## Trame

| # | Bloc | Itérations | Message clé (une phrase) | Preuve dans le notebook | C | Durée |
|---|---|---|---|---|---|---|
| 1 | Le problème | — | Prioriser chaque mois 140 comptes à risque, par valeur, pour des conseillers qui décident | § 1, § 2 | C1 | 2 min |
| 2 | Le cadrage remis en cause | 2 | 10 % des départs portent 72 % du revenu perdu : on priorise la valeur, pas le rappel global — et on en traite la conséquence éthique | § 2 (figure de concentration), § 4 | C1, C2 | 3 min |
| 3 | Les données se taisent | 3, 4, 5, 6, 7 | Cinq défauts silencieux, aucun ne levait d'erreur : 21 secteurs pour 7, 570 délais effacés par « h », 960 dates inversées, une empreinte qui dépendait du système | § 6.4, § 7.1 | C3, C1 | 4 min |
| 4 | Le modèle trop beau | 1 | AUC 0,999 : une fuite, pas un exploit ; démontrée, puis exclue (0,891) | § 8.A (démonstration de la fuite) | C3, C4 | 3 min |
| 5 | Moins de variables, autant de signal | 9 | Les variables construites n'apportent rien (+0,003) : 25 → 18 variables ; la régression logistique bat forêt et XGBoost sur 24 plis sur 25 | § 8.B, 8.C, § 9.A | C4, C5 | 4 min |
| 6 | Ce que le modèle produit | 10 | PR-AUC 0,761 sur un test évalué une seule fois ; 2,3 M€ couverts sur 4,1 M€ ; la Suisse sous le critère d'équité, documentée et surveillée | § 9.C, § 12.A à 12.D | C8, C2 | 4 min |
| 7 | En exploitation | 11, 12, 15 | Une API sans décision, un lot qui décide, un seul champion par alias ; la plateforme vérifiée (captures) | § 10, § 11 (schéma, captures) | C6, C7 | 4 min |
| 8 | Le suivi | 8, 13, 14 | M1 à M10 ; une dérive simulée restée muette, gardée telle quelle ; 48 témoins par trimestre ne prouvent rien : arbitrage remonté | § 13 | C9, C8 | 3 min |
| 9 | Conclusion | — | Quatre recommandations ; ce qui reste à décider par le commanditaire | § 14 | C1 | 2 min |

**Couverture des compétences** : C1 (1, 2, 3, 9) · C2 (2, 6) · C3 (3, 4) · C4 (4, 5) · C5 (5) · C6 (7) · C7 (7) ·
C8 (6, 8) · C9 (8).

## Points d'attention

- **C5 n'est porté que par le bloc 5.** Ajouter une diapositive « réglage et calibration » (§ 9.A, 9.B) si
  l'Annexe B de la grille l'exige, ou la garder en annexe.
- **C7 n'est porté que par le bloc 7.** Le schéma d'architecture et le chiffrage des scénarios (§ 11) y tiennent
  en une diapositive.
- Le bloc 3 regroupe cinq itérations : en montrer deux (dates inversées, unité « h »), citer les autres.
- L'ordre suit le cycle de vie (données → modèle → exploitation → suivi) plutôt que les numéros d'itération.

## Diapositives d'annexe (questions du jury)

| Annexe | Contenu | Source |
|---|---|---|
| A1 | Hypothèses chiffrées : capacité 140, efficacité 25 % (sensibilité 15–40 %), coût d'un contact | § 9.E |
| A2 | Grille des neuf compétences, critère par critère, avec la section de preuve | Annexe B |
| A3 | Ce qui a été écarté, et pourquoi (Optuna, CodeCarbon, serveur Prefect…) | `docs/05.REGISTRE_elements_ecartes.md` |
| A4 | Sobriété : temps, énergie, latence (57 ms → 12 ms) | § 9.G, `docs/06.SOBRIETE_calcul.md` |
| A5 | Chaîne CI : pre-commit, campagne, GitHub Actions | § 10 |

## Reste à décider

1. Format : PowerPoint (.pptx) ou PDF.
2. Gabarit imposé (charte, logo) ou non.
3. Garder ce parti pris (Annexe D) ou revenir au déroulé de l'Annexe C.
4. Si les propositions R6 (une seule évaluation affichée) et R7 sont retenues, les chiffres des blocs 6 et 5
   restent valables ; seule la source citée change.
