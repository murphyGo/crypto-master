# Code Generation Plan: consistency-hardening - CH-28 Paper testnet fill accounting

## Task

Start CH-28 paper/live trader contract parity by making paper-testnet order
records use exchange-reported fill economics like the live trader.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-28 paper testnet fill accounting
- Primary owner units: `trading-core`, `exchange-integration`

## Related Requirements

- FR-009 Live trading mode
- FR-010 Paper trading mode
- NFR-007 Trading history storage

## Steps

- [x] Record testnet open trades with `Order.average_price`,
      `Order.filled_quantity`, entry fee, and SL/TP metadata.
- [x] Record testnet closes with `Order.average_price`, exit quantity,
      exit order ID, and exit fee.
- [x] Add regression tests for paper-testnet actual fill and fee recording.
- [x] Run targeted paper/live trader tests.

## Verification

- [x] `uv run pytest tests/test_paper_trading.py tests/test_live_trading.py -q`
- [x] `uv run ruff check src/trading/paper.py tests/test_paper_trading.py`
- [x] `uv run black --check src/trading/paper.py tests/test_paper_trading.py`
- [x] `uv run mypy src/trading/paper.py tests/test_paper_trading.py`

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] Tests updated.
- [x] State/spec updated.
- [x] Session log and cross-check written.
