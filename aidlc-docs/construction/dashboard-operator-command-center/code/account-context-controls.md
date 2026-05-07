# Code Summary: Account Context Controls

## Slice

Extended the Home command center with account-context controls.

## Behavior

- Home now lets the operator select `paper` or `live` command-center mode.
- Home now lets the operator choose `Aggregate` or a discovered sub-account
  scope when more than one persisted sub-account exists.
- The command-center read model now carries the selected scope and reads only
  that scope's persisted trades/snapshots unless `Aggregate` is selected.
- Existing Trading, Engine, Strategies, and Feedback pages remain unchanged.

## Verification

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q
uv run black src tests --check
uv run ruff check src tests
```
