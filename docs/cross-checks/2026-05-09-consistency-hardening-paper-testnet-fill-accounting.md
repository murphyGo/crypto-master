# Cross-Check: consistency-hardening CH-28 Paper Testnet Fill Accounting

## Scope

Verify that paper-testnet open and close paths persist exchange-reported fill
economics rather than caller-side expected prices.

## Requirements

- FR-009 Live trading mode
- FR-010 Paper trading mode
- NFR-007 Trading history storage

## Evidence

- `open_position_on_testnet()` records `average_price`, `filled_quantity`,
  entry fee, SL/TP metadata, and entry order ID.
- `close_position_on_testnet()` records `average_price`, exit quantity, exit
  order ID, and exit fee.
- Targeted tests cover both open and close fill-accounting paths.

## Verification

- `uv run pytest tests/test_paper_trading.py tests/test_live_trading.py -q`
  - 121 passed.
- `uv run ruff check src/trading/paper.py tests/test_paper_trading.py`
  - passed.
- `uv run black --check src/trading/paper.py tests/test_paper_trading.py`
  - passed.
- `uv run mypy src/trading/paper.py tests/test_paper_trading.py`
  - passed.

## Result

PASS. Paper-testnet trade history now preserves actual exchange fill economics.
CH-28 remains open for remaining contract-parity cleanup.
