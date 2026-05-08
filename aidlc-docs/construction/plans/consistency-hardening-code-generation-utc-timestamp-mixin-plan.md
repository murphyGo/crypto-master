# Code Generation Plan: consistency-hardening - CH-36 UTC timestamp mixin

## Task

Start CH-36 shared validator mixins by extracting repeated UTC timestamp
coercion validators into a reusable Pydantic mixin.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-36 UTC timestamp mixin
- Primary owner units: `quality-governance`, `ai-feedback-loop`

## Related Requirements

- FR-026 Automated feedback loop
- NFR-008 Log retention / persisted feedback state

## Steps

- [x] Add `UtcTimestampMixin`.
- [x] Apply it to `AuditEvent`.
- [x] Apply it to `CandidateRecord`.
- [x] Apply it to `PromotionObservation`.
- [x] Keep explicit `evaluated_at` coercion in the promotion store.

## Verification

- [x] `uv run pytest tests/test_feedback_loop.py tests/test_feedback_audit.py
      tests/test_feedback_promotion_lab.py -q`
- [x] `uv run ruff check src/utils/pydantic_mixins.py src/feedback/audit.py
      src/feedback/loop.py src/feedback/promotion_lab.py`
- [x] `uv run black --check src/utils/pydantic_mixins.py src/feedback/audit.py
      src/feedback/loop.py src/feedback/promotion_lab.py`
- [x] `uv run mypy src/utils/pydantic_mixins.py src/feedback/audit.py
      src/feedback/loop.py src/feedback/promotion_lab.py`

## Completion Checklist

- [x] Code shipped under `src/`.
- [x] State/spec updated.
- [x] Session log and cross-check written.
