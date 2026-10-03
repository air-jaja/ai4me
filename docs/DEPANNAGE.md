# Démarrage sous Windows, et dépannage

> Déplacé depuis le `README.md` le 01/10/2026, pour que le README reste une porte d'entrée courte.
> Toute nouvelle difficulté rencontrée, avec sa cause et sa correction, s'ajoute au tableau ci-dessous.

## Démarrage sous Windows

```powershell
uv sync --frozen --group dev --group notebook
uv run python -m ipykernel install --user --name churn-saas-cisia --display-name "Python (churn-saas-cisia)"
```

Puis dans VS Code : **Ctrl+Shift+P** → `Python: Select Interpreter` → `.\.venv\Scripts\python.exe`,
et sélectionner le même noyau en haut à droite du notebook.

## Symptômes connus

| Symptôme | Cause | Correction |
|---|---|---|
| `Failed to build churn-saas-cisia` puis `Readme file does not exist` à la construction de l'image | `pyproject.toml` déclare `readme = "README.md"` et hatchling exige ce fichier pour construire la roue | Corrigé : le Dockerfile crée lui-même un README minimal, sans dépendre du contexte de construction |
| `failed to compute cache key: "/README.md": not found` | Le fichier est absent du **contexte** de construction — supprimé du répertoire, ou exclu par un `.dockerignore` créé localement | Plus d'objet : le Dockerfile ne le copie plus. Vérifier tout de même `Test-Path README.md` et `Get-Content .dockerignore`, un README manquant signalant un répertoire de travail abîmé |
| `service "db" has no container to start` | `docker compose start` ne crée aucun conteneur : il relance ceux qui existent déjà | Au premier lancement, `docker compose up -d --build`, ou `make up` |
| `The "POSTGRES_PASSWORD" variable is not set` | Le fichier `.env` n'a pas été créé à partir du modèle | `Copy-Item .env.example .env`, puis renseigner les mots de passe |
| *« requires the ipykernel package »* avec un chemin vers `AppData\Roaming\uv\python\...` | L'éditeur pointe sur l'interpréteur uv partagé, pas sur `.venv` | Lancer les deux commandes ci-dessus, puis sélectionner `.venv`. **Ne pas** accepter le `pip install` proposé par l'éditeur : il installerait hors du verrou |
| `.venv` absent de la liste des interpréteurs | L'environnement a été créé après l'ouverture du dossier | Recharger la fenêtre (`Developer: Reload Window`) |
| `make` : commande introuvable | `make` n'existe pas nativement sous Windows | Utiliser les commandes `uv run` directement, ou Git Bash |
| `uv sync` échoue à la construction du projet | Le paquet local ne se construit pas dans l'environnement | Ajouter `--no-install-project` : `preparer_import()` ajoute `src/` au chemin, le notebook fonctionne quand même |
| `ModuleNotFoundError: churn_saas` dans le notebook | La cellule d'amorçage n'a pas été exécutée | Exécuter la première cellule, qui appelle `preparer_import()` |
| `PermissionError [WinError 5]` sur `%TEMP%\pytest-of-<utilisateur>` | Ce dossier, que pytest réutilise d'une exécution à l'autre, est devenu illisible — souvent après une exécution interrompue ou lancée avec d'autres privilèges | Le supprimer : `Remove-Item -Recurse -Force "$env:TEMP\pytest-of-$env:USERNAME"`. La suite bascule sinon d'elle-même sur `~\.pytest-temp`, avec un avertissement |
| `PermissionError [WinError 5]` sur `.pytest-tmp` | `--basetemp` pointe **dans** le dépôt, et pytest **efface** ce répertoire au démarrage | Retirer l'option : le repli automatique rend le contournement inutile |
| Le pre-commit est vert mais les tests échouent | Les hooks de commit ne lancent pas les tests — ils tournent au **push** | Normal. Lancer `make test` avant de committer |
| `ExecutableNotFoundError: Executable /bin/sh not found` au commit | Un hook préexistant a été conservé sous `.git/hooks/<type>.legacy` ; son en-tête `#!/bin/sh` n'existe pas sous Windows | `Remove-Item .git\hooks\*.legacy` puis `uv run pre-commit install --overwrite` *(et `--hook-type pre-push --overwrite`)*. `make hooks` emploie désormais cette option |
| `RuntimeWarning: Proactor event loop does not implement add_reader…` (zmq) au lancement d'un carnet | Sous Windows, la boucle d'événements de Python n'offre pas tout ce qu'attend la communication de Jupyter ; tornado ajoute un fil de contournement | Aucune action : avertissement attendu sous Windows, sans effet sur les calculs |
| `Kernel is running over TCP without encryption` | Le noyau Jupyter communique en local, sans chiffrement | Aucune action en local |
| Trace `KeyError … joblib_memmapping_folder_…` (joblib, `resource_tracker`) en fin d'exécution | Sous Windows, le nettoyage des fichiers temporaires partagés entre processus tente de supprimer un dossier déjà supprimé ; déclenché par deux couches de calcul parallèle imbriquées | Corrigé au bloc 7.0 bis (une seule couche parallèle, `config.N_JOBS`). Sans effet sur les résultats ; les dossiers orphelins de `%TEMP%` peuvent être supprimés |
| Un dossier `notebooks/mlruns/` est apparu | Avant le bloc 7.0 bis, les artefacts MLflow suivaient le dossier courant | `make mlflow-nettoyer` (ou `uv run python tools/nettoyer_mlflow.py --confirmer`), puis relancer `materialiser.py`, `retracer_mlflow.py` et `pipeline_mlflow.py` |
| `test_le_notebook_de_certification_est_execute_en_entier_sans_erreur` échoue | Le notebook versionné porte des sorties qui ne viennent pas d'une exécution complète, dans l'ordre : cellules relancées à la main, exécution interrompue, cellule en erreur, ou un chemin du poste affiché | `make executer-notebook` (sans make : `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/cas_usage_churn_saas.ipynb`), puis committer le notebook. Pour un chemin du poste : afficher un chemin relatif à la racine |
| `RuntimeError: main thread is not in main loop` et `Tcl_AsyncDelete` à la fin de `pipeline_mlflow.py` (Windows) | matplotlib choisissait le moteur graphique Tk dans un script ; les figures dessinées par l'autolog de MLflow étaient détruites par un autre fil à la sortie | Corrigé : le script impose le moteur `Agg` (aucune fenêtre), et la matrice de confusion n'utilise plus pyplot. Les résultats n'étaient pas affectés |
| `RuntimeError: can't start new thread` pendant la grille de `pipeline_mlflow.py` (Windows) | L'autolog restait actif pendant les 25 entraînements de l'évaluation par le protocole, et la grille faisait tourner des forêts elles-mêmes parallèles : les fils d'exécution s'accumulaient jusqu'à la limite du processus | Corrigé : autolog limité à l'entraînement tracé, une seule couche parallèle (`config.N_JOBS`). Mesuré après correction : 20 fils au plus pour la chaîne complète |
| `MemoryError` puis `BrokenProcessPool: A task has failed to un-serialize` pendant la grille (Windows) | La recherche par grille répartissait les combinaisons sur des **processus** de calcul, à qui chaque tâche est envoyée sérialisée ; sous l'autolog de MLflow, un processus n'a pas pu la relire | Corrigé : plus aucun processus de calcul. Les combinaisons sont évaluées l'une après l'autre, et le parallélisme est **dans le modèle, par fils d'exécution** (`config.N_JOBS`), qui partagent la mémoire. Mesuré : 0 processus enfant, 10 fils au plus ; résultats identiques |

**Règle générale :** toute installation passe par `uv`. Un `pip install` direct sort du
verrou et rend l'environnement non reproductible — ce qui contredit un critère
d'acceptation bloquant du projet.
