# Prédiction de résiliation client (churn) — B2B SaaS

Production de certification **CISIA** — « Concevoir et implémenter une solution d'intelligence
artificielle ».

Le projet estime, pour chaque compte client d'un éditeur de logiciel par abonnement, la probabilité
de résiliation à l'échéance contractuelle, et produit une **liste de comptes priorisée** à
destination des équipes Customer Success.

> **Le modèle ne décide pas.** Il classe. La décision appartient aux équipes. Cette limite est un
> choix, documenté au notebook § 4.

---

## Démarrage

```bash
# Installation de l'environnement, à l'identique du verrou
make install            # ou : uv sync --frozen --group dev --group notebook

# Lancer le notebook
make notebook

# Contrôles
make test               # toute la suite de tests
make test-activite      # campagne de l'activité : tests courants + non-régression
make lint               # style du code
make executer-notebook  # rejoue le notebook de bout en bout — contrôle avant remise
make ressources         # mesure CE poste : ressources et temps de calcul (docs/06.SOBRIETE_calcul.md)
make materialiser       # réécrit silver, gold et découpage au manifeste, sans Jupyter (+ run « données » MLflow)
make mlflow             # interface MLflow sur le magasin du projet (mlruns/mlflow.db)
make mlflow-nettoyer    # vide le magasin MLflow local (il se reconstruit : MLflow n'est qu'un journal)
uv run python tools/liste_operationnelle.py   # liste du mois pour les conseillers (sorties/)
uv run python tools/promouvoir.py --etat     # modèle en service ; --retour-arriere pour revenir au précédent
uv run python tools/livraison.py --verifier  # paquet de livraison vérifié (docs/LIVRAISON.md)
```

Les fichiers CSV sources sont versionnés dans `data/raw/` : l'énoncé exige que les jeux de données
soient « intégrés ou clairement référencés et accessibles », et leur volume le permet ici (moins de
2 Mo). Les instantanés d'entraînement et les fichiers dérivés, eux, restent hors dépôt — voir le
cycle de vie des données dans `docs/00.README_choix_methodologiques.md` § 3.

---

## Démarrage sous Windows, et dépannage

Les commandes propres à Windows et le tableau des symptômes connus, avec leur cause et leur
correction, sont dans **[`docs/DEPANNAGE.md`](docs/DEPANNAGE.md)**.

**Règle générale :** toute installation passe par `uv`. Un `pip install` direct sort du
verrou et rend l'environnement non reproductible.

---

## Structure du dépôt

```
churn-saas-cisia/
├── pyproject.toml          Dépendances et configuration des outils
├── uv.lock                 Résolution exacte des dépendances — reproductibilité
├── Makefile                Raccourcis de commandes (`make aide`)
├── Dockerfile              Image du service de scoring
├── docker-compose.yml      API · PostgreSQL · MLflow · Prometheus · Grafana
├── .pre-commit-config.yaml Contrôles au commit, suite de tests au push
├── .github/workflows/      Chaîne CI — tests, linter, hooks, fraîcheur du catalogue
│
├── config/
│   └── ressources_poste.toml     Ressources du poste et hypothèses d'énergie — entrée du projet
│
├── data/
│   ├── raw/                      CSV sources — **versionnés** (2 Mo, référence de tout)
│   ├── processed/                Instantanés Parquet — non versionnés, recalculables
│   ├── interim/                  Travail intermédiaire — non versionné
│   ├── simulation/               Lots de démonstration **simulés** (phase 11) — versionnés
│   └── manifeste_v1.0.json       Empreintes des sources et des instantanés — versionné
│
├── notebooks/              Carnets de phase et livrable remis au jury
├── models/                 Modèles sérialisés et fiches — non versionnés
├── reports/figures/        Figures en PNG et SVG — non versionnées, régénérables
├── monitoring/             Configuration Prometheus et Grafana
├── resultats/
│   └── reference_baseline.json   Résultats de référence des baselines, que la phase 7 doit battre
│
├── tools/                  Outils de dépôt — catalogue, registre, ressources, matérialisation, campagnes,
│                           référence, chaîne MLflow et retraçage
├── docs/                   Documents méthodologiques et de suivi
│                           (commencer par 00.REGLES_DE_TRAVAIL.md ; dépannage : DEPANNAGE.md)
├── tests/                  Tests par activité, plus les contrôles transverses
│
└── src/churn_saas/         Source de vérité unique du code
    ├── config.py                 Paramètres et hypothèses, centralisés
    ├── notebook.py               Affichage du code et des tableaux dans les carnets
    ├── figures.py                Enregistrement des figures, cache données + code
    │
    ├── donnees/            1. GESTION DES DONNÉES
    │   ├── ingestion.py          bronze — lecture brute, tout en texte
    │   ├── silver.py             silver — nettoyage, typage, normalisation, jointure
    │   ├── gold.py               gold   — exclusions motivées, séparation de la cible
    │   ├── schema.py             rôle de chaque colonne, audit de qualité
    │   ├── qualite.py            contrat de données, appliqué à l'entraînement et au lot
    │   ├── reconstruction.py     reconstruction déterministe depuis la ligne elle-même
    │   ├── profilage.py          manquants, doublons, distributions, mécanisme
    │   ├── gouvernance.py        cycle de vie, sensibilité, modes de stockage
    │   └── empreinte.py          empreintes SHA-256, manifeste, contrôle d'intégrité
    │
    ├── features/           2. CONTRÔLE DES FEATURES
    │   ├── construction.py       ratios d'usage, indicateur de compte abandonné
    │   ├── controle.py           schéma, détection générique de fuite, leurres
    │   ├── exploration.py        déséquilibre, corrélations, tendances
    │   ├── graphiques.py         figures du notebook de certification, source unique
    │   ├── selection.py          apport des variables construites, ablation, plancher des leurres
    │   ├── pipeline.py           chaîne bronze → silver → gold, avec journal
    │   └── materialisation.py    écriture des instantanés et de leurs empreintes
    │
    ├── modelisation/       3. MODÉLISATION
    │   ├── baseline.py           régression logistique et préprocesseur
    │   ├── reglage.py            grilles bornées et calibration apprise dans le pli (phase 7)
    │   ├── selection.py          candidat, grille bornée, comparaison en CV
    │   ├── sobriete.py           temps de calcul mesurés, charge déclarée, énergie et CO₂e
    │   ├── validation.py         validation adverse, test de permutation, courbe d'apprentissage
    │   └── valeur_vie.py         valeur client des comptes récents, linéaire contre forêt (B5)
    │
    ├── evaluation/         4. ÉVALUATION DE LA PERFORMANCE
    │   ├── metriques.py          métriques et intervalle de confiance
    │   ├── decision.py           priorisation par valeur espérée, sensibilité
    │   ├── impact.py             MRR exposé / couvert / préservé
    │   ├── valeur_vie.py         la valeur vie client encode-t-elle l'issue ? (diagnostic)
    │   ├── protocole.py          protocole d'évaluation : plis, métriques, calibration (phase 6)
    │   └── explicabilite.py      valeurs de Shapley, motif lisible par un CSM
    │
    ├── packaging/          5. PACKAGING DU MODÈLE
    │   ├── artefacts.py          sérialisation, fiche modèle, versioning
    │   ├── model_card.py         génération depuis le gabarit
    │   ├── modelcard_template.md gabarit Hugging Face
    │   ├── dependances.py        graphe d'imports des outils (identité), descriptif lu sur le modèle
    │   ├── suivi.py              MLflow — expériences et registre de modèles
    │   └── versions.py           version X.Y.Z, alias champion et précédent, retour arrière
    │
    ├── industrialisation/  6. SERVICES D'INDUSTRIALISATION
    │   ├── liste.py              liste opérationnelle : libellés métier, motifs rédigés
    │   ├── scoring.py            lot mensuel — décide, voit tout le portefeuille
    │   ├── service.py            appel unitaire — ne décide pas
    │   ├── api.py                service HTTP FastAPI (/health, /ready, /score), clé d'API
    │   ├── dictionnaire.py       dictionnaire des variables : libellés métier, types, exemples
    │   ├── flux.py               orchestration Prefect du lot mensuel
    │   └── entrepot.py           entrepôt des scores produits (SQLAlchemy)
    │
    └── monitoring/         7. SERVICES DE MONITORING
        ├── derive.py             PSI, Kolmogorov-Smirnov, rapport
        ├── alertes.py            indicateur → seuil → action → responsable
        ├── exporteur.py          exposition des indicateurs à Prometheus
        ├── suivi.py              verdicts mensuels M5, M8, M9 contre le profil de référence
        └── simulation.py         lots de démonstration simulés, dérive injectée (S1 à S7)
```

Le découpage suit les **activités du cycle de vie**, pas les types d'objets. Une activité,
un dossier, un fichier de tests.

---

## Un seul code, un notebook auto-porteur

Le règlement impose un notebook compréhensible sans explication orale ; l'ingénierie
impose un code écrit et testé une seule fois. Recopier les fonctions produirait deux
versions divergentes, dont une seule testée.

Le notebook importe le paquet et **affiche le code au moment où il l'explique** :

```python
from churn_saas.notebook import preparer_import, afficher_source
preparer_import()   # importable même sans `uv sync`, depuis l'archive décompressée

from churn_saas.donnees.silver import nettoyer_decimal_texte
afficher_source(nettoyer_decimal_texte)   # le code s'affiche, coloré
```

Le code affiché est lu dans le module : c'est celui qui s'exécute, et celui que `pytest`
vérifie. `tests/test_notebook.py` garantit cet invariant.

Détail complet et procédure de migration : `docs/ORGANISATION_CODE.md`.

---

## Dépendances

| Groupe | Contenu | Compétence | Installation |
|---|---|---|---|
| **base** | pandas, numpy, scikit-learn, joblib, scipy, matplotlib, seaborn, pyarrow | C3–C5 | `uv sync` |
| **dev** | pytest, ruff, pre-commit | C6 | inclus par défaut |
| **notebook** | jupyterlab, ipykernel, nbconvert, jinja2 | — | `--group notebook` |
| **explicabilite** | shap | C4, C5 | `--group explicabilite` |
| **suivi** | mlflow | C5, C6, C9 | `--group suivi` |
| **boosting** | xgboost-cpu (sans les bibliothèques CUDA) | C5 | `--group boosting` |
| **stockage** | sqlalchemy, psycopg | C3, C7 | `--group stockage` |
| **orchestration** | prefect | C6, C7 | `--group orchestration` |
| **observabilite** | prometheus-client, prometheus-fastapi-instrumentator | C8, C9 | `--group observabilite` |
| **api** | fastapi, uvicorn | C6 | `--group api` |
| **plateforme** | tous les groupes ci-dessus | — | `--group plateforme` |

**Le notebook s'exécute avec les seules dépendances de base.** Aucun groupe de la
plateforme n'est requis pour le rejouer : un correcteur peut le faire tourner sans
installer la stack.

### Décisions révisées

Trois outils écartés au cadrage initial avaient été retenus le 26/09 ; les arbitrages du
01/10, pris avant tout résultat de modélisation, en ont révisé deux à nouveau et différé un.
Les revirements sont documentés plutôt que dissimulés — c'est une itération, consignée au
registre et dans `docs/00.README_choix_methodologiques.md` § 7 bis.

| Outil | 26/09 | 01/10 — décision et motif |
|---|---|---|
| Optuna | Retenu (TPE + élagage, 30 essais) | **Écarté.** L'espace compte 44 combinaisons : `GridSearchCV` est exhaustif en quelques minutes et donne les courbes de validation. Le module et le groupe de dépendances sont retirés le 02/10 |
| CodeCarbon | Retenu | **Écarté, chiffres à l'appui.** Les temps de calcul sont mesurés sur le poste de développement (`make ressources`) et convertis en énergie et en CO₂e : quelques minutes et quelques grammes pour toute la phase 5, une mesure qui ne changerait aucune décision. Chiffrage : `docs/06.SOBRIETE_calcul.md` |
| MLflow | Retenu | **Différé** à la phase 10, pour tracer le modèle final |
| SHAP | Retenu | **À arbitrer** après le choix du modèle : une régression logistique s'explique sans lui |

**Toujours écartés**, et défendables comme tels :

| Écarté | Motif |
|---|---|
| TensorFlow, OpenCV, YOLO | Aucune image ni donnée non structurée dans ce cas d'usage |
| XGBoost | Une troisième famille n'apporte rien tant que les deux premières ne sont pas départagées |
| DVC | Un seul instantané de données dans cet exercice ; le versioning est décrit au § 3 |
| imbalanced-learn (SMOTE) | Fabrique des observations inexistantes sur des variables catégorielles nombreuses |

---

## Plateforme locale

```bash
cp .env.example .env     # renseigner POSTGRES_PASSWORD
make up                  # api, db, mlflow, prometheus, grafana
make smoke               # vérifie /ready — modèle chargé, pas seulement processus vivant
```

| Service | Image épinglée | Rôle | Accès |
|---|---|---|---|
| `api` | construite localement | Scoring unitaire | http://localhost:8000/docs |
| `db` | `postgres:16` | Entrepôt des scores | `localhost:5432` |
| `mlflow` | `ghcr.io/mlflow/mlflow:v3.1.1` | Suivi et registre de modèles | http://localhost:5000 |
| `prometheus` | `prom/prometheus:v2.53.0` | Collecte des indicateurs | http://localhost:9090 |
| `grafana` | `grafana/grafana:11.1.0` | Restitution | http://localhost:3000 |

Aucune image en `latest` : deux constructions du même commit doivent produire le même
résultat. Le modèle n'est pas embarqué dans l'image mais monté depuis un volume — l'image
est du code, le modèle est une donnée versionnée séparément.

---

## Reproductibilité

`uv.lock` fige la version exacte de chacune des 265 dépendances résolues, avec son empreinte
cryptographique.
`uv sync --frozen` installe cet état sans le modifier, et échoue si le verrou ne correspond plus au
`pyproject.toml` — c'est ce contrôle qui empêche un dépôt de dériver silencieusement.

**Règle :** toute dépendance ajoutée passe par `uv add`, jamais par une modification manuelle du
verrou.

```bash
uv add nom-du-paquet          # ajoute et met à jour le verrou
uv lock --upgrade-package X   # met à jour une seule dépendance
```

## Licence

Code et modèle sous licence MIT (`LICENSE`), comme indiqué dans la model card (`docs/MODEL_CARD.md`).
Les jeux de données fournis pour la certification n'en relèvent pas.
