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

import getpass
import os
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path

import pytest


def _racine_temporaire_inutilisable(racine: Path) -> str | None:
    """Return why pytest could not use this temp root, or None if it can.

    pytest reuses a `pytest-of-<user>` directory inside the temp root across runs. One
    unreadable directory there poisons every run afterwards: `os.scandir` raises, and
    every test taking `tmp_path` errors out at setup - not because anything is wrong with
    the code, but because of a leftover folder.

    Seen on Windows after a run interrupted or launched with different privileges.
    """
    try:
        racine.mkdir(parents=True, exist_ok=True)
    except OSError as erreur:
        return f"création impossible ({erreur.__class__.__name__})"

    dossier_pytest = racine / f"pytest-of-{getpass.getuser()}"
    if dossier_pytest.exists():
        try:
            # The exact call pytest makes, and the one that fails.
            next(os.scandir(dossier_pytest), None)
        except OSError as erreur:
            return f"`{dossier_pytest}` illisible ({erreur.__class__.__name__})"

    try:
        temoin = racine / ".pytest-ecriture-temoin"
        temoin.write_text("", encoding="utf-8")
        temoin.unlink()
    except OSError as erreur:
        return f"écriture impossible ({erreur.__class__.__name__})"

    return None


def _choisir_racine_temporaire() -> None:
    """Fall back to a usable temp root rather than failing every `tmp_path` test.

    `PYTEST_DEBUG_TEMPROOT` is the documented way to move pytest's temp root. Setting it
    here, at conftest import time, happens before the factory is built.

    The fallback is a directory under the user's home - never inside the repository, where
    pytest's own cleanup and the antivirus have repeatedly got in each other's way.
    """
    if os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return

    defaut = Path(tempfile.gettempdir())
    motif = _racine_temporaire_inutilisable(defaut)
    if motif is None:
        return

    secours = Path.home() / ".pytest-temp"
    motif_secours = _racine_temporaire_inutilisable(secours)
    if motif_secours is not None:
        warnings.warn(
            f"Racine temporaire par défaut inutilisable ({motif}) et le repli "
            f"{secours} ne l'est pas davantage ({motif_secours}). "
            "Définir PYTEST_DEBUG_TEMPROOT vers un dossier accessible.",
            stacklevel=2,
        )
        return

    os.environ["PYTEST_DEBUG_TEMPROOT"] = str(secours)
    warnings.warn(
        f"Racine temporaire par défaut inutilisable : {motif}. "
        f"Repli sur {secours}. Pour revenir au défaut, supprimer le dossier "
        f"`pytest-of-{getpass.getuser()}` de {defaut}.",
        stacklevel=2,
    )


_choisir_racine_temporaire()

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


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Each test session gets its own temporary directory, removed at the end.

    By default pytest numbers its directories under %TEMP%\pytest-of-<user> and, at the
    end of every session, scans them through the `pytest-current` link. On Windows that
    scan crashed every campaign AFTER all tests had passed (PermissionError, WinError 5,
    on `pytest-current`): a link whose target is still being deleted - a file held open,
    a pytest launched in parallel by VS Code - cannot even be read. With a directory of
    its own (`--basetemp`), a session never touches that shared tree. Runs first, so
    pytest's own temporary-path factory sees the setting. An explicit --basetemp wins.
    """
    import tempfile

    if config.option.basetemp is None:
        config.option.basetemp = tempfile.mkdtemp(prefix="pytest-ai4me-")
        config._dossier_temporaire_de_session = config.option.basetemp


def pytest_unconfigure(config):
    """Remove the session's directory; a file still held open (Windows) is left behind
    rather than failing a session whose tests all passed."""
    import shutil

    dossier = getattr(config, "_dossier_temporaire_de_session", None)
    if dossier:
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture(scope="session")
def _magasin_mlflow_vierge(tmp_path_factory):
    """An empty MLflow store, migrated ONCE per session (optimisation A2).

    Creating a SQLite store runs MLflow's schema migrations: 0.6 to 1.5 s here, more on
    Windows, paid by every test that touched MLflow. Copying an already migrated, empty
    store costs 0.03 s. None when MLflow is not installed (the CI).
    """
    import importlib.util

    if importlib.util.find_spec("mlflow") is None:
        return None
    mlflow = importlib.import_module("mlflow")  # optional: the `suivi` group, not dev

    chemin = tmp_path_factory.mktemp("mlflow_vierge") / "mlflow.db"
    mlflow.MlflowClient(tracking_uri=f"sqlite:///{chemin.as_posix()}").search_experiments()
    return chemin


@pytest.fixture(autouse=True)
def suivi_mlflow_isole(tmp_path, monkeypatch, request):
    """No test ever writes into the project's MLflow store.

    Every test, and every tool a test launches as a subprocess, sees its own temporary
    store through MLFLOW_TRACKING_URI - which the project's configuration reads first. The
    store is a copy of an empty, already migrated one; it is only prepared for the tests
    of the files that use MLflow, so the others pay nothing.
    """
    import shutil

    magasin = tmp_path / "mlflow.db"
    if Path(request.node.fspath).name in FICHIERS_AVEC_MLFLOW:
        vierge = request.getfixturevalue("_magasin_mlflow_vierge")
        if vierge is not None:
            shutil.copy(vierge, magasin)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{magasin.as_posix()}")
    monkeypatch.setenv("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")


# Test files that create MLflow runs; the others get an (unused) path but no store.
FICHIERS_AVEC_MLFLOW = {"test_suivi.py", "test_non_regression.py", "test_materialisation.py"}


# --- Optimisation A3: the preparation chain, computed once per argument set and session ----
def _memoriser_la_chaine() -> None:
    """Tests re-ran the whole preparation chain 14 times on the same files (5.4 s here).

    Installed when conftest loads, before the test modules import `executer_pipeline`, so
    they all receive the memoised version. Each caller gets a DEEP COPY: a test that alters
    its result cannot leak into another. The key includes the files' modification times: a
    changed file is never served from the cache.
    """
    import copy
    import functools
    import os

    import churn_saas.features as features
    import churn_saas.features.pipeline as pipeline

    original = pipeline.executer_pipeline
    memoire: dict = {}

    @functools.wraps(original)
    def executer_pipeline(*args, **kwargs):
        def horodatage(valeur):
            return (
                os.path.getmtime(valeur)
                if isinstance(valeur, (str, os.PathLike)) and os.path.exists(valeur)
                else None
            )

        cle = repr((args, sorted(kwargs.items()), [horodatage(a) for a in args]))
        if cle not in memoire:
            memoire[cle] = original(*args, **kwargs)
        return copy.deepcopy(memoire[cle])

    pipeline.executer_pipeline = executer_pipeline
    features.executer_pipeline = executer_pipeline


_memoriser_la_chaine()
