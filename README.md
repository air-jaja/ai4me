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
make test               # tests unitaires
make lint               # style du code
make executer-notebook  # rejoue le notebook de bout en bout — contrôle avant remise
```

Les fichiers CSV sources doivent être placés dans `data/raw/`. Ils ne sont pas versionnés dans Git
(voir `docs/README_choix_methodologiques.md` § 3).

---

## Structure du dépôt

```
churn-saas-cisia/
├── pyproject.toml          Dépendances et configuration des outils
├── uv.lock                 Résolution exacte des dépendances — reproductibilité
├── Makefile                Raccourcis de commandes
├── .github/workflows/      Chaîne CI (étapes 1–2 du notebook § 10)
│
├── data/                   raw · interim · processed — non versionnés
├── notebooks/              Livrable principal remis au jury
├── models/                 Modèles sérialisés et fiches — non versionnés
├── reports/figures/        Figures produites
├── docs/                   Documents méthodologiques et de suivi
├── tests/                  Un fichier par activité
│
└── src/churn_saas/         Source de vérité unique du code
    ├── config.py                 Paramètres et hypothèses, centralisés
    ├── notebook.py               Affichage du code source dans le notebook
    │
    ├── donnees/            1. GESTION DES DONNÉES
    │   ├── ingestion.py          bronze — lecture brute, tout en texte
    │   ├── silver.py             silver — nettoyage, typage, jointure catalogue
    │   └── gold.py               gold   — exclusions motivées, séparation de la cible
    │
    ├── features/           2. CONTRÔLE DES FEATURES
    │   ├── construction.py       ratios d'usage
    │   └── controle.py           schéma, détection générique de fuite, leurres
    │
    ├── modelisation/       3. MODÉLISATION
    │   ├── baseline.py           régression logistique et préprocesseur
    │   └── selection.py          candidat, grille bornée, comparaison en CV
    │
    ├── evaluation/         4. ÉVALUATION DE LA PERFORMANCE
    │   ├── metriques.py          métriques et intervalle de confiance
    │   ├── decision.py           priorisation par valeur espérée, sensibilité
    │   └── impact.py             MRR exposé / couvert / préservé
    │
    ├── packaging/          5. PACKAGING DU MODÈLE
    │   ├── artefacts.py          sérialisation, fiche modèle, versioning
    │   ├── model_card.py         génération depuis le gabarit
    │   └── modelcard_template.md gabarit Hugging Face
    │
    ├── industrialisation/  6. SERVICES D'INDUSTRIALISATION
    │   ├── scoring.py            lot mensuel — décide, voit tout le portefeuille
    │   └── service.py            appel unitaire — ne décide pas
    │
    └── monitoring/         7. SERVICES DE MONITORING
        ├── derive.py             PSI, Kolmogorov-Smirnov, rapport
        └── alertes.py            indicateur → seuil → action → responsable
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
| **optimisation** | optuna, codecarbon | C4 | `--group optimisation` |
| **suivi** | mlflow | C5, C6, C9 | `--group suivi` |
| **stockage** | sqlalchemy, psycopg | C3, C7 | `--group stockage` |
| **orchestration** | prefect | C6, C7 | `--group orchestration` |
| **observabilite** | prometheus-client, prometheus-fastapi-instrumentator | C8, C9 | `--group observabilite` |
| **api** | fastapi, uvicorn | C6 | `--group api` |
| **plateforme** | tous les groupes ci-dessus | — | `--group plateforme` |

**Le notebook s'exécute avec les seules dépendances de base.** Aucun groupe de la
plateforme n'est requis pour le rejouer : un correcteur peut le faire tourner sans
installer la stack.

### Décisions révisées

Trois outils écartés au cadrage initial sont finalement retenus. Le revirement est
documenté plutôt que dissimulé — c'est une itération, et le notebook la consigne.

| Outil | Position initiale | Ce qui a changé |
|---|---|---|
| Optuna | Écarté au nom de l'éco-conception | L'argument portait sur l'**étendue** de la recherche, pas sur l'outil. L'échantillonnage TPE avec élagage consomme moins qu'une grille exhaustive à couverture égale. Le budget reste borné à 30 essais. |
| MLflow | Écarté, « surdimensionné pour un notebook » | La convention de nommage ne survit ni à plusieurs réentraînements ni à plusieurs personnes. MLflow outille la convention sans la changer. |
| SHAP, CodeCarbon | Options ouvertes | Retenus : l'un rend le signalement actionnable compte par compte, l'autre transforme un argument déclaratif en mesure. |

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

`uv.lock` fige la version exacte de chacune des 164 dépendances, avec son empreinte cryptographique.
`uv sync --frozen` installe cet état sans le modifier, et échoue si le verrou ne correspond plus au
`pyproject.toml` — c'est ce contrôle qui empêche un dépôt de dériver silencieusement.

**Règle :** toute dépendance ajoutée passe par `uv add`, jamais par une modification manuelle du
verrou.

```bash
uv add nom-du-paquet          # ajoute et met à jour le verrou
uv lock --upgrade-package X   # met à jour une seule dépendance
```
