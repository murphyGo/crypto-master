"""Import-hygiene regression tests.

These guard against circular-import regressions that the normal pytest /
mypy gate masks. Test collection happens to import ``src.ai`` before
``src.strategy.loader``, which is the one import order that resolves the
``loader <-> ai.ports <-> ai.improver`` cycle. A cold interpreter that
imports the modules in a different order would crash with
``ImportError: cannot import name ... from partially initialized
module``.

Each test runs the import in a FRESH subprocess interpreter so the
import-ordering mask cannot hide a regression.

Related: CAH-10 (LLM port cluster) circular-import fix.
"""

import subprocess
import sys

import pytest

# Modules whose cold (fresh-interpreter, first-thing) import previously
# crashed because of the loader <-> ai.ports cycle.
COLD_IMPORT_TARGETS = [
    "src.dashboard.app",
    "src.strategy.loader",
    "src.strategy",
    # CAH-15 Slice 2: the monitor collaborator must cold-import cleanly — it
    # uses a function-local import for the engine's EngineError/ErrorCategory to
    # avoid a module-level engine↔position_monitor cycle.
    "src.runtime.position_monitor",
]


@pytest.mark.parametrize("module", COLD_IMPORT_TARGETS)
def test_cold_import_succeeds(module: str) -> None:
    """Importing ``module`` as the first thing in a fresh interpreter must not crash."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"cold `import {module}` failed (rc={result.returncode}).\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_activity_events_pure_module_has_no_io_dependency() -> None:
    """The pure activity-event vocabulary must not pull IO machinery (CAH-13 / LAYER-F4).

    ``activity_events`` holds only the model + enum; importing it cold must
    not transitively load the JSONL rotator or the activity-log IO adapter.
    This guards the layer split that lets pure consumers (e.g.
    ``safety_score``) depend on the vocabulary without the file-write layer.

    (``src.config`` is intentionally NOT asserted-absent here: importing any
    ``src.runtime`` submodule runs the package ``__init__``, which eagerly
    imports config-bound siblings — a pre-existing, separate concern.)
    """
    code = (
        "import sys; import src.runtime.activity_events; "
        "io = [m for m in ('src.runtime.jsonl_rotator', "
        "'src.runtime.activity_log') if m in sys.modules]; "
        "print(','.join(io))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    pulled = result.stdout.strip()
    assert pulled == "", f"activity_events cold-pulled IO modules: {pulled}"


def test_safety_score_does_not_import_activity_log_io_module() -> None:
    """``safety_score`` imports the vocabulary from the PURE module, not the IO adapter.

    A source-level check (not transitive) — the ``src.runtime`` package
    ``__init__`` eagerly imports unrelated modules, so we assert on
    ``safety_score``'s own import statements rather than ``sys.modules``.
    """
    from pathlib import Path

    source = Path("src/runtime/safety_score.py").read_text()
    assert "from src.runtime.activity_events import" in source
    assert "from src.runtime.activity_log import" not in source
