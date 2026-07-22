"""Smoke tests for ``scripts/run_robustness_gate.py``.

The script is operator tooling; production runs hit Binance's public
API. These tests exercise the runner against an in-memory synthetic
OHLCV stream so the strategy-list resolution, end-to-end report
shape, and CLI plumbing are covered without touching the network.
"""

from __future__ import annotations

import io
import random
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scripts import run_robustness_gate
from scripts.run_robustness_gate import (
    STRATEGIES_DIR,
    STRATEGY_SPECS,
    main,
    render_report,
    run_all,
    run_all_snapshot,
)
from src.backtest.snapshot import (
    Snapshot,
    SnapshotMetadata,
    baseline_directory,
    save_snapshot,
)
from src.backtest.snapshot_v2 import load_snapshot_versioned
from src.backtest.validator import GateResult, RobustnessReport
from src.exchange.derivatives import (
    FundingRate,
    OpenInterestHistory,
    OpenInterestPoint,
)
from src.models import OHLCV

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _synthetic_ohlcv(
    n: int,
    *,
    seed: int = 42,
    start_price: float = 30000.0,
    delta: timedelta = timedelta(hours=1),
) -> list[OHLCV]:
    """Deterministic random-walk OHLCV stream.

    Mirrors the fixture in ``test_scripts_backtest_baselines.py`` so the
    two operator scripts share assumptions about candle shape.
    """
    rng = random.Random(seed)
    start = datetime(2026, 1, 1)
    candles: list[OHLCV] = []
    price = start_price
    for i in range(n):
        step = rng.gauss(0, 0.01)
        new_price = max(price * (1 + step), 100.0)
        high = max(price, new_price) * 1.005
        low = min(price, new_price) * 0.995
        candles.append(
            OHLCV(
                timestamp=start + i * delta,
                open=Decimal(str(round(price, 2))),
                high=Decimal(str(round(high, 2))),
                low=Decimal(str(round(low, 2))),
                close=Decimal(str(round(new_price, 2))),
                volume=Decimal("1000"),
            )
        )
        price = new_price
    return candles


class _FakeExchange:
    """Stand-in for :class:`BinanceExchange` that serves canned candles.

    Minimal surface (``connect``/``disconnect``/``get_ohlcv``) — the
    runner injects this directly so no network call is attempted.
    """

    def __init__(self, candles_by_tf: dict[str, list[OHLCV]]) -> None:
        self._candles_by_tf = candles_by_tf
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: int | None = None,
    ) -> list[OHLCV]:
        candles = self._candles_by_tf.get(timeframe)
        if candles is None:
            raise AssertionError(f"unexpected timeframe {timeframe!r}")
        page_limit = min(limit, 1500)
        if since is None:
            return candles[-page_limit:]
        for i, candle in enumerate(candles):
            since_ms = int(candle.timestamp.timestamp() * 1000)
            if since_ms >= since:
                return candles[i : i + page_limit]
        return []


class _FakeDerivativesExchange(_FakeExchange):
    def __init__(
        self,
        candles_by_tf: dict[str, list[OHLCV]],
        funding: list[FundingRate],
        open_interest: OpenInterestHistory,
    ) -> None:
        super().__init__(candles_by_tf)
        self.funding = funding
        self.open_interest = open_interest
        self.funding_requests: list[tuple[int, int | None]] = []
        self.oi_requests: list[tuple[int | None, int | None]] = []

    async def get_funding_rate_history(
        self,
        symbol: str,
        since: int,
        limit: int = 1000,
        *,
        until: int | None = None,
    ) -> list[FundingRate]:
        del symbol, limit
        self.funding_requests.append((since, until))
        return list(self.funding)

    async def get_open_interest_history(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = 500,
        *,
        until: int | None = None,
    ) -> OpenInterestHistory:
        del symbol, timeframe, limit
        self.oi_requests.append((since, until))
        return self.open_interest


@pytest.fixture
def fake_exchange() -> _FakeExchange:
    """Fake exchange seeded with one stream per used timeframe.

    Sized comfortably above the longest 90-day window in the spec so
    each gate has enough data to evaluate.
    """
    return _FakeExchange(
        {
            "1h": _synthetic_ohlcv(2200, seed=1, delta=timedelta(hours=1)),
            "4h": _synthetic_ohlcv(560, seed=2, delta=timedelta(hours=4)),
            "15m": _synthetic_ohlcv(8800, seed=3, delta=timedelta(minutes=15)),
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_runner_loads_target_strategies() -> None:
    """Every hardcoded ``StrategySpec`` resolves to an existing file.

    A typo in the spec table would silently no-op a strategy on the
    real run. Pin the existence of each file so the runner stays in
    sync with what's on disk.
    """
    # P0~P4 + DEBT-060/DEBT-061 cohort (7) + raschke_holy_grail, ma_crossover (2)
    assert len(STRATEGY_SPECS) == 9
    seen_names: set[str] = set()
    for spec in STRATEGY_SPECS:
        path = STRATEGIES_DIR / spec.strategy_file
        assert path.exists(), f"missing strategy file for {spec.name}: {path}"
        assert spec.name not in seen_names, f"duplicate spec name {spec.name}"
        seen_names.add(spec.name)


async def test_runner_returns_report_for_synthetic_ohlcv(
    fake_exchange: _FakeExchange,
) -> None:
    """End-to-end: one strategy → a populated ``RobustnessReport``.

    Picks ``rsi_universal`` because it has both an ``__init__`` factory
    (so the sensitivity gate runs) and a 1h cadence (so the synthetic
    1h stream covers it).

    No assertion on PASSED/FAILED — synthetic random-walk data is
    unrealistic and the gate's verdict is not the unit under test.
    """
    spec = next(s for s in STRATEGY_SPECS if s.name == "rsi_universal")

    report = await run_robustness_gate.evaluate_strategy(
        spec,
        fake_exchange,
        symbol="BTC/USDT",
        # Trim runtime: 60 days ≈ 1440 1h bars, plenty for every gate.
        window_days=60,
    )

    assert isinstance(report, RobustnessReport)
    # Four gates always run regardless of outcome.
    assert {g.name for g in report.gates} == {
        "oos",
        "walk_forward",
        "regime",
        "sensitivity",
    }
    # Sensitivity gate should have *fired* (not skipped) because we
    # supplied both a factory and a non-empty grid.
    sens = next(g for g in report.gates if g.name == "sensitivity")
    assert sens.status.value in {"passed", "failed"}, (
        f"sensitivity should have fired for rsi_universal; got "
        f"{sens.status} ({sens.reason})"
    )


async def test_runner_skips_sensitivity_when_grid_empty(
    fake_exchange: _FakeExchange,
) -> None:
    """Strategies with empty ``param_grid`` should SKIP sensitivity.

    Pins the contract called out in the script's docstring so
    refactors that accidentally pass an empty dict where a None was
    intended don't silently break the gate.
    """
    spec = next(s for s in STRATEGY_SPECS if s.name == "vwap_mean_reversion")
    report = await run_robustness_gate.evaluate_strategy(
        spec,
        fake_exchange,
        symbol="BTC/USDT",
        window_days=60,
    )
    sens = next(g for g in report.gates if g.name == "sensitivity")
    assert sens.status.value == "skipped"


async def test_runner_main_dry_invocation(
    fake_exchange: _FakeExchange,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``run_all`` + ``render_report`` produce a markdown summary.

    Drives the same code path as ``main()`` but injects the fake
    exchange, so the test never reaches the ``BinanceExchange``
    construction branch.
    """
    reports = await run_all(
        exchange=fake_exchange,
        only_strategy="rsi_universal",
        window_days=60,
    )
    assert len(reports) == 1
    spec, report = reports[0]
    assert spec.name == "rsi_universal"

    rendered = render_report(reports)
    assert "# Robustness gate verdicts" in rendered
    assert "`rsi_universal`" in rendered
    assert "## Summary" in rendered
    # Every sub-gate appears in the summary table header.
    assert "OOS" in rendered
    assert "Walk-fwd" in rendered
    assert "Regime" in rendered
    assert "Sensitivity" in rendered


async def test_runner_continues_after_single_strategy_failure(
    monkeypatch: pytest.MonkeyPatch,
    fake_exchange: _FakeExchange,
) -> None:
    """A raise in one ``evaluate_strategy`` does not abort the run.

    Operators want every verdict — failures get wrapped as a single
    FAILED placeholder gate so the summary table stays complete.
    """

    async def _boom(*args: object, **kwargs: object) -> RobustnessReport:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(run_robustness_gate, "evaluate_strategy", _boom)

    reports = await run_all(
        exchange=fake_exchange,
        only_strategy="rsi_universal",
    )
    assert len(reports) == 1
    _, report = reports[0]
    assert not report.overall_passed
    assert report.gates[0].name == "runner"
    assert "RuntimeError" in report.gates[0].reason
    assert "synthetic failure" not in report.model_dump_json()


def test_main_without_live_flag_exits_nonzero_with_message(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing snapshot data fails loudly without falling through to live."""
    rc = main(["--snapshot", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no live fallback" in captured.out


def test_main_unknown_strategy_raises(
    fake_exchange: _FakeExchange,
) -> None:
    """``--strategy unknown`` should raise rather than silently no-op."""
    import asyncio

    with pytest.raises(ValueError, match="Unknown strategy"):
        asyncio.run(
            run_all(
                exchange=fake_exchange,
                only_strategy="not_a_real_strategy",
            )
        )


def test_main_live_routes_through_run_all(
    monkeypatch: pytest.MonkeyPatch,
    fake_exchange: _FakeExchange,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--live`` invokes ``run_all`` and prints the rendered report.

    Patches ``run_all`` to bypass the live-Binance construction so the
    test is hermetic; asserts the markdown summary lands on stdout.
    """
    captured: dict[str, object] = {}

    async def _stub_run_all(**kwargs: object) -> list[tuple[object, object]]:
        captured["kwargs"] = kwargs
        # Hand back one synthetic (spec, report) pair through the real
        # evaluate path so the rendered output contains real markup.
        spec = next(s for s in STRATEGY_SPECS if s.name == "rsi_universal")
        report = await run_robustness_gate.evaluate_strategy(
            spec,
            fake_exchange,
            symbol="BTC/USDT",
            window_days=60,
        )
        return [(spec, report)]

    monkeypatch.setattr(run_robustness_gate, "run_all", _stub_run_all)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--live", "--strategy", "rsi_universal", "--window-days", "60"])
    assert rc == 0
    output = buf.getvalue()
    assert "# Robustness gate verdicts" in output
    assert "`rsi_universal`" in output
    # CLI args reach the runner.
    assert captured["kwargs"]["only_strategy"] == "rsi_universal"
    assert captured["kwargs"]["window_days"] == 60


@pytest.mark.asyncio
async def test_snapshot_runner_loads_pinned_source_without_exchange(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candles = [
        candle.model_copy(
            update={"timestamp": candle.timestamp.replace(tzinfo=timezone.utc)}
        )
        for candle in _synthetic_ohlcv(100, seed=7)
    ]
    target = baseline_directory(tmp_path, "BTC/USDT", "1h")
    save_snapshot(
        Snapshot(
            metadata=SnapshotMetadata(
                symbol="BTC/USDT",
                timeframe="1h",
                source="binance",
                fetched_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                candle_count=len(candles),
                first_timestamp=candles[0].timestamp,
                last_timestamp=candles[-1].timestamp,
                fetcher_version="test",
            ),
            ohlcv=candles,
        ),
        target,
    )
    captured: dict[str, object] = {}

    async def _stub(spec: object, replay: object, **kwargs: object) -> RobustnessReport:
        captured["replay"] = replay
        captured["kwargs"] = kwargs
        return RobustnessReport(overall_passed=True, gates=[], summary="passed")

    monkeypatch.setattr(run_robustness_gate, "evaluate_snapshot_strategy", _stub)

    reports = await run_all_snapshot(
        snapshot_root=tmp_path,
        only_strategy="rsi_universal",
        seed=17,
    )

    assert len(reports) == 1
    replay = captured["replay"]
    assert isinstance(replay, run_robustness_gate.SnapshotReplaySource)
    assert replay.schema_version == 1
    assert captured["kwargs"] == {
        "strategies_dir": STRATEGIES_DIR,
        "seed": 17,
    }


@pytest.mark.asyncio
async def test_snapshot_runner_forwards_exact_generation_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generation_id = "a" * 64
    captured: dict[str, object] = {}
    replay = object()

    def _load(
        directory: Path,
        *,
        generation_id: str | None = None,
    ) -> object:
        captured["directory"] = directory
        captured["generation_id"] = generation_id
        return replay

    async def _evaluate(
        spec: object, source: object, **kwargs: object
    ) -> RobustnessReport:
        captured["source"] = source
        return RobustnessReport(overall_passed=True, gates=[], summary="passed")

    monkeypatch.setattr(
        run_robustness_gate.SnapshotReplaySource,
        "from_directory",
        _load,
    )
    monkeypatch.setattr(run_robustness_gate, "evaluate_snapshot_strategy", _evaluate)

    reports = await run_all_snapshot(
        snapshot_root=tmp_path,
        only_strategy="rsi_universal",
        generation_ids={"rsi_universal": generation_id},
    )

    assert len(reports) == 1
    assert captured["generation_id"] == generation_id
    assert captured["source"] is replay


@pytest.mark.asyncio
async def test_refresh_snapshot_v2_transfers_requested_derivatives_range(
    tmp_path: Path,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        OHLCV(
            timestamp=start + timedelta(hours=4 * index),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for index in range(6)
    ]
    funding = [
        FundingRate(
            symbol="BTC/USDT",
            timestamp=start + timedelta(hours=8 * index),
            rate=Decimal("0.0001"),
        )
        for index in range(3)
    ]
    oi_points = tuple(
        OpenInterestPoint(
            symbol="BTC/USDT",
            timestamp=start + timedelta(hours=index),
            open_interest=Decimal("1000") + index,
        )
        for index in range(2, 21)
    )
    oi = OpenInterestHistory(
        symbol="BTC/USDT",
        requested_since=start,
        requested_until=start + timedelta(hours=20),
        actual_since=oi_points[0].timestamp,
        actual_until=oi_points[-1].timestamp,
        truncated_at_venue_retention=True,
        points=oi_points,
    )
    exchange = _FakeDerivativesExchange({"4h": candles}, funding, oi)

    written = await run_robustness_gate.refresh_snapshots_v2(
        snapshot_root=tmp_path,
        exchange=exchange,
        only_strategy="rsi_4h",
        window_days=1,
    )

    assert len(written) == 1
    target, generation_id = written[0]
    loaded = load_snapshot_versioned(target, generation_id=generation_id)
    assert loaded.schema_version == 2
    assert loaded.snapshot_v2 is not None
    assert loaded.snapshot_v2.ohlcv == tuple(candles)
    assert loaded.snapshot_v2.funding == tuple(funding)
    assert loaded.snapshot_v2.open_interest == oi
    assert loaded.snapshot_v2.metadata.open_interest.truncated_at_venue_retention
    expected_bounds = (
        int(candles[0].timestamp.timestamp() * 1000),
        int(candles[-1].timestamp.timestamp() * 1000),
    )
    assert exchange.funding_requests == [expected_bounds]
    assert exchange.oi_requests == [expected_bounds]


@pytest.mark.asyncio
async def test_refresh_reload_replay_report_is_hermetic_and_deterministic(
    tmp_path: Path,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        candle.model_copy(update={"timestamp": start + timedelta(hours=index)})
        for index, candle in enumerate(_synthetic_ohlcv(120, seed=19))
    ]
    funding = [
        FundingRate(
            symbol="BTC/USDT",
            timestamp=start + timedelta(hours=8 * index),
            rate=Decimal("0.0001"),
        )
        for index in range(15)
    ]
    oi_points = tuple(
        OpenInterestPoint(
            symbol="BTC/USDT",
            timestamp=start + timedelta(hours=index),
            open_interest=Decimal("1000") + index,
        )
        for index in range(120)
    )
    oi = OpenInterestHistory(
        symbol="BTC/USDT",
        requested_since=start,
        requested_until=candles[-1].timestamp,
        actual_since=oi_points[0].timestamp,
        actual_until=oi_points[-1].timestamp,
        points=oi_points,
    )
    exchange = _FakeDerivativesExchange({"1h": candles}, funding, oi)

    written = await run_robustness_gate.refresh_snapshots_v2(
        snapshot_root=tmp_path,
        exchange=exchange,
        only_strategy="rsi_universal",
        window_days=5,
    )
    generation_id = written[0][1]
    first = await run_all_snapshot(
        snapshot_root=tmp_path,
        only_strategy="rsi_universal",
        generation_ids={"rsi_universal": generation_id},
        seed=29,
    )
    second = await run_all_snapshot(
        snapshot_root=tmp_path,
        only_strategy="rsi_universal",
        generation_ids={"rsi_universal": generation_id},
        seed=29,
    )

    first_report = first[0][1]
    second_report = second[0][1]
    assert first_report.replay_identity is not None
    assert first_report.replay_identity.generation_id == generation_id
    assert first_report.configuration_digest is not None
    assert first_report.seed == 29
    assert all(gate.name != "runner" for gate in first_report.gates)
    assert first_report.model_dump(mode="json") == second_report.model_dump(mode="json")


def test_generation_id_parser_and_insufficient_rendering() -> None:
    parsed = run_robustness_gate.parse_generation_ids([f"rsi_universal={'a' * 64}"])
    assert parsed == {"rsi_universal": "a" * 64}
    with pytest.raises(ValueError, match="64-lowercase-hex"):
        run_robustness_gate.parse_generation_ids(["rsi_universal=BAD"])

    spec = next(item for item in STRATEGY_SPECS if item.name == "rsi_universal")
    report = RobustnessReport(
        overall_passed=False,
        gates=[
            GateResult(
                name="market_context",
                status=run_robustness_gate.GateStatus.INSUFFICIENT_DATA,
                reason="missing",
            )
        ],
        summary="insufficient",
    )
    rendered = render_report([(spec, report)], mode="snapshot-pinned")
    assert "INSUFFICIENT_DATA" in rendered
    assert "snapshot-pinned" in rendered


def test_runner_failure_report_does_not_serialize_raw_exception_text() -> None:
    secret = "apiKey=top-secret"
    local_path = "/private/tmp/operator/snapshot"
    report = run_robustness_gate._failed_placeholder_report(
        RuntimeError(f"{secret} {local_path}?signature=deadbeef")
    )
    payload = report.model_dump_json()

    assert not report.overall_passed
    assert report.gates[0].details == {"error_type": "RuntimeError"}
    assert secret not in payload
    assert local_path not in payload
    assert "signature" not in payload
