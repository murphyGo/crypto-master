"""Regression guard for the leverage-double-apply bug (DEBT-024 / Phase 20.1+20.2).

Phase 20.1 fixed a bug where the backtester and portfolio multiplied
per-trade PnL by ``leverage`` even though ``calculate_position_size``
already returned a leverage-aware ``quantity`` (so the levered notional
was already baked in). Phase 20.2 sweeps every PnL surface in the
codebase to confirm no other call site reintroduces the bug, and pins
the convention via this string-search regression test.

The convention: every per-trade PnL site goes through
:func:`src.utils.trading_math.pnl_for_trade`; ``leverage`` is *not* a
parameter to PnL math anywhere downstream of position sizing.

This test asserts that no ``* leverage`` / ``* self.leverage`` /
``* position.leverage`` / ``* trade.leverage`` substring appears
anywhere in the four files that own a PnL computation. If a future
contributor re-adds the second multiplication this test will fail at
CI before the bug ships to baselines or paper trades.

Limitation: this is a string-search guard. Indirect aliasing such as
``lev = self.leverage; pnl = raw * lev`` would slip past — the bound
name ``lev`` is not in the banned-pattern list. The guard targets the
realistic copy-paste-bug shape; tightening to AST-level analysis would
chase ghosts. If a reintroduction goes through an alias the numeric-
equality alignment tests in ``tests/test_backtest_engine.py::
TestPnLConventionAlignment`` and the persistence-layer regression in
``tests/test_strategy_performance.py::TestTradeHistoryTracker`` will
still flag the divergence on a levered fixture.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# The four files that own a per-trade PnL surface. Any future PnL
# computation should land in one of these and route through
# ``pnl_for_trade``.
PNL_OWNING_FILES = [
    Path("src/backtest/engine.py"),
    Path("src/trading/portfolio.py"),
    Path("src/trading/paper.py"),
    Path("src/strategy/performance.py"),
]

# Banned arithmetic patterns. We match ``* leverage`` with optional
# attribute access (``self.``, ``position.``, ``trade.``, ``open_trade.``)
# but NOT ``* leverage_cap`` or other tokens that merely start with
# "leverage" — the regex pins a non-identifier boundary after the word.
BANNED_PATTERNS = [
    # ``*= leverage`` (augmented multiplication) and ``* leverage``
    # (binary multiplication). ``=?`` lets us catch both shapes.
    re.compile(r"\*=?\s*leverage\b"),
    re.compile(r"\*=?\s*self\.leverage\b"),
    re.compile(r"\*=?\s*position\.leverage\b"),
    re.compile(r"\*=?\s*trade\.leverage\b"),
    re.compile(r"\*=?\s*open_trade\.leverage\b"),
    re.compile(r"\*=?\s*self\.config\.leverage\b"),
]

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("relative_path", PNL_OWNING_FILES)
def test_no_leverage_multiplication_on_pnl_surfaces(
    relative_path: Path,
) -> None:
    """No ``* leverage`` substring may appear in PnL-owning files.

    DEBT-024 / Phase 20.1+20.2: ``calculate_position_size`` returns a
    levered ``quantity``, so PnL math is ``(exit - entry) * qty`` with
    no second multiplication. Every PnL site routes through
    :func:`src.utils.trading_math.pnl_for_trade`. If this test trips,
    surface to the lead — the bug fixed in Phase 20.1 is back.
    """
    full_path = REPO_ROOT / relative_path
    assert full_path.exists(), f"Expected file {full_path} to exist"
    text = full_path.read_text(encoding="utf-8")

    # Strip comments and docstrings is overkill for a string-search
    # guard; we instead match per-line and ignore lines that are
    # demonstrably comments or part of a docstring (start with ``#``
    # or live inside triple-quoted blocks). The simpler scan: only
    # lines that look like executable code (no leading ``#``) are
    # tested. This still catches every realistic reintroduction.
    offending: list[tuple[int, str]] = []
    in_docstring = False
    docstring_token: str | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()

        # Docstring tracking (handles """ and ''' on same/separate
        # lines — sufficient for our four files which use """).
        if in_docstring:
            assert docstring_token is not None
            if docstring_token in stripped:
                in_docstring = False
                docstring_token = None
            continue
        for token in ('"""', "'''"):
            if stripped.startswith(token):
                # Single-line docstring: opens and closes on same line.
                rest = stripped[len(token) :]
                if token in rest:
                    break
                in_docstring = True
                docstring_token = token
                break
        if in_docstring:
            continue

        # Skip pure-comment lines.
        if stripped.startswith("#"):
            continue

        for pattern in BANNED_PATTERNS:
            if pattern.search(raw):
                offending.append((lineno, raw.rstrip()))
                break

    assert not offending, (
        f"Found banned ``* leverage`` pattern(s) in {relative_path} — "
        f"DEBT-024 / Phase 20.1 bug reintroduced. Route per-trade PnL "
        f"through ``src.utils.trading_math.pnl_for_trade`` instead. "
        f"Offending lines:\n" + "\n".join(f"  L{ln}: {src}" for ln, src in offending)
    )


def test_guard_fires_on_artificial_reintroduction(tmp_path: Path) -> None:
    """Sanity check: the guard regex actually catches a reintroduction.

    Confirms the banned-pattern regex matches the exact shape of the
    pre-Phase-20.1 bug (``pnl *= leverage``, ``pnl = raw * leverage``,
    ``total += price_diff * position.leverage``, etc.) so a future
    contributor cannot trivially evade it.
    """
    bug_shapes = [
        "pnl *= leverage",
        "pnl = raw * leverage",
        "total += price_diff * position.leverage",
        "pnl = (exit_p - entry) * qty * self.leverage",
        "value = move * trade.leverage",
        "x = base * open_trade.leverage",
        "y = base * self.config.leverage",
    ]
    for shape in bug_shapes:
        matched = any(p.search(shape) for p in BANNED_PATTERNS)
        assert matched, f"Guard failed to match bug shape: {shape!r}"

    # Negative cases: legitimate position-sizing / margin math must
    # NOT match — these are the (a)/(c) classifications we keep.
    legitimate_shapes = [
        "margin_required = notional_value / Decimal(leverage)",
        "max_notional = max_position_value * Decimal(leverage)",
        "default_leverage=self.config.leverage,",
        "max_leverage=self.config.leverage,",
        "leverage=position.leverage,",  # kwarg passing
    ]
    for shape in legitimate_shapes:
        matched = any(p.search(shape) for p in BANNED_PATTERNS)
        assert not matched, (
            f"Guard incorrectly flagged legitimate sizing/margin " f"math: {shape!r}"
        )
