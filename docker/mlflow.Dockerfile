# Image MLflow complétée du pilote PostgreSQL.
#
# L'image officielle ne contient aucun pilote de base de données : `mlflow server
# --backend-store-uri postgresql+psycopg://...` y échoue sur `ModuleNotFoundError:
# No module named 'psycopg'`. MLflow déclare des extras pour cela, mais l'image publiée
# ne les installe pas — c'est à l'utilisateur de le faire.
#
# Trois lignes suffisent, et cette couche se construit en quelques secondes.

FROM ghcr.io/mlflow/mlflow:v3.1.1

# Version épinglée, et identique à celle du verrou du projet : le service et le code
# parlent ainsi à PostgreSQL par le même pilote. Une version flottante ici produirait
# deux comportements possibles pour une même base.
RUN pip install --no-cache-dir "psycopg[binary]==3.3.6"
