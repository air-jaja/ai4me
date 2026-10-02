"""Measure the machine that runs the project, and render what its compute costs.

Two modes, kept apart on purpose:

    uv run python tools/ressources_calcul.py --mesurer   # on the development laptop
    uv run python tools/ressources_calcul.py             # render, anywhere (CI included)

`--mesurer` describes the machine (processor, cores, memory, system) and times the
project's own operations on the real data, then writes both into the project input
`config/ressources_poste.toml`. The hypotheses section of that file - power, carbon
intensity, number of runs - is left untouched: it is declared by a person, not measured.

Rendering reads that file only and writes `docs/06.SOBRIETE_calcul.md`. It is a pure
function of the input, so the CI can check the document is up to date without re-running a
benchmark that would measure the CI machine instead of the laptop.

Written in UTF-8 by the script itself, as `catalogue_tests.py` explains.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import os
import platform
import subprocess
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ENTREE = RACINE / "config" / "ressources_poste.toml"
DESTINATION_PAR_DEFAUT = RACINE / "docs" / "06.SOBRIETE_calcul.md"
ORIGINE_POSTE = "poste de développement"


# --- Describing the machine ------------------------------------------------------------
def _processeur() -> str:
    """Commercial name of the processor, from the system's own source."""
    systeme = platform.system()
    try:
        if systeme == "Windows":
            import winreg

            cle = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            return str(winreg.QueryValueEx(cle, "ProcessorNameString")[0]).strip()
        if systeme == "Linux":
            for ligne in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if ligne.startswith("model name"):
                    return ligne.split(":", 1)[1].strip()
        if systeme == "Darwin":
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return platform.processor() or "inconnu"


def _memoire_go() -> float:
    """Installed memory, in GB."""
    systeme = platform.system()
    try:
        if systeme == "Windows":

            class Etat(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            etat = Etat()
            etat.dwLength = ctypes.sizeof(Etat)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(etat)):
                return 0.0
            return round(etat.ullTotalPhys / 1e9, 1)
        if systeme == "Linux":
            for ligne in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if ligne.startswith("MemTotal"):
                    return round(int(ligne.split()[1]) * 1024 / 1e9, 1)
        if systeme == "Darwin":
            octets = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
            ).stdout
            return round(int(octets) / 1e9, 1)
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        pass
    return 0.0


def memoire_pic_processus_mo() -> float:
    """Peak memory of this process so far, in MB: what the computation really occupied.

    Read from the system, compiled code included - which Python's own allocation tracing
    would miss, the forest's trees living outside it.
    """
    try:
        if platform.system() == "Windows":

            class Compteurs(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            # Handles are pointer-sized on 64-bit Windows: declare the signatures, or ctypes
            # truncates the process handle to 32 bits and the call silently fails.
            noyau, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            noyau.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(Compteurs),
                ctypes.c_ulong,
            ]
            compteurs = Compteurs()
            compteurs.cb = ctypes.sizeof(Compteurs)
            if not psapi.GetProcessMemoryInfo(
                noyau.GetCurrentProcess(), ctypes.byref(compteurs), compteurs.cb
            ):
                return 0.0
            return round(compteurs.PeakWorkingSetSize / 1e6, 1)
        import resource

        pic = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Kilobytes on Linux, bytes on macOS.
        return round(pic / 1e6 if platform.system() == "Darwin" else pic / 1e3, 1)
    except (OSError, AttributeError, ImportError):
        return 0.0


def collecter_poste() -> dict[str, object]:
    """What the machine is, as far as the standard library can tell."""
    import sklearn

    return {
        "systeme": f"{platform.system()} {platform.release()}",
        "processeur": _processeur(),
        "coeurs_logiques": os.cpu_count() or 0,
        "memoire_go": _memoire_go(),
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
    }


# --- Reading and writing the project input ----------------------------------------------
def charger_entree(chemin: Path = ENTREE) -> dict:
    with open(chemin, "rb") as flux:
        return tomllib.load(flux)


def _valeur(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4) if isinstance(v, float) else v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def ecrire_entree(contenu: dict, chemin: Path = ENTREE) -> None:
    """Write the input file, sections in a fixed order, comments kept as a header."""
    lignes = [
        "# Ressources du poste qui exécute le projet — ENTRÉE DU PROJET.",
        "#",
        "# [poste] et [mesures] sont écrits par `make ressources` (tools/ressources_calcul.py",
        "# --mesurer), lancé sur le poste de développement. Ne pas les éditer à la main.",
        "# [hypotheses] est déclaré par une personne : à ajuster, en citant la source.",
        "# Le document docs/06.SOBRIETE_calcul.md est généré à partir de ce fichier.",
        "",
    ]
    for section in ("source", "poste", "mesures", "hypotheses"):
        lignes.append(f"[{section}]")
        for cle, v in contenu.get(section, {}).items():
            lignes.append(f"{cle} = {_valeur(v)}")
        lignes.append("")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes).rstrip() + "\n", encoding="utf-8", newline="\n")


def mesurer(origine: str = ORIGINE_POSTE) -> dict:
    """Describe the machine, time the project's operations, keep the declared hypotheses."""
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.config import FICHIER_CATALOGUE, FICHIER_COMPLET
    from churn_saas.features import executer_pipeline
    from churn_saas.modelisation import mesurer_temps

    resultat = executer_pipeline(FICHIER_COMPLET, FICHIER_CATALOGUE)
    temps = mesurer_temps(resultat.X, resultat.y.astype(int))
    temps["memoire_pic_processus_mo"] = memoire_pic_processus_mo()
    actuel = charger_entree() if ENTREE.exists() else {}
    return {
        "source": {"origine": origine, "date": dt.date.today().isoformat()},
        "poste": collecter_poste(),
        "mesures": {k: round(v, 4) for k, v in temps.items()},
        "hypotheses": actuel.get("hypotheses", {}),
    }


# --- Rendering ---------------------------------------------------------------------------
def _fr(valeur: object, decimales: int = 1) -> str:
    """French number formatting: decimal comma, narrow space for thousands."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return str(valeur)
    texte = f"{valeur:,.{decimales}f}" if isinstance(valeur, float) else f"{valeur:,}"
    return texte.replace(",", "\u202f").replace(".", ",")


def _tableau(df, decimales: int = 1) -> list[str]:
    entetes = [str(c)[0].upper() + str(c)[1:] for c in df.columns]
    lignes = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    for _, rangee in df.iterrows():
        lignes.append("| " + " | ".join(_fr(rangee[c], decimales) for c in df.columns) + " |")
    return lignes


AVERTISSEMENT = [
    "> **Document généré — ne pas éditer.** Source : `config/ressources_poste.toml`,",
    "> entrée du projet. Mesurer le poste : `make ressources` ; régénérer :",
    "> `make sobriete-doc`. La CI vérifie qu'il est à jour. Arbitrage et motifs :",
    "> `00.README_choix_methodologiques.md` § 7 bis ; registre E-502.",
]

LECTURE = [
    "## Lecture",
    "",
    "Aucun arbitrage du projet — grille ou recherche bayésienne, forêt ou régression — ne se",
    "joue à l'échelle de ces chiffres. C'est ce qui a fait écarter CodeCarbon : la mesure ne",
    "changerait aucune décision, et sans accès aux compteurs d'énergie du processeur elle",
    "reviendrait à ce même calcul. Elle redeviendrait pertinente si le volume changeait",
    "d'ordre de grandeur (registre, E-502).",
]


def _section_poste(source: dict, poste: dict) -> list[str]:
    return [
        "## Le poste",
        "",
        "| Caractéristique | Valeur |",
        "|---|---|",
        f"| Origine des mesures | {source.get('origine')} — {source.get('date')} |",
        f"| Système | {poste['systeme']} |",
        f"| Processeur | {poste['processeur']} |",
        f"| Cœurs logiques | {poste['coeurs_logiques']} |",
        f"| Mémoire installée | {_fr(poste['memoire_go'])} Go |",
        f"| Python · scikit-learn | {poste['python']} · {poste['scikit_learn']} |",
    ]


def _section_temps(m: dict) -> list[str]:
    operations = [
        ("Entraînement, régression logistique", m["entrainement_lr_s"], 3, "s"),
        ("Entraînement, forêt aléatoire (300 arbres)", m["entrainement_foret_s"], 3, "s"),
        ("Importance par permutation, régression (10 répétitions)", m["importance_lr_s"], 2, "s"),
        ("Importance par permutation, forêt (10 répétitions)", m["importance_foret_s"], 2, "s"),
        ("Scoring du portefeuille (5 000 comptes)", m["scoring_portefeuille_s"], 3, "s"),
        ("Pic de mémoire du processus", m["memoire_pic_processus_mo"], 0, "Mo"),
    ]
    return [
        "## Temps élémentaires mesurés",
        "",
        f"Sur un pli de {int(m['lignes_entrainement'])} comptes, avec la configuration du",
        "projet (la forêt utilise tous les cœurs), médiane de trois exécutions.",
        "",
        "| Opération | Mesure |",
        "|---|---|",
        *[f"| {nom} | {_fr(v, d)} {unite} |" for nom, v, d, unite in operations],
    ]


def _hypotheses(h: dict) -> list[str]:
    basse, haute = _fr(h["puissance_basse_w"]), _fr(h["puissance_haute_w"])
    return [
        "**Hypothèses déclarées** (section `[hypotheses]` de l'entrée) :",
        "",
        f"- puissance basse {basse} W, haute {haute} W — {h['source_puissance']} ;",
        f"- intensité carbone {_fr(h['intensite_carbone_g_kwh'])} g CO₂e/kWh"
        f" — {h['source_intensite']} ;",
        f"- {h['executions_developpement']} exécutions complètes pendant le développement.",
    ]


def _empreinte_annuelle(secondes: float, puissances: dict, intensite: float):
    import pandas as pd

    from churn_saas.modelisation import convertir_empreinte

    lignes = []
    for libelle, puissance in puissances.items():
        valeurs = convertir_empreinte(secondes, puissance, intensite)
        lignes.append(
            {
                "hypothèse": libelle,
                "puissance (W)": puissance,
                "énergie par an (Wh)": round(valeurs["énergie (Wh)"], 3),
                "CO₂e par an (g)": round(valeurs["émissions (g CO₂e)"], 3),
            }
        )
    return pd.DataFrame(lignes)


def rendre_markdown(contenu: dict | None = None) -> str:
    """The readable footprint document: a pure function of the input file."""
    sys.path.insert(0, str(RACINE / "src"))
    from churn_saas.modelisation import (
        CHARGE_PHASE5,
        CHARGE_PRODUCTION_ANNUELLE,
        estimer_charge,
        table_empreinte,
    )

    contenu = charger_entree() if contenu is None else contenu
    source, poste, m, h = (contenu[k] for k in ("source", "poste", "mesures", "hypotheses"))
    puissances = {"basse": h["puissance_basse_w"], "haute": h["puissance_haute_w"]}
    intensite = h["intensite_carbone_g_kwh"]
    phase5 = estimer_charge(m, CHARGE_PHASE5)
    production = estimer_charge(m, CHARGE_PRODUCTION_ANNUELLE)
    total5, total_prod = float(phase5["secondes"].sum()), float(production["secondes"].sum())
    executions = int(h["executions_developpement"])

    sortie = [
        "# Sobriété du calcul — ressources du poste et empreinte chiffrée",
        "",
        *AVERTISSEMENT,
    ]
    if source.get("origine") != ORIGINE_POSTE:
        sortie += [
            "",
            "> ⚠ **Mesures provisoires**, prises dans l'environnement",
            f"> « {source.get('origine')} », et non sur le poste de développement.",
            "> Lancer `make ressources` sur le poste pour les remplacer.",
        ]
    total = f"**{_fr(total5, 0)} s ≈ {_fr(total5 / 60)} min**"
    sortie += [
        "",
        *_section_poste(source, poste),
        "",
        *_section_temps(m),
        "",
        "## Charge de calcul de la phase 5",
        "",
        *_tableau(phase5),
        f"| **Total** | {int(phase5['entraînements'].sum())} | {total} |",
        "",
        "## Empreinte",
        "",
        "Énergie = durée × puissance ; émissions = énergie × intensité carbone de l'électricité.",
        "",
        *_hypotheses(h),
        "",
        "### Phase 5 (développement)",
        "",
        *_tableau(table_empreinte(total5, puissances, intensite, executions), decimales=2),
        "",
        "### Production, sur un an",
        "",
        *_tableau(production),
        "",
        *_tableau(_empreinte_annuelle(total_prod, puissances, intensite), decimales=3),
        "",
        *LECTURE,
    ]
    return "\n".join(sortie) + "\n"


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Ressources du poste et empreinte du calcul.")
    analyseur.add_argument(
        "--mesurer",
        action="store_true",
        help="mesurer ce poste et mettre à jour config/ressources_poste.toml avant de générer",
    )
    analyseur.add_argument(
        "--origine",
        default=ORIGINE_POSTE,
        help="libellé de l'environnement mesuré (par défaut : poste de développement)",
    )
    analyseur.add_argument("--sortie", default=str(DESTINATION_PAR_DEFAUT))
    arguments = analyseur.parse_args(argv)

    if arguments.mesurer:
        ecrire_entree(mesurer(arguments.origine))
        print(f"Mesures écrites : {ENTREE.relative_to(RACINE)}")

    destination = Path(arguments.sortie)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendre_markdown(), encoding="utf-8", newline="\n")
    try:
        affiche = destination.relative_to(RACINE)
    except ValueError:
        affiche = destination
    print(f"Document écrit : {affiche}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
