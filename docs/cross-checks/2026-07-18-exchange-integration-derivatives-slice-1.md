# Cross-Check: exchange-integration Derivatives Data Slice 1

## Scope

Verify that the operator-approved Funding/OI exchange/domain foundation matches
the FR-046 / US-025 design boundary without regressing existing Binance, Bybit,
OHLCV, order, credential, or live-trading behavior.

## Result

**PASS for Slice 1.** The bounded exchange/domain foundation is complete,
tested, and documented. FR-046 and US-025 remain **Partial** overall because
snapshot-v2 replay, runtime `MarketContext`, consumers, and robustness wiring
are intentionally assigned to later slices.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-016 | Complete for Slice 1 | Binance exposes normalized public Funding/OI current/history methods; public construction omits empty credentials. |
| FR-019 | Complete for Slice 1 | `BaseExchange` adds concrete default-unsupported methods, so existing/future adapters are not forced into partial implementations. |
| FR-020 | Complete / preserved | Existing OHLCV collection and snapshot behavior are unchanged; full exchange and repository suites pass. |
| FR-046 | Partial | Normalized acquisition boundary, pagination, intervals, gaps, and OI retention metadata are implemented. Snapshot replay and decision-time context remain later slices. |
| NFR-006 | Partial | Structured derivatives contracts are ready for persistence; snapshot schema v2 is not yet implemented. |
| NFR-009 | Complete for Slice 1 | Binance enables the capability; Bybit remains explicitly unsupported through the shared port contract. |
| NFR-011 | Complete for Slice 1 | No hardcoded credentials; empty public credential keys are omitted; raw CCXT payloads and unsanitized errors do not escape the adapter. |
| CON-002 | Complete for Slice 1 | Existing CCXT limiter remains; funding/OI page caps and actual-record cursor movement are deterministic. Runtime rolling budgets belong to the service slice. |
| DD-NFR-004 | Partial | Unsupported venue and malformed/partial adapter results are explicit; runtime consumer degradation is not wired yet. |
| DD-NFR-008/009 | Partial | UTC/Decimal/contiguity/retention contracts are present; immutable snapshot generations and no-look-ahead replay remain pending. |
| DD-NFR-011/012 | Complete for Slice 1 | Public-data boundary, test isolation, scoped formatting/lint, repository mypy, and full regression evidence are recorded. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-008 | Complete / preserved | Live credential and explicit-intent behavior is unchanged; no trading path was modified. |
| US-014 | Complete / preserved | No secret, deployment, or environment contract changed. |
| US-025 | Partial | Binance Funding/OI acquisition is implemented; optional `MarketContext` and deterministic snapshot replay are pending. |

## Implementation Evidence

- `src/exchange/derivatives.py`: frozen UTC/Decimal Funding/OI values, exact OI
  coverage metadata, and stable typed errors.
- `src/exchange/base.py`: backward-compatible capability and default unsupported
  port methods.
- `src/exchange/ccxt_base.py`: narrow unified CCXT protocol additions only.
- `src/exchange/binance.py`: credential-free public client construction,
  current/history normalization, actual-record pagination, inclusive bounds,
  de-duplication, strict grids, OI retention metadata, and sanitized errors.
- Existing Bybit behavior remains unchanged except an explicit capability
  assertion in tests.
- No runtime, proposal, strategy, backtest, dashboard, `data/`, deployment, or
  live-order file changed in Slice 1.

## Test Evidence

- Five exchange suites with coverage: **221 passed in 1.95s**.
- Coverage: `src.exchange` **87%**; generated derivatives module **92%**.
- Full repository regression: **2461 passed in 36.39s**.
- Changed-file Black and Ruff: pass for all nine Slice 1 Python files.
- Repository-wide mypy: 108 source files, zero issues.
- `git diff --check`: pass; no duplicate generated Python files.
- Tests use mocked CCXT clients; no real endpoint, credential, order, or runtime
  data is used.

## Gaps and Risks

- Snapshot schema v2, atomic generation publication, and version negotiation
  are not implemented; this is the next approved sequence item.
- Runtime caching/deadlines/budgets, `MarketContextBuilder`, strategy/proposal
  consumers, and snapshot-only robustness remain explicitly deferred.
- No live public Binance smoke was run in Build & Test; integration evidence is
  deterministic and mocked.
- Repository-wide Black/Ruff baseline drift is unrelated to Slice 1 and tracked
  as DEBT-081. Slice 1 files themselves are clean.

## Unit and Debt Mapping

- **Primary Unit**: `exchange-integration`
- **Secondary Units**: `backtesting-validation`, `persistence-data-integrity`,
  later `strategy-framework` and `proposal-runtime`
- **Related Debt**: Resolved DEBT-080 pagination precedent; active DEBT-081 is
  quality-governance-only and non-blocking for this slice
- **Legacy Phase Context**: Phases 2, 13.3, 21, 22, and 25

## Recommendations

1. Seal Slice 1 as complete and approved.
2. Implement Snapshot Schema v2 as a separate `backtesting-validation` slice
   with `persistence-data-integrity` and `exchange-integration` traceability.
3. Preserve the existing schema-v1 reader and data directories unchanged.
4. Do not mark FR-046 or US-025 complete until runtime and deterministic replay
   consumers have Build & Test evidence.
