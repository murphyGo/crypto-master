"""Smoke test for ``scripts/backtest_baselines.py``.

The script itself is operator tooling that hits Binance's public API;
this test exercises the script's machinery against an in-memory
synthetic OHLCV stream so we can verify the artefact layout, the
summary contract, and the docs-table rewriter without touching the
network.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scripts import backtest_baselines
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
    """Generate a deterministic random-walk OHLCV stream.

    Walk is symmetric so the strategies produce a mix of long/short
    triggers; the high/low are placed half a percent above/below the
    close so SL/TP intra-bar checks have something to catch.
    """
    rng = random.Random(seed)
    start = datetime(2026, 1, 1)
    candles: list[OHLCV] = []
    price = start_price
    for i in range(n):
        # ~1% std-dev steps; bounded so the price can't drift to zero.
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


class _FakeBinanceExchange:
    """Stand-in for :class:`BinanceExchange` that serves canned candles.

    Implements just the surface ``run_baseline`` touches:
    ``get_ohlcv``, ``connect``, ``disconnect``. Since the smoke test
    constructs the exchange itself and passes it through the
    ``exchange=`` injection, the script never tries to dial Binance.
    """

    def __init__(self, candles_by_tf: dict[str, list[OHLCV]]) -> None:
        self._candles_by_tf = candles_by_tf
        self.connected = False

    async def connect(self) -> None:  # pragma: no cover - not used by the test
        self.connected = True

    async def disconnect(self) -> None:  # pragma: no cover - not used
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
        # Mirror the real BinanceExchange clamp.
        page_limit = min(limit, 1500)
        if since is None:
            # Most-recent page (no anchor) — same shape as Binance default.
            return candles[-page_limit:]
        # ``since`` is inclusive on start. Walk forward.
        for i, candle in enumerate(candles):
            since_dt_ms = int(candle.timestamp.timestamp() * 1000)
            if since_dt_ms >= since:
                return candles[i : i + page_limit]
        return []


@pytest.fixture
def fake_exchange() -> _FakeBinanceExchange:
    """A fake exchange seeded with one candle stream per used timeframe."""
    return _FakeBinanceExchange(
        {
            "1h": _synthetic_ohlcv(2200, seed=1, delta=timedelta(hours=1)),
            "4h": _synthetic_ohlcv(550, seed=2, delta=timedelta(hours=4)),
            "15m": _synthetic_ohlcv(2900, seed=3, delta=timedelta(minutes=15)),
        }
    )


@pytest.fixture
def baselines_doc(tmp_path: Path) -> Path:
    """A throwaway copy of docs/baselines.md for table-rewrite tests.

    We copy the real doc so the regex matches the canonical header.
    """
    src = Path(__file__).resolve().parents[1] / "docs" / "baselines.md"
    dst = tmp_path / "baselines.md"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


# ---------------------------------------------------------------------------
# Rendering helpers — pure, no I/O
# ---------------------------------------------------------------------------


def test_render_table_includes_every_baseline_row() -> None:
    summaries = [
        {
            "technique_name": "rsi_universal",
            "symbol": "BTC/USDT",
            "period_label": "3mo 1h",
            "win_rate": 0.55,
            "total_return_percent": 12.34,
            "sharpe_ratio": 1.23,
            "max_drawdown_percent": 8.45,
            "total_trades": 20,
        },
        {
            "technique_name": "rsi_4h",
            "symbol": "BTC/USDT",
            "period_label": "3mo 4h",
            "win_rate": 0.48,
            "total_return_percent": -2.0,
            "sharpe_ratio": None,  # < 2 trades
            "max_drawdown_percent": 5.0,
            "total_trades": 1,
        },
    ]
    text = backtest_baselines.render_table(summaries)
    assert "`rsi_universal`" in text
    assert "`rsi_4h`" in text
    # Win rate rendered as 55.00% / 48.00%; Sharpe falls back to "n/a".
    assert "55.00%" in text
    assert "48.00%" in text
    assert "n/a" in text
    # Header preserved verbatim — the regex relies on it.
    assert text.startswith("| Strategy | Symbol | Period |")


def test_update_baselines_doc_replaces_tbd_rows(baselines_doc: Path) -> None:
    """A populated table replaces the TBD rows but leaves prose intact."""
    summaries = [
        {
            "technique_name": "rsi_universal",
            "symbol": "BTC/USDT",
            "period_label": "3mo 1h",
            "win_rate": 0.5,
            "total_return_percent": 1.0,
            "sharpe_ratio": 0.7,
            "max_drawdown_percent": 4.2,
            "total_trades": 10,
        }
    ]
    new_text = backtest_baselines.update_baselines_doc(
        summaries, doc_path=baselines_doc
    )
    # TBD rows gone, real numbers in.
    assert "_TBD_" not in new_text
    assert "50.00%" in new_text
    assert "0.70" in new_text
    # Prose surrounding the table is preserved.
    assert "Reference numbers" in new_text
    assert (
        "These numbers are the bar each LLM-driven technique needs to clear."
        in new_text
    )


# ---------------------------------------------------------------------------
# fetch_ohlcv_window — pagination logic
# ---------------------------------------------------------------------------


async def test_fetch_ohlcv_window_short_window_uses_get_ohlcv(
    fake_exchange: _FakeBinanceExchange,
) -> None:
    """When total_candles ≤ 1500, the helper just calls get_ohlcv."""
    out = await backtest_baselines.fetch_ohlcv_window(
        exchange=fake_exchange,  # type: ignore[arg-type]
        symbol="BTC/USDT",
        timeframe="1h",
        total_candles=500,
    )
    assert len(out) == 500
    # Ascending order preserved.
    assert all(out[i].timestamp <= out[i + 1].timestamp for i in range(len(out) - 1))


# ---------------------------------------------------------------------------
# End-to-end smoke: run_all writes every artefact
# ---------------------------------------------------------------------------


async def test_run_all_writes_expected_artifacts(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    output_root = tmp_path / "baselines"

    summaries = await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=True,
        doc_path=baselines_doc,
        exchange=fake_exchange,  # type: ignore[arg-type]
    )

    # One summary per spec, in declared order.
    assert [s["technique_name"] for s in summaries] == [
        spec.technique_name for spec in backtest_baselines.BASELINES
    ]

    expected_keys = {
        "win_rate",
        "sharpe_ratio",
        "max_drawdown_percent",
        "total_return_percent",
    }
    for spec, _summary in zip(backtest_baselines.BASELINES, summaries, strict=True):
        baseline_dir = output_root / spec.technique_name
        assert (baseline_dir / "result.json").exists()
        assert (baseline_dir / "analysis.md").exists()
        assert (baseline_dir / "summary.json").exists()

        # summary.json holds the four metrics the docs table consumes.
        on_disk = json.loads((baseline_dir / "summary.json").read_text())
        assert expected_keys.issubset(on_disk.keys())
        assert on_disk["technique_name"] == spec.technique_name
        assert on_disk["period_label"] == spec.period_label
        # win_rate is a float in [0, 1] (or 0 when no trades fired).
        assert 0.0 <= on_disk["win_rate"] <= 1.0
        # mdd is a non-negative percent.
        assert on_disk["max_drawdown_percent"] >= 0.0
        # sharpe is either None (n/a) or a finite float.
        sharpe = on_disk["sharpe_ratio"]
        assert sharpe is None or math.isfinite(sharpe)

        # result.json round-trips through BacktestResult.
        from src.backtest.engine import BacktestResult

        result_payload = json.loads((baseline_dir / "result.json").read_text())
        BacktestResult(**result_payload)  # raises if shape is wrong

        # analysis.md contains the standard report header.
        report = (baseline_dir / "analysis.md").read_text()
        assert report.startswith("# Backtest Report:")

    # docs table was rewritten — TBDs gone, baseline names present.
    doc_text = baselines_doc.read_text()
    assert "_TBD_" not in doc_text
    for spec in backtest_baselines.BASELINES:
        assert f"`{spec.technique_name}`" in doc_text


async def test_run_all_idempotent_overwrites_artifacts(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    """Re-running the script overwrites prior artefacts cleanly."""
    output_root = tmp_path / "baselines"

    await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=False,
        doc_path=baselines_doc,
        exchange=fake_exchange,  # type: ignore[arg-type]
    )
    # Mark each result.json with a sentinel so we can tell the second
    # run actually overwrote them.
    for spec in backtest_baselines.BASELINES:
        (output_root / spec.technique_name / "result.json").write_text(
            "STALE", encoding="utf-8"
        )

    await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=False,
        doc_path=baselines_doc,
        exchange=fake_exchange,  # type: ignore[arg-type]
    )
    for spec in backtest_baselines.BASELINES:
        text = (output_root / spec.technique_name / "result.json").read_text()
        assert text != "STALE"
        # Re-parsable as JSON => overwritten with fresh content.
        json.loads(text)


async def test_run_all_skips_doc_update_when_disabled(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    output_root = tmp_path / "baselines"
    original = baselines_doc.read_text()

    await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=False,
        doc_path=baselines_doc,
        exchange=fake_exchange,  # type: ignore[arg-type]
    )

    # Doc untouched — still has the TBD placeholders.
    assert baselines_doc.read_text() == original
    assert "_TBD_" in baselines_doc.read_text()


# ---------------------------------------------------------------------------
# Phase 25.2 — snapshot-pinned regenerator
# ---------------------------------------------------------------------------


def _populate_snapshot_root(
    snapshot_root: Path,
    fake_exchange: _FakeBinanceExchange,
    *,
    fetched_at: datetime | None = None,
) -> None:
    """Materialise a snapshot dataset on disk seeded from the fake exchange.

    Mirrors what ``--refresh-snapshot`` would write but stays in-test
    so we never touch live Binance. Walks every (symbol, timeframe)
    pair declared in ``BASELINES``, takes the matching synthetic
    candle stream out of the fake exchange, and saves a snapshot
    directory underneath ``snapshot_root``.
    """
    from src.backtest.snapshot import (
        Snapshot,
        SnapshotMetadata,
        baseline_directory,
        save_snapshot,
    )
    from src.utils.time import ensure_utc, now_utc

    when = ensure_utc(fetched_at or now_utc())
    pairs = sorted(
        {(spec.symbol, spec.timeframe) for spec in backtest_baselines.BASELINES}
    )
    for symbol, timeframe in pairs:
        # Make every row UTC-aware (matches the snapshot-loader contract).
        rows = [
            OHLCV(
                timestamp=ensure_utc(c.timestamp),
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in fake_exchange._candles_by_tf[timeframe]
        ]
        metadata = SnapshotMetadata(
            symbol=symbol,
            timeframe=timeframe,
            source="binance",
            fetched_at=when,
            candle_count=len(rows),
            first_timestamp=rows[0].timestamp,
            last_timestamp=rows[-1].timestamp,
            fetcher_version="phase-25.2-test",
        )
        snapshot = Snapshot(metadata=metadata, ohlcv=rows)
        save_snapshot(snapshot, baseline_directory(snapshot_root, symbol, timeframe))


async def test_run_all_snapshot_root_uses_snapshot_loader(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    """``snapshot_root`` short-circuits the live-exchange path."""
    snapshot_root = tmp_path / "snapshots"
    _populate_snapshot_root(snapshot_root, fake_exchange)
    output_root = tmp_path / "baselines"

    summaries = await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=False,
        doc_path=baselines_doc,
        snapshot_root=snapshot_root,
    )
    # Every baseline produced a summary; no live BinanceExchange was
    # constructed (would have raised inside ``connect`` without
    # network).
    assert [s["technique_name"] for s in summaries] == [
        spec.technique_name for spec in backtest_baselines.BASELINES
    ]


async def test_run_all_snapshot_missing_directory_raises(
    tmp_path: Path,
    baselines_doc: Path,
) -> None:
    """Missing snapshot path surfaces a SnapshotValidationError."""
    from src.backtest.snapshot import SnapshotValidationError

    snapshot_root = tmp_path / "snapshots"  # never populated
    output_root = tmp_path / "baselines"

    with pytest.raises(SnapshotValidationError):
        await backtest_baselines.run_all(
            output_root=output_root,
            update_doc=False,
            doc_path=baselines_doc,
            snapshot_root=snapshot_root,
        )


async def test_run_all_snapshot_stale_fails_loud(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    """A snapshot older than max_snapshot_age_days raises RuntimeError."""
    snapshot_root = tmp_path / "snapshots"
    # Stamp the snapshot 60 days ago — well outside the default 30-day
    # active-use window.
    stale_when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _populate_snapshot_root(snapshot_root, fake_exchange, fetched_at=stale_when)
    output_root = tmp_path / "baselines"

    with pytest.raises(RuntimeError, match="older than"):
        await backtest_baselines.run_all(
            output_root=output_root,
            update_doc=False,
            doc_path=baselines_doc,
            snapshot_root=snapshot_root,
            max_snapshot_age_days=30,
        )


async def test_run_all_snapshot_fresh_within_window_passes(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A snapshot just inside the freshness window runs normally."""
    snapshot_root = tmp_path / "snapshots"
    # Stamp the snapshot 5 days ago — well inside the 30-day window.
    fresh_when = datetime.now(timezone.utc) - timedelta(days=5)
    _populate_snapshot_root(snapshot_root, fake_exchange, fetched_at=fresh_when)
    output_root = tmp_path / "baselines"

    summaries = await backtest_baselines.run_all(
        output_root=output_root,
        update_doc=False,
        doc_path=baselines_doc,
        snapshot_root=snapshot_root,
        max_snapshot_age_days=30,
    )
    assert len(summaries) == len(backtest_baselines.BASELINES)


async def test_refresh_snapshots_writes_via_save_snapshot(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
) -> None:
    """``refresh_snapshots`` builds Snapshot objects and persists them."""
    snapshot_root = tmp_path / "snapshots"

    written = await backtest_baselines.refresh_snapshots(
        snapshot_root=snapshot_root,
        exchange=fake_exchange,  # type: ignore[arg-type]
    )

    # One write per unique (symbol, timeframe) pair in BASELINES.
    pairs = sorted(
        {(spec.symbol, spec.timeframe) for spec in backtest_baselines.BASELINES}
    )
    assert len(written) == len(pairs)
    for path in written:
        assert (path / "ohlcv.csv").exists()
        assert (path / "metadata.json").exists()
        # Round-trips through the loader.
        from src.backtest.snapshot import load_snapshot

        snap = load_snapshot(path)
        assert snap.metadata.fetcher_version == "phase-25.2"
        # Quant carry-over: refresh-time must be UTC-aware.
        assert snap.metadata.fetched_at.tzinfo is not None


async def test_cross_operator_determinism_byte_identical(
    tmp_path: Path,
    fake_exchange: _FakeBinanceExchange,
    baselines_doc: Path,
) -> None:
    """Same snapshot run twice → byte-identical result.json files.

    The reproducibility contract Phase 25 hinges on. If this ever
    fails, the regenerator has acquired a non-deterministic input
    (clock, RNG seed, dict-order leak) and the snapshot-pinned
    promise is broken.

    ``BacktestResult.run_id`` and ``Trade.trade_id`` are
    intentionally UUID-stamped (each run is a distinct ledger
    artefact), so we scrub those identifiers before comparison and
    assert that every other field is byte-identical. ``summary.json``
    has no UUIDs and is compared byte-for-byte.
    """
    snapshot_root = tmp_path / "snapshots"
    _populate_snapshot_root(snapshot_root, fake_exchange)

    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"

    await backtest_baselines.run_all(
        output_root=out_a,
        update_doc=False,
        doc_path=baselines_doc,
        snapshot_root=snapshot_root,
    )
    await backtest_baselines.run_all(
        output_root=out_b,
        update_doc=False,
        doc_path=baselines_doc,
        snapshot_root=snapshot_root,
    )

    def _scrub_run_id(payload: dict) -> dict:
        """Drop UUID fields whose drift is by-design (not an input)."""
        clone = dict(payload)
        clone.pop("run_id", None)
        clone["trades"] = [
            {k: v for k, v in trade.items() if k != "trade_id"}
            for trade in clone.get("trades", [])
        ]
        return clone

    for spec in backtest_baselines.BASELINES:
        a_payload = json.loads(
            (out_a / spec.technique_name / "result.json").read_text()
        )
        b_payload = json.loads(
            (out_b / spec.technique_name / "result.json").read_text()
        )
        # All inputs were the same snapshot; everything except UUID
        # identifiers must match exactly. The metrics, the trade
        # ledger, the equity curve, the timestamps — every bit of it.
        assert _scrub_run_id(a_payload) == _scrub_run_id(b_payload), (
            f"{spec.technique_name}: result.json drift between runs — "
            "non-determinism in the regenerator"
        )
        # summary.json has no UUIDs — pin byte equality directly.
        a_sum = (out_a / spec.technique_name / "summary.json").read_bytes()
        b_sum = (out_b / spec.technique_name / "summary.json").read_bytes()
        assert a_sum == b_sum, f"{spec.technique_name}: summary.json drift between runs"


# ---------------------------------------------------------------------------
# SnapshotExchange — slice-bounds enforcement (quant carry-over)
# ---------------------------------------------------------------------------


async def test_snapshot_exchange_clamps_limit_to_snapshot_length() -> None:
    """A ``limit`` larger than the snapshot returns the whole snapshot."""
    from src.backtest.snapshot import (
        Snapshot,
        SnapshotExchange,
        SnapshotMetadata,
    )

    rows = _synthetic_ohlcv(50, seed=10, delta=timedelta(hours=1))
    # Make rows UTC-aware (matches snapshot-loader contract).
    from src.utils.time import ensure_utc

    rows = [
        OHLCV(
            timestamp=ensure_utc(c.timestamp),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in rows
    ]
    metadata = SnapshotMetadata(
        symbol="BTC/USDT",
        timeframe="1h",
        source="binance",
        fetched_at=ensure_utc(datetime.now(timezone.utc)),
        candle_count=50,
        first_timestamp=rows[0].timestamp,
        last_timestamp=rows[-1].timestamp,
        fetcher_version="test",
    )
    exch = SnapshotExchange(
        {("BTC/USDT", "1h"): Snapshot(metadata=metadata, ohlcv=rows)}
    )

    out = await exch.get_ohlcv("BTC/USDT", "1h", limit=10_000)
    # Clamped to the snapshot length, not the requested limit.
    assert len(out) == 50


async def test_snapshot_exchange_refuses_extrapolation_past_last_timestamp() -> None:
    """A ``since`` past ``last_timestamp`` returns an empty list."""
    from src.backtest.snapshot import (
        Snapshot,
        SnapshotExchange,
        SnapshotMetadata,
    )
    from src.utils.time import ensure_utc

    rows = _synthetic_ohlcv(20, seed=11, delta=timedelta(hours=1))
    rows = [
        OHLCV(
            timestamp=ensure_utc(c.timestamp),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in rows
    ]
    metadata = SnapshotMetadata(
        symbol="BTC/USDT",
        timeframe="1h",
        source="binance",
        fetched_at=ensure_utc(datetime.now(timezone.utc)),
        candle_count=20,
        first_timestamp=rows[0].timestamp,
        last_timestamp=rows[-1].timestamp,
        fetcher_version="test",
    )
    exch = SnapshotExchange(
        {("BTC/USDT", "1h"): Snapshot(metadata=metadata, ohlcv=rows)}
    )

    last_ms = int(rows[-1].timestamp.timestamp() * 1000)
    # One hour past the last bar — strictly outside the snapshot.
    future_since = last_ms + 60 * 60 * 1000
    out = await exch.get_ohlcv("BTC/USDT", "1h", limit=100, since=future_since)
    assert out == []


async def test_snapshot_exchange_unknown_pair_raises_keyerror() -> None:
    """Asking for a pair not in the loaded set names what is missing."""
    from src.backtest.snapshot import SnapshotExchange

    exch = SnapshotExchange({})
    with pytest.raises(KeyError, match="no snapshot loaded"):
        await exch.get_ohlcv("ETH/USDT", "1h", limit=10)


# ---------------------------------------------------------------------------
# CLI smoke — argparse surface
# ---------------------------------------------------------------------------


def test_cli_snapshot_and_refresh_are_mutually_exclusive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--snapshot`` and ``--refresh-snapshot`` cannot both be set."""
    with pytest.raises(SystemExit):
        backtest_baselines.main(["--snapshot", str(tmp_path), "--refresh-snapshot"])
