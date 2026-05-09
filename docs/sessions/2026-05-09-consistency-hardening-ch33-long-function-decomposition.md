# Session: consistency-hardening CH-33 long-function decomposition

Date: 2026-05-09

## Scope

- Completed CH-33 follow-up for long-function decomposition.
- Extracted proposal-engine OHLCV fetch/cache/primary-stream selection into `_fetch_and_validate_ohlcv()` plus `_fetch_ohlcv_cached()`.
- Split improver prompt boilerplate into focused section helpers for failure analysis, hard constraints, code shape, code hard constraints, and code output format.
- Replaced notification detail construction with `_format_proposal_detail()` supporting plain and code-block output.

## Verification

- `uv run pytest tests/test_proposal_engine.py tests/test_ai_improver.py tests/test_proposal_notification.py -q`
- `uv run black --check src/proposal/engine.py src/ai/improver.py src/proposal/notification.py tests/test_proposal_engine.py tests/test_ai_improver.py tests/test_proposal_notification.py`
- `uv run ruff check src/proposal/engine.py src/ai/improver.py src/proposal/notification.py tests/test_proposal_engine.py tests/test_ai_improver.py tests/test_proposal_notification.py`
- `uv run mypy src/proposal/engine.py src/ai/improver.py src/proposal/notification.py`

## Notes

- Added direct helper coverage for OHLCV cache reuse, prompt section helpers, and notification detail formatting.
