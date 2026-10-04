# Chaîne de livraison

## Le flux

```
travail (Claude) ──► patchs ──► git am sur develop ──► campagne ──► push ──► CI
                                                                         │
            main ◄── pull request (une par phase) ◄──────────────────────┘
              │
              └──► étiquette annotée vX.Y.Z ──► git merge origin/main dans develop
```

| Étape | Commande | Rôle |
|---|---|---|
| Construire | `uv run python tools/livraison.py --verifier` | Patchs, fichiers modifiés, **A_LIRE.md généré** : base, ajouts / modifications / suppressions, actions à mener, résultat de `make check` et de la campagne sur base + patchs |
| Appliquer | `git am chemin\vers\patches\*.patch` | Conserve chaque commit, son message et sa date : la preuve d'antériorité des règles (règle 8) |
| Vérifier | `uv run python tools/campagne_tests.py` | Avant tout push |
| Fusionner | Pull request `develop` → `main` | Une par phase ; la CI tourne sur la pull request |
| Étiqueter | `git tag -a v0.10.0 -m "Phase 10 — Mise en exploitation"` puis `git push origin v0.10.0` | Point de retour à chaque état livré |
| Resynchroniser | `git checkout develop && git merge origin/main` | Les étiquettes deviennent visibles depuis `develop` |
| Journal | `uv run python tools/journal_modifications.py` | `CHANGELOG.md`, par phase |

## Conventions

- **Auteur des commits livrés** : le porteur du projet (`Rakotovoalavo Petera Haja`).
- **Message** : `NN · type: objet` — `NN` la phase ; type parmi `decision`, `feat`, `fix`, `resultats`, `perf`,
  `docs`, `notebook`. Objet court ; détail en trois lignes au plus.
- **Décisions** : un commit `decision` seul, **avant** les calculs qu'il gouverne, jamais regroupé avec eux.
- **Étiquettes** : `v0.N.0` pour la phase N ; les étiquettes `01.Cadrage` … `08.…` restent.

## Où vit chaque artefact

| Artefact | Lieu | Versionné |
|---|---|---|
| Code, tests, outils, documents, notebooks exécutés | Git | Oui |
| Résultats chiffrés, registre et alias des modèles | `resultats/` | Oui |
| Preuves d'antériorité | `docs/livraisons/` | Oui |
| Modèles (`.joblib`) et leur carte | `models/` | Non — reconstruits ou republiés (`modele_servi.py`) |
| Listes opérationnelles | `sorties/` | **Jamais** (comptes réels) |
| Suivi des expériences | MLflow (`mlruns/`) | Non — se reconstruit |
