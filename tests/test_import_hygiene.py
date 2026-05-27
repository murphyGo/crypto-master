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
