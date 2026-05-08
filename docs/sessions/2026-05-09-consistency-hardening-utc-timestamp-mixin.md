# Session: consistency-hardening CH-36 UTC Timestamp Mixin

## Unit

- `consistency-hardening`
- Primary owner units: `quality-governance`, `ai-feedback-loop`

## Related Requirements

- FR-026 Automated feedback loop
- NFR-008 Log retention / persisted feedback state

## Changes

- Added `src/utils/pydantic_mixins.py::UtcTimestampMixin`.
- Replaced repeated timestamp field validators in `AuditEvent`,
  `CandidateRecord`, and `PromotionObservation`.
- Preserved explicit promotion-store `evaluated_at` coercion because that value
  is normalized before model construction.

## Tests

- `uv run pytest tests/test_feedback_loop.py tests/test_feedback_audit.py tests/test_feedback_promotion_lab.py -q`
  - 43 passed.
- `uv run ruff check src/utils/pydantic_mixins.py src/feedback/audit.py src/feedback/loop.py src/feedback/promotion_lab.py`
  - passed.
- `uv run black --check src/utils/pydantic_mixins.py src/feedback/audit.py src/feedback/loop.py src/feedback/promotion_lab.py`
  - passed.
- `uv run mypy src/utils/pydantic_mixins.py src/feedback/audit.py src/feedback/loop.py src/feedback/promotion_lab.py`
  - passed.

## Decisions

- Used a mixin with `check_fields=False` so the same validator can be shared by
  models with different timestamp field names.

## Risks

- CH-36 remains open for Decimal field mixins and corrupt-record parse policy
  consolidation.
