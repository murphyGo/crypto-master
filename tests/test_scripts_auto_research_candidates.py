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
from src.config import reload_settings
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
        self.connected = False
        self.disconnected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int, since: int | None = None
    ):
        return self._by_tf[timeframe][:limit]


class _FailingConnectExchange(_FakeExchange):
    async def connect(self) -> None:
        self.connected = True
        raise RuntimeError("connect failed")


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
async def test_run_picks_threads_sub_account_id(tmp_path: Path) -> None:
    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles, "4h": candles})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")

    results = await run_picks(
        _make_picks()[:1],
        symbol="BTC/USDT",
        loop=loop,
        exchange=exchange,
        sub_account_id="experimental",
    )

    assert results[0].sub_account_id == "experimental"


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
        assert (
            saved_path.parent == dry_subdir
        ), f"dry-run file landed at {saved_path}; expected under {dry_subdir}"
    # Real experimental dir holds nothing; only the dry-runs subdir does.
    assert not any(p for p in real_experimental.iterdir() if p.is_file())


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
        line for line in rendered.splitlines() if line.startswith("    ")
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


def test_pick_generation_context_includes_param_grid_contract() -> None:
    """DEBT-014: generated code must expose the names the sensitivity
    gate will sweep."""
    pick = Pick(
        slug="x",
        context="Build a breakout strategy",
        timeframe="1h",
        candles=300,
        code_type=True,
        param_grid={"entry_period": [45, 55], "exit_period": [15, 20]},
    )

    assert "Build a breakout strategy" in pick.generation_context
    assert "Parameter sensitivity contract" in pick.generation_context
    assert "entry_period" in pick.generation_context
    assert "exit_period" in pick.generation_context


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


def test_top_picks_have_sensitivity_grids_within_gate_cap() -> None:
    """DEBT-014: catalog picks should exercise parameter sensitivity.

    Keep each cartesian grid below the default robustness cap so a
    normal operator run does not fail before testing any variants.
    """
    default_cap = 64
    for pick in script.TOP_PICKS:
        assert pick.param_grid, f"{pick.slug} is missing param_grid"
        combos = 1
        for values in pick.param_grid.values():
            combos *= len(values)
        assert combos <= default_cap, (
            f"{pick.slug} param_grid has {combos} combos, exceeding "
            f"default cap {default_cap}"
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


def test_default_results_dir_follows_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime-data"))
    reload_settings()
    try:
        assert script.default_results_dir() == tmp_path / "runtime-data/research_runs"
    finally:
        reload_settings()


@pytest.mark.asyncio
async def test_run_async_uses_caller_built_loop_and_exchange(
    tmp_path: Path,
) -> None:
    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles, "4h": candles})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")

    rc = await script.run_async(
        _make_picks()[:1],
        "BTC/USDT",
        dry_run=False,
        results_dir=tmp_path / "results",
        loop=loop,
        exchange=exchange,  # type: ignore[arg-type]
    )

    assert rc == 0
    assert exchange.connected is True
    assert exchange.disconnected is True
    assert list((tmp_path / "results").glob("run_*.json"))


def test_main_builds_runtime_before_calling_run_async(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loop = object()
    exchange = object()
    seen: dict[str, object] = {}

    async def fake_run_async(*args, **kwargs):
        del args
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(script, "build_loop", lambda: loop)
    monkeypatch.setattr(script, "build_exchange", lambda: exchange)
    monkeypatch.setattr(script, "run_async", fake_run_async)

    rc = script.main(["--picks", "1", "--results-dir", str(tmp_path)])

    assert rc == 0
    assert seen["loop"] is loop
    assert seen["exchange"] is exchange
    assert seen["dry_run"] is False


def test_build_exchange_ignores_trading_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-research fetches public OHLCV and must not require trade keys."""
    monkeypatch.setenv("BINANCE_API_KEY", "invalid-live-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "invalid-live-secret")
    monkeypatch.setenv("BINANCE_TESTNET_API_KEY", "invalid-testnet-key")
    monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", "invalid-testnet-secret")

    exchange = script.build_exchange()

    assert exchange.config.api_key == ""
    assert exchange.config.api_secret == ""
    assert exchange.config.testnet_api_key == ""
    assert exchange.config.testnet_api_secret == ""


@pytest.mark.asyncio
async def test_run_async_disconnects_when_owned_exchange_connect_fails(
    tmp_path: Path,
) -> None:
    exchange = _FailingConnectExchange({"1h": _synthetic_ohlcv(10)})
    loop = _make_mock_loop(tmp_path, audit_path=tmp_path / "audit.jsonl")

    with pytest.raises(RuntimeError, match="connect failed"):
        await script.run_async(
            _make_picks()[:1],
            "BTC/USDT",
            dry_run=False,
            results_dir=tmp_path / "results",
            loop=loop,
            exchange=exchange,  # type: ignore[arg-type]
            owns_exchange=True,
        )

    assert exchange.connected is True
    assert exchange.disconnected is True


def test_top_picks_are_ohlcv_only() -> None:
    """Sanity: every default pick must run on a TF that BinanceExchange
    supports natively (no funding/OI/on-chain dependencies)."""
    allowed = {"15m", "1h", "4h"}
    for pick in script.TOP_PICKS:
        assert (
            pick.timeframe in allowed
        ), f"Pick {pick.slug} timeframe {pick.timeframe} not in allowed set"
        assert (
            "funding" not in pick.context.lower()
        ), f"Pick {pick.slug} references funding rate — needs data layer first"
        assert (
            "on-chain" not in pick.context.lower()
        ), f"Pick {pick.slug} references on-chain data — needs data layer first"


def test_top_picks_are_all_code_type() -> None:
    """Phase 17.5 / DEBT-019 Option B — every shipped TOP_PICK is a
    deterministic catalog technique (Donchian, Supertrend, Z-score,
    Connors RSI(2), NR7, BB %B+RSI, Larry Williams, Golden Cross, TTM
    Squeeze) and must be flagged ``code_type=True`` so the resulting
    backtest never invokes Claude per bar. Defaults to ``False`` is
    preserved on the dataclass; this test pins the per-pick flag."""
    for pick in script.TOP_PICKS:
        assert pick.code_type is True, (
            f"Pick {pick.slug} must be code_type=True for the local "
            "per-bar execution path; the prompt-type fallback is for "
            "operator-authored picks only."
        )


# =============================================================================
# Phase 17.5 / DEBT-019 Option B — code-type integration test
# =============================================================================


# A Python ``BaseStrategy`` body the improver will return. Mirrors the
# canonical shape of ``strategies/rsi.py``: TECHNIQUE_INFO dict + class
# extending BaseStrategy + async ``analyze``. The body is intentionally
# trivial (always neutral) — the test cares about the loader and
# call-count invariants, not P&L.
GOOD_PYTHON_STRATEGY = '''\
```python
"""Donchian fixture — code-type integration test."""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo

TECHNIQUE_INFO = {
    "name": "donchian_codepath_fixture",
    "version": "0.1.0",
    "description": "Donchian fixture for code-path integration test",
    "author": "system",
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "status": "experimental",
    "changelog": "fixture",
}


class DonchianCodepathFixture(BaseStrategy):
    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=20)
        price = float(ohlcv[-1].close)
        return AnalysisResult(
            signal="neutral",
            confidence=0.3,
            entry_price=Decimal(str(round(price, 2))),
            stop_loss=Decimal(str(round(price * 0.99, 2))),
            take_profit=Decimal(str(round(price * 1.01, 2))),
            reasoning="fixture neutral",
            timestamp=datetime.now(),
        )
```
'''

TRADE_PRODUCING_PYTHON_STRATEGY = '''\
```python
"""Trade-producing code-type fixture."""

from datetime import datetime
from decimal import Decimal

from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo

TECHNIQUE_INFO = {
    "name": "donchian_trade_fixture",
    "version": "0.1.0",
    "description": "Trade-producing fixture for code-path integration test",
    "author": "system",
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "status": "experimental",
    "changelog": "fixture",
}


class DonchianTradeFixture(BaseStrategy):
    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
    ) -> AnalysisResult:
        self.validate_input(ohlcv, min_candles=20)
        price = Decimal(str(ohlcv[-1].close))
        if len(ohlcv) == 60:
            return AnalysisResult(
                signal="long",
                confidence=0.9,
                entry_price=price,
                stop_loss=price * Decimal("0.999"),
                take_profit=price * Decimal("1.003"),
                reasoning="fixture long breakout",
                timestamp=datetime.now(),
            )
        return AnalysisResult(
            signal="neutral",
            confidence=0.1,
            entry_price=price,
            stop_loss=price * Decimal("0.99"),
            take_profit=price * Decimal("1.01"),
            reasoning="fixture waiting",
            timestamp=datetime.now(),
        )
```
'''


def _make_code_type_loop(
    tmp_path: Path, audit_path: Path, claude_mock: AsyncMock
) -> FeedbackLoop:
    """Build a loop with the supplied ClaudeCLI mock + REAL Backtester.

    The Backtester runs end-to-end against the loaded strategy so we
    can prove that ``ClaudeCLI.analyze`` is never called per bar — if
    the backtest were silently routing through a prompt-type strategy
    it would fire ``analyze`` once per candle, blowing the call count
    past 0.
    """
    from src.ai.improver import StrategyImprover
    from src.backtest.analyzer import PerformanceAnalyzer
    from src.backtest.engine import BacktestConfig, Backtester
    from src.backtest.validator import RobustnessGate, RobustnessReport

    improver = StrategyImprover(
        claude=claude_mock,
        experimental_dir=tmp_path / "experimental",
        catalog_path=tmp_path / "no_catalog.md",
    )
    backtester = Backtester(BacktestConfig(), data_dir=tmp_path / "backtest")
    analyzer = PerformanceAnalyzer()
    gate = RobustnessGate(backtester=backtester)

    # Stub the gate to avoid OOS / walk-forward / regime / sensitivity
    # sub-runs — those would multiply backtest time without exercising
    # the per-bar code path beyond what the baseline already does.
    async def _stub_evaluate(*args, **kwargs):
        return RobustnessReport(
            overall_passed=True,
            gates=[],
            summary="stubbed pass for code-type integration",
            baseline_sharpe=1.0,
            baseline_trades=0,
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
async def test_code_type_pick_runs_without_per_bar_claude_calls(
    tmp_path: Path,
) -> None:
    """**Critical Phase 17.5 invariant.**

    A ``Pick(code_type=True)`` must:

    1. Trigger the improver's code-generation prompt (one
       ``ClaudeCLI.complete`` call total).
    2. Land on disk as a ``.py`` file under
       ``strategies/experimental/<slug>_<ts>.py``.
    3. Load cleanly via ``src.strategy.loader.load_strategy`` (the
       loader's ``.py`` dispatch path).
    4. Run end-to-end through ``Backtester.run_for_strategy`` against
       synthetic OHLCV with **zero** ``ClaudeCLI.analyze`` calls — the
       per-bar hot path is local Python, not an LLM round-trip.

    If invariant (4) ever fails the backtest is back to per-bar Claude
    calls, which is the exact failure DEBT-019 was filed to eliminate.
    The assertion ``analyze.call_count == 0`` is the load-bearing
    contract Phase 17.5 establishes.
    """
    from src.ai.claude import ClaudeCLI

    claude = AsyncMock(spec=ClaudeCLI)
    claude.complete.return_value = GOOD_PYTHON_STRATEGY
    # ``analyze`` is the per-bar entry point on PromptStrategy. A
    # code-type strategy must NEVER reach it. We track the call count
    # on this mock — anything > 0 means the per-bar LLM hot path is
    # back, and Phase 17.5 has regressed.
    claude.analyze = AsyncMock(return_value={})

    candles = _synthetic_ohlcv(300)
    exchange = _FakeExchange({"1h": candles})
    loop = _make_code_type_loop(
        tmp_path, audit_path=tmp_path / "audit.jsonl", claude_mock=claude
    )

    pick = Pick(
        slug="donchian_codepath",
        context="Donchian breakout, code-type integration test",
        timeframe="1h",
        candles=300,
        code_type=True,
    )

    results = await run_picks([pick], symbol="BTC/USDT", loop=loop, exchange=exchange)

    assert len(results) == 1
    result = results[0]
    assert result.status == LoopStatus.AWAITING_APPROVAL.value, (
        f"code-type pick should pass the (stubbed) gate; got {result.status} "
        f"with reason {result.decision_reason}"
    )
    assert result.technique_name == "donchian_codepath_fixture"

    # 1. Improver was called exactly once for code generation.
    assert claude.complete.call_count == 1, (
        "Expected exactly one ClaudeCLI.complete call (the code-"
        f"generation step); got {claude.complete.call_count}"
    )
    # The generation prompt steered toward the code branch — sanity-
    # check the canonical baseline references made it into the prompt.
    generation_prompt = claude.complete.call_args.args[0]
    assert "BaseStrategy" in generation_prompt
    assert "strategies/rsi.py" in generation_prompt

    # 2 + 3. The .py file landed under experimental/, was loaded by the
    # loader's .py dispatch path, and the loaded class is what ran.
    assert result.saved_path is not None
    saved_path = Path(result.saved_path)
    assert (
        saved_path.suffix == ".py"
    ), f"code-type generation must produce a .py file; got {saved_path}"
    assert saved_path.exists()
    # Loader reload sanity — independent of the loop's internal load.
    from src.strategy.loader import load_strategy

    reloaded = load_strategy(saved_path)
    assert reloaded.name == "donchian_codepath_fixture"
    assert reloaded.info.technique_type == "code"

    # 4. **The load-bearing assertion.** Per-bar ClaudeCLI.analyze was
    # never reached. If this trips, the backtest is silently routing
    # through an LLM hot path and Phase 17.5 has regressed.
    assert claude.analyze.call_count == 0, (
        "ClaudeCLI.analyze was invoked during the code-type backtest "
        f"({claude.analyze.call_count} calls). The whole point of "
        "code-type strategies is no LLM in the hot path. Phase 17.5 "
        "regression."
    )


@pytest.mark.asyncio
async def test_code_type_pick_produces_backtest_trade_without_claude_analyze(
    tmp_path: Path,
) -> None:
    """DEBT-049: code-type integration must exercise the trade path.

    The original load-bearing fixture was neutral-only. This companion
    fixture emits one long signal, lets the real Backtester open and
    close the trade, and still asserts zero per-bar Claude calls.
    """
    from src.ai.claude import ClaudeCLI
    from src.ai.improver import StrategyImprover
    from src.backtest.analyzer import PerformanceAnalyzer
    from src.backtest.engine import BacktestConfig, Backtester
    from src.backtest.validator import RobustnessGate, RobustnessReport
    from src.strategy.loader import load_strategy

    claude = AsyncMock(spec=ClaudeCLI)
    claude.complete.return_value = TRADE_PRODUCING_PYTHON_STRATEGY
    claude.analyze = AsyncMock(return_value={})

    captured: dict[str, object] = {}
    backtester = Backtester(BacktestConfig(), data_dir=tmp_path / "backtest")
    original_run_for_strategy = backtester.run_for_strategy

    async def _capturing_run_for_strategy(*args, **kwargs):
        result = await original_run_for_strategy(*args, **kwargs)
        captured["backtest"] = result
        return result

    backtester.run_for_strategy = _capturing_run_for_strategy  # type: ignore[assignment]
    gate = RobustnessGate(backtester=backtester)

    async def _stub_evaluate(*args, **kwargs):
        return RobustnessReport(
            overall_passed=True,
            gates=[],
            summary="stubbed pass for trade-producing code-type integration",
            baseline_sharpe=1.0,
            baseline_trades=1,
        )

    gate.evaluate = _stub_evaluate  # type: ignore[assignment]
    loop = FeedbackLoop(
        improver=StrategyImprover(
            claude=claude,
            experimental_dir=tmp_path / "experimental",
            catalog_path=tmp_path / "no_catalog.md",
        ),
        backtester=backtester,
        analyzer=PerformanceAnalyzer(),
        gate=gate,
        audit_log=AuditLog(path=tmp_path / "audit.jsonl"),
        experimental_dir=tmp_path / "experimental",
        active_dir=tmp_path / "active",
        state_dir=tmp_path / "state",
    )
    candles = _synthetic_ohlcv(120)
    exchange = _FakeExchange({"1h": candles})
    pick = Pick(
        slug="donchian_trade",
        context="Trade-producing Donchian fixture",
        timeframe="1h",
        candles=120,
        code_type=True,
    )

    results = await run_picks([pick], symbol="BTC/USDT", loop=loop, exchange=exchange)

    assert results[0].status == LoopStatus.AWAITING_APPROVAL.value
    assert results[0].technique_name == "donchian_trade_fixture"
    assert results[0].saved_path is not None

    backtest = captured["backtest"]
    assert backtest.total_trades >= 1
    assert backtest.trades[0].side == "long"
    assert backtest.trades[0].close_reason in {"take_profit", "stop_loss"}

    reloaded = load_strategy(Path(results[0].saved_path))
    assert reloaded.name == "donchian_trade_fixture"
    assert claude.complete.call_count == 1
    assert claude.analyze.call_count == 0
