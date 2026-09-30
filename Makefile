# =============================================================================
# Makefile — commandes du projet churn SaaS (certification CISIA)
# -----------------------------------------------------------------------------
# ATTENTION : chaque ligne de recette DOIT commencer par une TABULATION.
# `make aide` liste les cibles.
# =============================================================================

.PHONY: aide install install-plateforme kernel test test-doc lint format check notebook executer-notebook \
        serve docker-build up down logs ps smoke mlflow lot-mensuel exporteur clean

aide:
	@echo "--- Développement ---"
	@echo "  install             Environnement minimal (base + dev + notebook)"
	@echo "  install-plateforme  Ajoute MLflow, Optuna, SHAP, SQLAlchemy, Prefect, Prometheus"
	@echo "  kernel              Enregistre le noyau Jupyter du projet (VS Code, Jupyter)"
	@echo "  test                Suite de tests"
	@echo "  test-doc            Régénère docs/TESTS.md depuis les fichiers de tests"
	@echo "  lint                Style du code"
	@echo "  format              Reformate le code"
	@echo "  check               test + lint + format --check"
	@echo "--- Notebook ---"
	@echo "  notebook            Lance JupyterLab"
	@echo "  executer-notebook   Rejoue le notebook de bout en bout (contrôle avant remise)"
	@echo "--- Plateforme ---"
	@echo "  serve               API en local, rechargement auto"
	@echo "  up / down / logs    Stack Docker complète"
	@echo "  smoke               Vérifie que l'API répond"
	@echo "  mlflow              Interface MLflow en local"
	@echo "  lot-mensuel         Exécute le flux Prefect de scoring"
	@echo "  exporteur           Démarre l'exporteur Prometheus du lot"

# --- Développement -----------------------------------------------------------
install:
	uv sync --frozen --group dev --group notebook

install-plateforme:
	uv sync --frozen --group dev --group notebook --group plateforme

# Registers the project venv as a selectable Jupyter kernel. Without it, editors
# fall back to the shared interpreter, which has no ipykernel and no project deps.
kernel:
	uv run python -m ipykernel install --user --name churn-saas-cisia \
		--display-name "Python (churn-saas-cisia)"

test:
	uv run pytest -q

# The catalogue is generated, never hand-written: a stale inventory claims coverage
# that no longer exists.
test-doc:
	uv run python tools/catalogue_tests.py > docs/TESTS.md

lint:
	uv run ruff check .

format:
	uv run ruff format src tests

check:
	uv run pytest -q
	uv run ruff check .
	uv run ruff format --check src tests

# --- Notebook ----------------------------------------------------------------
notebook:
	uv run jupyter lab

# Rejoue le notebook sur les données réelles, kernel neuf. Contrôle exigé avant remise :
# il doit se terminer sans erreur.
executer-notebook:
	uv run jupyter nbconvert --to notebook --execute \
		--ExecutePreprocessor.timeout=1800 \
		--output cas_usage_churn_saas_execute.ipynb \
		notebooks/cas_usage_churn_saas.ipynb

# --- Plateforme --------------------------------------------------------------
serve:
	uv run uvicorn churn_saas.industrialisation.api:app --reload

docker-build:
	docker build -t churn-saas-api:local .

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# /ready et non /health : on veut savoir si le modèle est chargé, pas seulement
# si le processus répond.
smoke:
	curl -fsS http://localhost:8000/ready && echo " OK"

mlflow:
	uv run mlflow ui --port 5000

lot-mensuel:
	uv run python -m churn_saas.industrialisation.flux

exporteur:
	uv run python -c "from churn_saas.monitoring.exporteur import demarrer_exporteur; import time; demarrer_exporteur(9109); print('exporteur sur :9109'); time.sleep(3600)"

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
