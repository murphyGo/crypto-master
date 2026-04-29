"""Smoke test for ``scripts/auto_research_candidates.py``.

Mocks the ClaudeCLI (no real network), the BinanceExchange (no public
API hits), and the RobustnessGate (so the test stays fast and
deterministic). What we verify here is the script's orchestration —
that picks flow through the loop, results are captured into the
summary structure, and the artefact JSON lands on disk. The actual
Backtester / RobustnessGate behavior has its own tests.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts import auto_research_candidates as script
from scripts.auto_research_candidates import Pick, PickResult, run_picks
from src.feedback.audit import AuditLog
from src.feedback.loop import FeedbackLoop, LoopStatus
from tests.test_scripts_backtest_baselines import _synthetic_ohlcv

GOOD_RESPONSE = (
    "```markdown\n"
    "---\n"
    "name: smoke_donchian\n"
    "version: 0.1.0\n"
    "description: smoke test technique\n"
    "technique_type: prompt\n"
    "hypothesis: 55-bar Donchian breakouts capture mean-reverting "
    "trend regime in BTC.\n"
    "---\n"
    "# Smoke Donchian\n"
    "Long when close > 55-bar high. SL at 20-bar low.\n"
    "```"
)


class _FakeExchange:
    """Minimal exchange returning deterministic candles."""

    def __init__(self, candles_by_tf: dict[str, list]) -> None:
        self._by_tf = candles_by_tf

    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int, since: int | None = None
    ):
        return self._by_tf[timeframe][:limit]


def _make_picks() -> list[Pick]:
    return [
        Pick(slug="pick_a", context="Test pick A", timeframe="1h", candles=300),
        Pick(slug="pick_b", context="Test pick B", timeframe="4h", candles=300),
    ]


def _make_mock_loop(tmp_path: Path, audit_path: Path) -> FeedbackLoop:
    """Build a FeedbackLoop with mocked ClaudeCLI plus stubbed
    backtester and gate — smoke test verifies orchestration only,
    not real backtest math (covered by other tests)."""
    from src.ai.claude import ClaudeCLI
    from src.ai.improver import StrategyImprover
    from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
    from src.backtest.engine import BacktestConfig, Backtester, BacktestResult
    from src.backtest.validator import RobustnessGate, RobustnessReport

    claude = AsyncMock(spec=ClaudeCLI)
    claude.complete.return_value = GOOD_RESPONSE

    improver = StrategyImprover(
        claude=claude,
        experimental_dir=tmp_path / "experimental",
        catalog_path=tmp_path / "no_catalog.md",
    )
    backtester = Backtester(BacktestConfig(), data_dir=tmp_path / "backtest")
    analyzer = PerformanceAnalyzer()
    gate = RobustnessGate(backtester=backtester)

    async def _stub_run_for_strategy(*args, **kwargs):
        now = datetime.now()
        return BacktestResult(
            run_id="stub-run",
            technique_name="smoke_donchian",
            technique_version="0.1.0",
            symbol="BTC/USDT",
            timeframe="1h",
            start_time=now,
            end_time=now,
            initial_balance=Decimal("10000"),
            final_balance=Decimal("10500"),
            total_trades=10,
            wins=6,
            losses=4,
            breakevens=0,
            total_pnl=Decimal("500"),
            total_fees=Decimal("10"),
            win_rate=0.6,
            return_percent=5.0,
            trades=[],
        )

    backtester.run_for_strategy = _stub_run_for_strategy  # type: ignore[assignment]

    def _stub_analyze(*args, **kwargs):
        return PerformanceMetrics(
            total_trades=10,
            wins=6,
            losses=4,
            win_rate=0.6,
            return_percent=5.0,
            sharpe_ratio=1.5,
            max_drawdown_percent=2.0,
        )

    analyzer.analyze = _stub_analyze  # type: ignore[assignment]

    async def _stub_evaluate(*args, **kwargs):
        return RobustnessReport(
            overall_passed=True,
            gates=[],
            summary="stubbed pass",
            baseline_sharpe=1.5,
            baseline_trades=10,
        )

    gate.evaluate = _stub_evaluate  # type: ignore[assignment]

    return FeedbackLoop(
        improver=improver,
        backtester=backtester,
        analyzer=analyzer,
        gate=gate,
        audit_log=AuditLog(path=audit_path),
        experimental_dir=tmp_path / "experimental",
        active_dir=tmp_path / "active",
        state_dir=tmp_path / "state",
    )


@pytest.mark.asyncio
async def test_run_picks_orchestrates_each_candidate(tmp_path: Path) -> None:
    """Each pick produces one PickResult; passing picks land in
    AWAITING_APPROVAL with their saved technique path."""
    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles, "4h": candles})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")

    results = await run_picks(
        _make_picks(), symbol="BTC/USDT", loop=loop, exchange=exchange
    )

    assert len(results) == 2
    for r in results:
        assert r.status == LoopStatus.AWAITING_APPROVAL.value
        assert r.candidate_id is not None
        assert r.technique_name == "smoke_donchian"
        assert r.saved_path is not None
        assert r.robustness_passed is True


@pytest.mark.asyncio
async def test_dry_run_skips_backtest(tmp_path: Path) -> None:
    """``--dry-run`` should generate the technique file but not run
    the gate. The result status reflects this. Files must land under
    a ``dry_runs/`` subdir of the experimental dir so a subsequent
    real pass doesn't mix ungated and gated candidates."""
    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles, "4h": candles})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")
    real_experimental = loop.improver.experimental_dir

    results = await run_picks(
        _make_picks(),
        symbol="BTC/USDT",
        dry_run=True,
        loop=loop,
        exchange=exchange,
    )

    assert len(results) == 2
    dry_subdir = real_experimental / "dry_runs"
    for r in results:
        assert r.status == "generated_only"
        assert r.decision_reason == "dry-run"
        assert r.robustness_passed is None
        assert r.saved_path is not None
        saved_path = Path(r.saved_path)
        # File was still written, and lives under the dry-runs subdir,
        # not the main experimental dir.
        assert saved_path.exists()
        assert saved_path.parent == dry_subdir, (
            f"dry-run file landed at {saved_path}; expected under {dry_subdir}"
        )
    # Real experimental dir holds nothing; only the dry-runs subdir does.
    assert not any(
        p for p in real_experimental.iterdir() if p.is_file()
    )


@pytest.mark.asyncio
async def test_pick_failure_captured_not_raised(tmp_path: Path) -> None:
    """If one pick errors, the others still run; the error is recorded
    on the result rather than aborting the whole batch."""
    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles, "4h": candles})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")

    # Make the first pick raise during generate_idea (Claude error path)
    call_count = {"n": 0}

    async def _flaky_complete(prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("claude flaked on first call")
        return GOOD_RESPONSE

    loop.improver.claude.complete = AsyncMock(side_effect=_flaky_complete)

    results = await run_picks(
        _make_picks(), symbol="BTC/USDT", loop=loop, exchange=exchange
    )

    assert len(results) == 2
    assert results[0].status == LoopStatus.ERRORED.value
    assert "claude flaked" in (results[0].error or "")
    assert results[1].status == LoopStatus.AWAITING_APPROVAL.value


def test_render_summary_table_shape() -> None:
    """Summary renders as markdown with one header + one row per pick."""
    results = [
        PickResult(
            slug="x",
            context_preview="ctx",
            status="awaiting_approval",
            candidate_id="abc",
            technique_name="t",
            saved_path="/p",
            robustness_passed=True,
            failed_gates=[],
            decision_reason="ok",
        ),
        PickResult(
            slug="y",
            context_preview="ctx2",
            status="discarded",
            candidate_id="def",
            technique_name="t2",
            saved_path="/p2",
            robustness_passed=False,
            failed_gates=["regime", "oos"],
            decision_reason="failed",
        ),
    ]
    rendered = script.render_summary(results)
    lines = rendered.splitlines()
    assert lines[0].startswith("| slug |")
    assert "✓" in rendered  # passing pick
    assert "✗" in rendered  # failing pick
    assert "regime, oos" in rendered


def test_render_summary_surfaces_decision_reason_and_gate_summary() -> None:
    """Operators reading the table need to see WHY a candidate was
    DISCARDED — the failed-gate column lists names but not detail.
    Each row must therefore be followed by a continuation line with
    ``decision_reason`` (and ``robustness_summary`` when present)."""
    results = [
        PickResult(
            slug="discarded_pick",
            context_preview="ctx",
            status="discarded",
            candidate_id="d1",
            technique_name="t",
            saved_path="/p",
            robustness_passed=False,
            failed_gates=["regime"],
            decision_reason="Discarded: gate FAILED on regime",
            robustness_summary=(
                "regime gate FAILED: only 1 evaluable regime "
                "(insufficient bull/bear coverage)"
            ),
        ),
    ]
    rendered = script.render_summary(results)
    # Row 1 = header, 2 = separator, 3 = data row, 4 = continuation.
    assert "Discarded: gate FAILED on regime" in rendered
    assert "1 evaluable regime" in rendered
    # Continuation line is indented so it visually attaches to its row.
    continuation_lines = [
        line
        for line in rendered.splitlines()
        if line.startswith("    ")
    ]
    assert continuation_lines, "expected at least one indented detail line"
    assert all(
        "reason" in line or "gate" in line or "error" in line
        for line in continuation_lines
    )


def test_render_summary_continuation_carries_error_for_errored_pick() -> None:
    """Errored picks have no robustness data, but the captured
    exception is still useful triage info — surface it."""
    results = [
        PickResult(
            slug="boom",
            context_preview="ctx",
            status="errored",
            candidate_id=None,
            technique_name=None,
            saved_path=None,
            robustness_passed=None,
            failed_gates=[],
            decision_reason="",
            error="RuntimeError: claude flaked",
        ),
    ]
    rendered = script.render_summary(results)
    assert "RuntimeError: claude flaked" in rendered


def test_default_candles_for_spans_at_least_one_year() -> None:
    """The regime gate's 200-bar SMA + ±2% band only verdicts when at
    least one regime has trades. Each timeframe's default must give us
    enough bars that BTC has crossed its 200-SMA both ways."""
    # 4h: 4380 bars × 4h = 17520h ≈ 730 days ≈ 2 years.
    assert script._default_candles_for("4h") >= 4380
    # 1h: 8760 bars × 1h = 8760h ≈ 365 days.
    assert script._default_candles_for("1h") >= 8760
    # 15m: 17520 bars × 15m = 4380h ≈ 182 days ≈ 6mo.
    assert script._default_candles_for("15m") >= 17520


def test_pick_candles_default_uses_helper() -> None:
    """A Pick constructed without an explicit candles= argument should
    pick up the per-timeframe default, not the dataclass zero."""
    p4h = Pick(slug="x", context="c", timeframe="4h")
    p1h = Pick(slug="y", context="c", timeframe="1h")
    assert p4h.candles == script._default_candles_for("4h")
    assert p1h.candles == script._default_candles_for("1h")


def test_pick_candles_explicit_value_preserved() -> None:
    """Tests pass an explicit small ``candles`` to keep wallclock low;
    that override must NOT be silently bumped to the default."""
    p = Pick(slug="x", context="c", timeframe="1h", candles=300)
    assert p.candles == 300


def test_top_picks_use_default_candle_windows() -> None:
    """Every shipped TOP_PICK should be on the long-window default —
    the regime gate is meaningless on the short windows that hide
    every transition."""
    for pick in script.TOP_PICKS:
        expected = script._default_candles_for(pick.timeframe)
        assert pick.candles == expected, (
            f"{pick.slug} has candles={pick.candles}, expected {expected} "
            f"for timeframe {pick.timeframe}"
        )


def test_write_run_artifacts_writes_json(tmp_path: Path) -> None:
    """Run snapshot is written to the configured directory as JSON."""
    results = [
        PickResult(
            slug="x",
            context_preview="ctx",
            status="awaiting_approval",
            candidate_id="abc",
            technique_name="t",
            saved_path="/p",
            robustness_passed=True,
            failed_gates=[],
            decision_reason="ok",
        ),
    ]
    path = script.write_run_artifacts(results, results_dir=tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["results"][0]["slug"] == "x"
    assert payload["results"][0]["robustness_passed"] is True


def test_top_picks_are_ohlcv_only() -> None:
    """Sanity: every default pick must run on a TF that BinanceExchange
    supports natively (no funding/OI/on-chain dependencies)."""
    allowed = {"15m", "1h", "4h"}
    for pick in script.TOP_PICKS:
        assert pick.timeframe in allowed, (
            f"Pick {pick.slug} timeframe {pick.timeframe} not in allowed set"
        )
        assert "funding" not in pick.context.lower(), (
            f"Pick {pick.slug} references funding rate — needs data layer first"
        )
        assert "on-chain" not in pick.context.lower(), (
            f"Pick {pick.slug} references on-chain data — needs data layer first"
        )
