"""Compact, bounded read-side projections; runtime writers are unchanged."""

from __future__ import annotations

import heapq
import json
import re
import sys
from collections.abc import Generator
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from src.config import get_settings
from src.dashboard.read_models import Limits, Query, utc_now
from src.dashboard.sources import Source, discover
from src.proposal.funnel import FunnelCounts, _classify, _record_timestamp
from src.proposal.interaction import ProposalRecord
from src.runtime.activity_events import ActivityEvent
from src.runtime.safety_score import RuntimeSafetyScore
from src.strategy.trade_history import TradeHistory
from src.trading.portfolio import AssetSnapshot
from src.utils.bounded_read import (
    ReadFailure,
    json_array_records,
    json_object,
    jsonl_records,
    reverse_jsonl_records,
)
from src.utils.time import ensure_utc

_THRESHOLD = re.compile(r"^composite \d+\.\d+ below threshold \d+\.\d+$")
_COUNTERS = {
    "proposal_generated": "Generated",
    "proposal_accepted": "Accepted",
    "position_opened": "Opened",
    "position_closed": "Closed",
}
_COMPANIONS = {"risk_kill_switch_tripped", "operator_freeze_engaged"}
_INCIDENTS = {
    "cycle_errored",
    "notification_failed",
    "liquidated",
    "cold_start_blocked",
    "correlation_warning",
}
_SAFETY = _INCIDENTS | {"llm_timeout", "risk_kill_switch_tripped"}
_RISK = {
    "risk_cap_advisory",
    "risk_kill_switch_tripped",
    "operator_freeze_engaged",
    "stale_position_detected",
    "stale_position_auto_closed",
}


@dataclass(slots=True)
class CycleState:
    """Fixed slots avoid a repeated dictionary/key set for every cycle."""

    first: list[Any]
    start: str | None = None
    end: list[Any] | None = None
    error: bool = False
    Generated: int = 0
    Accepted: int = 0
    Opened: int = 0
    Closed: int = 0
    Rejected: int = 0

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)


def encode(value: Any) -> Any:
    """JSON-compatible immutable cache representation."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


class StateBudget:
    """Conservative owned-state accounting, checked before retention.

    Recursive Python object sizes plus 128 bytes per retained slot cover
    container/key expansion. Shared values are conservatively charged at
    each owning slot. This is an admission bound, not a process RSS claim.
    All reducers in the sole active job share this account.
    """

    def __init__(self, limits: Limits):
        self.limits = limits
        self.bytes = 0
        self.identities = 0
        self.accounts: set[str] = set()
        self.strategies: set[str] = set()

    def size(self, value: Any) -> int:
        seen: set[int] = set()
        stack = [value]
        total = 128
        while stack:
            item = stack.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            total += sys.getsizeof(item)
            if isinstance(item, dict):
                stack.extend(item.keys())
                stack.extend(item.values())
            elif isinstance(item, (list, tuple, set)):
                stack.extend(item)
            elif is_dataclass(item) and not isinstance(item, type):
                stack.extend(getattr(item, field.name) for field in fields(item))
        return total

    def change(self, old: Any, new: Any, *, new_key: bool = False) -> None:
        delta = self.size(new) - (self.size(old) if old is not None else 0)
        if self.bytes + delta > self.limits.state_bytes:
            raise ReadFailure("state_budget_exhausted")
        if new_key and self.identities >= self.limits.identities:
            raise ReadFailure("identity_budget_exhausted")
        self.bytes += delta
        self.identities += int(new_key)

    def account(self, account: str) -> None:
        if account not in self.accounts:
            if len(self.accounts) >= self.limits.accounts:
                raise ReadFailure("account_budget_exhausted")
            self.change(None, account, new_key=True)
            self.accounts.add(account)

    def strategy(self, strategy: str) -> None:
        if strategy not in self.strategies:
            if len(self.strategies) >= self.limits.strategies:
                raise ReadFailure("strategy_budget_exhausted")
            self.change(None, strategy, new_key=True)
            self.strategies.add(strategy)


class Top:
    """Newest N in stable legacy order, without sorting the archive."""

    def __init__(self, count: int, budget: StateBudget):
        self.count = count
        self.budget = budget
        self.heap: list[tuple[datetime, int, dict[str, Any]]] = []

    def add(self, at: datetime, ordinal: int, value: dict[str, Any]) -> None:
        # On equal timestamps, legacy newest-first tables retain earliest
        # source ordinal. Callers needing the timeline's ascending tail use
        # the opposite ordinal deliberately.
        entry = (at, -ordinal, value)
        if len(self.heap) >= self.count and entry[:2] <= self.heap[0][:2]:
            return
        old = self.heap[0][2] if len(self.heap) >= self.count else None
        self.budget.change(old, value)
        if old is None:
            heapq.heappush(self.heap, entry)
        else:
            heapq.heapreplace(self.heap, entry)

    def values(self) -> list[dict[str, Any]]:
        return [
            entry[2] for entry in sorted(self.heap, key=lambda e: e[:2], reverse=True)
        ]


class ActivityProjection:
    def __init__(self, query: Query, budget: StateBudget):
        self.query, self.budget = query, budget
        self.now = ensure_utc(query.at or utc_now())
        self.cycles: dict[str, CycleState] = {}
        self.rejected: set[tuple[str | None, str]] = set()
        self.rejected_global: set[str] = set()
        self.companions: dict[tuple[str | None, str | None, str], int] = {}
        self.sub: dict[str, dict[str, int]] = {}
        self.latest: dict[tuple[str, ...], tuple[datetime, int, dict[str, Any]]] = {}
        self.recent: list[dict[str, Any]] = []
        self.timeline = Top(300, budget)
        self.incidents = Top(10, budget)
        self.unscoped_incidents = Top(10, budget)
        self.tables = {
            key: Top(25, budget) for key in ("risk", "regime", "degraded", "crowding")
        }
        self.types: set[str] = set()
        self.crowding = {"evaluated": 0, "would_block": 0, "skipped": 0}
        self.total = 0

    def _latest(
        self,
        key: tuple[str, ...],
        event: ActivityEvent,
        ordinal: int,
        payload: dict[str, Any],
        *,
        last_tie: bool = False,
    ) -> None:
        old = self.latest.get(key)
        rank = (event.timestamp, ordinal if last_tie else -ordinal)
        if old is None or rank > old[:2]:
            self.budget.change(
                [key, old[2]] if old else None, [key, payload], new_key=old is None
            )
            self.latest[key] = (rank[0], rank[1], payload)

    def add(self, raw: dict[str, Any], source: Source, ordinal: int) -> None:
        if "timestamp" not in raw:
            raise ReadFailure("missing_timestamp")
        event = ActivityEvent.model_validate(raw)
        typ, details, at = event.event_type, event.details, event.timestamp
        # Validation is one record at a time. The recent timeline owns at
        # most 300 rich rows; the full raw event list is never retained.
        payload = event.model_dump(mode="json")
        payload["_ordinal"] = ordinal
        recent = at >= self.now - timedelta(hours=24)
        if recent and typ in _INCIDENTS:
            self.unscoped_incidents.add(at, ordinal, payload)
        if self.query.scope != "Aggregate" and str(
            details.get("sub_account_id", "")
        ) not in {"", self.query.scope}:
            # Reconciliation is global even for a scoped Home query.
            if typ.startswith("reconciliation_health_"):
                self._latest(("reconciliation",), event, ordinal, payload)
            return
        self.total += 1
        account = str(details.get("sub_account_id", "default"))
        self.budget.account(account)
        if typ not in self.types:
            self.budget.change(None, typ, new_key=True)
            self.types.add(typ)
        self.timeline.add(at, -ordinal, payload)
        (
            self._latest(("last_cycle_event",), event, ordinal, payload)
            if event.cycle_id
            else None
        )
        if typ.startswith("reconciliation_health_"):
            self._latest(("reconciliation",), event, ordinal, payload)
        if recent and (
            typ in _SAFETY
            or "stale_quote" in str(details.get("reason", ""))
            or "stale-quote" in event.message
        ):
            compact = {
                "timestamp": payload["timestamp"],
                "event_type": typ,
                "message": "stale-quote" if "stale-quote" in event.message else "",
                "cycle_id": event.cycle_id,
                "details": {
                    k: details[k]
                    for k in (
                        "cycle_id",
                        "gate_reason",
                        "reason",
                        "sub_account_id",
                        "advisory",
                    )
                    if k in details
                },
            }
            self.budget.change(None, compact, new_key=True)
            self.recent.append(compact)
        if recent and typ in _INCIDENTS:
            self.incidents.add(at, ordinal, payload)
        if event.cycle_id:
            cid = event.cycle_id
            if cid not in self.cycles:
                state = CycleState(first=[at.isoformat(), ordinal])
                self.budget.change(None, [cid, state], new_key=True)
                self.cycles[cid] = state
            state = self.cycles[cid]
            if (at.isoformat(), ordinal) < tuple(state["first"]):
                state["first"] = [at.isoformat(), ordinal]
            if typ == "cycle_started" and (
                state["start"] is None or at.isoformat() < state["start"]
            ):
                state["start"] = at.isoformat()
            if typ in {"cycle_completed", "cycle_errored"}:
                previous = state["end"]
                if previous is None or (at.isoformat(), ordinal) < (
                    previous[0],
                    previous[1],
                ):
                    terminal = [at.isoformat(), ordinal, typ, event.message]
                    self.budget.change(previous, terminal)
                    state["end"] = terminal
                state["error"] |= typ == "cycle_errored"
            if typ in _COUNTERS:
                state[_COUNTERS[typ]] += 1
            if typ == "proposal_rejected" and not details.get("advisory"):
                state["Rejected"] += 1
        row = self.sub.get(account)
        if (
            typ in _COUNTERS
            or typ == "proposal_rejected"
            and not details.get("advisory")
        ):
            if row is None:
                row = dict.fromkeys(
                    ("Generated", "Accepted", "Rejected", "Opened", "Closed"), 0
                )
                self.budget.change(None, [account, row], new_key=True)
                self.sub[account] = row
            row[_COUNTERS.get(typ, "Rejected")] += 1
        pid_raw = details.get("proposal_id")
        pid = str(pid_raw) if pid_raw is not None else None
        if typ in _COMPANIONS and not details.get("advisory"):
            companion = (event.cycle_id, pid, account)
            if companion not in self.companions:
                self.budget.change(None, companion, new_key=True)
            self.companions[companion] = self.companions.get(companion, 0) + 1
        if (
            typ
            in {
                "risk_cap_advisory",
                "risk_kill_switch_tripped",
                "operator_freeze_engaged",
            }
            or typ == "proposal_rejected"
            and details.get("gate_reason")
            in {
                "account_aggregate_cap",
                "global_cap",
                "daily_loss_kill_switch",
                "open_drawdown_kill_switch",
                "open_stop_risk_kill_switch",
                "portfolio_kill_switch",
                "portfolio_daily_loss_kill_switch",
                "operator_freeze",
            }
        ):
            self.tables["risk"].add(at, ordinal, payload)
        if typ in _RISK:
            # Keep newest source of each individual metric, not just the
            # newest risk row (different gates carry different fields).
            for field in (
                "equity",
                "realized_pnl_today",
                "portfolio_realized_pnl_today",
                "unrealized_pnl_open",
                "portfolio_unrealized_pnl",
                "open_stop_risk_total",
                "open_stop_risk",
                "gross_notional_total",
            ):
                if details.get(field) not in (None, ""):
                    self._latest(
                        ("risk_field", account, field), event, ordinal, payload
                    )
            self._latest(("risk_account", account), event, ordinal, payload)
            if typ in {"risk_kill_switch_tripped", "stale_position_detected"}:
                self._latest(
                    ("cycle_risk", event.cycle_id or "", account, typ),
                    event,
                    ordinal,
                    payload,
                )
        if details.get("gate_reason") == "global_cap" and typ in {
            "risk_cap_advisory",
            "proposal_rejected",
        }:
            self._latest(("global_cap",), event, ordinal, payload)
            self._latest(
                (
                    "global_symbol",
                    str(details.get("symbol", "")),
                    str(details.get("side", "")),
                ),
                event,
                ordinal,
                payload,
            )
        if typ == "operator_freeze_engaged":
            self._latest(("freeze",), event, ordinal, payload)
        if typ.startswith("derivatives_data_"):
            self._latest(
                (
                    "derivatives",
                    str(details.get("exchange", "unknown")),
                    str(details.get("symbol", "unknown")),
                    str(details.get("series", "unknown")),
                ),
                event,
                ordinal,
                payload,
                last_tie=True,
            )
        if typ == "market_regime_blocked":
            self._latest(("regime_account", account), event, ordinal, payload)
            self._latest(
                (
                    "regime_symbol",
                    str(details.get("symbol", "")),
                    str(details.get("timeframe", "")),
                ),
                event,
                ordinal,
                payload,
            )
            self.tables["regime"].add(at, ordinal, payload)
        if typ == "market_regime_degraded":
            self.tables["degraded"].add(at, ordinal, payload)
        if typ.startswith("funding_oi_crowding_"):
            self.tables["crowding"].add(at, ordinal, payload)
            self.crowding[
                "evaluated" if typ == "funding_oi_crowding_observed" else "skipped"
            ] += 1
            self.crowding["would_block"] += int(
                typ == "funding_oi_crowding_observed"
                and bool(details.get("would_block"))
            )
        # Gate samples match on gate_reason OR legacy reason prefix, even
        # for non-rejection event types, matching the existing pure helper.
        from src.dashboard.pages.proposals import GATE_REASON_BY_STATE

        for gate, reasons in GATE_REASON_BY_STATE.items():
            if details.get("gate_reason") in reasons or any(
                str(details.get("reason", "")) == reason
                or str(details.get("reason", "")).startswith(reason + "_")
                for reason in reasons
            ):
                self._latest(("gate_sample", gate), event, ordinal, payload)

    def finish(self) -> dict[str, Any]:
        from src.dashboard.pages.engine import CycleSummary

        for (cid, pid, account), count in self.companions.items():
            if cid and (pid is None or (cid, pid) not in self.rejected):
                self.cycles[cid]["Rejected"] += count
            if pid is None or pid not in self.rejected_global:
                row = self.sub.get(account)
                if row is None:
                    row = dict.fromkeys(
                        ("Generated", "Accepted", "Rejected", "Opened", "Closed"), 0
                    )
                    self.budget.change(None, [account, row], new_key=True)
                    self.sub[account] = row
                row["Rejected"] += count
        # Sort ids, not another lifetime list of rich CycleSummary objects.
        # Account for pointer arrays and sort scratch before allocation.
        reserve = 192 + 32 * len(self.cycles)
        if self.budget.bytes + reserve > self.budget.limits.state_bytes:
            raise ReadFailure("state_budget_exhausted")
        self.budget.bytes += reserve
        ordered = sorted(self.cycles, key=lambda cid: tuple(self.cycles[cid]["first"]))
        ordered.sort(key=lambda cid: self.cycles[cid]["start"] or "", reverse=True)
        cycles: list[CycleSummary] = []
        duration_sum = 0.0
        duration_count = 0
        errored = opened = closed = 0
        for cid in ordered:
            state = self.cycles[cid]
            start = datetime.fromisoformat(state["start"]) if state["start"] else None
            terminal = state["end"]
            end = datetime.fromisoformat(terminal[0]) if terminal else None
            duration = (end - start).total_seconds() if start and end else None
            if duration is not None:
                duration_sum += duration
                duration_count += 1
            errored += int(state["error"])
            opened += state["Opened"]
            closed += state["Closed"]
            if len(cycles) >= 50:
                continue
            cycles.append(
                CycleSummary(
                    cycle_id=cid,
                    started_at=start,
                    completed_at=end,
                    duration_seconds=duration,
                    proposals_generated=state["Generated"],
                    proposals_accepted=state["Accepted"],
                    proposals_rejected=state["Rejected"],
                    positions_opened=state["Opened"],
                    positions_closed=state["Closed"],
                    errored=state["error"],
                    error_message=(
                        terminal[3]
                        if terminal and terminal[2] == "cycle_errored"
                        else None
                    ),
                )
            )
        last = cycles[0] if cycles else None
        metrics = {
            "total_cycles": len(self.cycles),
            "last_cycle_started_at": last.started_at if last else None,
            "last_cycle_status": (
                (
                    "errored"
                    if last.errored
                    else "running" if last.completed_at is None else "ok"
                )
                if last
                else None
            ),
            "avg_duration_seconds": (
                duration_sum / duration_count if duration_count else None
            ),
            "errored_cycles": errored,
            "positions_opened_total": opened,
            "positions_closed_total": closed,
        }
        del ordered
        self.budget.bytes -= reserve
        evaluated = ensure_utc(self.query.at or utc_now())
        if evaluated < self.now:
            raise ReadFailure("evaluation_clock_reversed")
        safety = bounded_safety(self.recent, evaluated, self.budget)
        cutoff = evaluated - timedelta(hours=24)
        incidents = [
            raw
            for raw in self.incidents.values()
            if datetime.fromisoformat(raw["timestamp"]) >= cutoff
        ]
        unscoped_incidents = [
            raw
            for raw in self.unscoped_incidents.values()
            if datetime.fromisoformat(raw["timestamp"]) >= cutoff
        ]
        # A bounded set of exact latest/detail events feeds existing read
        # helpers. Lifetime counts and safety use separate exact reductions.
        details: dict[str, dict[str, Any]] = {}
        last_cycle = self.latest.get(("last_cycle_event",))
        last_cid = last_cycle[2].get("cycle_id") if last_cycle else None
        for key, (_, _, payload) in self.latest.items():
            if key[0] == "cycle_risk" and key[1] != (last_cid or ""):
                continue
            details[json.dumps(payload, sort_keys=True)] = payload
        for table in self.tables.values():
            for payload in table.values():
                details[json.dumps(payload, sort_keys=True)] = payload
        events = sorted(
            details.values(),
            key=lambda payload: (payload["timestamp"], payload.get("_ordinal", 0)),
        )
        sub_rows = [
            {"Sub-account": account, **row} for account, row in sorted(self.sub.items())
        ]
        if sub_rows:
            sub_rows.insert(
                0,
                {
                    "Sub-account": "Aggregate",
                    **{
                        field: sum(row[field] for row in self.sub.values())
                        for field in (
                            "Generated",
                            "Accepted",
                            "Rejected",
                            "Opened",
                            "Closed",
                        )
                    },
                },
            )
        output: dict[str, Any] = encode(
            {
                "total": self.total,
                "metrics": metrics,
                "cycles": [asdict(cycle) for cycle in cycles[:50]],
                "safety": safety.model_dump(mode="json"),
                "_safety_events": self.recent,
                "_unscoped_incidents": unscoped_incidents,
                "events": events,
                "timeline": list(reversed(self.timeline.values())),
                "incidents": incidents,
                "actionable": len(unscoped_incidents),
                "sub_rows": sub_rows,
                "types": sorted(self.types),
                "crowding": self.crowding,
                "evaluated_at": evaluated,
            }
        )
        return output


class HistoryProjection:
    def __init__(self, query: Query, budget: StateBudget):
        self.query, self.budget = query, budget
        self.now = ensure_utc(query.at or utc_now())
        self.counts = dict.fromkeys(FunnelCounts.model_fields, 0)
        self.by_strategy: dict[str, dict[str, int]] = {}
        self.by_account: dict[str, dict[str, int]] = {}
        self.threshold = 0
        self.boundaries: list[dict[str, Any]] = []
        self.window_records: list[dict[str, Any]] = []
        self.open: list[dict[str, Any]] = []
        self.history = Top(25, budget)
        self.trade_counts = {
            "open_positions": 0,
            "closed_trades": 0,
            "wins": 0,
            "realized_pnl": 0.0,
        }
        self.latest: dict[str, dict[str, Any]] = {}
        self.curves: dict[str, list[dict[str, Any]]] = {}
        self.curve_limit = max(4, 4096 // max(1, len(query.accounts)))
        self.sampled = False
        self.candidate_counts: dict[str, int] = {"total": 0}
        self.candidates = Top(5, budget)
        self.catalog: list[dict[str, Any]] = []
        self.observations: dict[str, dict[str, Any]] = {}
        self.audit = Top(300, budget)
        self.audit_total = 0

    def add(self, raw: dict[str, Any], source: Source, ordinal: int) -> None:
        kind = self.query.kind
        if kind == "proposals":
            record = ProposalRecord.model_validate(raw)
            ts = _record_timestamp(record)
            if (
                record.decision == "rejected"
                and record.rejection_reason
                and _THRESHOLD.match(record.rejection_reason)
            ):
                self.threshold += 1
            days = {"24h": 1, "7d": 7, "30d": 30}.get(self.query.window)
            field = _classify(record).value
            account = record.sub_account_id or record.proposal.sub_account_id
            strategy = record.proposal.technique_name
            self.budget.account(account)
            self.budget.strategy(strategy)
            if days is not None and ts >= self.now - timedelta(days=days):
                descriptor = {
                    "timestamp": ts.isoformat(),
                    "field": field,
                    "account": account,
                    "strategy": strategy,
                }
                self.budget.change(None, descriptor, new_key=True)
                self.window_records.append(descriptor)
            for mapping, key in (
                (self.by_account, account),
                (self.by_strategy, strategy),
            ):
                if key not in mapping:
                    row = dict.fromkeys(FunnelCounts.model_fields, 0)
                    self.budget.change(None, [key, row], new_key=True)
                    mapping[key] = row
            if days is not None and self.query.at is None:
                cutoff = self.now - timedelta(days=days)
                if cutoff <= ts <= cutoff + timedelta(
                    seconds=30
                ) or self.now < ts <= self.now + timedelta(seconds=30):
                    boundary = {
                        "timestamp": ts.isoformat(),
                        "field": field,
                        "account": account,
                        "strategy": strategy,
                    }
                    self.budget.change(None, boundary, new_key=True)
                    self.boundaries.append(boundary)
            if days is not None and not (
                self.now - timedelta(days=days) <= ts <= self.now
            ):
                return
            self.budget.account(account)
            self.budget.strategy(strategy)
            self.counts[field] += 1
            self.counts["total"] += 1
            for mapping, key in (
                (self.by_account, account),
                (self.by_strategy, strategy),
            ):
                if key not in mapping:
                    row = dict.fromkeys(FunnelCounts.model_fields, 0)
                    self.budget.change(None, [key, row], new_key=True)
                    mapping[key] = row
                mapping[key][field] += 1
                mapping[key]["total"] += 1
        elif kind == "ledger":
            trade = TradeHistory.model_validate(raw)
            self.budget.account(source.account)
            if trade.status == "open":
                self.budget.change(None, [source.account, raw], new_key=True)
                self.open.append({"account": source.account, "trade": raw})
                self.trade_counts["open_positions"] += 1
            elif trade.status == "closed":
                self.trade_counts["closed_trades"] += 1
                self.trade_counts["wins"] += int(trade.close_reason == "take_profit")
                self.trade_counts["realized_pnl"] += (
                    float(trade.pnl) if trade.pnl is not None else 0.0
                )
            self.history.add(trade.exit_time or trade.entry_time, ordinal, raw)
        elif kind == "snapshots":
            snapshot = AssetSnapshot.model_validate(raw)
            raw = snapshot.model_dump(mode="json")
            account = source.account
            self.budget.account(account)
            old = self.latest.get(account)
            if old is None or snapshot.timestamp > datetime.fromisoformat(
                old["timestamp"]
            ):
                self.budget.change(old, raw, new_key=old is None)
                self.latest[account] = raw
            curve = self.curves.setdefault(account, [])
            point = {
                "timestamp": snapshot.timestamp.isoformat(),
                "equity": str(snapshot.total_equity),
            }
            self.budget.change(None, point)
            curve.append(point)
            if len(curve) > self.curve_limit:
                # Hierarchical adjacent buckets preserve first/latest and
                # local extrema. This is display sampling, never a total.
                ordered = sorted(curve, key=lambda point: point["timestamp"])
                reduced = [ordered[0]]
                for i in range(1, len(ordered) - 1, 8):
                    bucket = ordered[i : min(i + 8, len(ordered) - 1)]
                    extrema = {
                        id(point): point
                        for point in (
                            min(bucket, key=lambda point: Decimal(point["equity"])),
                            max(bucket, key=lambda point: Decimal(point["equity"])),
                        )
                    }
                    reduced.extend(
                        sorted(extrema.values(), key=lambda point: point["timestamp"])
                    )
                reduced.append(ordered[-1])
                self.budget.bytes -= sum(
                    self.budget.size(point) for point in curve
                ) - sum(self.budget.size(point) for point in reduced)
                self.curves[account] = reduced
                self.sampled = True
        elif kind == "candidates":
            from src.feedback.loop import CandidateRecord

            candidate = CandidateRecord.model_validate(raw)
            if (
                self.query.scope != "Aggregate"
                and candidate.sub_account_id != self.query.scope
            ):
                return
            self.budget.account(candidate.sub_account_id)
            self.candidate_counts["total"] += 1
            status = str(candidate.status)
            self.candidate_counts[status] = self.candidate_counts.get(status, 0) + 1
            # Home only uses a handful of scalar evidence fields. Backtest
            # payloads and full proposal/model artifacts are not cached.
            compact = candidate.model_dump(
                mode="json",
                include={
                    "candidate_id",
                    "kind",
                    "source_path",
                    "technique_name",
                    "technique_version",
                    "status",
                    "robustness_passed",
                    "backtest_run_id",
                    "sub_account_id",
                    "created_at",
                    "updated_at",
                },
            )
            self.candidates.add(candidate.updated_at, ordinal, compact)
            if self.query.window == "catalog":
                payload = candidate.model_dump(mode="json")
                self.budget.change(None, payload, new_key=True)
                self.catalog.append(payload)
        elif kind == "promotion":
            from src.feedback.promotion_lab import PromotionObservation

            observation = PromotionObservation.model_validate(raw)
            payload = observation.model_dump(mode="json")
            old = self.observations.get(observation.candidate_id)
            self.budget.change(old, payload, new_key=old is None)
            self.observations[observation.candidate_id] = payload
        elif kind == "audit":
            from src.feedback.audit import AuditEvent

            audit = AuditEvent.model_validate(raw)
            if audit.candidate_id != self.query.scope:
                return
            self.audit_total += 1
            self.audit.add(audit.timestamp, ordinal, audit.model_dump(mode="json"))

    def finish(self) -> dict[str, Any]:
        evaluated = ensure_utc(self.query.at or utc_now())
        if evaluated < self.now:
            raise ReadFailure("evaluation_clock_reversed")
        days = {"24h": 1, "7d": 7, "30d": 30}.get(self.query.window)
        if (
            self.query.kind == "proposals"
            and days is not None
            and self.query.at is None
        ):
            if (evaluated - self.now).total_seconds() > 30:
                raise ReadFailure("window_evaluation_budget_exhausted")
            old_start = self.now - timedelta(days=days)
            new_start = evaluated - timedelta(days=days)
            for boundary in self.boundaries:
                at = datetime.fromisoformat(boundary["timestamp"])
                delta = int(new_start <= at <= evaluated) - int(
                    old_start <= at <= self.now
                )
                if not delta:
                    continue
                account, strategy = boundary["account"], boundary["strategy"]
                self.budget.account(account)
                self.budget.strategy(strategy)
                for mapping, key in (
                    (self.by_account, account),
                    (self.by_strategy, strategy),
                ):
                    if key not in mapping:
                        row = dict.fromkeys(FunnelCounts.model_fields, 0)
                        self.budget.change(None, [key, row], new_key=True)
                        mapping[key] = row
                    mapping[key][boundary["field"]] += delta
                    mapping[key]["total"] += delta
                self.counts[boundary["field"]] += delta
                self.counts["total"] += delta
        return {
            "counts": self.counts,
            "by_strategy": self.by_strategy,
            "by_account": self.by_account,
            "threshold": self.threshold,
            "_window_records": self.window_records,
            "open": self.open,
            "history": self.history.values(),
            "metrics": self.trade_counts,
            "latest": self.latest,
            "curves": self.curves,
            "sampled": self.sampled,
            "candidate_counts": self.candidate_counts,
            "candidates": self.candidates.values(),
            "catalog": sorted(
                self.catalog, key=lambda raw: raw["updated_at"], reverse=True
            ),
            "observations": self.observations,
            "audit": list(reversed(self.audit.values())),
            "audit_total": self.audit_total,
            "evaluated_at": evaluated.isoformat(),
        }


def build_projection(
    query: Query, limits: Limits, *, previous: bytes | None = None
) -> Generator[dict[str, Any] | None, None, None]:
    budget = StateBudget(limits)
    manifest = discover(query, limits, get_settings().log_retention_months)
    digest = manifest.digest()
    if previous is not None:
        cached = json.loads(previous)
        if cached.get("_source_digest") == digest:
            # Verify every captured file and membership; an unchanged root
            # or directory mtime alone cannot authorize cached contents.
            budget.change(None, cached)
            refreshed = refresh_projection(query, cached, budget)
            manifest.verify()
            yield refreshed
            return
        del cached
    reducer = (
        ActivityProjection(query, budget)
        if query.kind == "activity"
        else HistoryProjection(query, budget)
    )
    ordinal = 0
    files = (
        manifest.reverse_files
        if query.kind in {"activity", "audit"}
        else manifest.files
    )
    for index, source in enumerate(files):
        line = 0
        reader = {
            "jsonl": reverse_jsonl_records,
            "object": json_object,
            "array": json_array_records,
        }[source.format]
        iterator = reader(source.path, source.generation)
        try:
            for raw in iterator:
                if raw is None:
                    yield None
                    continue
                ordinal = (
                    ((manifest.file_count - index - 1) << 48) + raw.pop("_offset")
                    if query.kind in {"activity", "audit"}
                    else ordinal
                )
                reducer.add(raw, source, ordinal)
                ordinal += 1
                line += 1
                if ordinal % 256 == 0:
                    yield None
        except ValueError as exc:
            raise ReadFailure("invalid_record") from exc
        finally:
            iterator.close()
    if isinstance(reducer, ActivityProjection) and reducer.companions:
        # The companion set is compact. A second bounded pass records only
        # sibling ids needed by those companions, rather than all lifetime
        # rejected proposal identities (most have no companion at all).
        pids = {pid for _, pid, _ in reducer.companions if pid is not None}
        budget.change(None, pids)
        for source in manifest.files:
            iterator = jsonl_records(source.path, source.generation)
            try:
                for raw in iterator:
                    if raw is None:
                        yield None
                        continue
                    if raw.get("event_type") != "proposal_rejected":
                        continue
                    details = raw.get("details") or {}
                    if query.scope != "Aggregate" and str(
                        details.get("sub_account_id", "")
                    ) not in {"", query.scope}:
                        continue
                    pid = (
                        str(details["proposal_id"])
                        if details.get("proposal_id") is not None
                        else None
                    )
                    if pid not in pids:
                        continue
                    key = (raw.get("cycle_id"), pid)
                    if key not in reducer.rejected:
                        budget.change(None, key, new_key=True)
                        reducer.rejected.add(key)
                    if pid not in reducer.rejected_global:
                        budget.change(None, pid, new_key=True)
                        reducer.rejected_global.add(pid)
            finally:
                iterator.close()
    manifest.verify()
    result = reducer.finish()
    result["_source_digest"] = digest
    result["source_coverage"] = {
        "files": manifest.file_count,
        "captured_bytes": sum(source.generation.size for source in manifest.files),
        "verified": True,
    }
    yield result


def refresh_projection(
    query: Query, data: dict[str, Any], budget: StateBudget
) -> dict[str, Any]:
    """Re-evaluate exact windows on a verified unchanged compact projection."""
    now = ensure_utc(query.at or utc_now())
    if now < datetime.fromisoformat(data["evaluated_at"]):
        raise ReadFailure("evaluation_clock_reversed")
    if query.kind == "activity":

        cutoff = now - timedelta(hours=24)
        data["_safety_events"] = [
            raw
            for raw in data["_safety_events"]
            if datetime.fromisoformat(raw["timestamp"]) >= cutoff
        ]
        data["safety"] = bounded_safety(data["_safety_events"], now, budget).model_dump(
            mode="json"
        )
        for key in ("incidents", "_unscoped_incidents"):
            data[key] = [
                raw
                for raw in data[key]
                if datetime.fromisoformat(raw["timestamp"]) >= cutoff
            ]
        data["actionable"] = len(data["_unscoped_incidents"])
    elif query.kind == "proposals" and query.window != "lifetime":
        days = {"24h": 1, "7d": 7, "30d": 30}.get(query.window)
        if days is not None:
            cutoff = now - timedelta(days=days)
            data["counts"] = dict.fromkeys(FunnelCounts.model_fields, 0)
            for grouping in ("by_account", "by_strategy"):
                data[grouping] = {
                    key: dict.fromkeys(FunnelCounts.model_fields, 0)
                    for key in data[grouping]
                }
            data["_window_records"] = [
                row
                for row in data["_window_records"]
                if datetime.fromisoformat(row["timestamp"]) >= cutoff
            ]
            for row in data["_window_records"]:
                if datetime.fromisoformat(row["timestamp"]) > now:
                    continue
                for counts in (
                    data["counts"],
                    data["by_account"][row["account"]],
                    data["by_strategy"][row["strategy"]],
                ):
                    counts[row["field"]] += 1
                    counts["total"] += 1
    data["evaluated_at"] = now.isoformat()
    return data


def bounded_safety(
    rows: list[dict[str, Any]], now: datetime, budget: StateBudget
) -> RuntimeSafetyScore:
    from src.runtime.safety_score import (
        RuntimeSafetyInputs,
        compute_runtime_safety_score,
        event_cycle_id,
        event_gate_reason,
        event_sub_account_id,
        inputs_from_activity_events,
    )

    counts = dict.fromkeys(RuntimeSafetyInputs.model_fields, 0)
    seen = set()
    cutoff = now - timedelta(hours=24)
    for row in rows:
        event = ActivityEvent.model_validate(row)
        if event.timestamp < cutoff:
            continue
        inputs = inputs_from_activity_events([event]).model_dump()
        if inputs["kill_switch_conditions"]:
            key = (
                event_cycle_id(event),
                event_gate_reason(event),
                event_sub_account_id(event),
            )
            if key in seen:
                inputs["kill_switch_conditions"] = 0
            else:
                budget.change(None, key, new_key=True)
                seen.add(key)
        for field, value in inputs.items():
            counts[field] += value
    return compute_runtime_safety_score(RuntimeSafetyInputs(**counts))
