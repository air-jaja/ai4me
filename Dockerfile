# syntax=docker/dockerfile:1
# =============================================================================
#  Dockerfile — service de scoring churn
# -----------------------------------------------------------------------------
#  Construction en deux étapes (multi-stage) :
#    build   : installe les dépendances figées par uv.lock, puis le projet
#    runtime : image finale, mince, sans outil de construction, utilisateur non-root
#
#  Le modèle n'est PAS embarqué dans l'image. Il est monté au démarrage depuis un
#  volume (voir docker-compose.yml). Motif : l'image est du code, le modèle est une
#  donnée versionnée séparément (notebook § 10 — code, données et modèle sont
#  versionnés conjointement mais distinctement). Embarquer le modèle obligerait à
#  reconstruire l'image à chaque réentraînement.
# =============================================================================

# ---- étape build : dépendances figées, puis projet installé en wheel ----
FROM python:3.13-slim AS build

# Version d'uv épinglée : deux constructions du même commit donnent la même image.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Les manifestes d'abord : tant qu'ils ne changent pas, la couche d'installation
# est réutilisée même si le code source a été modifié.
COPY pyproject.toml uv.lock ./

# --frozen : échoue si uv.lock ne correspond pas à pyproject.toml, au lieu de
#            résoudre à nouveau. C'est le garde-fou de reproductibilité.
# --no-dev : ni pytest ni ruff dans l'image de production.
# Groupes retenus pour le service : api, stockage, observabilite.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev \
        --group api --group stockage --group observabilite

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable \
        --group api --group stockage --group observabilite

# ---- étape runtime : image finale ----
FROM python:3.13-slim AS runtime

# Correctifs de sécurité Debian, puis retrait de pip et setuptools : l'environnement
# est déjà construit, ces outils ne servent qu'à élargir la surface d'attaque.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip setuptools

# Utilisateur non privilégié : une compromission du service n'hérite pas de root.
RUN useradd -m -u 10001 appuser

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CHURN_MODEL_PATH=/app/models/churn_model.joblib

COPY --from=build /app/.venv /app/.venv

USER appuser
EXPOSE 8000

# Santé du service : l'orchestrateur distingue « processus démarré » de « prêt à servir ».
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "churn_saas.industrialisation.api:app", "--host", "0.0.0.0", "--port", "8000"]
