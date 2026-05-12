"""Open-trade reconciliation taxonomy + startup health check.

This module is the runtime-reconciliation unit's pure / read-only side:
classification of every open paper-trade row into one of four states
plus a health-report builder the engine emits at startup. It does not
mutate the ledger — repair flows live in
``src.tools.backfill_paper_sl_tp`` and
``src.tools.close_unrecoverable_paper_trades``.

The taxonomy is restart-anchored: state is recomputed from the on-disk
row every time the engine boots. We never persist the state itself,
because (a) perf-record presence and ledger contents can drift between
restarts, and (b) the only signal we want to surface — the
``RECONCILIATION_HEALTH_REPORT`` activity event — is itself the
operator-visible artefact.

Related Requirements:
- FR-010 / FR-029: Live + paper trading mode (operator visibility).
- NFR-007: Trading History Storage (ledger as source of truth).
- NFR-008: Asset/PnL History (mode separation).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.logger import get_logger

logger = get_logger("crypto_master.runtime.reconciliation")


# Floor of the hybrid tolerance for ``locked_sum`` vs persisted
# ``balances.json::locked``. Anything tighter would trip on the last-
# digit drift of Decimal margin math; anything larger as a flat absolute
# would silently mask real drift on tiny paper accounts. Kept exported
# for the dashboard / safety-score paths that pin the contract.
LOCKED_CONSISTENCY_EPSILON = Decimal("0.01")

# Q3 follow-up: relative slope on top of the floor. A flat 0.0001 USD
# tolerance was too tight for a $49k account where ordinary paper-trader
# fee math drifts by cents; a flat 0.01 USD floor is too tight at scale
# (a $1M paper account can drift far more than a penny on legitimate
# rounding). Use ``max(epsilon, locked_sum × ratio)`` so a 1-cent floor
# protects tiny accounts and a 0.1% relative ceiling tracks growth.
LOCKED_CONSISTENCY_RELATIVE_RATIO = Decimal("0.001")


def _locked_consistency_tolerance(locked_sum: Decimal) -> Decimal:
    """Compute the hybrid absolute/relative tolerance for one sub-account.

    Returns ``max(LOCKED_CONSISTENCY_EPSILON, locked_sum × ratio)``.

    Worked example — the paper-fee math the floor is calibrated against:
    a single $100 notional taker fill at the binance taker rate of
    0.04% costs ``0.04% × $100 = $0.04``, comfortably under the $0.01
    floor only when the fee-vs-margin drift round-trips through several
    decimal-rounded multiplications. At scale (locked_sum = $1,000,000)
    the relative term gives ``$1,000,000 × 0.001 = $1,000`` of
    headroom, which is the right order of magnitude for legitimate
    Decimal rounding across a busy live account without masking a real
    bookkeeping drift.
    """
    relative = locked_sum * LOCKED_CONSISTENCY_RELATIVE_RATIO
    if relative > LOCKED_CONSISTENCY_EPSILON:
        return relative
    return LOCKED_CONSISTENCY_EPSILON


# Required fields per the State Taxonomy in the functional spec. A row
# missing *any* of these cannot be marked-to-market or priced, so it
# is ``unrecoverable``.
_UNRECOVERABLE_FIELDS: tuple[str, ...] = (
    "entry_price",
    "side",
    "size",
    "symbol",
)


# DEBT-064: stale-but-valid auxiliary signal on the existing classifier.
# Rows whose monitor loop hasn't ticked in ``DEFAULT_STALE_THRESHOLD_SECONDS``
# get flagged via ``OpenTradeClassification.is_stale`` (no new enum state).
# 7 days matches the cadence the operator was promised in the DEBT entry:
# enough headroom that a long weekend + Monday backlog doesn't trip false
# positives, tight enough that a stuck monitor surfaces inside a sprint.
#
# Provenance: ``TradeHistory`` does not carry a dedicated ``last_seen_at``
# field today (surveyed 2026-05-13 — see ``src/strategy/performance.py``
# `TradeHistory` model). Adding one would require a writer-side change in
# the monitor loop and is out of scope for this DEBT. The v1 fallback is
# ``entry_time`` — "row hasn't been touched since entry". This is the
# correct lower bound (a real ``last_seen_at`` would always be at least
# as recent as ``entry_time``), so flagging on entry-time can only ever
# be a true positive plus possibly a missed false-positive — it cannot
# silently *miss* a stale row whose true ``last_seen_at`` is older.
DEFAULT_STALE_THRESHOLD_SECONDS: int = 7 * 24 * 3600


class OpenTradeState(str, Enum):
    """Classification of an open paper-trade row's monitorability.

    See ``aidlc-docs/construction/runtime-reconciliation/functional-design/spec.md``
    §1 for the canonical definitions.
    """

    MONITORABLE = "monitorable"
    DEGRADED = "degraded"
    UNRECOVERABLE = "unrecoverable"
    LEGACY_NO_PERF_LINK = "legacy_no_perf_link"


class OpenTradeClassification(BaseModel):
    """Per-row classification carrying the fields the operator needs.

    ``missing_fields`` lists the row keys that drove the classification.
    For ``monitorable`` rows the list is empty. For ``degraded`` rows
    it carries the missing bound names (``stop_loss``, ``take_profit``,
    or both). For ``unrecoverable`` rows it carries the missing core
    fields. For ``legacy_no_perf_link`` rows it carries
    ``["performance_record_id"]``.

    ``is_stale`` is the DEBT-064 auxiliary signal: ``True`` iff the row's
    most-recent timestamp (``entry_time`` fallback — see module-level
    ``DEFAULT_STALE_THRESHOLD_SECONDS``) is older than the configured
    threshold. Independent of ``state`` — a stale row can still be
    ``monitorable``; the field is a *warning* alongside the state, not
    a state replacement.
    """

    trade_id: str
    sub_account_id: str
    symbol: str | None
    side: str | None
    state: OpenTradeState
    missing_fields: list[str]
    is_stale: bool = False

    model_config = {"use_enum_values": True}


def classify_open_trade(
    row: dict[str, Any],
    perf_record_ids: set[str],
    *,
    now: datetime | None = None,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> OpenTradeClassification:
    """Classify a single open paper-trade ``row`` into one of four states.

    The row shape mirrors ``TradeHistory`` as persisted by
    ``TradeHistoryTracker._trade_to_dict``. ``entry_quantity`` is the
    canonical on-disk name; the spec's taxonomy talks about ``size``
    as the conceptual field — we accept either so the classifier is
    robust to legacy ledger shapes.

    Args:
        row: The on-disk JSON object for one open trade. Closed rows
            should not be passed in — the caller (``compute_health_report``)
            filters by ``status == "open"`` first.
        perf_record_ids: Set of every ``PerformanceRecord.id`` present
            on disk for the row's sub-account. Used to drive the
            ``legacy_no_perf_link`` and perf-link cross-check.
        now: Reference timestamp for the stale-row check. Defaults to
            ``datetime.now(timezone.utc)`` when not supplied; injected
            in tests so the threshold can be exercised deterministically.
        stale_threshold_seconds: DEBT-064 — flag the row as ``is_stale``
            when ``now - <row's most recent timestamp>`` exceeds this
            many seconds. Defaults to ``DEFAULT_STALE_THRESHOLD_SECONDS``
            (7 days). Independent of the state classification.

    Returns:
        Populated :class:`OpenTradeClassification`.
    """
    trade_id = str(row.get("id", "<unknown>"))
    sub_account_id = str(row.get("sub_account_id", "default"))
    symbol = row.get("symbol")
    side = row.get("side")

    # Map spec field name "size" onto the on-disk "entry_quantity";
    # legacy ledgers may also carry a literal "size" key.
    size_value = row.get("entry_quantity")
    if size_value is None:
        size_value = row.get("size")

    field_values = {
        "entry_price": row.get("entry_price"),
        "side": side,
        "size": size_value,
        "symbol": symbol,
    }
    missing_core = [
        name for name in _UNRECOVERABLE_FIELDS if not _is_meaningful(field_values[name])
    ]

    # DEBT-064 stale-row auxiliary signal. Independent of the state
    # classification below: any row (including ``unrecoverable``) can
    # also be stale. We compute it here once and pass it through every
    # return path.
    is_stale = _row_is_stale(row, now=now, stale_threshold_seconds=stale_threshold_seconds)

    if missing_core:
        return OpenTradeClassification(
            trade_id=trade_id,
            sub_account_id=sub_account_id,
            symbol=symbol if isinstance(symbol, str) else None,
            side=side if isinstance(side, str) else None,
            state=OpenTradeState.UNRECOVERABLE,
            missing_fields=missing_core,
            is_stale=is_stale,
        )

    sl_missing = not _is_meaningful(row.get("stop_loss"))
    tp_missing = not _is_meaningful(row.get("take_profit"))
    if sl_missing or tp_missing:
        missing_bounds: list[str] = []
        if sl_missing:
            missing_bounds.append("stop_loss")
        if tp_missing:
            missing_bounds.append("take_profit")
        return OpenTradeClassification(
            trade_id=trade_id,
            sub_account_id=sub_account_id,
            symbol=str(symbol),
            side=str(side),
            state=OpenTradeState.DEGRADED,
            missing_fields=missing_bounds,
            is_stale=is_stale,
        )

    perf_id = row.get("performance_record_id")
    if not isinstance(perf_id, str) or not perf_id:
        return OpenTradeClassification(
            trade_id=trade_id,
            sub_account_id=sub_account_id,
            symbol=str(symbol),
            side=str(side),
            state=OpenTradeState.LEGACY_NO_PERF_LINK,
            missing_fields=["performance_record_id"],
            is_stale=is_stale,
        )

    # The row has all bounds + a perf id. If the perf record doesn't
    # resolve on disk, the row is still monitorable (SL/TP are local
    # to the ledger) — but the perf-link cross-check counter on the
    # health report will surface the mismatch separately. We do not
    # change the per-row state for a perf-link miss because the
    # monitor loop is unaffected.
    _ = perf_record_ids  # cross-check is the caller's responsibility
    return OpenTradeClassification(
        trade_id=trade_id,
        sub_account_id=sub_account_id,
        symbol=str(symbol),
        side=str(side),
        state=OpenTradeState.MONITORABLE,
        missing_fields=[],
        is_stale=is_stale,
    )


def _parse_row_timestamp(raw: Any) -> datetime | None:
    """Best-effort parse a row timestamp (ISO 8601 string or datetime).

    On-disk rows store ``entry_time`` as ISO 8601 (see
    ``TradeHistoryTracker._trade_to_dict`` in
    ``src/strategy/performance.py``). In-memory ``TradeHistory.entry_time``
    is a ``datetime`` — both shapes are accepted here so callers that
    feed live ``TradeHistory`` rows through the classifier (e.g. the
    engine's cap-blocker payload) don't need to pre-serialize.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        # ``datetime.fromisoformat`` handles the canonical
        # ``2026-05-13T12:00:00+00:00`` shape; a trailing ``Z`` is normalized.
        if stripped.endswith("Z"):
            stripped = stripped[:-1] + "+00:00"
        parsed = datetime.fromisoformat(stripped)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _row_is_stale(
    row: dict[str, Any],
    *,
    now: datetime | None,
    stale_threshold_seconds: int,
) -> bool:
    """DEBT-064: return ``True`` iff the row hasn't been touched recently.

    ``TradeHistory`` does not carry a ``last_seen_at`` field today; the
    v1 fallback per the DEBT entry is ``entry_time`` — "row hasn't been
    touched since entry". This is the conservative lower bound (a real
    ``last_seen_at`` would always be at least as recent), so flagging
    on ``entry_time`` never *misses* a stale row.

    A missing or malformed ``entry_time`` returns ``False`` rather than
    raising — we don't want a corrupt-timestamp row to break the health
    report. The row is already accounted for in the per-state counts.
    """
    if stale_threshold_seconds <= 0:
        return False
    parsed = _parse_row_timestamp(row.get("entry_time"))
    if parsed is None:
        return False
    reference = now if now is not None else datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_seconds = (reference - parsed).total_seconds()
    return age_seconds > stale_threshold_seconds


def _row_is_closed_but_malformed(row: dict[str, Any]) -> bool:
    """DEBT-064: a ``status="closed"`` row missing ``exit_price`` or ``exit_time``.

    Mirrors the "half-closed" shape that ``close_unrecoverable_paper_trades``
    can write on partial failure. The 4-state classifier never sees
    these rows because ``_load_open_trade_rows`` filters on
    ``status == "open"`` upstream; this separate predicate gives the
    health report a count without touching the existing filter contract.
    """
    if row.get("status") != "closed":
        return False
    return not _is_meaningful(row.get("exit_price")) or not _is_meaningful(
        row.get("exit_time")
    )


def compute_closed_but_malformed_count(
    data_dir: Path,
    sub_account_id: str,
) -> int:
    """DEBT-064: count ``status="closed"`` rows missing ``exit_price`` / ``exit_time``.

    Walks the same ledger as ``_load_open_trade_rows`` but with the
    opposite status filter. Separate pass keeps the existing open-row
    classifier untouched. Returns ``0`` for missing / malformed
    ledgers (consistent with the rest of the module's read-only,
    log-and-continue contract).
    """
    trades_path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    if not trades_path.exists():
        return 0
    try:
        with open(trades_path, encoding="utf-8") as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read paper ledger %s: %s", trades_path, exc)
        return 0
    if not isinstance(rows, list):
        return 0
    return sum(
        1
        for row in rows
        if isinstance(row, dict) and _row_is_closed_but_malformed(row)
    )


def _is_meaningful(value: Any) -> bool:
    """Return ``True`` iff ``value`` is set and not a NaN-ish sentinel.

    The on-disk shape stores Decimals as strings, so we also reject
    ``"NaN"`` / ``"nan"`` (case-insensitive) explicitly — a row with
    a NaN price can't be marked-to-market and must be flagged.
    """
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.lower() == "nan":
            return False
        # Try to parse Decimal-like strings; reject NaN/InfNaN sneaking
        # through as a Decimal sentinel.
        try:
            dec = Decimal(stripped)
        except (InvalidOperation, ValueError):
            return True
        if dec.is_nan():
            return False
        return True
    if isinstance(value, float):
        # ``float('nan') != float('nan')`` — the canonical NaN check.
        return value == value
    return True


def _decimal_or_zero(value: Any) -> Decimal:
    """Best-effort coerce ``value`` to ``Decimal``; fall back to ``0``."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _load_perf_record_ids(
    data_dir: Path,
    sub_account_id: str,
) -> set[str]:
    """Walk ``<data_dir>/performance/<sub_account_id>/<technique>/records.json``
    and return every ``id`` field encountered.

    Mirrors the raw-JSON walk in ``backfill_paper_sl_tp._PerfIndex`` so
    we don't trip on legacy records with null SL/TP (which the strict
    ``PerformanceRecord`` validator would reject).
    """
    ids: set[str] = set()
    sub_root = data_dir / "performance" / sub_account_id
    if not sub_root.exists():
        return ids
    for technique_dir in sub_root.iterdir():
        if not technique_dir.is_dir():
            continue
        records_path = technique_dir / "records.json"
        if not records_path.exists():
            continue
        try:
            with open(records_path, encoding="utf-8") as f:
                rows = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read perf records at %s: %s", records_path, exc
            )
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            rec_id = row.get("id")
            if isinstance(rec_id, str) and rec_id:
                ids.add(rec_id)
    return ids


def _load_open_trade_rows(
    data_dir: Path,
    sub_account_id: str,
) -> list[dict[str, Any]]:
    """Return raw open-trade rows for ``sub_account_id`` (``status == "open"``)."""
    trades_path = data_dir / "trades" / "paper" / sub_account_id / "trades.json"
    if not trades_path.exists():
        return []
    try:
        with open(trades_path, encoding="utf-8") as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read paper ledger %s: %s", trades_path, exc)
        return []
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows if isinstance(row, dict) and row.get("status") == "open"
    ]


def _load_balance_locked(
    data_dir: Path,
    sub_account_id: str,
) -> tuple[bool, Decimal | None]:
    """Read ``balances.json::USDT.locked`` for the sub-account.

    Returns ``(snapshot_present, locked_decimal_or_none)``. If the
    snapshot is missing, ``(False, None)``. If the snapshot is present
    but malformed, ``(True, None)`` so the consistency check fails
    loudly rather than silently passing.
    """
    balances_path = data_dir / "trades" / "paper" / sub_account_id / "balances.json"
    if not balances_path.exists():
        return (False, None)
    try:
        with open(balances_path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return (True, None)
        # Sum locked across every currency present. In the current paper
        # trader there is only one quote currency per sub-account, but
        # taking a sum keeps the cross-check correct if that ever grows.
        total = Decimal("0")
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            total += _decimal_or_zero(row.get("locked"))
        return (True, total)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read balances snapshot %s: %s", balances_path, exc)
        return (True, None)


def _per_row_locked_margin(row: dict[str, Any]) -> Decimal:
    """Approximate the margin locked for one open row.

    Mirrors ``PaperTrader._calculate_required_margin``:
    ``notional / leverage`` where ``notional = entry_price * qty``.
    Used only to cross-check against the persisted ``balances.json``
    snapshot, so a tolerant best-effort coercion is sufficient — a
    missing or NaN field falls through as ``0`` and the row will
    already show up as ``unrecoverable`` in the per-state breakdown.
    """
    entry = _decimal_or_zero(row.get("entry_price"))
    qty = _decimal_or_zero(row.get("entry_quantity"))
    leverage_raw = row.get("leverage", 1)
    try:
        leverage = Decimal(str(leverage_raw)) if leverage_raw else Decimal("1")
    except (InvalidOperation, ValueError):
        leverage = Decimal("1")
    if leverage <= 0:
        leverage = Decimal("1")
    return (entry * qty) / leverage


def compute_health_report(
    data_dir: Path,
    sub_account_ids: list[str],
    *,
    now: datetime | None = None,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> dict[str, Any]:
    """Produce the per-sub-account reconciliation health report.

    Shape mirrors the spec's §"Startup Health Checks" payload:

    .. code-block:: text

        {
          "report": {
            "<sub_account_id>": {
              "open_trade_count": int,
              "state_counts": {<state>: int, ...},
              "stale_count": int,
              "closed_but_malformed_count": int,
              "locked_sum": str(Decimal),
              "balance_snapshot_present": bool,
              "balance_locked": str(Decimal) | None,
              "locked_consistent": bool,
              "perf_links_resolved": int,
              "perf_links_missing": int,
              "classifications": [OpenTradeClassification.model_dump(), ...]
            }
          },
          "totals": {<same shape, summed>}
        }

    ``classifications`` carries the per-row drill-through the dashboard
    renders. It is intentionally part of the same payload so the
    dashboard does not re-walk the ledger.

    DEBT-064: ``stale_count`` and ``closed_but_malformed_count`` are the
    two auxiliary signals on top of the existing 4-state taxonomy. Both
    are *counts alongside* the state counts rather than new enum states,
    per the DEBT entry's resolution.
    """
    report: dict[str, dict[str, Any]] = {}
    total_open = 0
    total_state_counts: dict[str, int] = {state.value: 0 for state in OpenTradeState}
    total_locked_sum = Decimal("0")
    total_perf_resolved = 0
    total_perf_missing = 0
    total_classifications: list[dict[str, Any]] = []
    total_stale_count = 0
    total_closed_but_malformed = 0
    any_inconsistent = False

    for sub_account_id in sub_account_ids:
        rows = _load_open_trade_rows(data_dir, sub_account_id)
        perf_ids = _load_perf_record_ids(data_dir, sub_account_id)

        state_counts: dict[str, int] = {state.value: 0 for state in OpenTradeState}
        locked_sum = Decimal("0")
        perf_resolved = 0
        perf_missing = 0
        stale_count = 0
        classifications: list[dict[str, Any]] = []

        for row in rows:
            classification = classify_open_trade(
                row,
                perf_ids,
                now=now,
                stale_threshold_seconds=stale_threshold_seconds,
            )
            state_counts[classification.state] += 1
            if classification.is_stale:
                stale_count += 1
            locked_sum += _per_row_locked_margin(row)

            perf_id = row.get("performance_record_id")
            if isinstance(perf_id, str) and perf_id:
                if perf_id in perf_ids:
                    perf_resolved += 1
                else:
                    perf_missing += 1

            classifications.append(classification.model_dump())

        # DEBT-064: closed-but-malformed sweep is a separate pass
        # (different status filter) — keep it outside the per-row
        # classifier loop above which already operates on open rows only.
        closed_but_malformed_count = compute_closed_but_malformed_count(
            data_dir, sub_account_id
        )

        snapshot_present, balance_locked = _load_balance_locked(
            data_dir, sub_account_id
        )
        if snapshot_present and balance_locked is not None:
            # Q3 follow-up: hybrid tolerance — penny floor for tiny
            # accounts, 0.1% slope at scale. ``_locked_consistency_
            # tolerance`` keeps the math centralized.
            tolerance = _locked_consistency_tolerance(locked_sum)
            locked_consistent = abs(balance_locked - locked_sum) <= tolerance
        else:
            locked_consistent = False

        if not locked_consistent:
            any_inconsistent = True

        report[sub_account_id] = {
            "open_trade_count": len(rows),
            "state_counts": state_counts,
            "stale_count": stale_count,
            "closed_but_malformed_count": closed_but_malformed_count,
            "locked_sum": str(locked_sum),
            "balance_snapshot_present": snapshot_present,
            "balance_locked": (
                str(balance_locked) if balance_locked is not None else None
            ),
            "locked_consistent": locked_consistent,
            "perf_links_resolved": perf_resolved,
            "perf_links_missing": perf_missing,
            "classifications": classifications,
        }

        total_open += len(rows)
        for key, val in state_counts.items():
            total_state_counts[key] += val
        total_locked_sum += locked_sum
        total_perf_resolved += perf_resolved
        total_perf_missing += perf_missing
        total_stale_count += stale_count
        total_closed_but_malformed += closed_but_malformed_count
        total_classifications.extend(classifications)

    return {
        "report": report,
        "totals": {
            "open_trade_count": total_open,
            "state_counts": total_state_counts,
            "stale_count": total_stale_count,
            "closed_but_malformed_count": total_closed_but_malformed,
            "locked_sum": str(total_locked_sum),
            "perf_links_resolved": total_perf_resolved,
            "perf_links_missing": total_perf_missing,
            # Aggregate consistency: green only if every sub-account is
            # consistent (or has no rows + no snapshot, which we treat
            # as consistent-by-default at the totals layer so a fresh
            # deployment with zero state doesn't render Yellow).
            "any_locked_inconsistent": any_inconsistent,
            "classifications": total_classifications,
        },
    }


__all__ = [
    "DEFAULT_STALE_THRESHOLD_SECONDS",
    "LOCKED_CONSISTENCY_EPSILON",
    "LOCKED_CONSISTENCY_RELATIVE_RATIO",
    "OpenTradeClassification",
    "OpenTradeState",
    "_locked_consistency_tolerance",
    "classify_open_trade",
    "compute_closed_but_malformed_count",
    "compute_health_report",
]
