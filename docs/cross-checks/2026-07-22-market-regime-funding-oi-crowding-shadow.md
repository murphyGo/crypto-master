# Cross-Check: market-regime Funding+OI Crowding Shadow Filter

## Scope

Independent cross-check of the initial Funding+OI proposal-layer consumer. It
covers deterministic crowding classification, disabled-by-default per-account
policy, runtime gate ordering, shadow-only behavior, fail-open telemetry,
dashboard visibility, and the dual-lane evidence contract that keeps veto
unavailable.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-045 Market regime and per-account gating | Complete for shadow slice | Funding/OI crowding is a typed `market-regime` signal with per-account enablement and operator-visible decisions. Existing OHLCV regime enforcement is unchanged. |
| FR-046 Derivatives market context | Complete consumer integration | The pure classifier consumes the sealed time-bounded `MarketContext`; predicted Funding is ignored, and missing/stale/short data remains explicit. |
| FR-011/012 Proposal selection safety | Complete | Evaluation uses `proposal.symbol` and signal side after earlier selection gates; shadow results cannot reject or execute a proposal. |
| FR-014 Proposal/activity history | Complete | One allowlisted observed or skipped activity event records each enabled evaluation without mutating `ProposalRecord.final_state`. |
| NFR-003 Streamlit UI | Complete | Engine Market Regime renders evaluated/would-block/skipped counts and recent rows with `SHADOW — NOT ENFORCING`. |
| NFR-006 Structured evidence | Complete for qualification contract | Immutable evidence input/result models require both replay lanes, identity, digest, seed, samples, expectancy, and regime diversity. Actual veto evidence is intentionally not claimed. |
| NFR-007 Safe operational telemetry | Complete | Stable UTC/Decimal-derived fields are recorded; provider exception messages, raw responses, paths, URLs, and secrets are excluded. |
| CFO-NFR-001..012 | Complete | No hot-path I/O, p95 budget, disabled/shadow invariants, deterministic no-look-ahead behavior, safe events/UI, no infra/dependency change, and full tests all pass. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-024 | Complete, unchanged | Existing OHLCV regime classifier/gate remains authoritative; this slice adds a separate shadow crowding view without changing its terminal precedence. |
| US-025 | Complete, reused | The sealed runtime context service supplies proposal-time Funding/OI from its in-memory cache. No new acquisition or replay contract was introduced. |
| US-026 | Complete for shadow observation | Side-aware Funding extreme plus rising OI is no-look-ahead; missing context fails open; impact is visible; schema makes veto unavailable pending qualifying evidence. |

## Implementation Evidence

- `src/runtime/funding_oi_filter.py` — pure Decimal nearest-rank classifier,
  side matching, immutable result, and fail-closed evidence qualification.
- `src/trading/sub_account.py` — frozen disabled-default policy with a
  shadow-only action literal.
- `src/runtime/engine.py` — evaluation after correlation/OHLCV regime gates,
  before sizing/risk caps, using cached context at `proposal.created_at`.
- `src/runtime/activity_events.py` — dedicated observed/skipped event types.
- `src/dashboard/pages/engine_market_regime.py` and `engine.py` — pure read
  models and honest shadow presentation.

## Test Evidence

- Focused classifier/gate-reason/policy/runtime/dashboard: 317 passed in 3.75s.
- Focused classifier coverage run: 317 passed in 5.62s; classifier 91%.
- Performance: 100 runs at 90 Funding/500 OI, p95 0.000064s; target 0.005s.
- Complete repository: 2604 passed in 45.09s.
- Black/Ruff pass on all 12 changed Python files; `mypy src` passes 114 files;
  lock, compile, offline import, whitespace, dependency/deployment/data scope
  checks pass.
- Repository-wide Black/Ruff still reports only existing DEBT-081: 16 Black
  candidates and 22 Ruff findings, none in this slice.

## Gaps and Risks

- No blocking gap remains for the shadow release.
- A veto is intentionally absent, not deferred debt. It needs new empirical
  evidence from proposal-history replay and pinned Snapshot-v2 backtesting;
  configuration cannot bypass that boundary.
- Shadow events will only accumulate when both the global derivatives context
  service and a sub-account's filter policy are explicitly enabled. Missing
  service/context remains visible and fail-open.
- No live endpoint, order path, production config, deployment, or runtime data
  was exercised.

## Unit and Debt Mapping

- **Primary Unit:** `market-regime`
- **Secondary Units:** `proposal-runtime`, `exchange-integration`,
  `dashboard-operator-ui`, `quality-governance`
- **Related Debt:** DEBT-081 is active and unrelated; no new debt.
- **Legacy Phase Context:** proposal/runtime Phases 6, 8, 12, 18, 21 and
  dashboard Phases 7, 8.2, 19.3.

## Recommendations

**PASS.** Seal the disabled-by-default shadow observer. The next product step
is observation, not enforcement: accumulate shadow events, generate both
evidence lanes, and open a separate veto construction slice only if the
evidence qualifier passes.
