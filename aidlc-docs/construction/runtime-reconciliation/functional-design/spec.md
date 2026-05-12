# Runtime Reconciliation Functional Specification

## Purpose

`runtime-reconciliation` keeps the deployed paper runtime state consistent
across restarts and migrations so the engine can actually monitor every open
trade, the balance ledger matches open exposure, and the dashboard never shows
cash-only state while open ledger rows still exist.

The unit is intentionally not a new IO primitive. `backfill_paper_sl_tp`
(DEBT-058) and `balances.json` snapshots (DEBT-059) already exist. What is
missing is the operator-visible workflow on top of them: a classification of
open-trade health, a documented repair playbook, runtime startup health checks,
and a dashboard signal that fails loudly when the ledger disagrees with the
portfolio snapshot.

The 2026-05-13 Fly snapshot (release v43) motivated this unit: 49 open paper
trades, 44 with no persisted SL/TP, 6,148 `MONITOR_ERRORED` events over the
snapshot window, and a Trading dashboard reporting zero positions on the same
sub-accounts that had 49 open rows on disk.

## Concepts

### Open-Trade State Taxonomy

Every open row in `data/trades/paper/<sub_account>/trades.json` is classified
into exactly one state. Closed rows are out of scope — their null SL/TP is
benign and the runtime never re-monitors them.

- `monitorable`: row has all of `entry_price`, `side`, `size`, `symbol`,
  `stop_loss`, `take_profit`, and a `performance_record_id` whose target perf
  record exists on disk. The monitor loop can mark-to-market and auto-close on
  SL or TP bound.
- `degraded`: row has `entry_price`, `side`, `size`, `symbol` but is missing
  `stop_loss` and/or `take_profit`. This is the 44-of-49 Fly case. The
  monitor loop can mark-to-market and timestamp the row but cannot auto-close
  on a bound. Auto-recoverable via `backfill_paper_sl_tp` when a linked perf
  record carries the bounds.
- `unrecoverable`: row is missing one or more of `entry_price`, `side`, `size`,
  `symbol`. The monitor loop cannot mark-to-market and cannot price a close.
  Requires manual operator action — no automatic recovery path exists.
- `legacy_no_perf_link`: row has `stop_loss` and `take_profit` set but no
  `performance_record_id`. Monitorable, but cross-system audits cannot link
  the trade back to a strategy outcome. Pre-DEBT-058 ledger format.

State is computed purely from the on-disk row plus a lookup against
`data/performance/<sub_account>/<technique>/records.json`. It is not stored —
the engine recomputes on every startup health check.

### State Transitions

- `degraded` -> `monitorable`: operator runs `backfill_paper_sl_tp` and the
  linked perf record carries non-null SL/TP. Transition is atomic with the
  ledger rewrite in `_backfill_one_file`.
- `unrecoverable` -> `monitorable`: not automatic. Requires operator to either
  hand-edit the ledger (off-policy) or close the orphan with the
  reconciliation close tool (see Operator Repair Flow). Recovery is only
  considered complete when the next startup health check returns zero
  `unrecoverable` rows.
- `legacy_no_perf_link` -> `monitorable`: not automatic. New trades opened
  after DEBT-058 always carry `performance_record_id`; existing legacy rows
  stay in this state until manually closed and reopened.
- A `monitorable` row can never regress — once SL/TP land on disk the rewrite
  is durable. `MONITOR_ERRORED` on a `monitorable` row is a separate runtime
  fault, not a state regression.

## Operator Repair Flow

The canonical playbook the operator follows when a startup health check
reports a non-empty `degraded` or `unrecoverable` count. Each step lists the
CLI invocation and the activity event the operator should see in the timeline.

### Step 1 — Detect

The engine's startup health check (see Startup Health Checks) emits one
`RECONCILIATION_HEALTH_REPORT` event per startup with per-sub-account counts
broken down by state. The operator reads this from the dashboard Engine page
or by tailing `data/runtime/activity.jsonl`. No CLI invocation needed.

### Step 2 — Preview backfill

```
python -m src.tools.backfill_paper_sl_tp --dry-run
```

Emits per-sub-account INFO logs of the form `Backfilled SL/TP for N open
paper trades in <sub_account> (M rows examined, K skipped)`. No ledger or
activity-log writes occur. The operator confirms the projected backfill count
matches the `degraded` count from Step 1.

If the dry-run reports skipped rows broken down by `skipped_no_perf`,
`skipped_perf_unset`, or `skipped_perf_missing`, those rows will remain in
`degraded` or `legacy_no_perf_link` after the live run.

### Step 3 — Live backfill

```
python -m src.tools.backfill_paper_sl_tp
```

Rewrites each sub-account's `trades.json` via `atomic_write_text` and emits
one `BACKFILL_PAPER_SL_TP_RAN` activity event per invocation (new event
type — see Code-Generation Plan §1). The event payload carries the same
counters as `BackfillSummary` so the dashboard timeline can show the operator
the exact effect of the repair.

### Step 4 — Close `unrecoverable` rows

No tool exists for this today. The Code-Generation Plan recommends a sibling
script `src/tools/close_unrecoverable_paper_trades.py` that:

- Loads each sub-account ledger.
- Identifies `unrecoverable` rows by the per-row field check from the State
  Taxonomy section.
- Marks them `status = "closed"` with `close_reason = "reconciliation_close"`
  and `exit_price = None`, leaving the PnL impact explicit (zero, since we
  cannot compute a fair close price).
- Supports `--dry-run` and `--sub-account` matching the existing backfill
  tool's CLI shape.
- Emits one `RECONCILIATION_CLOSED_UNRECOVERABLE` activity event per closed
  row carrying `(trade_id, sub_account_id, symbol, missing_fields)`.

The tool is the only sanctioned mechanism for clearing `unrecoverable` rows.
Hand-editing the ledger is off-policy and bypasses the activity log.

### Step 5 — Verify

Restart the engine (or call the health check helper directly — see Code
Generation Plan §1) and confirm the next `RECONCILIATION_HEALTH_REPORT` event
shows zero `degraded` and zero `unrecoverable` rows. Any
`legacy_no_perf_link` rows can remain — they are monitorable.

## Startup Health Checks

Before the engine enters its cycle loop, it runs a single reconciliation pass
that produces one `RECONCILIATION_HEALTH_REPORT` activity event. The pass is
side-effect-free with respect to the ledger — it only reads.

For each enabled sub-account the check computes:

- `open_trade_count`: total rows where `status == "open"`.
- `state_counts`: a `{state: count}` map covering the four states in the
  taxonomy (`monitorable`, `degraded`, `unrecoverable`,
  `legacy_no_perf_link`).
- `locked_sum`: the sum of per-row locked margin for open rows.
- `balance_snapshot_present`: whether
  `data/trades/paper/<sub_account>/balances.json` exists.
- `balance_locked`: the `locked` value from the snapshot (or `None` if
  absent).
- `locked_consistent`: `True` if `balance_snapshot_present` is `True` and
  `abs(balance_locked - locked_sum) <= epsilon`. Otherwise `False`. Epsilon
  is the existing fee/Decimal-rounding tolerance used by
  `_reconcile_legacy_rehydrated_balances`.
- `perf_links_resolved`: count of open rows whose `performance_record_id`
  points to a perf record that exists on disk.
- `perf_links_missing`: count of open rows whose `performance_record_id` is
  set but does not resolve to an on-disk perf record.

The event payload is then:

```
{
  "report": {
    "<sub_account_id>": {
      "open_trade_count": int,
      "state_counts": {"monitorable": int, "degraded": int,
                       "unrecoverable": int, "legacy_no_perf_link": int},
      "locked_sum": str (Decimal),
      "balance_snapshot_present": bool,
      "balance_locked": str (Decimal) | null,
      "locked_consistent": bool,
      "perf_links_resolved": int,
      "perf_links_missing": int
    },
    ...
  },
  "totals": { ...same shape, summed across sub-accounts... }
}
```

The check runs once per engine startup, after sub-account rehydration and
before `run_forever` enters its loop. It does not run on every cycle — open
counts can drift between startups but the operator-visible signal is
restart-anchored.

### Failure Mode (recommended)

If any sub-account has `unrecoverable > 0`, the engine logs at WARNING and
continues. It does not fail-startup. Rationale: a fail-startup policy makes
the Fly machine unbootable until an operator SSHes in, which defeats the
purpose of having the dashboard signal. Live mode may tighten this — see
Open Decisions.

If any sub-account has `locked_consistent == False`, the engine logs at
WARNING and emits a separate `RECONCILIATION_LOCKED_INCONSISTENT` event so
the dashboard can render the discrepancy. It does not auto-correct.

## Dashboard Behavior

The dashboard must surface every reconciliation signal that motivated this
unit. The failure mode to prevent is the Fly snapshot's exact pathology:
ledger holds 49 open rows, portfolio snapshot reports zero positions, Trading
page renders cash-only state.

### Reconciliation Status Banner

A new banner at the top of the Trading and Engine pages, sourced from the
most recent `RECONCILIATION_HEALTH_REPORT` event. The banner renders a single
status:

- Green — every open trade across every sub-account is `monitorable` or
  `legacy_no_perf_link`, and every sub-account's `locked_consistent` is
  `True`.
- Yellow — at least one open trade is `degraded`, or any sub-account's
  `locked_consistent` is `False`. The banner includes a one-line "Run
  `python -m src.tools.backfill_paper_sl_tp --dry-run`" call-to-action.
- Red — at least one open trade is `unrecoverable`. The banner includes a
  one-line "Run the reconciliation close tool" call-to-action.

The banner is non-dismissible while a non-green state exists. The Open
Decisions section flags whether the user wants this rule relaxed.

### Drill-Through Table

Below the banner, a `Reconciliation status` expander shows one row per open
trade with columns: `sub_account_id`, `trade_id`, `symbol`, `side`, `state`,
`missing_fields` (comma-separated list of fields per the State Taxonomy
checks). The source is the same `RECONCILIATION_HEALTH_REPORT` event payload;
the dashboard does not re-walk the ledger.

### Cash-Only Rendering Rule

The Trading page must not render "no open positions" or any equivalent
cash-only summary if the most recent `RECONCILIATION_HEALTH_REPORT` shows
`totals.open_trade_count > 0`. Instead it renders the reconciliation status
banner and the drill-through table, with portfolio snapshot data shown below
labeled "portfolio snapshot (may be stale relative to ledger)".

This rule applies independently of whether the portfolio snapshot itself
reports positions. The ledger is the source of truth for "does the engine
think it has open trades", not the snapshot.

## Test Scope

Future implementation should include:

- Pure state-classifier tests covering all four states with explicit
  fixtures for the missing-field permutations.
- Health-check tests asserting per-sub-account counts, locked consistency,
  and perf-link resolution.
- Activity-event tests for `RECONCILIATION_HEALTH_REPORT`,
  `RECONCILIATION_LOCKED_INCONSISTENT`, `BACKFILL_PAPER_SL_TP_RAN`, and
  `RECONCILIATION_CLOSED_UNRECOVERABLE`.
- CLI tests for the new close tool covering dry-run, sub-account filter, and
  idempotency.
- Dashboard tests for green/yellow/red banner states, the drill-through
  table, and the cash-only suppression rule.

## Inception Sync

The unit is registered in the inception unit-of-work map. No new FR/NFR is
introduced — this is operator workflow over the existing trading-core and
persistence-data-integrity contracts.

## Code-Generation Plan

Implementation steps the developer will tick off in the next cycle. Each
bullet names the module location, the function or method to add, and the
test file that gates it.

### 1. Runtime engine: startup health check

- Module: `src/runtime/reconciliation.py` (new).
  - Add `OpenTradeState` enum with the four states.
  - Add `classify_open_trade(row, perf_index) -> OpenTradeState`.
  - Add `compute_health_report(data_dir, sub_account_ids) -> dict`.
- Module: `src/runtime/engine.py`.
  - Add `TradingEngine._run_reconciliation_health_check()` invoked from
    `run_forever` before the cycle loop.
  - Emit `RECONCILIATION_HEALTH_REPORT` via `ActivityLog.record`.
  - Emit `RECONCILIATION_LOCKED_INCONSISTENT` when any sub-account fails the
    locked-sum cross-check.
- Module: `src/runtime/activity_log.py`.
  - Add `ActivityEventType.RECONCILIATION_HEALTH_REPORT`,
    `ActivityEventType.RECONCILIATION_LOCKED_INCONSISTENT`,
    `ActivityEventType.BACKFILL_PAPER_SL_TP_RAN`,
    `ActivityEventType.RECONCILIATION_CLOSED_UNRECOVERABLE`.
- Tests: `tests/test_runtime_reconciliation.py` (new) for classifier,
  health-report shape, and locked-consistency cross-check.
- Tests: `tests/test_runtime_engine.py` for the integration path —
  `test_startup_emits_reconciliation_health_report`,
  `test_startup_emits_locked_inconsistent_event`.

### 2. Backfill tool: emit activity event

- Module: `src/tools/backfill_paper_sl_tp.py`.
  - After the live run completes (not in dry-run), append a single
    `BACKFILL_PAPER_SL_TP_RAN` event carrying the aggregated
    `BackfillSummary` counters.
- Tests: `tests/test_tools_backfill_paper_sl_tp.py` —
  `test_live_run_emits_activity_event`,
  `test_dry_run_does_not_emit_activity_event`.

### 3. New tool: close unrecoverable trades

- Module: `src/tools/close_unrecoverable_paper_trades.py` (new).
  - `close_unrecoverable_paper_trades(data_dir, sub_account, dry_run) ->
    CloseSummary`.
  - CLI mirroring `backfill_paper_sl_tp`'s flags.
  - Emits one `RECONCILIATION_CLOSED_UNRECOVERABLE` event per closed row.
- Tests: `tests/test_tools_close_unrecoverable_paper_trades.py` (new) —
  classifier-driven row selection, `--dry-run` non-mutation, idempotency,
  single-sub-account filter.

### 4. Dashboard banner + drill-through

- Module: `src/dashboard/pages/engine.py`.
  - Add `build_reconciliation_status_banner(events) -> ReconciliationBanner`
    that reads the most recent `RECONCILIATION_HEALTH_REPORT` event and
    returns `(color, message, cta)`.
  - Render the banner at the top of the page.
- Module: `src/dashboard/pages/trading.py`.
  - Render the same banner at the top of the page.
  - Add the cash-only suppression rule: if `totals.open_trade_count > 0`,
    suppress the cash-only summary and render the reconciliation drill-
    through above the portfolio snapshot.
- Module: `src/dashboard/pages/engine.py` (continued).
  - Add `build_reconciliation_drilldown_dataframe(events) -> pd.DataFrame`
    for the per-trade expander.
- Tests: `tests/test_dashboard_engine.py` —
  `test_reconciliation_banner_green`,
  `test_reconciliation_banner_yellow_on_degraded`,
  `test_reconciliation_banner_red_on_unrecoverable`,
  `test_reconciliation_drilldown_dataframe_shape`.
- Tests: `tests/test_dashboard_trading.py` —
  `test_cash_only_suppressed_when_ledger_has_open_trades`.

### 5. Documentation

- Update `docs/TECH-DEBT.md` to reference the runtime-reconciliation unit
  closing out the deployed-state remediation work that DEBT-058 and DEBT-059
  began.
- Add a session log entry per the standard `/dev-crypto` cycle.

## Open Decisions

The team-lead will resolve these before the code-generation cycle begins.

- Should the startup health check be sync (blocks startup until the operator
  acks a non-green state) or async (logs the event, continues, lets the
  dashboard surface the state)? Spec currently recommends async.
- Should `unrecoverable` open trades auto-close at startup, or always wait
  for the operator to invoke the close tool explicitly? Spec currently
  recommends operator-explicit.
- Should the dashboard reconciliation banner be dismissible per-session, or
  persistent until the underlying state clears? Spec currently recommends
  persistent.
- Does live mode tighten the failure-mode contract — for example, always
  fail-startup if any sub-account has `unrecoverable > 0`, regardless of the
  paper-mode policy? Spec currently treats this as live-mode TBD.
- Should the close tool record a synthetic `PerformanceRecord` for
  `unrecoverable` closures so feedback-loop counters don't silently lose the
  trade, or is the activity event sufficient?
