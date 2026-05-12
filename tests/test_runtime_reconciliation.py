"""Tests for ``src.runtime.reconciliation`` (runtime-reconciliation unit §1).

Covers the state taxonomy classifier and the ``compute_health_report``
walker. The classifier is a pure function so the tests build dict
fixtures inline rather than seeding a full ledger — keeps the test
density at the same level as ``test_tools_backfill_paper_sl_tp.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from src.runtime.reconciliation import (
    DEFAULT_STALE_THRESHOLD_SECONDS,
    LOCKED_CONSISTENCY_EPSILON,
    LOCKED_CONSISTENCY_RELATIVE_RATIO,
    OpenTradeState,
    _locked_consistency_tolerance,
    classify_open_trade,
    compute_closed_but_malformed_count,
    compute_health_report,
)

# =============================================================================
# Helpers
# =============================================================================


def _row(
    *,
    trade_id: str = "trade-1",
    sub_account_id: str = "default",
    symbol: str | None = "BTC/USDT",
    side: str | None = "long",
    entry_quantity: str | None = "0.1",
    entry_price: str | None = "50000",
    leverage: int = 10,
    stop_loss: str | None = "49500",
    take_profit: str | None = "51500",
    performance_record_id: str | None = "perf-1",
    status: str = "open",
    entry_time: str | None = None,
    exit_price: str | None = None,
    exit_time: str | None = None,
) -> dict:
    """Build an on-disk open-trade row matching ``TradeHistory._trade_to_dict``."""
    return {
        "id": trade_id,
        "sub_account_id": sub_account_id,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "entry_quantity": entry_quantity,
        "entry_time": entry_time,
        "leverage": leverage,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "exit_price": exit_price,
        "exit_time": exit_time,
        "performance_record_id": performance_record_id,
        "status": status,
        "mode": "paper",
    }


def _seed_paper_ledger(
    data_dir: Path,
    sub_account_id: str,
    rows: list[dict],
) -> Path:
    """Write a list of trade dicts to ``<data_dir>/trades/paper/<sub>/trades.json``."""
    path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))
    return path


def _seed_balances_snapshot(
    data_dir: Path,
    sub_account_id: str,
    locked: Decimal,
    free: Decimal = Decimal("9000"),
    currency: str = "USDT",
) -> Path:
    """Write a ``balances.json`` snapshot matching ``PaperTrader._save_balances``."""
    path = data_dir / "trades" / "paper" / sub_account_id / "balances.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        currency: {
            "currency": currency,
            "free": str(free),
            "locked": str(locked),
        }
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def _seed_perf_record(
    data_dir: Path,
    sub_account_id: str,
    technique_name: str,
    record_id: str,
) -> Path:
    """Write one perf record so ``compute_health_report`` can resolve its id."""
    path = (
        data_dir / "performance" / sub_account_id / technique_name / "records.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": record_id,
            "technique_name": technique_name,
            "technique_version": "1.0.0",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "signal": "long",
            "entry_price": "50000",
            "stop_loss": "49500",
            "take_profit": "51500",
            "confidence": 0.8,
            "outcome": "pending",
            "mode": "paper",
            "sub_account_id": sub_account_id,
        }
    ]
    path.write_text(json.dumps(payload, indent=2))
    return path


# =============================================================================
# Classifier — happy path
# =============================================================================


def test_classify_monitorable_row_returns_monitorable() -> None:
    """All fields + bounds + perf-id present → monitorable."""
    row = _row()
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.MONITORABLE.value
    assert classification.missing_fields == []
    assert classification.symbol == "BTC/USDT"
    assert classification.side == "long"


def test_classify_monitorable_even_when_perf_record_missing() -> None:
    """Per the spec: perf-link miss is reported separately on the health report,
    but the per-row state stays ``monitorable`` because SL/TP are local."""
    row = _row(performance_record_id="ghost-id")
    classification = classify_open_trade(row, perf_record_ids=set())
    assert classification.state == OpenTradeState.MONITORABLE.value
    assert classification.missing_fields == []


# =============================================================================
# Classifier — degraded
# =============================================================================


def test_classify_missing_stop_loss_is_degraded() -> None:
    row = _row(stop_loss=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.DEGRADED.value
    assert classification.missing_fields == ["stop_loss"]


def test_classify_missing_take_profit_is_degraded() -> None:
    row = _row(take_profit=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.DEGRADED.value
    assert classification.missing_fields == ["take_profit"]


def test_classify_missing_both_bounds_lists_both() -> None:
    """The Fly 2026-05-13 case: 44 rows missing both SL and TP."""
    row = _row(stop_loss=None, take_profit=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.DEGRADED.value
    assert classification.missing_fields == ["stop_loss", "take_profit"]


def test_classify_nan_stop_loss_is_degraded() -> None:
    """A literal ``"NaN"`` string on SL is treated as missing, not monitorable."""
    row = _row(stop_loss="NaN")
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.DEGRADED.value
    assert "stop_loss" in classification.missing_fields


# =============================================================================
# Classifier — unrecoverable
# =============================================================================


def test_classify_missing_entry_price_is_unrecoverable() -> None:
    row = _row(entry_price=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.UNRECOVERABLE.value
    assert "entry_price" in classification.missing_fields


def test_classify_missing_side_is_unrecoverable() -> None:
    row = _row(side=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.UNRECOVERABLE.value
    assert "side" in classification.missing_fields


def test_classify_missing_symbol_is_unrecoverable() -> None:
    row = _row(symbol=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.UNRECOVERABLE.value
    assert "symbol" in classification.missing_fields


def test_classify_missing_size_is_unrecoverable() -> None:
    row = _row(entry_quantity=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.UNRECOVERABLE.value
    assert "size" in classification.missing_fields


def test_classify_unrecoverable_takes_precedence_over_degraded() -> None:
    """A row missing a core field is unrecoverable even if bounds are also missing.

    The taxonomy is mutually exclusive — unrecoverable wins because
    the operator's repair path is fundamentally different (close vs
    backfill).
    """
    row = _row(entry_price=None, stop_loss=None, take_profit=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.UNRECOVERABLE.value


# =============================================================================
# Classifier — legacy_no_perf_link
# =============================================================================


def test_classify_legacy_no_perf_link() -> None:
    """SL/TP set, all core fields present, but no perf id → legacy."""
    row = _row(performance_record_id=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.LEGACY_NO_PERF_LINK.value
    assert classification.missing_fields == ["performance_record_id"]


def test_classify_empty_string_perf_id_is_legacy() -> None:
    row = _row(performance_record_id="")
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.state == OpenTradeState.LEGACY_NO_PERF_LINK.value


# =============================================================================
# compute_health_report — payload shape
# =============================================================================


def test_compute_health_report_shape_empty_sub_account(tmp_path: Path) -> None:
    """No ledger, no perf, no balances → empty per-account block, zero totals."""
    report = compute_health_report(tmp_path, ["default"])
    assert "default" in report["report"]
    default = report["report"]["default"]
    assert default["open_trade_count"] == 0
    assert default["state_counts"] == {
        OpenTradeState.MONITORABLE.value: 0,
        OpenTradeState.DEGRADED.value: 0,
        OpenTradeState.UNRECOVERABLE.value: 0,
        OpenTradeState.LEGACY_NO_PERF_LINK.value: 0,
    }
    assert default["balance_snapshot_present"] is False
    assert default["balance_locked"] is None
    # No snapshot → not consistent (snapshot is the cross-check anchor).
    assert default["locked_consistent"] is False
    assert report["totals"]["open_trade_count"] == 0
    assert report["totals"]["any_locked_inconsistent"] is True


def test_compute_health_report_counts_each_state(tmp_path: Path) -> None:
    """One row in each of the four states is counted correctly."""
    rows = [
        _row(trade_id="mon", performance_record_id="perf-1"),
        _row(trade_id="deg", stop_loss=None, performance_record_id="perf-1"),
        _row(trade_id="unr", entry_price=None, performance_record_id="perf-1"),
        _row(trade_id="leg", performance_record_id=None),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    _seed_perf_record(tmp_path, "default", "tech_a", "perf-1")

    report = compute_health_report(tmp_path, ["default"])
    counts = report["report"]["default"]["state_counts"]
    assert counts[OpenTradeState.MONITORABLE.value] == 1
    assert counts[OpenTradeState.DEGRADED.value] == 1
    assert counts[OpenTradeState.UNRECOVERABLE.value] == 1
    assert counts[OpenTradeState.LEGACY_NO_PERF_LINK.value] == 1
    # Drill-through carries one entry per row.
    assert len(report["report"]["default"]["classifications"]) == 4


def test_compute_health_report_skips_closed_rows(tmp_path: Path) -> None:
    """A ``status=closed`` row does not appear in the report counts."""
    rows = [
        _row(trade_id="open-1"),
        _row(trade_id="closed-1", status="closed"),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    report = compute_health_report(tmp_path, ["default"])
    assert report["report"]["default"]["open_trade_count"] == 1


def test_compute_health_report_locked_consistent_within_epsilon(tmp_path: Path) -> None:
    """``balance_locked`` within the hybrid tolerance → True.

    Q3 follow-up: tolerance is now ``max(0.01, locked_sum × 0.001)``.
    An exact-match snapshot is the simplest case that stays consistent
    under either the old flat ``0.0001`` epsilon or the new hybrid rule.
    """
    # Single open row: locked = entry*qty/leverage = 50000*0.1/10 = 500
    _seed_paper_ledger(tmp_path, "default", [_row()])
    _seed_balances_snapshot(tmp_path, "default", locked=Decimal("500"))
    report = compute_health_report(tmp_path, ["default"])
    assert report["report"]["default"]["locked_consistent"] is True
    assert report["totals"]["any_locked_inconsistent"] is False


def test_compute_health_report_locked_drift_flags_inconsistent(tmp_path: Path) -> None:
    """Locked drift beyond the hybrid tolerance flags the sub-account as inconsistent.

    locked_sum = 500 → tolerance = max(0.01, 500 × 0.001) = 0.5. A drift
    of 10 USD comfortably exceeds the tolerance and should trip the
    inconsistency flag.
    """
    _seed_paper_ledger(tmp_path, "default", [_row()])
    drift = Decimal("10")  # 20x the relative tolerance at locked_sum=500
    _seed_balances_snapshot(
        tmp_path, "default", locked=Decimal("500") + drift
    )
    report = compute_health_report(tmp_path, ["default"])
    assert report["report"]["default"]["locked_consistent"] is False
    assert report["totals"]["any_locked_inconsistent"] is True


def test_compute_health_report_perf_link_resolution_counts(tmp_path: Path) -> None:
    """``perf_links_resolved`` / ``perf_links_missing`` count perf-id presence."""
    rows = [
        _row(trade_id="resolved", performance_record_id="perf-1"),
        _row(trade_id="ghost", performance_record_id="ghost-id"),
        _row(trade_id="legacy", performance_record_id=None),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    _seed_perf_record(tmp_path, "default", "tech_a", "perf-1")

    report = compute_health_report(tmp_path, ["default"])
    default = report["report"]["default"]
    assert default["perf_links_resolved"] == 1
    assert default["perf_links_missing"] == 1


def test_compute_health_report_aggregates_totals_across_sub_accounts(
    tmp_path: Path,
) -> None:
    """Totals are the sum of per-account counters."""
    _seed_paper_ledger(tmp_path, "alpha", [_row(stop_loss=None)])  # degraded
    _seed_paper_ledger(tmp_path, "beta", [_row(entry_price=None)])  # unrecoverable
    report = compute_health_report(tmp_path, ["alpha", "beta"])
    totals = report["totals"]
    assert totals["open_trade_count"] == 2
    assert totals["state_counts"][OpenTradeState.DEGRADED.value] == 1
    assert totals["state_counts"][OpenTradeState.UNRECOVERABLE.value] == 1
    assert len(totals["classifications"]) == 2


# =============================================================================
# Q3 follow-up: hybrid locked-consistency tolerance
# =============================================================================


def test_locked_consistency_tolerance_hybrid_scales_with_notional() -> None:
    """``_locked_consistency_tolerance`` is ``max(floor, locked_sum × ratio)``.

    - Tiny accounts (``locked_sum × ratio`` below the floor) get the
      penny floor so a single $100 paper fill's fee math drift doesn't
      trip the consistency check.
    - Large accounts get a relative slope so ordinary Decimal rounding
      across a busy live ledger doesn't masquerade as a real drift.
    """
    # Floor regime: locked_sum=5 → 5 × 0.001 = 0.005 < 0.01 floor.
    assert _locked_consistency_tolerance(Decimal("5")) == LOCKED_CONSISTENCY_EPSILON
    # Crossover point: locked_sum=10 → 10 × 0.001 = 0.01 = floor (kept on floor).
    assert _locked_consistency_tolerance(Decimal("10")) == LOCKED_CONSISTENCY_EPSILON
    # Relative regime: locked_sum=49000 → 49000 × 0.001 = 49.
    assert (
        _locked_consistency_tolerance(Decimal("49000"))
        == Decimal("49000") * LOCKED_CONSISTENCY_RELATIVE_RATIO
    )
    # Large-account regime: locked_sum=1_000_000 → tolerance = 1000.
    assert _locked_consistency_tolerance(Decimal("1000000")) == Decimal("1000")


def test_locked_consistency_floor_protects_tiny_accounts(tmp_path: Path) -> None:
    """A $0.04 fee-level drift on a tiny account stays consistent.

    The pre-Q3 0.0001 USD epsilon would have flagged this as drift; the
    new 0.01 USD floor accommodates the paper trader's taker fee math
    (0.04% × $100 = $0.04) without masking a real bookkeeping bug.
    """
    _seed_paper_ledger(tmp_path, "default", [_row()])
    # locked_sum = 500; drift = 0.005 sits below the 0.01 floor.
    _seed_balances_snapshot(
        tmp_path, "default", locked=Decimal("500") + Decimal("0.005")
    )
    report = compute_health_report(tmp_path, ["default"])
    assert report["report"]["default"]["locked_consistent"] is True


def test_locked_consistency_relative_slope_scales_with_account(
    tmp_path: Path,
) -> None:
    """At scale the tolerance is 0.1% of locked_sum, not a flat penny.

    Seed two open rows so locked_sum > 0, then drift the snapshot by an
    amount above the floor but within ``locked_sum × ratio``. The flat
    pre-Q3 epsilon (and the pre-Q3 ``0.0001``) would have flagged
    inconsistent; the hybrid tolerance keeps the report green.
    """
    # 10 open rows of entry=50000 qty=0.1 lev=10 → 10 × 500 = 5000 locked.
    rows = [_row(trade_id=f"t-{i}") for i in range(10)]
    _seed_paper_ledger(tmp_path, "default", rows)
    # Relative tolerance at locked_sum=5000 is 5000 × 0.001 = 5.0 USD.
    # Drift of $2 is comfortably above the 0.01 floor but inside 5.0.
    _seed_balances_snapshot(
        tmp_path, "default", locked=Decimal("5000") + Decimal("2")
    )
    report = compute_health_report(tmp_path, ["default"])
    assert report["report"]["default"]["locked_consistent"] is True


# =============================================================================
# DEBT-064: stale-but-valid auxiliary signal
# =============================================================================


def test_classify_open_trade_marks_stale_when_last_seen_exceeds_threshold() -> None:
    """A row whose ``entry_time`` is 8 days old → ``is_stale=True``.

    DEBT-064 v1 fallback: ``TradeHistory`` has no ``last_seen_at`` today
    so the classifier uses ``entry_time`` as the most-recent timestamp.
    With the default 7-day threshold, an 8-day-old entry trips the flag.
    """
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    eight_days_ago = (now - timedelta(days=8)).isoformat()
    row = _row(entry_time=eight_days_ago)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"}, now=now)
    assert classification.is_stale is True
    # Auxiliary signal is independent of the state classification —
    # the row is still ``monitorable``.
    assert classification.state == OpenTradeState.MONITORABLE.value


def test_classify_open_trade_marks_not_stale_when_within_threshold() -> None:
    """A row whose ``entry_time`` is 1 day old → ``is_stale=False``."""
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    one_day_ago = (now - timedelta(days=1)).isoformat()
    row = _row(entry_time=one_day_ago)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"}, now=now)
    assert classification.is_stale is False


def test_classify_open_trade_is_stale_defaults_false_when_entry_time_missing() -> None:
    """A row with no ``entry_time`` falls through as ``is_stale=False``.

    The classifier's read-only contract is "log and continue"; a missing
    or malformed timestamp must not break the report. The row is still
    accounted for in the per-state counts.
    """
    row = _row(entry_time=None)
    classification = classify_open_trade(row, perf_record_ids={"perf-1"})
    assert classification.is_stale is False


def test_classify_open_trade_respects_custom_stale_threshold() -> None:
    """An explicit ``stale_threshold_seconds`` overrides the default."""
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).isoformat()
    row = _row(entry_time=two_hours_ago)
    # Custom 1h threshold flips the stale flag for a 2h-old entry.
    classification = classify_open_trade(
        row,
        perf_record_ids={"perf-1"},
        now=now,
        stale_threshold_seconds=3600,
    )
    assert classification.is_stale is True
    # ...but the default 7d threshold leaves it fresh.
    classification_default = classify_open_trade(
        row, perf_record_ids={"perf-1"}, now=now
    )
    assert classification_default.is_stale is False


def test_classify_stale_flag_set_alongside_unrecoverable_state() -> None:
    """A row can be both ``unrecoverable`` *and* stale.

    Auxiliary signal is computed independently of the state classifier
    path; the operator gets both signals on the same row.
    """
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    eight_days_ago = (now - timedelta(days=8)).isoformat()
    row = _row(entry_price=None, entry_time=eight_days_ago)
    classification = classify_open_trade(row, perf_record_ids=set(), now=now)
    assert classification.state == OpenTradeState.UNRECOVERABLE.value
    assert classification.is_stale is True


# =============================================================================
# DEBT-064: closed-but-malformed sweep
# =============================================================================


def test_compute_closed_but_malformed_count_finds_rows_with_null_exit_fields(
    tmp_path: Path,
) -> None:
    """A ``status="closed"`` row missing ``exit_price`` or ``exit_time`` is counted.

    Mirrors the half-closed shape that ``close_unrecoverable_paper_trades``
    can write on partial failure (per the DEBT-064 description).
    """
    rows = [
        # Open row — never counted by the malformed-closed sweep.
        _row(trade_id="open-1"),
        # Closed with both exit fields missing — the canonical half-closed.
        _row(
            trade_id="half-closed-a",
            status="closed",
            exit_price=None,
            exit_time=None,
        ),
        # Closed with only exit_time missing — also counted.
        _row(
            trade_id="half-closed-b",
            status="closed",
            exit_price="51000",
            exit_time=None,
        ),
        # Closed with only exit_price missing — also counted.
        _row(
            trade_id="half-closed-c",
            status="closed",
            exit_price=None,
            exit_time="2026-05-12T12:00:00+00:00",
        ),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    assert compute_closed_but_malformed_count(tmp_path, "default") == 3


def test_compute_closed_but_malformed_count_ignores_well_formed_closed_rows(
    tmp_path: Path,
) -> None:
    """A properly-closed row (both exit fields present) is NOT counted."""
    rows = [
        _row(
            trade_id="good-close",
            status="closed",
            exit_price="51000",
            exit_time="2026-05-12T12:00:00+00:00",
        ),
        # Also: an open row with no exit fields is not malformed-closed.
        _row(trade_id="open-1"),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    assert compute_closed_but_malformed_count(tmp_path, "default") == 0


def test_compute_closed_but_malformed_count_handles_missing_ledger(
    tmp_path: Path,
) -> None:
    """No ledger on disk → 0, no exception (read-only log-and-continue)."""
    assert compute_closed_but_malformed_count(tmp_path, "ghost") == 0


# =============================================================================
# DEBT-064: end-to-end — health report surfaces both auxiliary signals
# =============================================================================


def test_health_report_surfaces_stale_and_malformed_counts(tmp_path: Path) -> None:
    """``compute_health_report`` exposes both DEBT-064 aux signals.

    Per-account ``stale_count`` and ``closed_but_malformed_count`` plus
    matching totals — independent of the 4-state ``state_counts`` block.
    """
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    stale = (now - timedelta(days=10)).isoformat()
    rows = [
        # Fresh + monitorable.
        _row(trade_id="fresh-mon", entry_time=fresh),
        # Stale-but-valid (still monitorable).
        _row(trade_id="stale-mon", entry_time=stale),
        # Stale + unrecoverable (both signals fire on same row).
        _row(trade_id="stale-unr", entry_price=None, entry_time=stale),
        # Half-closed row counted by the separate sweep.
        _row(
            trade_id="half-closed",
            status="closed",
            exit_price=None,
            exit_time=None,
        ),
    ]
    _seed_paper_ledger(tmp_path, "default", rows)

    report = compute_health_report(tmp_path, ["default"], now=now)
    per_account = report["report"]["default"]
    # 3 open rows + 1 closed-malformed (closed rows are filtered out of
    # the open-trade walker, so open_trade_count counts the 3 open rows).
    assert per_account["open_trade_count"] == 3
    # Two of the three open rows have stale entry_time.
    assert per_account["stale_count"] == 2
    # One closed row with null exit fields.
    assert per_account["closed_but_malformed_count"] == 1

    # Totals mirror per-account at a single-sub-account fixture.
    totals = report["totals"]
    assert totals["stale_count"] == 2
    assert totals["closed_but_malformed_count"] == 1


def test_health_report_stale_count_zero_when_all_rows_fresh(tmp_path: Path) -> None:
    """A ledger of fresh rows reports ``stale_count == 0``.

    Pins the negative case — the aux signal must not false-positive on
    healthy ledgers (which would defeat its triage value).
    """
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=12)).isoformat()
    rows = [
        _row(trade_id=f"fresh-{i}", entry_time=fresh) for i in range(3)
    ]
    _seed_paper_ledger(tmp_path, "default", rows)
    report = compute_health_report(tmp_path, ["default"], now=now)
    assert report["report"]["default"]["stale_count"] == 0
    assert report["totals"]["stale_count"] == 0


def test_default_stale_threshold_constant_is_seven_days() -> None:
    """DEBT-064: pin the 7-day default so dashboards / docs can reference it."""
    assert DEFAULT_STALE_THRESHOLD_SECONDS == 7 * 24 * 3600
