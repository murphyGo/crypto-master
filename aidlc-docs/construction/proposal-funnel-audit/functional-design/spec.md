# Proposal Funnel Audit Functional Specification

## Purpose

`proposal-funnel-audit` makes the full proposal lifecycle observable as a
single end-to-end funnel so operators can distinguish a weak strategy signal
from a healthy risk control firing without tailing logs.

The 2026-05-13 Fly snapshot recorded 2,624 proposal files generated, 773
runtime-accepted events, 118 final-accepted proposal files, and 100 opened
positions. The drop-off from 2,624 to 773 to 118 to 100 is currently invisible
on the dashboard. DEBT-061 shipped a single coarse fail-closed rate per
`(sub_account, technique)` that catches whole-strategy silent collapse, but it
does not explain *which* gate is killing a proposal once the strategy emits.
This unit owns the funnel taxonomy, the per-state counters, the
post-acceptance rejection-record contract, the cap diagnostic payload, and
the dashboard surface that ties the pieces together.

The unit is intentionally a re-projection of state Crypto Master already
emits. It does not introduce new gates, new strategy logic, or new exchange
behavior. It only requires that every gate transition is recorded with
enough context for operators and dashboards to count and drill through.

## Funnel States and Transitions

The proposal funnel is a linear taxonomy with explicit transition events.
Every proposal moves through these states in order; the first terminal
rejection state stops progression. The names match the existing
`ProposalEngine` / `_handle_proposal` flow so operators recognise them.

### State 1: `generated`

The proposal engine produced a `Proposal` candidate for a strategy on a
symbol. Reached after the strategy's `analyze()` returned non-neutral and
sizing succeeded (i.e. the proposal cleared the `proposals_emitted`
denominator from DEBT-061).

Transition event: `PROPOSAL_GENERATED` (already exists).

### State 2: `scored`

The composite score is attached to the proposal. This is a logical
sub-state of `generated` and shares the same event; called out separately
so the funnel UI can display "score < threshold" rejections distinctly.

### State 3a: `score_accepted` / State 3b: `score_rejected`

Composite score evaluated against the configured threshold by the proposal
engine's decision gate. `score_rejected` is the dominant single failure
mode in the 2,624 to 773 drop-off.

Transition events:
- `score_accepted`: `PROPOSAL_ACCEPTED` with `details.reason="score_above_threshold"`.
- `score_rejected`: `PROPOSAL_REJECTED` with `details.reason` carrying
  the existing free-form rejection text (composite below threshold, R/R
  below floor, sample size insufficient, etc.).

### State 4: `gate_accepted` / `gate_rejected_<gate_name>`

A score-accepted proposal then runs the post-acceptance gate chain in
`_handle_proposal`. The chain executes in the current order — do not
re-order in this unit; gate-sequencing changes belong to DEBT-062. The
named gates are:

1. `market_regime` — emits `MARKET_REGIME_BLOCKED` on reject.
2. `correlation` — emits `CORRELATION_WARNING` (advisory) or
   `PROPOSAL_REJECTED` with `details.reason="correlation_blocked"` when
   enforcing.
3. `trend_filter` — emits `PROPOSAL_REJECTED` with
   `details.reason="trend_filter_blocked"`.
4. `sibling_family` — emits `PROPOSAL_REJECTED` with
   `details.reason="sibling_family_dedup"`.
5. `runtime_safety_pause` — emits `PROPOSAL_REJECTED` with
   `details.reason="runtime_safety_paused"`.
6. `total_position_cap` — emits `PROPOSAL_REJECTED` with
   `details.reason="total_cap"` and the cap-diagnostic payload (§3).
7. `per_symbol_position_cap` — emits `PROPOSAL_REJECTED` with
   `details.reason="symbol_cap"` and the cap-diagnostic payload (§3).
8. `stale_quote` — emits `PROPOSAL_REJECTED` with
   `details.reason="stale_quote_no_live_data"` (fires inside `_execute`).

Each event payload must include `proposal_id`, `record_id`, `symbol`,
`signal`, `sub_account_id`, `technique_name`, and the gate-specific
diagnostic (see §3 for caps; for market-regime use the existing
`MARKET_REGIME_BLOCKED` payload contract). The `record_id` field is the
join key the dashboard needs to collapse "accepted-then-blocked" events
into a single funnel row.

### State 5: `proposal_opened`

`_execute` invoked `trader.open_position`. Reached when every gate in
State 4 returned accept.

Transition event: `POSITION_OPENED` (already exists). Must additionally
carry `record_id` and `proposal_id` so funnel joins are one query.

### State 6: `trade_opened`

The trader confirmed the fill (paper or exchange acknowledged). On
exception the path emits `POSITION_OPEN_ERRORED` and the proposal stays
in state 5 with a terminal `open_errored` final state.

Transition event: `POSITION_OPENED` (same event as State 5; the funnel
distinguishes the two via the presence or absence of a paired
`POSITION_OPEN_ERRORED`).

### State 7: `outcome_linked`

A closed trade is linked back to its proposal record via
`ProposalHistory.attach_outcome`. The record's `trade_id`,
`outcome_pnl_percent`, and `outcome_recorded_at` are now populated.

Transition event: `POSITION_CLOSED` carrying the originating
`proposal_id` and `record_id` so the funnel UI can render PnL alongside
the funnel row.

### Transition contract summary

| From | To | Event | Reason field |
|------|----|-------|--------------|
| (start) | `generated` | `PROPOSAL_GENERATED` | n/a |
| `generated` | `score_rejected` | `PROPOSAL_REJECTED` | composite below threshold, R/R below floor, sizing failure |
| `generated` | `score_accepted` | `PROPOSAL_ACCEPTED` | `score_above_threshold` |
| `score_accepted` | `gate_rejected_market_regime` | `MARKET_REGIME_BLOCKED` | `market_regime_blocked_<regime>` |
| `score_accepted` | `gate_rejected_correlation` | `PROPOSAL_REJECTED` | `correlation_blocked` |
| `score_accepted` | `gate_rejected_trend_filter` | `PROPOSAL_REJECTED` | `trend_filter_blocked` |
| `score_accepted` | `gate_rejected_sibling_family` | `PROPOSAL_REJECTED` | `sibling_family_dedup` |
| `score_accepted` | `gate_rejected_runtime_safety` | `PROPOSAL_REJECTED` | `runtime_safety_paused` |
| `score_accepted` | `gate_rejected_total_cap` | `PROPOSAL_REJECTED` | `total_cap` (+ cap diagnostic) |
| `score_accepted` | `gate_rejected_symbol_cap` | `PROPOSAL_REJECTED` | `symbol_cap` (+ cap diagnostic) |
| `score_accepted` | `gate_rejected_stale_quote` | `PROPOSAL_REJECTED` | `stale_quote_no_live_data` |
| `gate_accepted` | `proposal_opened` | `POSITION_OPENED` | n/a |
| `proposal_opened` | `trade_opened` | (paired with absence of `POSITION_OPEN_ERRORED`) | n/a |
| `proposal_opened` | `open_errored` | `POSITION_OPEN_ERRORED` | exchange error |
| `trade_opened` | `outcome_linked` | `POSITION_CLOSED` | close reason |

## Post-Approval Rejection Records

The currently-ambiguous case: a proposal passes the score-threshold gate
(emits `PROPOSAL_ACCEPTED`) and is then blocked by a later gate. Today the
proposal record reads `accepted=true` and a separate activity event reads
`rejected`; operators must fuzzy-join by `proposal_id`.

The funnel contract:

- `ProposalRecord` gains a `final_state` field carrying the funnel terminal
  state from §1: one of `score_rejected`, `gate_rejected_<gate_name>`,
  `proposal_opened`, `trade_opened`, `outcome_linked`, or `open_errored`.
- The existing `decision` field (`PENDING` / `ACCEPTED` / `REJECTED`)
  remains untouched. `decision` records the score-time outcome; the new
  `final_state` records the funnel terminal. A proposal can carry
  `decision=ACCEPTED` and `final_state=gate_rejected_symbol_cap` — that is
  no longer a contradiction, it is the explicit shape of a post-approval
  rejection.
- When a later gate fires, the proposal record is rewritten via
  `record.model_copy(update={...})` so the on-disk record's `final_state`
  reflects the terminal gate, the `rejection_reason` carries the gate's
  reason string, and the `decision_at` timestamp moves to the gate-fire
  time.
- Every gate activity event must carry `record_id` in its `details`
  payload so the funnel join is exactly one indexed lookup, not a fuzzy
  text match.
- Dashboard counts are computed from `final_state`, not from `decision`.
  The DEBT-061 emit/fail-closed counters remain authoritative for the
  coarse "did this strategy fire at all" question and continue to ignore
  post-approval gate rejections by design (see §6 Open Decisions for the
  subsume-vs-sibling question).

The score-time `PROPOSAL_ACCEPTED` event is preserved as an emission
signal. The funnel UI shows it but counts the proposal in its terminal
bucket, not the accepted bucket.

## Cap-Rejection Diagnostics

When `total_position_cap` or `per_symbol_position_cap` rejects a proposal,
operators need to know which *existing* position is blocking. Today the
event payload only carries `open_count` and `cap`. The funnel contract
adds:

```text
gate_rejection.details = {
  proposal_id: str
  record_id: str
  symbol: str
  signal: "long" | "short"
  sub_account_id: str
  technique_name: str
  reason: "symbol_cap" | "total_cap"
  cap: int                          # configured limit
  open_count: int                   # current open count at decision time
  blocking_trades: [                # one entry per existing trade counted toward the cap
    {
      trade_id: str                 # TradeHistory.id of the blocker
      symbol: str
      side: "long" | "short"
      entry_time: datetime          # UTC-aware
      age_seconds: int              # now_utc() - entry_time at decision time
      unrealized_pnl_percent: float # at decision time, against current ticker
      monitorable: bool             # coordinate with runtime-reconciliation
      technique_name: str
      proposal_record_id: str | None  # link back to the blocker's proposal
    },
    ...
  ]
}
```

`monitorable` carries the boolean from the `runtime-reconciliation` state
taxonomy (open trade has a live monitor cycle observing it). An open trade
that is counting toward the cap but is *not* monitorable is exactly the
operator-facing case "I am blocked by a position the engine cannot even
close" — that should surface in the funnel UI.

The correlation gate uses the same diagnostic shape for its blocker (a
sibling trade in another sub-account), with `reason="correlation_blocked"`
and `blocking_trades` listing the correlated open exposure.

## Dashboard Behavior

The dashboard surfaces the funnel across five views. All views read from
the existing `ProposalHistory` + `ActivityLog` storage; no new persistence
layer is required.

### Funnel-conversion table

A single table per sub-account showing the count at each state in §1 for
a selectable time window (last 24h, last 7d, lifetime). Columns:

- `generated`
- `score_accepted` / `score_rejected`
- `gate_rejected_market_regime`
- `gate_rejected_correlation`
- `gate_rejected_trend_filter`
- `gate_rejected_sibling_family`
- `gate_rejected_runtime_safety`
- `gate_rejected_total_cap`
- `gate_rejected_symbol_cap`
- `gate_rejected_stale_quote`
- `proposal_opened`
- `trade_opened`
- `outcome_linked`

The conversion ratio between adjacent states is rendered inline so a
2,624 to 773 to 118 to 100 collapse is one glance.

### Per-gate rejection volume

Bar chart of gate-rejection counts in the selected window plus a clickable
sample rejection. Clicking a bar opens the most recent rejection's full
diagnostic (cap blockers, regime label, correlated trades) so the
operator can immediately answer "which existing position is blocking?".

### Per-strategy emitted-to-opened heatmap

Rows are strategies, columns are funnel states in §1. Cell value is the
count, cell colour scales by ratio against the strategy's `generated`
count. Operators reading "RSI emitted 400 proposals but opened 4" can
immediately see which gate ate the other 396.

### Per-strategy drill-through

Selecting a strategy + sub-account opens a panel listing the
rejection-cause breakdown across the window (one row per terminal state),
the most recent example of each, and a link to the matching proposal
record file. Answers the "why is strategy X not firing?" question that
the 2026-05-13 review surfaced.

### Per-account funnel summary

The dashboard `command-center` home view gets a single-line funnel
summary per sub-account: `generated -> opened` conversion percent plus
the top blocking gate by volume. This is the entry point; the four views
above are the drill-through.

## Test Scope

Future implementation should include:

- Funnel-state transition tests in `tests/test_runtime_engine.py` for each
  gate in §1 — every gate must produce its terminal `final_state` value
  on the proposal record.
- `ProposalRecord.final_state` schema tests in
  `tests/test_proposal_interaction.py` including round-trip persistence
  and the backward-compatible default for legacy records without the
  field.
- Cap-diagnostic payload tests in `tests/test_runtime_engine.py` covering
  the symbol-cap and total-cap paths, the `blocking_trades` shape, the
  `monitorable` flag, and the multi-blocker case.
- `record_id` join tests asserting every post-acceptance gate event
  carries the record id.
- Dashboard tests in `tests/test_dashboard_engine.py` (or a new
  `tests/test_dashboard_funnel.py`) for the conversion table, per-gate
  view, heatmap, drill-through, and per-account summary.
- Counter tests for the funnel-state aggregator covering the time-window
  selection and per-sub-account isolation.

## Inception Sync

The unit is registered in the inception unit-of-work breakdown
(`aidlc-docs/inception/units/unit-of-work.md`) and the legacy phase map.
Requirements coverage is FR-011, FR-012, FR-013, FR-014, FR-015, FR-029,
FR-043, NFR-007, NFR-012 — every entry already exists; no new FR or NFR
is introduced.

## Open Decisions

- **Subsume vs sibling DEBT-061.** The `FailClosedMetricsTracker` from
  DEBT-061 counts a coarse `emitted` / `fail_closed` pair *before* the
  composite score gate. The funnel taxonomy treats `generated` as the
  funnel entry. Decision: should this unit absorb the tracker (treat the
  coarse rate as the most-coarse funnel layer) or sit alongside it as a
  separate post-emission projection? Recommendation: sibling for now —
  the DEBT-061 counters are persisted per `(sub_account, technique)` and
  serve the "did the strategy fire at all?" question, which is upstream
  of every state in §1. The funnel counters live on the proposal records
  themselves and are derived, not authoritative.
  - **Resolved 2026-05-13**: sibling. Rationale: DEBT-061's single-rate counter is the coarsest funnel layer and earned its place; funnel audit consumes/extends it, doesn't replace.
- **Time-window contract.** DEBT-061 is lifetime cumulative. Dashboards
  for the funnel views want rolling 24h / 7d / lifetime so operators can
  see today's collapse against the long-run baseline. Decision: ship
  rolling windows in the dashboard layer, derived from
  `ProposalRecord.decision_at` timestamps; do not change the on-disk
  persistence contract.
  - **Resolved 2026-05-13**: derive rolling at dashboard layer; persist lifetime cumulative only. Rationale: persistence stays simple; operator picks the window at query time.
- **Per-gate counter cardinality.** Should every gate get a persistent
  counter (paralleling `FailClosedMetricsTracker`) or should the
  dashboard derive gate counts on read from `final_state`? Recommendation:
  derive on read for v1 — the proposal record store is small enough
  (thousands of files, not millions) that scanning is cheap, and a
  derived view avoids a second persistence contract that can drift from
  the records. Promote to persistent counters only if the dashboard read
  cost becomes the bottleneck.
  - **Resolved 2026-05-13**: derived-on-read for v1. Rationale: counters are computed from activity-event stream; avoids persistence-schema explosion as gates evolve.
- **Backfill strategy.** Existing proposal files do not carry
  `final_state`. Options: (a) backfill once on first read by inferring
  the terminal state from existing fields (`decision`, `rejection_reason`,
  `trade_id`), (b) count forward only and treat pre-cutover proposals as
  a separate "legacy" bucket. Recommendation: (a) — the inference is
  unambiguous for the common cases (`decision=REJECTED` and no `trade_id`
  yields `score_rejected`; `decision=ACCEPTED` and `trade_id` set yields
  at least `trade_opened`); the post-approval gate cases need a fallback
  bucket (`gate_rejected_unknown`) because the original reason isn't on
  the record.
  - **Resolved 2026-05-13**: forward-only with `gate_rejected_unknown` fallback bucket for legacy. Rationale: don't rewrite history; legacy rows show in their own bucket until natural rollover.
- **Stale-quote gate position.** Stale-quote rejection fires inside
  `_execute` after every other gate accepts. Operators may want it
  grouped with State 4 gates in the dashboard even though it executes in
  State 5. Recommendation: present it as a State 4 gate for UI purposes;
  the on-disk record's `final_state` is still
  `gate_rejected_stale_quote`.
  - **Resolved 2026-05-13**: State 4 (gate-rejected, pre-open). Rationale: stale-quote rejection is a pre-open gate, not a post-open execution event.

All decisions above resolved 2026-05-13; code-generation cycle unblocked.

## Cross-Unit Dependencies

- `proposal-runtime` — owns `ProposalEngine`, `_handle_proposal`,
  `ProposalRecord`, and `ActivityLog`. This unit adds fields and
  payloads; gate semantics stay there.
- `runtime-reconciliation` — owns the `monitorable` flag on open trades
  consumed by the cap diagnostic.
- `strategy-correlation-governor` — owns the correlation gate and its
  event payload; the cap-diagnostic shape extends to correlated
  blockers.
- `market-regime` — already emits `MARKET_REGIME_BLOCKED` with the right
  payload contract; the funnel only needs the `record_id` join field.
- `dashboard-operator-command-center` — owns the home-view single-line
  funnel summary entry point.
- `dashboard-operator-ui` — owns the four drill-through views in §4.
- DEBT-061 (`FailClosedMetricsTracker`) — upstream coarse counter; this
  unit is a sibling per §6.

## Code-Generation Plan

A separate plan document at
`aidlc-docs/construction/plans/proposal-funnel-audit-code-generation-plan.md`
covers the implementation steps, verification, and completion checklist.
The plan mirrors `proposal-funnel-audit-code-generation-plan` in shape
and depth.

The implementation slices are:

1. **Schema additions.** Add `final_state: FunnelTerminalState` to
   `ProposalRecord` with a default that preserves legacy reads. The
   enum lives next to `ProposalDecision` in `src/proposal/interaction.py`.
2. **Activity event coordinates.** Every gate event in §1 must carry
   `record_id` in `details`. The market-regime event already does; the
   correlation, trend-filter, sibling, runtime-safety, total-cap,
   symbol-cap, and stale-quote events need the field added. No new
   `ActivityEventType` values are introduced — the funnel uses
   `details.reason` as the gate discriminator. (Per market-regime
   spec §4: a gate earns its own event type *iff* the dashboard charts
   it over time. Cap, sibling, and stale-quote do not meet that bar.)
3. **`_handle_proposal` rewrites.** Each gate's `model_copy(update=...)`
   call gains `final_state=<terminal_value>`. The accept path sets
   `final_state="proposal_opened"` after `_stale_quote_gate` passes.
   `_execute` sets `final_state="trade_opened"` on
   `trader.open_position` success.
4. **Cap diagnostic.** Extract a `_build_cap_blocker_payload(open_trades,
   trader, exchange)` helper into `src/runtime/engine.py` that emits the
   `blocking_trades` array described in §3. The `monitorable` flag is
   looked up via the runtime-reconciliation accessor.
5. **Outcome linkage.** `attach_outcome` sets
   `final_state="outcome_linked"` and propagates `proposal_id` /
   `record_id` into the `POSITION_CLOSED` event payload.
6. **Funnel aggregator.** New `src/proposal/funnel.py` with a
   `FunnelCounts` Pydantic model and a `compute_funnel_counts(records,
   window)` pure function that takes an iterable of `ProposalRecord` and
   returns per-state counts. No persistence — derived on read per §6.
7. **Counter coordination.** Do *not* extend `FailClosedMetricsTracker`.
   The funnel aggregator reads `final_state` from proposal records; the
   fail-closed tracker stays the coarse upstream signal.
8. **Dashboard views.** New page `src/dashboard/pages/funnel.py` (or
   section under the existing engine page) renders the conversion table,
   per-gate volume, per-strategy heatmap, and drill-through. The
   command-center home view consumes `compute_funnel_counts` for the
   one-line summary.
9. **Tests.** Per §5: gate transition tests, schema round-trip,
   cap-diagnostic payload, `record_id` join, dashboard rendering, and
   funnel aggregator pure-function tests.

The full sequencing and verification matrix lives in the code-generation
plan.
