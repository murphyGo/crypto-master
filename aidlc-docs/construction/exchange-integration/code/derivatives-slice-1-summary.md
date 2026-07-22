# Derivatives Data Slice 1 Code Generation Summary

**Unit:** `exchange-integration`

**Stage:** Code Generation Part 2

**Status:** Generated; explicit operator review pending

## Scope generated

Slice 1 adds the normalized exchange/domain foundation for Binance public
Funding and Open Interest data. It deliberately does not wire collection into
the runtime engine, snapshots, proposal filters, strategies, backtests, the
dashboard, or deployment.

## Contracts

- Frozen Pydantic domain values use `Decimal` and reject naive timestamps:
  `FundingRate`, `CurrentFundingRate`, `OpenInterestPoint`, and
  `OpenInterestHistory`.
- OI history carries requested/actual bounds and
  `truncated_at_venue_retention`; no missing values are synthesized.
- Stable errors cover `unsupported_venue`, `invalid_payload`, `timestamp_gap`,
  and `unsupported_interval`.
- `BaseExchange.supports_derivatives_data` defaults to `False`. Its concrete
  derivatives methods raise typed unsupported errors, so existing adapters do
  not gain new abstract implementation requirements.
- `CCXTClient` contains only the four unified Funding/OI calls used by Binance.

## Binance behavior

- Binance advertises derivatives-data support and maps current Funding/OI
  responses into normalized values. Raw ccxt `info` dictionaries never leave
  the adapter.
- Empty public credentials omit the `apiKey` and `secret` configuration keys;
  existing credentialed configuration remains unchanged.
- Funding history uses a 1000-record page cap, inclusive request bounds,
  chronological de-duplication, last-actual-record cursor advancement, and a
  strict UTC 8h grid. Gaps and unsupported intervals fail loudly.
- OI history uses a 500-record page cap and equivalent actual-record cursor
  semantics on the UTC 1h grid. A missing requested prefix is reported as
  venue-retention truncation.
- ccxt failures are translated to sanitized stable categories without
  serializing raw URLs or response bodies.

## Files

Created:

- `src/exchange/derivatives.py`
- `tests/test_exchange_derivatives.py`
- `aidlc-docs/construction/exchange-integration/code/derivatives-slice-1-summary.md`
- `docs/sessions/2026-07-18-exchange-integration-derivatives-slice-1.md`

Modified:

- `src/exchange/base.py`
- `src/exchange/ccxt_base.py`
- `src/exchange/binance.py`
- `tests/test_exchange_base.py`
- `tests/test_exchange_ccxt_base.py`
- `tests/test_exchange_binance.py`
- `tests/test_exchange_bybit.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/exchange-integration-code-generation-plan.md`

## Verification evidence

- Pre-edit exchange baseline: `165 passed`.
- Focused current/domain suite: `105 passed`.
- Complete exchange group after generation: `221 passed`.
- Repository suite: `2461 passed` in 38.61 seconds.
- Black: clean on all changed Python source/tests.
- Ruff: all checks passed on all changed Python source/tests.
- Mypy: `Success: no issues found in 7 source files` for `src/exchange`.
- Repository-wide mypy: `Success: no issues found in 108 source files`.
- `git diff --check`: clean.
- No `_new.py` / `_modified.py` duplicates, production dependencies,
  migrations, deployment artifacts, or runtime-data changes were introduced.

## Compatibility and safety

- Existing OHLCV, ticker, balance, order, testnet, and credentialed-client
  behavior is unchanged.
- Bybit remains explicitly unsupported for derivatives context in v1.
- No collection is activated and no trading/proposal decision can change from
  this slice alone.
- User-owned `.claude/settings.local.json` and
  `.claude/scheduled_tasks.lock` changes were preserved and excluded.

## Slice 2 and later interface assumptions

- Snapshot schema v2 will persist only normalized Funding/OI series and
  availability metadata, never raw responses or predicted funding.
- The later engine-scoped `DerivativesContextService` owns caching, deadlines,
  retry/circuit state, request budgets, collection scheduling, and
  degraded/recovered events; none are adapter responsibilities in Slice 1.
- The runtime service will construct a dedicated mainnet USD-M public Binance
  source with empty credentials and consume it through a narrow data protocol.
- Proposal Funding+OI filtering and Funding-Extreme MR remain separate,
  evidence-gated consumer slices after snapshot/runtime wiring.

No new technical debt was filed. Remaining work is already bounded by the
approved derivatives-data slice sequence rather than being an untracked gap.
