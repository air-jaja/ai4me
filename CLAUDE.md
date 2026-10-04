# CLAUDE.md — relais pour Claude Code

Projet de certification CISIA : score de risque de départ (churn) de comptes B2B SaaS, liste mensuelle priorisée par
valeur pour les conseillers, API de score à la demande. Porteur : Rakotovoalavo Petera Haja.

## Règles qui comptent (détail : `docs/00.REGLES_DE_TRAVAIL.md`)

- **Une décision est committée seule, avant le calcul qu'elle gouverne** (règle 8) ; preuves dans `docs/livraisons/`.
- **Le jeu de test a été lu deux fois, pour de bon** (évaluation phase 7, restitution phase 9). Ne jamais le relire ;
  `tools/restitution_test.py` et `tools/evaluation_finale.py` le refusent.
- Commits **au nom du porteur**, message `NN · type: objet` (`docs/LIVRAISON.md`) ; jamais `--no-verify`.
- **Commit au fil de l'activité, push une seule fois à la fin** : on commite sans pousser ; le push final se fait quand
  l'activité est terminée, sur demande du porteur. Chaque message de commit lui est soumis avant le commit.
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
3. **Phase 11 (suivi et réentraînement)** — valeurs par défaut **validées le 04/10/2026** (M1 à M10,
   `docs/00.README_choix_methodologiques.md` § 7 nonies ; `monitoring/alertes.py`, figées par un test). Reste à
   implémenter : dérive combinée (M5), manquants relatifs (M8), volume des comptes signalés (M9), surveillance de la Suisse (M7),
   sélection des données de réentraînement (M2, M4). À demander au commanditaire : l'issue de **tous** les comptes,
   les responsables nommés.
4. **Support de soutenance** : reproposer la table de correspondance des noms de modèles, français du dépôt ↔ anglais
   (D-08).
