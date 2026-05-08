# Code Generation Plan: consistency-hardening — CH-02 .py promotion + atomic strategy artifact writes

## Task

Fix the silent regression where `FeedbackLoop._promote_file` ran every approved
candidate through `_rewrite_frontmatter_status`. For `.py` candidates that
prepended a YAML frontmatter block (`---\nstatus: active\n---`) onto a Python
file, which made the promoted artifact non-parseable and effectively broke the
just-shipped `.py` strategy promotion path. Also route the generator's `_save`
and the promotion write through `atomic_write_text` so a crash mid-write
cannot leave a torn `.py`/`.md` candidate that the loader either rejects or
silently parses as a half-strategy.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice ID: CH-02
- Primary owner units: `ai-feedback-loop`, `strategy-framework`,
  `persistence-data-integrity`

## Related Requirements

- FR-026 Automated Feedback Loop
- FR-027 Technique Adoption (user approval required)
- NFR-008 Atomic Persistence

## Steps

- [x] Branch `_promote_file` on suffix; route `.py` through new
      `_rewrite_py_status_to_active`.
- [x] Implement `_rewrite_py_status_to_active` via AST scan +
      column-bounded source replacement to preserve formatting.
- [x] Route `_promote_file` write through `atomic_write_text`.
- [x] Route `StrategyImprover._save` through `atomic_write_text`.
- [x] Add tests: rewrite helper unit tests, idempotency, syntax-error
      surfacing, end-to-end approve-of-`.py`, atomic write usage.
- [x] Targeted pytest: `tests/test_feedback_loop.py`,
      `tests/test_ai_improver.py`, `tests/test_feedback_audit.py`,
      `tests/test_feedback_promotion_lab.py`.
- [x] Lint: ruff, black, mypy on changed files.
- [x] Update `aidlc-docs/aidlc-state.md`.
- [x] Session log under `docs/sessions/`.

## Verification

- 87 / 87 targeted tests pass.
- Ruff, black clean on changed files.
- Mypy clean for the two changed modules; pre-existing `src/backtest/harness.py:113`
  Decimal-vs-float error is unrelated and falls under CH-09.

## Completion Checklist

- [x] Code changes shipped under `src/`.
- [x] Tests added/updated.
- [x] Plan steps closed.
- [x] State row updated.
- [x] Session log written.
