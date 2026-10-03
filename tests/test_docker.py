"""The local platform's configuration (docker-compose.yml, .env.example, Dockerfiles).

Docker is not needed for most of these checks: they read the files and catch what breaks
a `docker compose up` silently - a malformed interpolation, a variable the example file
does not declare, a container port that follows a host-side variable, an internal URL
pointing at the wrong port, a mounted file that does not exist. When Docker is installed,
`docker compose config` validates the whole file as Docker itself reads it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.phase7

RACINE = Path(__file__).resolve().parents[1]
COMPOSE = RACINE / "docker-compose.yml"
EXEMPLE = RACINE / ".env.example"
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:?-[^}]*)?\}")


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _exemple() -> dict[str, str]:
    lignes = [ligne.strip() for ligne in EXEMPLE.read_text(encoding="utf-8").splitlines()]
    return dict(
        ligne.split("=", 1)
        for ligne in lignes
        if ligne and not ligne.startswith("#") and "=" in ligne
    )


def test_le_docker_compose_se_lit_et_declare_ses_cinq_services():
    services = _compose()["services"]
    assert set(services) == {"api", "db", "mlflow", "prometheus", "grafana"}


def test_aucune_interpolation_mal_formee():
    """A `$` not followed by `{NAME}` or `$` makes Docker refuse the file
    ("invalid interpolation format"); `$:` once slipped into the MLflow URL."""
    texte = "\n".join(
        ligne
        for ligne in COMPOSE.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )
    fautifs = [
        m.group(0) for m in re.finditer(r"\$(?!\{[A-Za-z_][A-Za-z0-9_]*(:?-[^}]*)?\}|\$)", texte)
    ]
    assert not fautifs, f"Interpolations mal formées : {fautifs}"


def test_chaque_variable_sans_defaut_est_declaree_dans_l_exemple():
    """Without a default, a variable missing from .env becomes an empty string - an empty
    password or port, discovered at start-up."""
    declarees = set(_exemple())
    sans_defaut = {
        m.group(1) for m in VARIABLE.finditer(COMPOSE.read_text(encoding="utf-8")) if not m.group(2)
    }
    assert not sans_defaut - declarees, f"Absentes de .env.example : {sans_defaut - declarees}"


def test_l_exemple_d_environnement_n_a_que_des_lignes_cle_valeur():
    """`CLE: valeur` is YAML, not the env-file format: the line is silently ignored."""
    lignes = [ligne.strip() for ligne in EXEMPLE.read_text(encoding="utf-8").splitlines()]
    fautives = [
        ligne
        for ligne in lignes
        if ligne
        and not ligne.startswith("#")
        and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", ligne)
    ]
    assert not fautives, f"Lignes mal formées dans .env.example : {fautives}"


def test_les_ports_internes_ne_suivent_pas_les_variables_du_poste():
    """`HOTE:CONTENEUR` - only the host side may be configurable. A server listens on a
    fixed port inside its container (Prometheus 9090, Grafana 3000): a variable on the
    container side breaks the service as soon as someone changes the host port."""
    fautifs = []
    for nom, service in _compose()["services"].items():
        for publication in service.get("ports", []):
            conteneur = str(publication).rsplit(":", 1)[-1]
            if "$" in conteneur:
                fautifs.append(f"{nom}: {publication}")
    assert not fautifs, f"Port côté conteneur variable : {fautifs}"


def test_l_api_joint_mlflow_sur_le_port_ou_il_ecoute():
    services = _compose()["services"]
    url = services["api"]["environment"]["MLFLOW_TRACKING_URI"]
    port_api = url.rsplit(":", 1)[-1].strip("/")
    commande = " ".join(services["mlflow"]["command"].split())
    port_serveur = re.search(r"--port (\S+)", commande).group(1)
    assert port_api == port_serveur, (
        f"L'API vise mlflow:{port_api}, le serveur écoute sur {port_serveur}"
    )


def test_les_fichiers_montes_et_construits_existent():
    manquants = []
    for nom, service in _compose()["services"].items():
        for volume in service.get("volumes", []):
            source = str(volume).split(":", 1)[0]
            if source.startswith("./") and not (RACINE / source).exists():
                manquants.append(f"{nom}: {source}")
        construction = service.get("build")
        if isinstance(construction, dict):
            fichier = construction.get("dockerfile", "Dockerfile")
            if not (RACINE / construction.get("context", ".") / fichier).exists():
                manquants.append(f"{nom}: {fichier}")
        elif construction and not (RACINE / construction / "Dockerfile").exists():
            manquants.append(f"{nom}: Dockerfile")
    assert not manquants, f"Fichiers absents : {manquants}"


def test_chaque_image_est_epinglee():
    flottantes = [
        f"{n}: {s['image']}"
        for n, s in _compose()["services"].items()
        if "image" in s and (":" not in s["image"] or s["image"].endswith(":latest"))
    ]
    assert not flottantes, f"Images non épinglées : {flottantes}"


@pytest.mark.xfail(
    strict=True,
    reason="Écart connu (registre D-06) : image du serveur MLflow à "
    "aligner sur le client du verrou, en phase 10.",
)
def test_le_serveur_mlflow_a_la_version_du_client():
    """The server and the client must speak the same MLflow version: a 3.16 client writing
    to a 3.1 server can fail on objects the server does not know (logged models)."""
    image = re.search(
        r"FROM ghcr\.io/mlflow/mlflow:v?([\d.]+)",
        (RACINE / "docker" / "mlflow.Dockerfile").read_text(encoding="utf-8"),
    ).group(1)
    verrou = (RACINE / "uv.lock").read_text(encoding="utf-8")
    client = re.search(r'name = "mlflow"\nversion = "([\d.]+)"', verrou).group(1)
    assert image == client


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker absent de ce poste")
def test_docker_compose_valide_le_fichier(tmp_path):
    """Docker's own reading of the file, with the example environment."""
    sortie = subprocess.run(
        ["docker", "compose", "--env-file", str(EXEMPLE), "-f", str(COMPOSE), "config", "--quiet"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=RACINE,
        timeout=60,
    )
    assert sortie.returncode == 0, sortie.stderr[-800:]
