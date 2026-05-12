# Session: cross-account-risk-policy Slice 1 shipped

## Unit

- `cross-account-risk-policy` (primary)
- Secondary units: `proposal-runtime`, `persistence-data-integrity`

## Related Requirements

- FR-036
- FR-037
- FR-038
- FR-044
- NFR-007
- NFR-008
- NFR-012

## Scope

Shipped **Slice 1** of the `cross-account-risk-policy` unit — the schema + sizing-helper + 2 of 5 planned gates subset of the full functional-design spec. Concretely: `RiskPolicy` schema extensions (sizing mode + notional bounds + stop floor + aggregate caps + stale + kill-switch fields), new `GlobalRiskPolicy` model with operator-freeze flag, registry-side YAML `global_risk_policy` block loading, a pure `compute_risk_budget_size` Decimal helper with 5 structured `RiskSizingRejection` modes, `_account_aggregate_cap_gate` (notional + stop-risk) and `_stale_position_block_gate` wired after the symbol-cap gate with paper-advisory / live-hard-block semantics, and 3 new `ProposalFinalState` terminals (`gate_rejected_account_aggregate_cap`, `gate_rejected_stale_position_block`, `gate_rejected_risk_sizing`). Combined deliverable across R1 (initial implementation, +27 tests) and R2 (post-quant-review fixes for Q1 🔴 + Q2 🟡 + Q5 🔴, +2 tests).

**Slice 2 (deferred under DEBT-068 umbrella)**: global symbol/side caps, per-account + portfolio kill switches, operator freeze toggle reload-per-cycle, stale `auto_close` / `alert_only` actions, dashboard exposure panel, `compute_risk_budget_size` wire-in to `ProposalEngine`, and the dedicated `RISK_CAP_ADVISORY` event type. The Slice 1 scope hit ~706 LoC, well under the 1357-LoC scope-split guard.

## Changes

- `src/trading/sub_account.py` — `RiskPolicy` extensions (sizing mode + notional bounds + stop floor + aggregate caps + stale + kill-switch fields); new `GlobalRiskPolicy` model with operator-freeze flag; field validators. R2 added `_reject_risk_budget_mode_until_wired_in` validator (Q1 fix) that rejects `sizing_mode='risk_budget'` configuration with an explicit DEBT-068 pointer in the error message, preventing the silent footgun where operator-set risk-budget mode would otherwise be silently ignored by the engine.
- `src/trading/sub_account_registry.py` — `global_risk_policy` block YAML loading.
- `src/trading/risk_sizing.py` (NEW) — pure `compute_risk_budget_size` Decimal helper + 5 structured `RiskSizingRejection` modes. Unit-tested; **no production caller yet** (wire-in deferred under DEBT-068(a)).
- `src/runtime/engine.py` — `_account_aggregate_cap_gate` (notional + stop-risk) + `_stale_position_block_gate` wired after symbol-cap gate. Paper mode emits advisory-with-event via `PROPOSAL_REJECTED + details.advisory=True` reuse; live mode hard-blocks. R2 wrapped `trade.entry_time` in `ensure_utc()` at the stale-block gate (Q5 fix) — matches the established pattern at 3 other call sites in the codebase. R2 also rewrote both gate docstrings to admit the advisory-event reuse (Q2 fix); dedicated `RISK_CAP_ADVISORY` event type deferred to Slice 2.
- `src/proposal/interaction.py` + `src/proposal/funnel.py` — 3 new `ProposalFinalState` terminals (`gate_rejected_account_aggregate_cap`, `gate_rejected_stale_position_block`, `gate_rejected_risk_sizing`).
- Tests — `+27` in R1 (1978 → 2005) across `tests/test_trading_sub_account.py`, `tests/test_trading_sub_account_registry.py`, `tests/test_trading_risk_sizing.py` (NEW), and `tests/test_runtime_engine.py` (per-account aggregate-cap gate: live + paper advisory + over-stop-risk + no-caps no-op + under-caps pass; stale-position block gate: live + paper advisory + alert-only no-op + fresh-trade pass). R2 added `+2` more (2005 → 2007) — the `_reject_risk_budget_mode_until_wired_in` validator regression and the naive-tz stale-block defense.

## Quant adjudications (Q1-Q5)

- **Q1** (scope-split + unwired helper): 🔴 — `compute_risk_budget_size` is unit-tested but has no production caller; operator setting `sizing_mode='risk_budget'` would be silently ignored by the engine. Fixed in R2 with the `_reject_risk_budget_mode_until_wired_in` validator footgun-prevention. The validator's error message points at DEBT-068 so future operators get a clean signal toward the umbrella.
- **Q2** (advisory event-type reuse): 🟡 — paper-mode advisories ride on `PROPOSAL_REJECTED + details.advisory=True` rather than a dedicated `RISK_CAP_ADVISORY` event type; dashboard read-side has to filter on `details.advisory` to separate advisory noise from real rejections. Fixed in R2 with docstring honesty on both gates; dedicated event type deferred to Slice 2 under DEBT-068(g).
- **Q3** (aggregate notional math under mixed sizing): 🟢 ratified-as-shipped. Math is sizing-mode-agnostic by construction (reads `quantity` off the proposal, doesn't care how it was sized).
- **Q4** (`max_open_stop_risk` math): 🟢 ratified-as-shipped. `abs(entry - stop) * quantity` is the correct worst-case-on-simultaneous-stop formula; `abs()` is defense-in-depth against malformed `(entry, stop)` ordering.
- **Q5** (stale-block timezone): 🔴 — `trade.entry_time` could be UTC-naive on legacy reads, leading to `now_utc() - entry_time` raising `TypeError` mid-gate and silently disabling stale-block on the affected row. Fixed in R2 by wrapping `trade.entry_time` in `ensure_utc()` at the stale-block gate; regression test pins naive-tz defense.

## 🔴-and-fix

Two 🔴 verdicts in the quant review, both caught before ship and both fixed in R2:

R1 shipped `compute_risk_budget_size` as a unit-tested pure helper but left it unwired in `ProposalEngine`. The full `RiskPolicy.sizing_mode` field is in the schema and accepted at YAML parse time, so an operator who set `sizing_mode='risk_budget'` on a sub-account would get the configuration silently ignored at the proposal-sizing call site — the silent-footgun anti-pattern (operator believes they've changed engine behavior, engine ignores them). R2 added `_reject_risk_budget_mode_until_wired_in` as a model validator on `RiskPolicy`; the error message explicitly names DEBT-068(a) so any operator running into the wall is pointed at the umbrella debt entry that tracks the wire-in work. Validator goes away when DEBT-068(a) lands.

R1 wired `_stale_position_block_gate` consuming `trade.entry_time` directly without UTC coercion. Per the DEBT-025 chain (Phase 21.1/21.2/21.3), `datetime` arithmetic across UTC-aware and UTC-naive values raises `TypeError`, and three other call sites in `src/runtime/engine.py` already use `ensure_utc()` as the defensive wrap. The bare-read pattern at the stale-block gate would have made the gate silently fail-closed on any legacy ledger row that survived the Phase 21 sweep. R2 wrapped `trade.entry_time` in `ensure_utc()` and added a regression test pinning naive-tz tolerance.

## QA observation

QA flagged a docs-only nit at `src/proposal/interaction.py:108-111` — the comment says "four new terminals" but only three were added (`gate_rejected_account_aggregate_cap`, `gate_rejected_stale_position_block`, `gate_rejected_risk_sizing`). Captured as a future-work bullet; **not** filed as a separate DEBT entry on this cycle (judged below filing threshold — mechanical follow-up that bundles naturally with the Slice 2 `RISK_CAP_ADVISORY` event-type work or any future touch on the enum block). If subsequent reviewers think it deserves a tracking ID, DEBT-069 is reserved.

## Verification

- `pytest -q` — **2007 passed** (was 1978; net +29 across R1+R2, zero regressions).
- `ruff check` — fully clean.
- `mypy` on the 6 changed source files (`src/trading/sub_account.py`, `src/trading/sub_account_registry.py`, `src/trading/risk_sizing.py`, `src/runtime/engine.py`, `src/proposal/interaction.py`, `src/proposal/funnel.py`) — clean.

## Risks

- **`sizing_mode='risk_budget'` is fail-closed at validation until DEBT-068(a) lands.** Operators who want risk-budget sizing must either wait for the wire-in slice or stay on the default fixed-notional sizing path. The fail-closed posture is deliberate (silent footgun avoided) but does mean the schema admits a configuration the engine can't yet honor — operator-visible only via the validator error message that points at DEBT-068.
- **Slice 1 alone is operator-meaningful only for paper-mode per-account aggregate-cap observability.** The live-mode promotion path is incomplete without DEBT-068(a) risk-budget wire-in, (b) global symbol/side caps, and (c) kill switches. Live operators relying on aggregate-cap protection alone get the two new gates; everything else in the spec ships in Slice 2.
- **`PROPOSAL_REJECTED + details.advisory=True` reuse for paper-mode advisories** means dashboard read-side currently has to filter on `details.advisory` to distinguish advisory noise from real rejections. Quiet noise on the read surface until DEBT-068(g) lands the dedicated `RISK_CAP_ADVISORY` event type and the funnel-side filter migrates off the reuse pattern.

## Reviewer notes

- quant-trader-expert: 🔴 → 🟢 across the review. Q1 🔴 fixed in R2 (footgun-prevention validator); Q5 🔴 fixed in R2 (UTC defense + regression); Q2 🟡 fixed in R2 (docstring honesty, event-type deferral); Q3 + Q4 ratified-as-shipped. Final-diff verdict 🟢.
- qa-reviewer: 🟢 on the final diff. Flagged the `src/proposal/interaction.py:108-111` "four new terminals" comment nit; captured as future-work bullet (not filed as DEBT this cycle).

## Future work

- **DEBT-068** (Slice 2 umbrella) — eight sub-items: (a) `compute_risk_budget_size` wire-in to `ProposalEngine` and removal of the `_reject_risk_budget_mode_until_wired_in` validator; (b) global symbol/side caps (`max_open_positions_per_symbol_side`, `max_gross_notional_per_symbol_side`, `max_gross_notional_per_symbol`) with cross-sub-account aggregation in the engine cycle; (c) per-account + portfolio kill switches (`daily_loss_limit_pct`, `open_drawdown_limit_pct`, `portfolio_daily_loss_limit_pct`, `portfolio_open_drawdown_limit_pct`) with realized-PnL-since-UTC-midnight aggregation + persisted state surviving restart; (d) operator freeze toggle reload-per-cycle (`config/runtime_flags.yaml` or similar); (e) stale `auto_close` + `alert_only` actions (monitor-loop hook + interaction matrix with `runtime-reconciliation` state taxonomy); (f) dashboard exposure panel (per-account + global aggregate views, kill-switch + operator-freeze indicators, runtime-reconciliation banner color pattern); (g) `RISK_CAP_ADVISORY` `ActivityEventType` value + funnel-side filtering (migrates paper-mode emissions off `PROPOSAL_REJECTED + details.advisory=True` reuse); (h) `runtime-safety-score` integration (kill-switch triggers feed the safety-score signal). Sequencing: (a) first as a small wire-in cycle, then (b), (c), (e), (f), (g); (d) and (h) are smaller and can bundle with (f).
- **QA's `src/proposal/interaction.py:108-111` "four new terminals" comment nit** — mechanical 1-line edit; bundles naturally with the Slice 2 `RISK_CAP_ADVISORY` work or any next touch on the enum block. DEBT-069 reserved if a reviewer wants tracking.
- **Dual-emit alias cleanup on the dashboard `_proposal_summary` read path** — carryover from the proposal-funnel-audit unit; alias map can retire once dashboards fully migrate to spec-canonical names.
