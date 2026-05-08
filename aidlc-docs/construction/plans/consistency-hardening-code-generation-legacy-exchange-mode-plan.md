# Code Generation Plan: consistency-hardening — Legacy exchange config mode/credential alignment

## Task

Align the runtime testnet mode of `BinanceExchange` / `BybitExchange` with the
credential set actually selected from the legacy `BinanceConfig` /
`BybitConfig`. Today the exchange constructor's `testnet` argument controls the
ccxt `sandbox` URL, while `BaseConfig.get_credentials()` selects keys from
`self.testnet` (env-driven). When `build_exchange` forces a runtime mode
different from the env config (e.g. paper-mode forcing `testnet=True` while
`BINANCE_TESTNET=false`), ccxt is initialized with mismatched URL/keys.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice: P1 — Legacy exchange config mode/credential alignment
- Primary owner units: `exchange-integration`, `trading-core`

## Related Requirements

- FR-016 Binance Integration
- FR-017 Bybit Integration
- FR-019 Exchange Abstraction
- NFR-011 API Key Protection

## Related Source Findings

- 2026-05-08 five-subagent review: legacy `BinanceConfig`/`BybitConfig`
  credential selection ignores the runtime testnet flag passed to the
  exchange constructor.
- See `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
  → "Live and Exchange Safety" → "Align exchange instance mode with
  credential selection for legacy Binance/Bybit configs."

## Steps

- [x] Extend `BinanceConfig.get_credentials` to accept an optional explicit
      `testnet` override; preserve current behaviour when omitted.
- [x] Extend `BybitConfig.get_credentials` with the same optional override.
- [x] Wire `BinanceExchange.connect` to call
      `self.config.get_credentials(testnet=self.testnet)` so credentials
      follow the runtime mode that drives the ccxt sandbox flag.
- [x] Wire `BybitExchange.connect` to call
      `self.config.get_credentials(testnet=self.testnet)`.
- [x] Add unit tests in `tests/test_config.py` covering the explicit override.
- [x] Add a connect-time alignment test in `tests/test_exchange_binance.py`
      and `tests/test_exchange_bybit.py` for the mismatched-config case.
- [x] Run targeted `uv run pytest tests/test_config.py
      tests/test_exchange_binance.py tests/test_exchange_bybit.py
      tests/test_main_dispatch.py`.
- [x] Run `uv run ruff check src tests` and `uv run black src tests` on
      changed files.
- [x] Update `aidlc-docs/aidlc-state.md` consistency-hardening row.
- [x] Add session log under `docs/sessions/`.

## Verification

- Targeted pytest passes for the four test modules above.
- Lint/format clean for changed files.
- Exchange instance constructed with `testnet=True` and a config holding only
  live keys (or vice versa) returns the credentials matching the runtime mode
  when those are configured; falls back to the other set only when the
  requested-mode keys are absent (preserving current fallback behaviour).

## Completion Checklist

- [x] Code changes shipped under `src/`.
- [x] Tests added/updated.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.
