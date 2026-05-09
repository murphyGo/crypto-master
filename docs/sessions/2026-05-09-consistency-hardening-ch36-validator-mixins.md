# Session: consistency-hardening CH-36 validator mixins

Date: 2026-05-09

## Scope

- Completed CH-36 follow-up for shared validator mixins and parse-error semantics.
- Added `DecimalFieldsMixin` for persisted decimal fields and applied it to `PerformanceRecord` and `TradeHistory`.
- Extended `UtcTimestampMixin` for proposal and trade timestamp fields, then applied it to `Proposal` and `ProposalRecord`.
- Documented parse-error policy: read-only audit/listing paths warn-skip malformed records, while single-record write-path loads raise before mutation.

## Verification

- `uv run pytest tests/test_strategy_performance.py tests/test_feedback_loop.py tests/test_feedback_audit.py tests/test_feedback_promotion_lab.py tests/test_proposal_interaction.py -q`
- `uv run black --check src/utils/pydantic_mixins.py src/strategy/performance.py src/proposal/engine.py src/proposal/interaction.py src/feedback/audit.py src/feedback/loop.py tests/test_strategy_performance.py tests/test_feedback_loop.py tests/test_feedback_audit.py tests/test_feedback_promotion_lab.py tests/test_proposal_interaction.py`
- `uv run ruff check src/utils/pydantic_mixins.py src/strategy/performance.py src/proposal/engine.py src/proposal/interaction.py src/feedback/audit.py src/feedback/loop.py tests/test_strategy_performance.py tests/test_feedback_loop.py tests/test_feedback_audit.py tests/test_feedback_promotion_lab.py tests/test_proposal_interaction.py`
- `uv run mypy src/utils/pydantic_mixins.py src/strategy/performance.py src/proposal/engine.py src/proposal/interaction.py src/feedback/audit.py src/feedback/loop.py`

## Notes

- `FeedbackLoop.list_pending()` remains warn-skip for broad read-only scans.
- `FeedbackLoop.load_state()` now raises `FeedbackLoopError` with path and candidate id context on malformed JSON or model validation failure.
