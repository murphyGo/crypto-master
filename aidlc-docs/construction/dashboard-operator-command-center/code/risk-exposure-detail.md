# Code Summary: Risk Exposure Detail

## Slice

Added equity-relative exposure detail to the Home command center.

## Behavior

- Home command-center status now carries the latest portfolio snapshot equity
  when snapshot data is available.
- Open exposure rows now include estimated margin based on entry notional and
  leverage.
- Open exposure rows now include notional exposure as a percentage of latest
  portfolio equity when equity is positive.
- The Home exposure table renders `Estimated Margin` and `Notional % Equity`
  alongside notional, leverage, and duplicate-account flags.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```
