# CLAUDE.md — relais pour Claude Code

Projet de certification CISIA : score de risque de départ (churn) de comptes B2B SaaS, liste mensuelle priorisée par
valeur pour les conseillers, API de score à la demande. Porteur : Rakotovoalavo Petera Haja.

## Règles qui comptent (détail : `docs/00.REGLES_DE_TRAVAIL.md`)

- **Une décision est committée seule, avant le calcul qu'elle gouverne** (règle 8) ; preuves dans `docs/livraisons/`.
- **Le jeu de test a été lu deux fois, pour de bon** (évaluation phase 7, restitution phase 9). Ne jamais le relire ;
  `tools/restitution_test.py` et `tools/evaluation_finale.py` le refusent.
- Commits **au nom du porteur**, message `NN · type: objet` (`docs/LIVRAISON.md`) ; jamais `--no-verify`.
- **Commit au fil de l'activité, push une seule fois à la fin** : on commite à chaque fin d'étape, sans pousser ; le
  push final se fait quand l'activité est terminée, sur demande du porteur. Les messages ne lui sont plus soumis à
  chaque commit (04/10/2026) : il vérifie celui du dernier commit, avant le push final.
- Avant tout push : `uv run python tools/campagne_tests.py` (et `make check`) ; la CI a deux jobs, le job `complet`
  ne tolère aucun test ignoré.
- Hooks installés par `make hooks` après chaque clone : au commit, les documents générés dont une source change
  sont régénérés ; si l'un change, le commit s'arrête — relire, `git add`, recommiter (règle 2 bis).
- Code et docstrings en anglais ; noms de fonctions et documents en français. Modèles nommés en français dans le dépôt
  (E-714).
- Résultats dans `resultats/` : jamais saisis à la main, toujours produits par un outil de `tools/` ; l'identité
  d'exécution (graphe d'imports) évite les recalculs inutiles — `config.py` est dans le périmètre de **tous** les outils.
- Mesures de ressources : sur le poste du porteur (Windows), pas ailleurs.

## État au 04/10/2026

Phases 1 à 10 terminées (`docs/suivi_projet_ia.md`). Modèle en service : `churn_saas_servi 1.1` (régression
logistique calibrée, une copie), alias `champion` (`tools/promouvoir.py --etat`). Model card : `docs/MODEL_CARD.md`.

## À faire, dans l'ordre

1. **Budget de latence de bout en bout de l'API** : à décider par le porteur. Le modèle tient 50 ms ; l'appel complet
   prend environ 80 ms à cause de la préparation du compte (`docs/API.md`).
2. **D-09** : harmonisation de la casse des catégories dépendante du lot (`donnees/silver.py`). L'API la contourne ;
   la corriger à la source impose un recalcul complet.
3. **Phase 11 (suivi et réentraînement)** — implémentée et démontrée sur lots simulés (M1 à M10, S1 à S8 ;
   carnet `notebooks/11_suivi.ipynb`). Reste : **exécuter le notebook de certification sur le poste du porteur**
   (`make executer-notebook`, § 13 à reporter) — le correctif CI du 04/10 a modifié `tools/modele_servi.py`, ce qui
   relance `modele_servi` et `regle_decision` : les latences doivent être mesurées sur le poste, pas ailleurs.
   Incohérence à trancher : l'alias `champion` désigne le fichier du 03/10, absent du registre (`f427144`).
   À demander au commanditaire : l'issue de **tous** les comptes, les responsables nommés ; taille du groupe témoin
   (48 témoins par trimestre ne suffisent pas à prouver l'efficacité).
4. **Support de soutenance** : reproposer la table de correspondance des noms de modèles, français du dépôt ↔ anglais
   (D-08).
