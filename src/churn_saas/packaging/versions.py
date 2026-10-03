"""Model versioning: increment rule, champion and previous aliases, immediate rollback.

Version X.Y.Z of a model:
- X (major): the input contract changes - variables, target or family. The API and the
  monthly batch must change with it; no rollback across majors.
- Y (minor): predictions change, the contract does not - retraining on new data,
  recalibration, new settings, one calibrated copy instead of five.
- Z (patch): nothing changes in the scores - re-serialisation, metadata. The reference
  scores of the sample file must be identical.

Two aliases, kept in a versioned file (`resultats/aliases_modeles.json`) so they work
without any server: `champion` (in service) and `precedent` (the champion before it).
Rollback swaps them in one command. Retention: the champion, the previous one, the last
three promoted models, and every model in service during the last 13 months are kept.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import MODELES

ALIASES = MODELES.parent / "resultats" / "aliases_modeles.json"
NATURES = {"contrat": 0, "predictions": 1, "technique": 2}
CONSERVATION_JOURS = 396  # 13 months
DERNIERS_CONSERVES = 3


def incrementer(version: str, nature: str) -> str:
    """Next version for a change of the given nature (contrat, predictions, technique)."""
    parties = [int(p) for p in (version.split(".") + ["0", "0"])[:3]]
    rang = NATURES[nature]
    parties[rang] += 1
    parties[rang + 1 :] = [0] * (2 - rang)
    return ".".join(map(str, parties))


def majeure(version: str) -> int:
    return int(version.split(".")[0])


def lire_aliases(chemin: Path = ALIASES) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {"historique": []}


def _ecrire(aliases: dict, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(aliases, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def promouvoir(entree: dict, chemin: Path = ALIASES, changement_de_contrat: bool = False) -> dict:
    """Make a registry entry the champion; the former champion becomes `precedent`.

    Refused across major versions unless the contract change is declared: a model expecting
    other inputs cannot replace the one the API and the batch are built for, silently.
    """
    aliases = lire_aliases(chemin)
    actuel = aliases.get("champion")
    if (
        actuel
        and majeure(entree["version"]) != majeure(actuel["version"])
        and not changement_de_contrat
    ):
        raise ValueError(
            f"Version majeure différente ({actuel['version']} -> {entree['version']}) : "
            "le contrat d'entrée change, déclarer changement_de_contrat=True."
        )
    if actuel and actuel["fichier_sha256"] == entree["fichier_sha256"]:
        return aliases
    aliases["precedent"], aliases["champion"] = actuel, entree
    aliases["historique"].append(
        {
            "date": date.today().isoformat(),
            "action": "promotion",
            "version": entree["version"],
            "fichier": entree["fichier"],
        }
    )
    _ecrire(aliases, chemin)
    return aliases


def retour_arriere(chemin: Path = ALIASES, dossier: Path = MODELES) -> dict:
    """Swap champion and previous - after checking the previous file is there and intact."""
    aliases = lire_aliases(chemin)
    precedent = aliases.get("precedent")
    if not precedent:
        raise ValueError("Aucun modèle précédent : retour arrière impossible.")
    fichier = Path(dossier) / precedent["fichier"]
    if (
        not fichier.exists()
        or hashlib.sha256(fichier.read_bytes()).hexdigest() != precedent["fichier_sha256"]
    ):
        raise ValueError(f"Fichier du modèle précédent absent ou altéré : {fichier.name}")
    if majeure(precedent["version"]) != majeure(aliases["champion"]["version"]):
        raise ValueError("Le modèle précédent n'a pas le même contrat d'entrée.")
    aliases["champion"], aliases["precedent"] = precedent, aliases["champion"]
    aliases["historique"].append(
        {
            "date": date.today().isoformat(),
            "action": "retour arrière",
            "version": precedent["version"],
            "fichier": precedent["fichier"],
        }
    )
    _ecrire(aliases, chemin)
    return aliases


def charger_champion(chemin: Path = ALIASES, dossier: Path = MODELES):
    """The model in service, by alias - its file's hash checked against the registry."""
    from .artefacts import charger_modele

    champion = lire_aliases(chemin).get("champion")
    if not champion:
        raise ValueError("Aucun champion promu.")
    fichier = Path(dossier) / champion["fichier"]
    if hashlib.sha256(fichier.read_bytes()).hexdigest() != champion["fichier_sha256"]:
        raise ValueError(f"Fichier du champion altéré : {fichier.name}")
    return charger_modele(fichier)


def a_conserver(
    registre: list[dict], chemin: Path = ALIASES, aujourd_hui: date | None = None
) -> set[str]:
    """Files to keep: champion, previous, the last 3 promoted, anything in service < 13 months."""
    aliases = lire_aliases(chemin)
    aujourd_hui = aujourd_hui or date.today()
    garder = {a["fichier"] for k in ("champion", "precedent") if (a := aliases.get(k))}
    promus = [h for h in aliases["historique"] if h["action"] == "promotion"]
    garder |= {h["fichier"] for h in promus[-DERNIERS_CONSERVES:]}
    limite = aujourd_hui - timedelta(days=CONSERVATION_JOURS)
    garder |= {
        h["fichier"] for h in aliases["historique"] if date.fromisoformat(h["date"]) >= limite
    }
    return garder & {e["fichier"] for e in registre} | garder
