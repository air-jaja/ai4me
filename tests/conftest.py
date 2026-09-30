"""Detailed reporting for the test suite.

A run shown as a row of dots tells you nothing: neither what was checked, nor what was
skipped. This plugin prints each case with its outcome, then a per-file summary.

Three levels, selected with `--recap`:

    --recap=resume   per-file summary table (default)
    --recap=detail   every case, grouped by file
    --recap=off      standard pytest output

**Two rates, not to be confused.**

    Execution rate = (passed + failed) / total
        How many tests actually ran. Skipped ones pull it down, which is the point: a
        skipped test proves nothing, and the rate makes that visible.

    Success rate = passed / (passed + failed)
        Among those that ran, how many pass.

Neither is code coverage, which measures source lines and is obtained with `pytest-cov`.
The two notions meet in practice - a skipped test covers nothing - but they do not measure
the same thing.

No dependency is added: pytest hooks only.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

# One symbol, one French label and one colour per outcome. The symbol carries the meaning
# on its own, which matters when colour is unavailable: redirected output, CI logs, or a
# reader with colour vision deficiency.
ISSUES: dict[str, tuple[str, str, dict]] = {
    "passed": ("v", "OK", {"green": True}),
    "failed": ("X", "ÉCHEC", {"red": True}),
    "error": ("E", "ERREUR", {"red": True, "bold": True}),
    "skipped": ("-", "IGNORÉ", {"yellow": True}),
    "xfailed": ("x", "ÉCHEC ATTENDU", {"yellow": True}),
    "xpassed": ("!", "PASSÉ INATTENDU", {"yellow": True}),
}

_compte: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_detail: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
_duree: dict[str, float] = defaultdict(float)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Expose the reporting level on the command line.

    The default is `resume`: this suite holds parametrised cases in the hundreds, and the
    per-case listing would bury the summary it is meant to introduce.
    """
    parser.addoption(
        "--recap",
        action="store",
        default="resume",
        choices=("detail", "resume", "off"),
        help="niveau du récapitulatif : resume (tableau), detail (chaque cas), off",
    )


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record each test outcome, per file.

    Called after every phase - setup, call, teardown - of every test. Without filtering,
    the same test would be counted three times.
    """
    fichier, _, nom = report.nodeid.partition("::")
    _duree[fichier] += report.duration

    issue = None
    # A skipped test is known at setup; a normal one is judged on its call phase.
    if report.when == "setup" and report.skipped:
        issue = "skipped"
    elif report.when == "setup" and report.failed:
        # A fixture raised: the test never started, which is worse than failing.
        issue = "error"
    elif report.when == "call":
        if report.passed:
            issue = "xpassed" if hasattr(report, "wasxfail") else "passed"
        elif report.failed:
            issue = "failed"
        elif report.skipped:
            issue = "xfailed" if hasattr(report, "wasxfail") else "skipped"

    if issue:
        _compte[fichier][issue] += 1
        _detail[fichier].append((nom, issue, report.duration))


def _taux(issues: dict[str, int]) -> tuple[int, int, int, float, float]:
    """Return total, executed, passed, execution rate and success rate.

    An expected failure counts as a success: the behaviour it documents is the one
    observed.
    """
    total = sum(issues.values())
    executes = total - issues.get("skipped", 0)
    reussis = issues.get("passed", 0) + issues.get("xfailed", 0)
    taux_execution = 100 * executes / total if total else 0.0
    taux_reussite = 100 * reussis / executes if executes else 0.0
    return total, executes, reussis, taux_execution, taux_reussite


def _format_taux(taux: float) -> str:
    """Format a rate so that 100% is only ever shown when it is exactly 100%.

    Rounding 99.5% to "100%" would announce a flawless run while a test failed - the
    single most misleading thing a summary can do.
    """
    if taux in (0.0, 100.0):
        return f"{taux:.0f}%"
    borne = min(taux, 99.9) if taux > 99 else taux
    return f"{borne:.1f}%"


def _style_fichier(issues: dict[str, int]) -> dict:
    """Colour a file by its most serious outcome, not by its majority one."""
    if issues.get("failed") or issues.get("error"):
        return {"red": True}
    if issues.get("skipped") and not issues.get("passed"):
        return {"yellow": True}
    if issues.get("skipped"):
        return {"cyan": True}
    return {"green": True}


def _ecrire_detail(tr, fichier: str) -> None:
    """Print every case of one file, aligned for scanning."""
    issues = _compte[fichier]
    total, _, _, taux_execution, _ = _taux(issues)

    tr.write("\n  " + fichier, bold=True, **_style_fichier(issues))
    tr.write(f"  ({total} cas, {_format_taux(taux_execution)} exécutés)\n")

    for nom, issue, duree in _detail[fichier]:
        symbole, libelle, style = ISSUES[issue]
        tr.write(f"    {symbole} ", **style)
        tr.write(f"{nom:<64}")
        tr.write(f"{libelle:<18}", **style)
        tr.write(f"{duree * 1000:>7.0f} ms\n")


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Print the per-case detail, then the per-file summary table."""
    niveau = config.getoption("--recap")
    if niveau == "off" or not _compte:
        return

    tr = terminalreporter

    if niveau == "detail":
        tr.write_sep("=", "Détail des cas de test", bold=True)
        for fichier in sorted(_detail):
            _ecrire_detail(tr, fichier)

    tr.write_sep("=", "Synthèse par fichier de test", bold=True)

    largeur = max(max(len(f) for f in _compte), 30) + 2
    entete = (
        f"  {'Fichier':<{largeur}}{'Cas':>5}{'OK':>6}{'KO':>5}"
        f"{'Ign.':>6}{'Exéc.':>9}{'Réuss.':>9}{'Durée':>9}"
    )
    tr.write(entete + "\n", bold=True)
    tr.write("  " + "-" * (len(entete) - 2) + "\n")

    cumul: dict[str, int] = defaultdict(int)

    for fichier in sorted(_compte):
        issues = _compte[fichier]
        total, _, reussis, taux_execution, taux_reussite = _taux(issues)
        echoues = issues.get("failed", 0) + issues.get("error", 0)
        ignores = issues.get("skipped", 0)

        for issue, nombre in issues.items():
            cumul[issue] += nombre

        tr.write(f"  {fichier:<{largeur}}", **_style_fichier(issues))
        tr.write(f"{total:>5}")
        tr.write(f"{reussis:>6}", **({"green": True} if reussis else {}))
        tr.write(f"{echoues:>5}", **({"red": True} if echoues else {}))
        tr.write(f"{ignores:>6}", **({"yellow": True} if ignores else {}))
        # The execution rate is the column that matters: it drops as soon as a test is
        # skipped, that is, as soon as a guarantee is no longer being checked.
        tr.write(
            f"{_format_taux(taux_execution):>9}",
            **({"green": True} if taux_execution == 100 else {"yellow": True}),
        )
        tr.write(
            f"{_format_taux(taux_reussite):>9}",
            **({"green": True} if taux_reussite == 100 else {"red": True}),
        )
        tr.write(f"{_duree[fichier]:>8.2f}s\n")

    tr.write("  " + "-" * (len(entete) - 2) + "\n")
    total, _, reussis, taux_execution, taux_reussite = _taux(cumul)
    echoues = cumul.get("failed", 0) + cumul.get("error", 0)
    ignores = cumul.get("skipped", 0)

    tr.write(f"  {'TOTAL':<{largeur}}", bold=True)
    tr.write(f"{total:>5}", bold=True)
    tr.write(f"{reussis:>6}", green=True, bold=True)
    tr.write(f"{echoues:>5}", **({"red": True, "bold": True} if echoues else {"bold": True}))
    tr.write(f"{ignores:>6}", **({"yellow": True, "bold": True} if ignores else {"bold": True}))
    tr.write(
        f"{_format_taux(taux_execution):>9}",
        **({"green": True} if taux_execution == 100 else {"yellow": True}),
    )
    tr.write(
        f"{_format_taux(taux_reussite):>9}",
        **({"green": True} if taux_reussite == 100 else {"red": True}),
    )
    tr.write(f"{sum(_duree.values()):>8.2f}s\n")

    if ignores:
        tr.write(
            f"\n  {ignores} cas sur {total} n'ont PAS été exécutés "
            f"(taux d'exécution : {_format_taux(taux_execution)}).\n",
            yellow=True,
        )
        tr.write("  Un test ignoré ne prouve rien. Détail : pytest -rs\n", yellow=True)
    else:
        tr.write("\n  Taux d'exécution : 100 % — tous les cas ont tourné.\n", green=True)
