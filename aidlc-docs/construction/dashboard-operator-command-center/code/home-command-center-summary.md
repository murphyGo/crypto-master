# Code Summary: Home Command Center

## Slice

Added the first read-only command-center status section to the Streamlit Home
page.

## Behavior

- Home now renders a `Command Center` section before the existing page cards.
- The section summarizes:
  - runtime safety band and score,
  - last cycle status,
  - open persisted paper positions,
  - latest portfolio snapshot freshness,
  - selected mode,
  - discovered sub-account count,
  - actionable runtime event count,
  - estimated open notional from persisted entry price and quantity.
- Existing Strategies, Trading, Feedback Loop, and Engine pages remain
  unchanged.
- The command center is read-only and uses persisted local state only.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```
