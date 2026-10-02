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
| `Failed to build churn-saas-cisia` puis `Readme file does not exist` à la construction de l'image | Le Dockerfile ne copiait pas `README.md`, que `pyproject.toml` déclare via `readme` et que hatchling lit pour construire les métadonnées de la roue | Corrigé : `COPY README.md ./` précède désormais le `uv sync --no-editable` |
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

**Règle générale :** toute installation passe par `uv`. Un `pip install` direct sort du
verrou et rend l'environnement non reproductible — ce qui contredit un critère
d'acceptation bloquant du projet.
