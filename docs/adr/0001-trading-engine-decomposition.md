# ADR 0001 — `TradingEngine` God-Object Decomposition (CAH-15)

- **Status**: Proposed
- **Date**: 2026-05-28
- **Deciders**: team-lead + user (go/no-go gate before any code)
- **Work unit**: CAH-15 (`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`)
- **Origin finding**: ENG-F3 (VALID, cold-read-verified) — God-Object / SRP /
  Divergent-Change in `src/runtime/engine.py`.
- **Reviewers required before implementation**: `quant-trader-expert` (trading
  semantics), full `pytest` + `ruff check src tests` + `mypy src` per slice.

> **This ADR is a DESIGN document. No code changes accompany it.** It exists to
> let the lead + user decide go/no-go and to pin the cache-ownership contract
> before any extraction begins. CAH-15 is gated on CAH-05 landing first.

---

## Context

`src/runtime/engine.py::TradingEngine` is **5,343 lines** with **65 methods**
spanning roughly six concerns. It is the per-cycle orchestrator: for each
sub-account it scans for proposals, runs each proposal through a long ordered
gate chain, executes survivors, monitors open positions for exits, and records a
portfolio snapshot. State that the cycle needs is held on `self` — including a
set of per-cycle caches — which is exactly what makes the class hard to change
along any single axis without reading the whole file (Divergent Change).

### Verified concern map (read against the live file 2026-05-28)

| Concern | Representative methods | Approx. extent |
|---|---|---|
| Cycle orchestration | `run_forever`, `stop`, `run_cycle` (898), `_run_one_cycle_with_guard`, `_interruptible_sleep`, `_scan`, `_auto_decide` | the spine; stays on engine |
| Gate chain (proposal path) | `_handle_proposal` (1160), `_finalize_rejection`, `_risk_budget_sizing_gate`, the kill-switch / cap / freeze / safety-pause / trend / regime / strategy-action / correlation / stale-quote gates, `_execute`, plus equity/pnl/cap-blocker helpers | ~1130–4205, the largest concern |
| Position monitoring & exits | `_monitor` (4421), `_maybe_stale_age_action`, `_maybe_time_stop`, orphan handling (inlined in `_monitor` ~4464+), `_classify_trade_reconciliation`, `_resolve_time_stop_window`, `_technique_name_for_trade`, `_missing_position_state` | ~4206–4789 |
| Persistence / snapshotting | `_record_portfolio_snapshot` (4790), `_record_closed_trade`, `_save_performance_record`, `_classify_close_reason`, `_find_proposal_record_for_trade` | ~4790–4995 |
| Reconciliation health | `_run_reconciliation_health_check`, `_reconciliation_data_dir` | ~4997–5108 |
| Caches / lookups / policy resolution | the per-cycle/cross-cycle caches + `_remember_mark_price`, `_get_cached_mark_price`, `_runtime_policy_for*`, `_trader_for_sub_account`, `_exchange_for_trader`, `_current_applied_state_map`, `_maybe_emit_strategy_action_transitions` | scattered |

### The caches — corrected from the brief

The brief states "8 per-cycle caches reset at `run_cycle:914-919`." The live code
does **not** match that. Verified at `engine.py:915-920`, the per-cycle reset
clears only **six** caches:

```
self._strategy_lookup_cache = None        # 915
self._runtime_policy_cache = {}           # 916
self._runtime_safety_score_cache = None   # 917
self._htf_trend_cache = {}                # 918
self._accepted_family_signals = {}        # 919
self._market_regime_cache = {}            # 920
```

The remaining two caches are **deliberately cross-cycle** and are **not** part of
the reset loop:

- `_mark_price_cache` (DEBT-066) — write-through populated by `_monitor` /
  `_record_portfolio_snapshot` ticker reads (`_remember_mark_price`, 3717) and
  read by `_build_cap_blocker_payload`. Freshness is enforced *at read time* in
  `_get_cached_mark_price` (3731); the cache is allowed to keep stale entries
  because the next cycle's write overwrites them. **Resetting it per cycle would
  be a behavior change** (it would null out the cap-blocker `unrealized_pnl_percent`
  path).
- `_orphan_strike_counts` (DEBT-058) — cross-cycle by design. It counts
  *consecutive* monitor cycles a trade is observed orphaned, and force-closes
  after `ORPHAN_AUTO_CLOSE_THRESHOLD` strikes. It is pruned (not reset) inside
  `_monitor` at 4453-4457 to currently-open trade ids. **Resetting it per cycle
  would defeat the watchdog entirely.**

This 6-reset / 2-cross-cycle split is the single most load-bearing invariant in
the decomposition and is the reason cache ownership (below) is specified
method-by-method rather than "move the caches with the methods."

### Why this is HIGH behavior-change risk

Today every cache, every injected dependency, and the per-cycle `cycle_id` /
`CycleResult` accumulator are reachable from any method via `self`. Extracting a
collaborator turns implicit shared state into an explicit interface. If the
ordering of the per-cycle reset, the write-through to `_mark_price_cache`, or the
prune-not-reset of `_orphan_strike_counts` shifts even slightly, the system mis-
sizes, mis-blocks, or fails to force-close orphans — all silent, all in the live
money path.

---

## Decision

Extract **two** collaborators with confidence — `SnapshotRecorder` and
`PositionMonitor` — and treat the gate-chain extraction (`ProposalGateChain`) as
a **conditional third slice that may be declined** after the first two land and
the true coupling is measured. See *Alternatives* for the honest recommendation.

All collaborators follow the existing constructor-injection (DI) pattern used in
`TradingEngine.__init__` and `main.build_engine`. `BaseExchange`, `Trader`,
`ProposalHistory`, `ActivityLog`, `PortfolioTracker`, and `EngineConfig` stay
injected dependencies — collaborators receive the instances they need, they do
not construct them. The engine remains the composition point that calls
collaborators **in the same order as today**.

### Collaborator 1 — `SnapshotRecorder` (lowest coupling, extract first)

Owns persistence/snapshotting. Pure outputs, no gate participation, no per-cycle
cache ownership.

- **Moves**: `_record_portfolio_snapshot`, `_record_closed_trade`,
  `_save_performance_record`, `_classify_close_reason`,
  `_find_proposal_record_for_trade`.
- **Receives (constructor-injected)**: `proposal_history: ProposalHistory`,
  `activity_log: ActivityLog`, `portfolio_tracker: PortfolioTracker | None`,
  `mode: Mode`, `quote_currency: str`, and a callback or reference for
  `_remember_mark_price` write-through (see cache ownership).
- **Receives (per-call)**: `cycle_id`, `sub_account`, `trader`, `exchange`,
  `trade`, `reason` — the same arguments these methods take today.
- **Exposed interface** (signatures preserved from the engine):
  - `async record_portfolio_snapshot(cycle_id, sub_account, trader, exchange=None) -> None`
  - `record_closed_trade(trade, reason, cycle_id) -> None`
- **Cache touch**: `_record_portfolio_snapshot` currently calls
  `self._remember_mark_price` (4830). Because `_mark_price_cache` stays
  engine-owned (below), the recorder writes through a `remember_mark_price`
  callable passed in at construction. It does **not** own the cache.

### Collaborator 2 — `PositionMonitor` (medium coupling, extract second)

Owns the monitor/exit pass and the orphan watchdog, including the
`_handle_orphan_trade` extraction called for by ENG-F6 (the orphan logic is
currently inlined in `_monitor` ~4464+; this slice extracts it into a named
method on the monitor).

- **Moves**: `_monitor`, `_maybe_stale_age_action`, `_maybe_time_stop`,
  `_classify_trade_reconciliation`, `_resolve_time_stop_window`,
  `_technique_name_for_trade`, `_missing_position_state`, and a new
  `_handle_orphan_trade` extracted from the `_monitor` orphan branch.
- **Owns**: `_orphan_strike_counts` (cross-cycle; pruned in `_monitor`, never
  reset per cycle). This cache is the monitor's private state and moving it with
  the monitor is correct precisely because it is **not** in the per-cycle reset
  loop. The prune logic at 4453-4457 moves with it.
- **Receives (constructor-injected)**: `activity_log`, a reference to the
  `SnapshotRecorder` (so a closed trade is recorded via
  `recorder.record_closed_trade`), the `proposal_engine`/strategy-lookup access
  needed by `_resolve_time_stop_window`/`_technique_name_for_trade`, and the
  `remember_mark_price` write-through callable (the monitor's ticker reads at
  4830-equivalent also write through to the engine-owned mark cache).
- **Receives (per-call)**: `cycle_id`, `result: CycleResult`, `sub_account`,
  `trader`, `exchange`.
- **Exposed interface**:
  - `async monitor(cycle_id, result, sub_account, trader, exchange=None) -> None`
- **Note**: the monitor mutates the shared `CycleResult` accumulator (closed
  counts). It receives `result` per call and mutates it in place exactly as
  `_monitor` does today — no change to the accumulation contract.

### Collaborator 3 — `ProposalGateChain` (highest coupling, CONDITIONAL)

This is the gate path: `_handle_proposal` plus ~20 gate methods, `_execute`, and
the equity/pnl/cap-blocker helpers. **Recommendation: do not commit to this slice
in this ADR.** Decide go/no-go on it only after Slices 1 and 2 land and the
residual coupling is measured (see *Alternatives* and *Risks*). If it proceeds:

- **Not a pipeline / not a registry.** Per the plan's §1.2 explicit rejection,
  gate **order is load-bearing trading semantics** with documented inter-gate
  dependencies and heterogeneous signatures. `ProposalGateChain` is a *named home
  for the gate methods*, called by the engine in the **same hardcoded order** as
  `_handle_proposal` today. It is **not** a list of pluggable `Gate` objects and
  there is **no** `GateContext`. The engine (or a thin `handle_proposal` method on
  the chain) invokes gate 1, then gate 2, ... in source order.
- **Moves (if it proceeds)**: `_handle_proposal`, `_finalize_rejection`, the gate
  methods listed in the concern map, `_execute`, and the cap-blocker / equity /
  pnl helpers (`_build_cap_blocker_payload`, `_account_equity`,
  `_open_unrealized_pnl`, `_open_stop_risk_sum`, `_realized_pnl_today`, etc.).
- **Owns / borrows caches**: this is where coupling is worst. The gates read
  `_runtime_safety_score_cache`, `_runtime_policy_cache`, `_htf_trend_cache`,
  `_market_regime_cache`, `_accepted_family_signals`, `_strategy_lookup_cache`,
  and `_mark_price_cache` (via `_build_cap_blocker_payload`). These are all in or
  adjacent to the per-cycle reset. See cache ownership for the mechanism.
- **Gate on CAH-05** having already extracted `_finalize_rejection` /
  `_finalize_acceptance` and the two inlined cap gates, so the seam is proven and
  `_handle_proposal` already reads as a flat gate list before this slice moves it.

---

## Cache ownership (the riskiest decision — specified concretely)

**The engine retains ownership of all six per-cycle-reset caches and the
per-cycle reset loop itself.** The reset loop at `run_cycle:915-920` stays on the
engine, verbatim and in the same order. Collaborators that need a per-cycle cache
**borrow** it, they do not own it.

| Cache | Owner | Reset policy | Mechanism after decomposition |
|---|---|---|---|
| `_strategy_lookup_cache` | **engine** | per-cycle (915) | engine resets; gate chain reads via accessor |
| `_runtime_policy_cache` | **engine** | per-cycle (916) | engine resets; `_runtime_policy_for*` stays engine-side accessors |
| `_runtime_safety_score_cache` | **engine** | per-cycle (917) | engine resets; `_current_runtime_safety_score` stays engine-side |
| `_htf_trend_cache` | **engine** | per-cycle (918) | engine resets; trend gate reads/writes via accessor |
| `_accepted_family_signals` | **engine** | per-cycle (919) | engine resets; sibling-family gate reads/writes via accessor |
| `_market_regime_cache` | **engine** | per-cycle (920) | engine resets; regime gate reads/writes via accessor |
| `_mark_price_cache` | **engine** | cross-cycle (overwrite-on-write) | engine owns; `_remember_mark_price`/`_get_cached_mark_price` stay engine-side; `SnapshotRecorder`/`PositionMonitor` write through an injected `remember_mark_price` callable |
| `_orphan_strike_counts` | **`PositionMonitor`** | cross-cycle (pruned, never reset) | moves WITH the monitor because it is private monitor state outside the reset loop |

**Why caches stay engine-owned rather than moving with the gate chain:** the
reset loop is a single atomic block whose *ordering and completeness* is the
behavior contract. If the six caches were distributed across collaborators, the
reset would become `engine.reset()` + `chain.reset_cycle_caches()` +
`monitor.reset()` — three call sites that can drift out of sync, the exact
Shotgun-Surgery smell we are removing. Keeping the six caches and the one reset
block on the engine means **the per-cycle reset semantics cannot regress in a
gate-chain extraction** because the gate chain never owns them; it reads/writes
them through narrow accessors the engine exposes (e.g. `htf_trend_cache_get/set`)
or through a small `CycleCaches` value the engine passes into `handle_proposal`
per cycle.

**Decision: the engine keeps the reset loop and the six per-cycle caches.**
`_orphan_strike_counts` is the one cache that moves (to `PositionMonitor`)
precisely because it is *not* reset per cycle. `_mark_price_cache` stays on the
engine and is written through a callback.

**Rejected alternative for the mechanism:** "engine owns the reset loop but calls
`collaborator.reset_cycle_caches()`." Rejected because it reintroduces the
multi-site reset drift this ADR is trying to eliminate, and it would split the
single atomic reset block into N calls whose ordering vs. the `_operator_freeze`
re-read (912) and `_maybe_emit_strategy_action_transitions` (933) would have to be
re-proven. Keeping the caches engine-owned makes the reset a no-op to verify.

---

## Staging plan

Each slice is an independent, behavior-preserving PR with its own full-suite gate
and (for any slice touching the money/gate path) a `quant-trader-expert` review.
No slice changes behavior. Order is strictly increasing coupling.

**Pre-req (already planned): CAH-05 lands first** — extracts
`_finalize_rejection`/`_finalize_acceptance` and the two inlined cap gates,
proving the finalize seam and flattening `_handle_proposal`.

### Slice 1 — `SnapshotRecorder`
- Extract the five persistence methods into `src/runtime/snapshot_recorder.py`.
- Engine constructs it in `__init__` and delegates `_record_portfolio_snapshot` /
  `_record_closed_trade` call sites to it.
- `_mark_price_cache` stays engine-owned; recorder gets a `remember_mark_price`
  callback.
- **Behavior proof**: `tests/test_runtime_engine.py` snapshot + closed-trade
  assertions pass unchanged; add an assertion that the mark-price write-through
  fires on the same ticker reads as today (cap-blocker `unrealized_pnl_percent`
  path is unchanged). Full `pytest`/`ruff`/`mypy`.

### Slice 2 — `PositionMonitor` (includes ENG-F6 `_handle_orphan_trade`)
- Extract the monitor/exit methods + `_orphan_strike_counts` into
  `src/runtime/position_monitor.py`; extract the inlined orphan branch into a
  named `_handle_orphan_trade`.
- Monitor holds `_orphan_strike_counts` and the prune logic (4453-4457); writes
  closed trades through the injected `SnapshotRecorder`; writes through the
  engine's `remember_mark_price`.
- **Behavior proof**: the existing monitor/time-stop/orphan tests in
  `tests/test_runtime_engine.py` (and any orphan-force-close test — the Fly 260h
  BNB regression) pass unchanged. Add an explicit assertion that orphan strike
  counting and force-close threshold behavior is byte-identical across two cycles
  (the cross-cycle prune-not-reset invariant). Full gate + quant review.

### Slice 3 — `ProposalGateChain` (CONDITIONAL — separate go/no-go)
- Only after Slices 1 and 2 land. Re-measure coupling and decide.
- If proceeding: move `_handle_proposal` + the ~20 gates + `_execute` + cap/
  equity/pnl helpers into `src/runtime/proposal_gate_chain.py`. Gate order
  preserved exactly; engine exposes per-cycle cache accessors; no pipeline/
  registry/`GateContext`.
- **Behavior proof**: the full gate/funnel suite in `tests/test_runtime_engine.py`,
  including the asymmetric event-count assertion from CAH-05 (correlation branch
  iterates `outcome.events` only; most others iterate the concatenated list).
  Add a funnel-state count equality assertion before/after for a fixed proposal
  fixture. Full gate + mandatory quant review.

**Rollback plan**: each slice is one PR on a branch off `main`. Because every
slice is behavior-preserving and gated on the full suite plus (where relevant) a
funnel/orphan before-after equality assertion, a regression caught in review or by
the suite is a single `git revert` of that PR — no downstream slice depends on an
un-landed later slice. Slice 3 is explicitly decoupled so declining it leaves
Slices 1+2 intact and shippable.

---

## Consequences

### Positive
- `TradingEngine` shrinks from ~5,343 lines / 65 methods toward a readable cycle
  spine plus two (possibly three) focused collaborators with single change axes.
- Persistence, monitoring, and (optionally) gating each become independently
  testable and independently reviewable.
- The per-cycle reset becomes trivially auditable: it is one block on one object
  that no collaborator can desync.
- ENG-F6's orphan extraction lands as a natural by-product of Slice 2.

### Negative / costs
- Three new modules + the DI wiring in `main.build_engine` and the engine ctor.
- Collaborators borrowing engine-owned caches through accessors/callbacks is
  slightly more ceremony than direct `self.` access — accepted as the price of a
  non-regressable reset contract.
- Slice 3, if taken, is genuinely high-risk and high-effort for moderate
  structural gain (see below).

---

## Risks

1. **Per-cycle cache-reset regression (highest).** Mitigated structurally: the
   six reset caches and the reset loop never leave the engine. The reset is a
   no-op to re-verify because nothing else owns those caches.
2. **`_mark_price_cache` write-through breakage.** The cap-blocker
   `unrealized_pnl_percent` path depends on `_monitor` / snapshot ticker reads
   writing through. Mitigated by the injected `remember_mark_price` callback and a
   Slice-1 test asserting the write-through fires.
3. **`_orphan_strike_counts` cross-cycle semantics.** Moving it to the monitor is
   correct only if the prune-not-reset behavior is preserved exactly. Mitigated by
   the two-cycle orphan equality assertion in Slice 2.
4. **Gate-order / event-shape regression (Slice 3 only).** The asymmetric event
   concatenation (CAH-05 verifier note) and the exact gate order are load-bearing.
   Mitigated by gating Slice 3 on CAH-05 and the funnel before-after assertion,
   and by the option to decline Slice 3 entirely.
5. **Shared-state surprise.** Any method assumed pure that actually mutates `self`
   state would break when moved. Mitigated by extracting in increasing-coupling
   order and by the full-suite gate per slice.

---

## Alternatives considered

### A. Leave as-is
The file is large but reasonably cohesive *per concern*, and it works in a live
money path. Per the guide's "duplication is cheaper than the wrong abstraction"
and "match ceremony to complexity," doing nothing is a legitimate option. Rejected
only in part: Slices 1 and 2 have clearly separable concerns and low coupling, so
the abstraction is *not* speculative — it pays for itself in testability.

### B. Full three-collaborator extraction in staged slices (the brief's framing)
Slices 1+2+3. Chosen for Slices 1 and 2. **Slice 3 is held as conditional.**

### C. Slices 1 and 2 only; leave the gate chain on the engine — RECOMMENDED
This is the honest recommendation. After Slices 1 and 2, the engine loses the
persistence and monitoring concerns (and the orphan watchdog state), which are the
extractions with genuinely low coupling and clear single-axis change reasons.

The gate chain is different: it reads **six** of the engine's caches, the
`_operator_freeze_active` per-cycle flag, the runtime-safety score, and the
sub-account/trader/exchange resolution helpers. Extracting it does **not** make it
a pluggable pipeline (the plan rejected that and this ADR upholds the rejection) —
it just relocates ~20 ordered methods to a class the engine still calls in the
same order, while threading six caches back through accessors. That is high
behavior-change risk for a structural win that is mostly cosmetic given gate order
must stay hardcoded. Per "match ceremony to complexity," the gate chain's
complexity is *irreducible ordering*, not *missing structure* — moving it does not
reduce the thing that makes it hard.

**Recommendation: commit to Slices 1 and 2 now. Defer Slice 3 (gate-chain
extraction) and re-evaluate only after Slices 1+2 land and CAH-05 has shipped, at
which point the residual `_handle_proposal` size and the real cache-coupling count
can be measured rather than estimated. If the coupling remains as high as it looks
today, leaving the gate chain on the engine is the correct, honest outcome.**

This is consistent with ENG-F3 being VALID: the God-Object finding is real, and
removing two of its six concerns materially improves it without betting the live
gate path on a refactor whose only structural payoff is relocation.

---

## quant-trader-expert review (2026-05-28, cold-read-verified against live `engine.py`)

**VERDICT: 🟡 sound design with two specified changes.** The boundaries are
trading-correctness-safe. Every line-citation in this ADR was checked against the
live file and matches. The cache-ownership contract is correct and is the right
call. Two items must be folded in before greenlight; neither blocks the design.

### 1. Cache-ownership contract — CONFIRMED SAFE
- The reset loop at `915-920` clears exactly the six caches the ADR lists, in that
  order, between the `_operator_freeze_active` re-read (912) and
  `_maybe_emit_strategy_action_transitions` (933). Keeping the loop **and** all six
  caches engine-owned makes the reset a no-op to re-verify — there is no cross-object
  `reset()` fan-out that could desync. The rejected `collaborator.reset_cycle_caches()`
  alternative is correctly rejected; it would reintroduce Shotgun-Surgery on the one
  invariant that mis-sizes/mis-blocks if it drifts.
- `_mark_price_cache` engine-owned + write-through callback is **correct given
  DEBT-066**. Freshness is enforced read-side in `_get_cached_mark_price` (3748-3754),
  the write always overwrites (3726), and there are exactly three write sites —
  `_record_portfolio_snapshot` (4830), the `_monitor` SL/TP path (4622), and the
  orphan force-close path (4525). Two of those three sites move to collaborators, so
  the injected `remember_mark_price` callable is mandatory, not optional. **Resetting
  it per cycle would null the cap-blocker `unrealized_pnl_percent` path — do not.**
- Moving `_orphan_strike_counts` to `PositionMonitor` is **SAFE**. It is prune-not-reset
  (4452-4457), incremented at 4470-4471, dropped on recovery (4597) and on successful
  force-close (4566), and never touched outside `_monitor`. It is genuinely private
  monitor state. Because it is the watchdog's only memory of *consecutive* strikes,
  the two-cycle byte-identical assertion in Slice 2 is the right guard — keep it
  mandatory, not optional.

### 2. SnapshotRecorder boundary — CONFIRMED persistence-only
`_record_portfolio_snapshot`, `_record_closed_trade`, `_save_performance_record`,
`_classify_close_reason`, `_find_proposal_record_for_trade` carry **no** sizing, risk,
or gate logic. `_classify_close_reason` is a static reason→outcome map (4976-4982).
None of the five reads any of the six per-cycle caches, so the borrow-pattern does
**not** need to thread a per-cycle cache into the recorder — the only shared-state
touch is the `_mark_price_cache` write-through (4830), already handled by the callback.

### 3. PositionMonitor boundary — CONFIRMED exit-coherent, with CHANGE A
The exit decision is **not** split across engine/monitor. SL/TP (4624-4634),
time-stop (4640-4649), and stale-age (4658-4667) are strictly ordered fallbacks
inside one `for trade` loop, each gated by a `continue` so a trade closed by an
earlier rung never reaches a later one — no drop, no double-close. The whole cluster
moves together. `_classify_trade_reconciliation`'s resolution table
(auto_close → degraded/unrecoverable suppression, 4351-4392) is the live-money safety
that prevents force-closing a position whose exchange/ledger state is in doubt; it
depends only on the imported `classify_open_trade`, so it relocates cleanly.

  - **CHANGE A (must fold in):** the ADR's Slice-2 interface lists `monitor(...)` but
    omits that `PositionMonitor` becomes the **sole owner of `closed_count` →
    `result.positions_closed` (4668)**. All four close paths bump `closed_count`
    locally and the single write to `result.positions_closed` happens at end of pass.
    The behavior proof must assert `result.positions_closed` is identical before/after
    for a fixture exercising SL/TP **and** time-stop **and** stale-age **and** orphan
    force-close in one pass — not just the orphan path. Today's mutual-exclusion via
    `continue` is the thing most likely to regress under extraction (an accidental
    fall-through would double-count or double-close). Make the multi-rung single-pass
    assertion explicit in the Slice-2 proof.

### 4. Gate-chain DEFER — AGREE, defer Slice 3
I concur with the recommendation (Alternative C). The gate chain's complexity is
*irreducible ordering*, not missing structure, and it reads six of the engine's
per-cycle caches plus `_operator_freeze_active` and the runtime-safety score.
Relocating ~20 ordered methods while threading those caches back through accessors is
high live-money risk for a cosmetic gain. There is **no trading-correctness value** in
extracting it — gate order is the correctness property, and it stays hardcoded either
way. Defer and re-measure after Slices 1+2 + CAH-05, exactly as written.

### 5. Staging order — CORRECT, with CHANGE B
SnapshotRecorder → PositionMonitor is the right risk order (increasing coupling;
the monitor depends on the recorder via `record_closed_trade`, so the recorder must
land first). 

  - **CHANGE B (must fold in):** the dependency direction creates a **transitive
    write-through chain** — `PositionMonitor` calls `recorder.record_closed_trade`,
    and *separately* both the monitor and the recorder call `remember_mark_price`.
    Wire `remember_mark_price` as a callback injected into **both** collaborators from
    the engine (one source of truth), **not** monitor → recorder → engine. Routing the
    monitor's mark writes through the recorder would change *when* the cache is
    written relative to the exit decision (4622 fires before the close at 4626) and
    could skew a same-cycle cap-blocker read. The ADR says "injected callable" — make
    it explicit that the monitor's `remember_mark_price` is the **engine's**, injected
    directly, identical to the recorder's, and not chained through the recorder.

### Net
The two genuinely-separable concerns (persistence, monitoring) have low coupling and
clean single-axis change reasons; the abstraction pays for itself in testability and
is not speculative. With CHANGE A (multi-rung single-pass close-count assertion) and
CHANGE B (mark-price callback injected directly into both collaborators, not chained),
this is safe to greenlight for Slices 1 and 2. Slice 3 deferred. 🟡
