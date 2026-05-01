"""Project-wide pytest configuration.

Phase 26.3 / DEBT-039: a logger-reset fixture so handler state from
``setup_logger`` does not leak across tests. ``src.logger`` caches
initialized loggers in a module-global ``_initialized_loggers`` set;
without a per-test reset, the first test to call ``setup_logger`` for
a given name installs file + console handlers that persist for the
rest of the suite, including ``propagate = False`` which silences
``caplog``-style assertions in any later test that wants them.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.logger import reset_loggers


@pytest.fixture(autouse=True)
def _reset_loggers_between_tests() -> Iterator[None]:
    """Reset the logger module's handler cache between tests.

    Idempotent — safe to call alongside per-file fixtures (e.g.
    ``tests/test_logger.py`` has its own ``clean_loggers`` fixture
    that does the same thing). Resets are cheap; double-resets are
    no-ops.
    """
    reset_loggers()
    yield
    reset_loggers()
