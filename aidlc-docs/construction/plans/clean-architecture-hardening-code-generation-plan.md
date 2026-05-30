# Clean-Architecture Hardening — Code-Generation Plan

> **Origin.** Guide-driven architecture review, 2026-05-28. Rubric: the team's
> `clean-code-architecture-guide` (SOLID, code smells → refactorings,
> Clean/Hexagonal/Onion layering, DDD value objects/entities, error-handling
> hierarchy, abstraction principles incl. AHA / Rule-of-Three / "duplication is
> cheaper than the wrong abstraction"). Eleven read-only review subagents (one
> per module/concern + one repo-wide dependency-direction audit) produced
> findings; two independent verifier subagents cold-read the cited code and
> confirmed every finding VALID or PARTIALLY VALID (zero INVALID, zero dishonest
> classifications). This plan converts the **verified** findings into bounded,
> behavior-preserving work units.

---

## 1. Architecture assessment (what the review found)

Crypto Master is a **mature modular monolith**, not a greenfield with primitive
obsession everywhere. The review's most valuable output is as much what to
**leave alone** as what to change. Establish this baseline before any work.

### 1.1 Existing strengths to PRESERVE (do not "improve")

- **`BaseExchange` port + `exchange/factory.py` registry** — ccxt is fully
  isolated in `binance.py`/`bybit.py` (zero `ccxt` imports anywhere else in
  `src/`); consumers type against the port. Textbook ports-and-adapters.
- **`proposal/notification.py` `Notifier` Protocol + dispatcher** — Slack/
  Telegram/Email/Console/File behind one Protocol; smtplib/urllib quarantined;
  failures surfaced (not swallowed) via `on_notifier_failure`. The model the
  LLM port (CAH-10) should copy.
- **`main.py` as composition root** — the only module importing concrete
  `BinanceExchange`/`BybitExchange`, `LiveTrader`/`PaperTrader`, `TradingEngine`.
  Wiring lives at the top, where it belongs.
- **`TYPE_CHECKING` discipline** — back-references (`runtime/engine`,
  `correlation_governor`, `trade_autopsy`, `trading/live|paper`) are guarded, so
  there are **zero runtime import cycles** in `src/`.
- **`utils/trading_math.py` single-source PnL (DEBT-024)**, **`utils/io`
  atomic writes (DEBT-028)**, **UTC time helpers (DEBT-025)**, and a **rich
  domain-error hierarchy** (~45 custom exception classes; 208 domain raises vs
  51 `ValueError`, only 3 bare `Exception`/`RuntimeError`).
- **Backtester DI + circuit-breaker** — depends on `BaseStrategy`;
  `SnapshotExchange` is a clean read-only determinism boundary;
  `BacktestAbortedError` surfaces loudly with structured reason.
- **Dashboard pure-builder / thin-render split** — every page except
  `pages/engine.py` and the Home portion of `app.py` already separates
  Streamlit-free `build_*` builders from thin `render()`.

### 1.2 Explicitly REJECTED ideas (do not let a future agent redo these)

The guide's AHA / Rule-of-Three / wrong-abstraction guardrails killed these.
Recorded so they are not re-proposed:

- **`Money`/`Price`/`Quantity` value-object migration over `Decimal`.** The
  single highest-risk, lowest-ROI refactor available. `Decimal` + Pydantic
  `Field(gt=0)` already give exact arithmetic + self-validation; PnL convention
  is already centralized. A VO migration touches the entire money path of a live
  system. **Bare `Decimal` is correct. Do not migrate.**
- **`Symbol` value object** — symbol parsing appears at ~2 sites; ccxt already
  normalizes. No Rule-of-Three.
- **`Side` enum replacing the `TradeSide` Literal** — the `Literal` already
  gives exhaustiveness + zero-cost validation; an enum adds `.value` unwrap
  ceremony at every serialization boundary. (Use the *existing* alias — CAH-04.)
- **Full `details: dict[str, Any]` → typed-payload migration** across ~20+ event
  types — the polymorphism is intentional and load-bearing; the on-disk JSONL is
  an append-only back-compat contract. (Only the bounded subset in CAH-13.)
- **Gate pipeline / `Gate` protocol + registry in `runtime/engine.py` and the
  robustness-gate set in `backtest/validator.py`** — gate ordering is
  load-bearing trading semantics with documented inter-gate dependencies; the
  gates have heterogeneous signatures/collaborators that would force a fat
  `GateContext` carrying per-gate-unused fields. Defer until a concrete new gate
  is specified.
- **Generic `JsonListRepository[T]` / `PerformanceRepository` port** — one
  file-backed impl, no second storage anticipated; constructor-injected paths +
  the existing `utils/io` helper suffice (CAH-14).
- **Splitting the monolith into `domain/`/`application/`/`infrastructure/`
  directories** — package-by-feature is fine; the goal is honest inward edges,
  not a directory reshuffle.
- **`config.py` split for being 626 lines** — it is a single Parnas boundary
  (only one stray `os.environ` use in the whole repo, unrelated). Length ≠
  god-object.
- Misc 2-site duplications below Rule-of-Three: `_record_emitted`/
  `_record_fail_closed`, the two `_FRONTMATTER_PATTERN`s (intentionally
  decoupled), `_touches_take_profit`/`_touches_stop_loss`, the side-guard in
  `trading_math.py`.

### 1.3 Dependency layer map (the one repo-wide finding)

Mostly clean inward dependencies. The verified violations are narrow and
addressed by CAH-10/CAH-13/CAH-14:

| Concern | Verdict |
|---|---|
| `strategy/loader.py` instantiates concrete `ClaudeCLI` inside `analyze()` | ❌ domain→edge (CAH-10) |
| `ai/improver.py` types the seam as concrete `ClaudeCLI` | ⚠️ no port (CAH-10) |
| `ai/exceptions.py` imports `strategy.base.StrategyError` | ⚠️ latent two-way coupling (CAH-10) |
| `runtime/safety_score.py` imports from IO module `activity_log.py` | ⚠️ import hygiene only (CAH-13) |
| `strategy/performance.py` pulls global `get_settings()` + raw `open()` | ⚠️ testability (CAH-14) |
| `dashboard/pages/replay.py` imports from `tools/proposal_replay` (CLI) | ⚠️ cross-edge (CAH-08) |

---

## 2. Work units (bounded, agent-workable)

Each unit is independently shippable, **behavior-preserving unless tagged
BUGFIX**, sized for one dev+QA cycle, and carries its own test obligation. All
units run the full `pytest` + `ruff check src tests` + `mypy src` gate. Trading-
domain units (CAH-01, CAH-02, CAH-05, CAH-06, CAH-07, CAH-12) get a
`quant-trader-expert` review.

Naming: `CAH-NN`. Effort S/M/L. Risk = behavior-change risk.

### Tier 0 — Bugfix (ship first, independent of the refactor)

#### CAH-01 — Exchange `None`-timestamp guard `[BUGFIX]` `[S]` `[risk: intended change]`
- **Finding**: EXCH-F2 (VALID, verified live bug). `from_unix_ms(None)` →
  `None/1000` raises `TypeError`, which escapes the adapter (the
  `RateLimitExceeded`/`CCXTExchangeError` ladders do not catch it), violating
  `BaseExchange`'s documented `ExchangeAPIError`-only contract. ccxt legitimately
  returns `None` timestamps (notably Bybit tickers / some orders). The adapters
  are self-inconsistent: `updated_at` already guards on `lastTradeTimestamp` but
  `Ticker.timestamp` / order `created_at` do not.
- **Sites**: `binance.py:280`, `bybit.py:263` (ticker `timestamp`);
  `binance.py:514`, `bybit.py:497` (order `created_at`). Sink: `utils/time.py:51`.
- **Change**: at the two unguarded sites in each adapter, translate a missing/
  `None` timestamp into a defined outcome inside the existing `try` — either
  fall back to `now_utc()` or raise `ExchangeAPIError("venue returned no
  timestamp")`. Decide fallback-vs-raise deliberately (recommend `now_utc()` for
  tickers, raise for orders — orders without a timestamp are a real anomaly).
- **Tests**: feed `{"timestamp": None}` ticker + order to each adapter's mapper;
  assert no `TypeError` escapes and the chosen contract holds.
- **Note**: this is the **only** unit that intentionally changes behavior. Ship
  it separately so reviewers don't mistake it for a pure extract.

### Tier 1 — Safe quick wins (pure, low risk)

#### CAH-02 — Order-side domain helpers `[S]` `[risk: low; correctness win]`
- **Finding**: TRAD-F1 (VALID, reclassified toward HIGH). The mapping
  `"buy" if side=="long" else "sell"` and its closing inverse
  `"sell" if side=="long" else "buy"` is hand-inlined 4×; a flipped closing
  ternary submits a **wrong-direction live order**.
- **Sites**: `paper.py:1210`, `paper.py:1323`, `live.py:242`, `live.py:485`.
- **Change**: add pure `entry_order_side(side) -> OrderSide` and
  `closing_order_side(side) -> OrderSide` (in `trading/base.py` or beside
  `OrderSide` in `utils/trading_types.py`); replace the 4 inlined ternaries.
- **Tests**: exhaustive (long/short → buy/sell for entry; inverse for close);
  assert the 4 call sites produce identical orders to before. Passes all 5
  litmus questions.

#### CAH-03 — `main.py build_engine` inlining `[S]` `[risk: very low]`
- **Finding**: MAIN-F1 (VALID). `build_engine` was over-decomposed into 7
  `_build_engine_*_phase` wrappers; `_build_engine_exchange_phase` (379-385) is a
  literal no-op (`del settings; return exchange`); `_build_engine_runtime_phase`
  (428-439) threads 10 params.
- **Change**: inline the trivial/no-op phases (`_settings`, `_exchange`,
  `_activity_log`) back into a flat `build_engine`. **Keep** `build_trader`,
  `build_notification_dispatcher`, `_engine_config_from_settings` — they have
  real reuse in `run()`.
- **Tests**: existing `tests/test_main_dispatch.py` should pass unchanged.

#### CAH-04 — Small dedup & dead-code sweep `[S]` `[risk: low]`
Three independent micro-fixes, bundled:
- **BT-F3** (VALID): delete the dead pass-through
  `analyzer.py:409 _sharpe_from_returns` (zero call sites; update the docstring
  reference at ~384).
- **DASH-F2** (VALID): hoist the byte-identical `cap_specs` 3-tuple list
  (`dashboard/pages/engine.py:1238-1254` and `1355-1371`) to a module-level
  `_GLOBAL_CAP_SPECS` + a `_pct_of_cap(details, total_key, limit_key)` helper.
- **RECON-F4** (VALID, genuine Rule-of-Three): extract `_load_json_list(path)`
  for the 3 fail-soft JSON-list readers in `reconciliation.py` (`345-372`,
  `415-452`, `455-473`); per-reader filtering stays at the call site. Preserve
  each reader's distinct warning message (pass a label) or accept a unified one
  only after checking no test asserts the text.
- **CAH-04b (hygiene)**: TRAD-F1's sibling — point the 6 inline
  `Literal["long","short"]` sites (`backtest/engine.py:235,868`,
  `risk_sizing.py:92`, `trade_autopsy.py:47`, `performance.py:824,948`) at the
  existing `TradeSide` alias. Type-identical.
- **Tests**: existing suites cover behavior; add a unit test for `_load_json_list`
  fail-soft (missing/malformed/non-list).

### Tier 2 — Bounded extractions (method-level, medium risk)

#### CAH-05 — `engine._handle_proposal` finalize helpers `[M]` `[risk: medium]`
- **Finding**: ENG-F1 (VALID; duplication is **15-16×**, worse than reported).
  `_handle_proposal` (~1130-1659, ~530 lines) copy-pastes the
  persist-and-replay rejection tail 15-16 times; two cap gates (total ~1436-1487,
  symbol ~1491-1549) are inlined while 13 siblings are extracted.
- **Change**: extract `_finalize_rejection(outcome, events, result)` and
  `_finalize_acceptance(...)`; extract `_total_cap_gate`/`_symbol_cap_gate` to
  match the sibling shape. `_handle_proposal` then reads as a flat gate list +
  finalize.
- **CRITICAL behavior note (verifier)**: the event-list shape is **asymmetric** —
  most reject sites iterate `events + outcome.events`, but the correlation
  branch (line ~1247) iterates `outcome.events` only (already the full list).
  The helper must take the **already-concatenated** list; do NOT blindly unify
  or events will be double/under-counted. Pin with the existing engine tests +
  an event-count assertion before/after.
- **Tests**: existing `tests/test_runtime_engine.py` gate/funnel assertions;
  add an assertion that per-rejection emitted-event counts are unchanged.

#### CAH-06 — Long-function splits in the money/order path `[M]` `[risk: medium]`
- **TRAD-F4** (VALID): `paper.py close_position` (~806-941, ~135 lines). Extract
  `_apply_close_to_balance(...)` (the liquidation-clamp block ~872-898) and
  `_emit_liquidation_event(...)` (~916-936). **Crux (verified)**: must preserve
  `unlock(margin)` (873) **before** reading `balance.free` (874) before
  `projected_free` (880) — pure statement-order-preserving move only. Pin with
  `test_under_water_close_emits_liquidated_event`.
- **PROP-F5** (VALID): `proposal/engine.py _build_proposal_for_strategy`
  (~652-804, ~153 lines). Extract `_apply_sl_floor(...)` (the ATR +
  `enforce_sl_floor` + conditional `model_copy` block ~747-761) and
  `_size_position(...)` (~763-784). Leave the genuine multi-TF vs single-TF
  `analyze()` two-arm branch alone.
- **Tests**: existing proposal/paper suites; the extracts are pure moves.

#### CAH-07 — LSP: uniform `analyze()` signatures `[S]` `[risk: low]`
- **Finding**: STRAT-F3 (VALID). `BaseStrategy.analyze` (base.py:393-402)
  declares keyword-only `ohlcv_by_timeframe`/`current_price`; 6 code strategies
  omit them and work only because the call-site (`proposal/engine.py:715-727`)
  passes kwargs únicamente when the `requires_multi_timeframe` gate is set — a
  single-TF strategy mis-flagged multi-TF would crash `TypeError`.
- **Change**: add the two ignored `*, ohlcv_by_timeframe=None, current_price=None`
  params to the truncated strategies (`rsi.py`, `ma_crossover.py`,
  `momentum_pinball_orb.py`, `turtle_soup_reclaim.py`, `weinstein_stage2_filter.py`,
  `raschke_holy_grail.py`) for honest substitutability. Behavior-preserving (the
  params are unused in those bodies; `tsmom_vol_breakout.py` already shows the
  full shape).
- **Tests**: existing baseline-strategy tests; add a contract test asserting
  every registered strategy's `analyze` accepts the base kwargs.

### Tier 3 — Module decomposition (pure file moves + re-export)

#### CAH-08 — Domain module splits & shared-logic relocation `[M]` `[risk: low]`
- **STRAT-F1** (VALID): split `strategy/performance.py` (1313 lines) into
  `performance.py` (records + `TechniquePerformance` + `PerformanceTracker`) and
  `trade_history.py` (`TradeHistory` + `TradeHistoryTracker` + `TradeOutcome`).
  They are independent aggregates (distinct dirs `data/performance` vs
  `data/trades`). Re-export both via `strategy/__init__.py` (44/47, `__all__`) so
  no external import breaks. Pure move.
- **LAYER-F5** (VALID; half-done already — `replay.py:19` already imports from
  `proposal/replay.py`): move `build_scenarios`/`load_replay_input` from
  `tools/proposal_replay.py` (a CLI script) into `proposal/replay.py`; the CLI
  tool and `dashboard/pages/replay.py:25` both import from there.
- **Tests**: import-surface tests; full suite catches breakage.

#### CAH-09 — Dashboard module decomposition `[M]` `[risk: low; import-cycle care]`
- **DASH-F1** (VALID; `__all__`=34 not 38): split `dashboard/pages/engine.py`
  (1864 lines, ~7 independent panel clusters) into sibling modules
  (`engine_reconciliation.py`, `engine_market_regime.py`,
  `engine_cross_account_risk.py`, …) with `engine.py` retained as the `render`
  orchestrator re-exporting public symbols. **Watch**: `trading.py:36-40` imports
  3 reconciliation symbols from here — preserve those import paths via re-export.
- **DASH-F6** (VALID): move the Home command-center read-model + builders
  (`app.py:96-1015`, ~900 of 1176 lines) into `pages/home.py`; leave `app.py` as
  pure chassis (`configure_page`, sidebar, `page_for_key`, `build_navigation`,
  `main`). Register `render_home` like every other page.
- **Tests**: `tests/test_dashboard_app.py` + page tests; pure moves.

### Tier 4 — DIP / ports / typed contracts (architecture)

#### CAH-10 — LLM port & AI/feedback cluster `[M]` `[risk: low-medium]`
- **AI-F1 / LAYER-F1** (VALID): define a narrow `LLMClient` Protocol
  (`async analyze(prompt) -> dict`, `async complete(prompt) -> str`) in an inner
  module (e.g. `ai/ports.py`). `ClaudeCLI` already structurally satisfies it (no
  adapter change). Type `StrategyImprover.__init__(llm: LLMClient | None)` and —
  the crux — stop `strategy/loader.py analyze()` (226/251/253) from
  instantiating a concrete `ClaudeCLI` mid-method; inject the client instead.
  **Does NOT touch NFR-002** — `ClaudeCLI` stays the only production CLI adapter.
- **LAYER-F2** (Low): re-root `ai/exceptions.py ClaudeError` off a neutral base
  (or move the shared `StrategyError` base to a neutral `src/exceptions.py`) so
  `ai` stops importing `strategy.base`. Bundle here since it closes the same
  two-way coupling.
- **AI-F4** (VALID): extract the ~370 lines of prompt-text static builders
  (`improver.py:594-994`) into `ai/prompts.py` (pure functions) — isolates the
  volatile "what we ask Claude" axis from the stable parse/validate/persist core.
- **AI-F5** (VALID; ~10 params not 12): introduce a frozen `BacktestContext`
  parameter object bundling `ohlcv/symbol/timeframe/profile/strategy_factory/
  param_grid/ohlcv_by_timeframe` threaded through `feedback/loop.py _run_cycle`
  (521) and its 4 entry points (211/251/313/341).
- **Tests**: existing AI/feedback suites already inject `AsyncMock(spec=ClaudeCLI)`
  — retype to the Protocol; add a fake `LLMClient` to prove the loader no longer
  news up a concrete client.

#### CAH-11 — `CcxtExchange` base adapter `[M]` `[risk: low; pure hoist]`
- **Finding**: EXCH-F1 (VALID; ~75/530 lines differ). `binance.py` and
  `bybit.py` are ~95% identical; `_map_order`, `_map_order_status`, balance/
  ticker/order/cancel/open-orders, and the exception ladders are byte-identical;
  the `CCXTClient` Protocol is duplicated.
- **Change**: extract `exchange/ccxt_base.py::CcxtExchange(BaseExchange)` holding
  the shared methods + Protocol + `TIMEFRAME_MAP`. Subclasses override only a
  real `_build_client()` hook (binance's futures/spot branch + `options` block
  vs bybit's single `ccxt.bybit`) and an `OHLCV_LIMIT` class constant (1500 vs
  200). Fold in **EXCH-F3** (annotate bybit `_ensure_connected -> CCXTClient`)
  and **EXCH-F5** (move the ccxt-mapping helpers `_extract_ccxt_fee`/
  `_decimal_or_none` out of the port module `base.py` into `ccxt_base.py`).
- **Order dependency**: ship **after CAH-01** (the None-timestamp guard) so the
  guard is written once in the shared base, not twice then merged.
- **Tests**: existing `tests/test_exchange_binance.py` / `test_exchange_bybit.py`
  must pass unchanged; add a test that a third toy `CcxtExchange` subclass works
  with only the two overrides (proves the NFR-009 extensibility goal).

#### CAH-12 — Proposal funnel & record contract `[M]` `[risk: low-medium]`
- **PROP-F1** (VALID; verified no live bug — future-proofing): derive
  `funnel._STATE_TO_FIELD` from the enum (`{s: s.value for s in
  ProposalFinalState}` — machine-verified to reproduce the table exactly across
  all 29 members) and derive `gate_rejected_total` by iterating
  `GATE_REJECTED_*` members instead of the hand-written 20-term sum. Add a
  coverage test: `set(FunnelCounts.model_fields) >= {s.value for s in
  ProposalFinalState}` and that `gate_rejected_total` sums exactly the
  `GATE_REJECTED_*` members. Keep the explicit `FunnelCounts` fields (the
  dashboard reads them by name — real contract).
- **PROP-F8** (VALID; 4-field reject bundle recurs 16× in engine.py): add
  `ProposalRecord.reject(final_state, reason, *, at=None)` and `mark(final_state)`
  domain methods returning the updated copy. **Must preserve `.value`
  serialization** (`use_enum_values=True` at interaction.py:240). Most of the
  call-site cleanup lands in `runtime/engine.py`, but the methods belong on the
  in-scope entity. No transition-validation state machine (that would risk
  accept/reject semantics).
- **Tests**: the new coverage test; existing funnel/interaction suites.

#### CAH-13 — `GateReason` enum + bounded safety accessors `[M]` `[risk: low]`
The cross-agent `details: dict[str, Any]` reconciliation. **Three correct,
complementary moves; do NOT migrate the whole dict.**
- **`GateReason` enum** (highest value): the `gate_reason` discriminator is a
  closed ~17-value vocabulary written in `engine.py` and read by string equality
  at 4+ consumer sites (`dashboard/pages/engine.py:1104`, the `risk_gate_reasons`
  set, `proposals.py:258`, `safety_score.py:252`) with silent-default fallbacks
  — a typo fails silently. Introduce a `str`-backed `GateReason` enum; on-disk
  JSON stays identical (`.value`).
- **Bounded safety accessors**: introduce typed accessor helpers (or a thin
  frozen view model) for **only** the keys `safety_score.py` consumes
  (`advisory`, `cycle_id`, `gate_reason`, `sub_account_id`, `reason`), so
  producer/consumer drift on the runtime-pausing path fails loud / is test-caught.
- **LAYER-F4** (Low; bundle here): extract the pure `ActivityEvent` /
  `ActivityEventType` into `runtime/activity_events.py` so `safety_score.py`
  stops importing the IO module `activity_log.py`; both import the pure module.
- **Leave** dashboard read sites and the free-form `details` container alone.
- **Tests**: enum round-trip vs current literals; safety-score accessor defaults;
  full suite for the import move.

#### CAH-14 — De-globalize `performance.py` reads `[M]` `[risk: low]`
- **Finding**: LAYER-F3 (Medium). Core P&L logic binds to a process-global
  `get_settings()` + raw `open()` for reads (writes already use
  `utils/io.atomic_write_text`), making it untestable without env/FS.
- **Change** (minimal, no new abstraction layer): (a) route raw `open()` reads
  through `utils/io` helpers; (b) accept the data dir / settings as a constructor
  argument with the `get_settings()` default kept for back-compat (the codebase
  already uses this `x or default()` pattern). **No `PerformanceRepository`
  port** (rejected — YAGNI, one impl).
- **Tests**: construct the tracker with a `tmp_path` data dir without monkey-
  patching settings.

### Tier 5 — Directional epic (design first, NOT a mechanical unit)

#### CAH-15 — `TradingEngine` God-Object decomposition `[L]` `[risk: HIGH — staged]`
- **Finding**: ENG-F3 (VALID; verified **65 methods** across 6 concerns, 8
  per-cycle caches reset at engine.py:914-919).
- **Why it is not a turn-key unit**: extracting `PositionMonitor`,
  `SnapshotRecorder`, `ProposalGateChain` collaborators moves state that is today
  shared via `self` across object boundaries — high behavior-change risk,
  especially the per-cycle cache-reset semantics.
- **Approach**: gate on **CAH-05** landing first (it shrinks `_handle_proposal`
  and proves the finalize seam). Then a dedicated **design ADR** proposing the
  collaborator boundaries + cache-ownership migration, reviewed by
  `quant-trader-expert`, before any code. Stage extraction one collaborator at a
  time (suggest `SnapshotRecorder` first — lowest coupling — then `PositionMonitor`
  via the `_handle_orphan_trade` extraction from ENG-F6, then the gate chain
  last). Each stage is its own behavior-preserving slice with full-suite gating.
- **Do not** attempt as one PR.
- **Progress**:
  - `[x]` Design ADR — `docs/adr/0001-trading-engine-decomposition.md` (commit 70b7802);
    quant-reviewed 🟡 → greenlit Slices 1+2, Slice 3 (gate-chain) deferred.
  - `[x]` **Slice 1 — `SnapshotRecorder`** (2026-05-31): five persistence methods →
    `src/runtime/snapshot_recorder.py`; stateless collaborator rebuilt on demand from
    live engine config; ADR CHANGE B (`_remember_mark_price` injected directly).
    Engine 5343→5196 lines; +11 tests; 2328 passed; black/ruff/mypy clean. Session log
    `docs/sessions/2026-05-31-clean-architecture-hardening-cah-15-slice-1-snapshot-recorder.md`.
  - `[ ]` Slice 2 — `PositionMonitor` (+ ENG-F6 `_handle_orphan_trade`); ADR CHANGE A
    (multi-rung single-pass close-count equality) + CHANGE B; mandatory quant review.
  - `[ ]` Slice 3 — `ProposalGateChain` — CONDITIONAL, deferred; re-measure coupling
    after Slice 2 before any go/no-go.

---

## 3. Sequencing & refactoring plan

### 3.1 Risk-tiered order

```
CAH-01 (bugfix)  ──► ship immediately, standalone
        │
Tier 1: CAH-02, CAH-03, CAH-04  ──► parallel-safe quick wins (no interdeps)
        │
Tier 2: CAH-05 ──► CAH-06, CAH-07
        │           (CAH-05 before CAH-15)
Tier 3: CAH-08, CAH-09  ──► pure module moves (parallel-safe)
        │
Tier 4: CAH-10, CAH-11, CAH-12, CAH-13, CAH-14
        │   (CAH-11 after CAH-01; others independent)
Tier 5: CAH-15  ──► design ADR → staged extraction (after CAH-05)
```

- **Ship CAH-01 first** — it is the only real bug.
- Tiers 1–3 are low-risk and can interleave; they build reviewer confidence and
  shrink the files that Tier 4/5 touch.
- **CAH-11 depends on CAH-01** (write the timestamp guard once in the shared base).
- **CAH-15 depends on CAH-05** and on a separate design ADR; treat as an epic.
- One unit per dev+QA cycle; trading-domain units get a `quant-trader-expert`
  review (CAH-01/02/05/06/07/12).

### 3.2 How the units serve the four goals

| Goal | Units | Mechanism |
|---|---|---|
| **Reusability** | CAH-02, CAH-04, CAH-08, CAH-10, CAH-11 | Shared domain helpers (order-side, `_load_json_list`), shared modules (`prompts.py`, `proposal/replay.py`), the `LLMClient` port, and the `CcxtExchange` base let new exchanges/LLM transports/consumers reuse instead of copy. |
| **Single Responsibility** | CAH-05, CAH-06, CAH-08, CAH-09, CAH-10, CAH-15 | Long functions split into named steps; `performance.py`/dashboard `engine.py`/`app.py`/`improver.py` divided along independent change axes; the engine God-Object decomposed (staged). |
| **Extensibility (OCP)** | CAH-11, CAH-12, CAH-13 | `CcxtExchange` + `_build_client()` hook adds an exchange without editing siblings (NFR-009); enum-derived funnel mapping + `ProposalRecord.reject()` make a new terminal a one-line add, not Shotgun Surgery; `GateReason` enum closes the stringly-typed gate vocabulary. |
| **Clean code** | CAH-01, CAH-03, CAH-04, CAH-07, CAH-13, CAH-14 | Bug + dead-code removal, de-over-decomposition (`build_engine`), honest LSP signatures, typed vocabulary on the safety path, testable de-globalized reads. |

### 3.3 Guardrails for every unit
- **Behavior-preserving** except CAH-01 (tagged BUGFIX). Money/order-path units
  (CAH-02/05/06) require an explicit before/after equality assertion.
- Full `pytest` + `ruff` + `mypy` gate per unit; no net test-count regression.
- Re-export across module moves so no external import path breaks.
- If a unit tempts you toward a §1.2 rejected idea, stop — the duplication is
  cheaper than the wrong abstraction.

---

## 4. Traceability

- Review rubric: `clean-code-architecture-guide` (external, fetched 2026-05-28).
- Finding IDs (per-module): ENG-F*, RECON-F*, MAIN-F*, TRAD-F*, PROP-F*, STRAT-F*,
  BT-F*, AI-F*, EXCH-F*, DASH-F*, LAYER-F*.
- Verification: two independent cold-read verifier passes (2026-05-28) — all
  VALID/PARTIALLY VALID; corrections folded in above (ENG-F1 15-16×, TRAD-F1→HIGH,
  EXCH-F2 BUGFIX, BT-F5 scalar-roll-up-only, AI-F5 ~10 params, DASH-F1 __all__=34).
- Unit registry: see `clean-architecture-hardening` in
  `aidlc-docs/inception/units/unit-of-work.md`.
