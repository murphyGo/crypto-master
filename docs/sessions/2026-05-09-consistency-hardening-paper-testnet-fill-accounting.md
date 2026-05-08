# Session: consistency-hardening CH-28 Paper Testnet Fill Accounting

## Unit

- `consistency-hardening`
- Primary owner units: `trading-core`, `exchange-integration`

## Related Requirements

- FR-009 Live trading mode
- FR-010 Paper trading mode
- NFR-007 Trading history storage

## Changes

- Updated `PaperTrader.open_position_on_testnet()` to record exchange
  `average_price`, `filled_quantity`, entry fee, stop loss, and take profit.
- Updated `PaperTrader.close_position_on_testnet()` to record exchange
  `average_price`, exit quantity, exit order ID, and exit fee.
- Added tests pinning paper-testnet trade history parity with live fill
  accounting.

## Tests

- `uv run pytest tests/test_paper_trading.py tests/test_live_trading.py -q`
  - 121 passed.
- `uv run ruff check src/trading/paper.py tests/test_paper_trading.py`
  - passed.
- `uv run black --check src/trading/paper.py tests/test_paper_trading.py`
  - passed.
- `uv run mypy src/trading/paper.py tests/test_paper_trading.py`
  - passed.

## Decisions

- Limited this CH-28 slice to persisted fill economics. Testnet order-status
  rejection parity and any broader signature cleanup remain separate changes.

## Risks

- CH-28 remains open for SL/TP signature unification and `_entry_fees` cleanup.
