# Session: consistency-hardening — Legacy exchange config mode/credential alignment

## Unit

- `consistency-hardening` (primary owner units: `exchange-integration`,
  `trading-core`)
- Stage: Code Generation
- Slice: P1 — Legacy exchange config mode/credential alignment

## Related Requirements

- FR-016 Binance Integration
- FR-017 Bybit Integration
- FR-019 Exchange Abstraction
- NFR-011 API Key Protection

## Problem

`BinanceExchange(config, testnet=...)` and `BybitExchange(config, testnet=...)`
forward their constructor `testnet` argument to ccxt's `sandbox` URL flag, but
`BinanceConfig.get_credentials()` / `BybitConfig.get_credentials()` selected
keys from `self.testnet` (the legacy `BINANCE_TESTNET` / `BYBIT_TESTNET` env
default). When `src.main.build_exchange` overrode the env default — for
example forcing `testnet=True` for paper-mode dispatch even though
`BINANCE_TESTNET=false` — ccxt was initialized with mismatched URL/keys
(sandbox URL with live keys, or live URL with testnet keys), causing
authentication failures or silent connections to the wrong network.

## Fix

- `BinanceConfig.get_credentials(testnet=None)` and
  `BybitConfig.get_credentials(testnet=None)` accept an optional explicit
  override. When provided, the override drives credential selection;
  otherwise behaviour is unchanged for existing callers.
- `BinanceExchange.connect` and `BybitExchange.connect` now call
  `self.config.get_credentials(testnet=self.testnet)` so the runtime sandbox
  flag and the credentials are always picked from the same source of truth.

## Files Changed

- `src/config.py`
- `src/exchange/binance.py`
- `src/exchange/bybit.py`
- `tests/test_config.py`
- `tests/test_exchange_binance.py`
- `tests/test_exchange_bybit.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-legacy-exchange-mode-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_config.py tests/test_exchange_binance.py
  tests/test_exchange_bybit.py tests/test_main_dispatch.py` — 212 passed.
- `uv run ruff check` on the six changed source/test files — clean.
- `uv run black --check` on the same six files — clean.
- `uv run mypy src/config.py src/exchange/binance.py src/exchange/bybit.py`
  — clean.

## Decisions

- Preserved the existing fallback semantics of `get_credentials`: when the
  resolved-mode key set is empty, it still returns the other configured set
  rather than raising. Keeping the slice tightly scoped to the alignment fix;
  any new validation gate ("paper mode without testnet creds should refuse
  to start") belongs in a separate hardening slice so we don't surprise live
  deployments here.
- Did not deprecate or remove the legacy `testnet` field on
  `BinanceConfig`/`BybitConfig`. Leaving it in place keeps `.env`
  configurations and `validate_for_live_trading` checks unchanged; only the
  credential resolution path now defers to the runtime mode.

## Risks

- Low. The only change in observable behaviour is that exchanges constructed
  with a `testnet` flag that disagrees with the env-config field now get
  credentials matching the constructor argument. Tests covered the
  previously-broken case explicitly.

## Debt Added / Resolved

- No new tech-debt entries opened or resolved. The remaining P1 slices in
  `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
  stay queued.

## Follow-up

- Continue the consistency-hardening backlog with the next P1 slice:
  `.py` strategy promotion integrity (`ai-feedback-loop`,
  `strategy-framework`).
