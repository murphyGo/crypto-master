# Session: proposal-funnel-audit unit shipped

## Unit

- `proposal-funnel-audit` (primary)
- Secondary units: `proposal-runtime`, `dashboard-operator-ui`, `dashboard-operator-command-center`, `runtime-reconciliation`

## Related Requirements

- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- FR-029
- FR-043
- NFR-007
- NFR-012

## Scope

Shipped the `proposal-funnel-audit` unit end-to-end: canonical 15-state funnel taxonomy (`ProposalFinalState` enum) on `ProposalRecord` with `gate_rejected_unknown` legacy fallback, `record_id` threaded into all 10 post-acceptance gate emission sites, `_handle_proposal` rewriting `final_state` on every transition via `record.model_copy(update={...})`, `_build_cap_blocker_payload` diagnostic helper consuming `runtime-reconciliation.classify_open_trade` for the `monitorable` flag, `attach_outcome` setting `final_state=outcome_linked` and propagating `record_id`/`proposal_id` to `POSITION_CLOSED`, the new pure aggregator `src/proposal/funnel.py` (`FunnelCounts` Pydantic model with `compute_funnel_counts` + per-strategy/per-sub-account variants, derived-on-read), and operator surfaces — a new Proposals dashboard page (`src/dashboard/pages/proposals.py`) plus a single-line command-center summary in `src/dashboard/app.py`. Combined deliverable across R1 (initial implementation) and R2 (post-quant-review fixes for Q1 🔴 + Q2 🟡).

## Changes

- `src/proposal/interaction.py` — `ProposalFinalState` enum (15 states + `gate_rejected_unknown` legacy fallback); `final_state` field added to `ProposalRecord`; `attach_outcome` sets `final_state=outcome_linked` and propagates `record_id` / `proposal_id` into `POSITION_CLOSED` details.
- `src/runtime/engine.py` — `record_id` threaded into all 10 post-acceptance gate emission sites (`market_regime`, `correlation`, `trend_filter`, `sibling_family`, `runtime_safety_pause`, `total_cap`, `symbol_cap`, `stale_quote`, plus accept/execute paths); `_handle_proposal` rewrites `final_state` on every transition via `record.model_copy(update={...})`; accept path sets `proposal_opened`, `_execute` success sets `trade_opened`; new `_build_cap_blocker_payload` helper consumes `runtime-reconciliation.classify_open_trade` for the `monitorable` flag. R2 dropped the per-blocker `await exchange.get_ticker()` from `_build_cap_blocker_payload` (Q1 🔴 fix); `unrealized_pnl_percent` unconditionally `None`; `exchange` param dropped; 2 call sites updated.
- `src/proposal/funnel.py` (NEW) — `FunnelCounts` Pydantic model + `compute_funnel_counts` + per-strategy/per-sub-account variants; pure, derived-on-read. R2 added `score_accepted_total` as a derived property (Q2 🟡 fix) so operator query "how many proposals passed score gate?" no longer requires manual summing across downstream states.
- `src/dashboard/pages/proposals.py` (NEW) — funnel conversion table, per-gate volume + sample, per-strategy heatmap, drill-through panel.
- `src/dashboard/app.py` — command-center single-line summary.
- Tests — `+34` in R1 (1942 → 1976) across `tests/test_proposal_interaction.py`, `tests/test_runtime_engine.py`, `tests/test_proposal_funnel.py`, `tests/test_dashboard_proposals.py`. R2 added `+2` more (1976 → 1978) covering Q1's `None`-fallback contract and Q2's `score_accepted_total` derived property.

## Quant adjudications (Q1-Q3)

- **Q1** (cap-blocker ticker fetch on hot path): 🔴 — 10+ sequential awaited ticker calls per cap rejection on the dominant rejection path per the 2026-05-13 Fly snapshot. Fixed in R2 by dropping the fetch and setting `unrealized_pnl_percent = None` per the spec's documented fallback; `exchange` param removed from `_build_cap_blocker_payload`; 2 call sites updated. Future-work shape (in-memory mark cache populated by existing monitor-pass / asset-snapshot ticker reads) filed as **DEBT-066**.
- **Q2** (`score_accepted_total` derived property): 🟡 — operator query "how many proposals passed score gate?" required manual summing across downstream states. Fixed in R2 with `score_accepted_total` as a derived property on `FunnelCounts`.
- **Q3** (`gate_rejected_unknown` decision pollution): 🟢 ratified-as-shipped. Verified no decision logic reads `final_state` outside `funnel.py` (`_cold_start_blocks_live`, `_score`, `attach_outcome` all confirmed not to read it). The legacy fallback is observability-only.

## 🔴-and-fix

One 🔴 verdict in the quant review, caught before ship and fixed in R2:

R1 of `_build_cap_blocker_payload` did a per-blocker `await exchange.get_ticker()` to enrich each blocking-trade entry with `unrealized_pnl_percent`. The 2026-05-13 Fly snapshot showed cap rejections are the dominant rejection path; with the helper invoked once per cap-rejection event and a `for trade in blockers: ticker = await exchange.get_ticker(...)` body, that's 10+ sequential awaited network round-trips on the hot rejection path. Quant Q1 verdict: drop the fetch. R2 set `unrealized_pnl_percent = None` per the spec's documented fallback, dropped the `exchange` param, and updated the 2 call sites. The first-order diagnostic signal (`entry_price + age_seconds + monitorable + symbol + record_id`) is intact; the lost second-order field is filed as DEBT-066 with a zero-new-exchange-call resolution shape (in-memory mark cache populated by ticker reads that already happen).

## Mark-cache survey surprise

During DEBT-066 filing the developer surveyed `src/runtime/engine.py`, `src/trading/portfolio.py`, and `src/trading/paper.py` for an in-memory mark-price cache to consume. There isn't one — `PortfolioManager` only sees marks when callers hand them in via `record_snapshot(current_prices=...)`, and there's no `PortfolioManager.get_mark_price` API (the quant review's suggested-resolution sketch had assumed one). Surfaced as the suggested-resolution shape for DEBT-066: a `dict[str, Decimal]` cache on `TradingEngine` populated by `_record_asset_snapshot` and the monitor-pass ticker reads (which already happen). Last-seen-timestamp or TTL freshness; zero new exchange calls on the rejection path.

## Verification

- `pytest -q` — **1978 passed** (was 1942; net +36 across R1+R2, zero regressions).
- `ruff check` — fully clean.
- `mypy` on changed modules — clean; 3 pre-existing `src/dashboard/app.py` errors at lines 285, 869, 882 remain (out of scope for this unit; filed as **DEBT-067**).

## Risks

- Cap-blocker `unrealized_pnl_percent` second-order diagnostic loss (DEBT-066): operators triaging "is the blocking position underwater?" must look elsewhere — the first-order signal (`entry_price + age_seconds + monitorable + symbol + record_id`) is intact, so this is a diagnostic-quality gap rather than a money-handling defect. Resolution shape requires no new exchange calls.
- Dual-emit alias cleanup: the dashboard read path currently tolerates both spec-canonical and legacy aliases for some `final_state` keys to ease migration. Once dashboards fully migrate to spec-canonical names, the alias map can be retired; until then aliases are quiet noise on the read surface.
- Dual-write atomicity on `_execute` success: `_handle_proposal`'s accept-then-execute path currently does two `load → model_copy → save` round-trips (one to mark `proposal_opened`, one to mark `trade_opened` after `_execute` returns). Each individual write is atomic via `atomic_write_text`, but the pair is not — a crash between them leaves the record at `proposal_opened` with a real open position. Narrow window; could collapse into a single save on success.

## Reviewer notes

- quant-trader-expert: 🔴 → 🟡 → 🟢 across the review. Q1 🔴 fixed in R2 (ticker-fetch dropped); Q2 🟡 fixed in R2 (derived property); Q3 🟢 ratified-as-shipped. Final-diff verdict 🟢.
- qa-reviewer: 🟢 on the final diff. Pre-existing `src/dashboard/app.py` mypy errors flagged as a recurring observation across the past 4 unit cycles and filed as DEBT-067.

## Future work

- **DEBT-066** (mark cache): `dict[str, Decimal]` mark cache on `TradingEngine` populated by `_record_asset_snapshot` + monitor-pass ticker reads (which already happen); TTL or last-seen-timestamp freshness; `_build_cap_blocker_payload` consumes from the cache and falls back to `None` if symbol is uncached. Zero new exchange calls on the rejection path.
- **DEBT-067** (dashboard `app.py` mypy cleanup): mechanical 2-line + 2-line fix — explicit `Literal[...]` cast on the line-285 `mode` default; `list[X]` → `Sequence[X]` covariant-read parameters at lines 869 + 882.
- Dual-emit alias cleanup: retire the alias map on the dashboard read path once dashboards fully migrate to spec-canonical `final_state` names.
- Dual-write atomicity on `_execute` success: collapse the two `load → model_copy → save` round-trips into a single save on success so the accept-then-execute path is crash-safe end-to-end.
