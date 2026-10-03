"""Generate CHANGELOG.md from the commit history, grouped by phase.

    uv run python tools/journal_modifications.py

Reads the phase number at the start of each commit subject - "09 · feat: ..." or the
earlier "09.Validation ..." - and groups the subjects under it, newest phase first.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def regrouper(sujets: list[str]) -> dict[str, list[str]]:
    """Phase number -> subjects (oldest first); subjects without a phase go to 'autres'."""
    phases: dict[str, list[str]] = defaultdict(list)
    for sujet in sujets:
        trouve = re.match(r"^(\d{2})\s*(?:·|\.)\s*", sujet)
        phases[trouve.group(1) if trouve else "autres"].append(sujet)
    return dict(phases)


def main(argv: list[str] | None = None) -> int:
    # A Windows terminal hands a piped child process cp1252, whatever the document holds:
    # the tool's output must not depend on who runs it - its errors on stderr included.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description="Journal des modifications par phase.")
    analyseur.add_argument("--reference", default="HEAD")
    analyseur.add_argument("--sortie", default=str(RACINE / "CHANGELOG.md"))
    arguments = analyseur.parse_args(argv)
    sujets = subprocess.run(
        ["git", "log", "--no-merges", "--format=%ad %s", "--date=short", arguments.reference],
        cwd=RACINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()[::-1]
    groupes = regrouper([s.split(" ", 1)[1] for s in sujets])
    dates = {s.split(" ", 1)[1]: s.split(" ", 1)[0] for s in sujets}
    lignes = ["# Journal des modifications", "", "Généré par `tools/journal_modifications.py`.", ""]
    for phase in sorted(groupes, key=lambda p: (p == "autres", p), reverse=False)[::-1]:
        lignes += [f"## Phase {phase}" if phase != "autres" else "## Autres", ""]
        lignes += [f"- {dates[s]} — {s}" for s in groupes[phase]] + [""]
    Path(arguments.sortie).write_text("\n".join(lignes), encoding="utf-8", newline="\n")
    print(f"{len(sujets)} commits -> {arguments.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
