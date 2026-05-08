# Session: consistency-hardening — CH-02 .py promotion + atomic strategy artifact writes

## Unit

- `consistency-hardening` (primary owner units: `ai-feedback-loop`,
  `strategy-framework`, `persistence-data-integrity`)
- Stage: Code Generation
- Slice ID: CH-02

## Related Requirements

- FR-026 Automated Feedback Loop
- FR-027 Technique Adoption (user approval required)
- NFR-008 Atomic Persistence

## Problem

`FeedbackLoop._promote_file` re-read the approved candidate and ran it through
`_rewrite_frontmatter_status`. For a `.py` candidate (which has no YAML
frontmatter) the helper hit its "no frontmatter — prepend a minimal one" branch
and emitted a `---\nstatus: active\n---` block at the top of the file. The
promoted artifact was no longer valid Python — `ast.parse` in
`validate_python_strategy_source` raised `SyntaxError` and the strategy never
loaded again, silently breaking the `.py` promotion path that had just been
shipped.

In addition, both `StrategyImprover._save` (writes the generator's candidate)
and `_promote_file` (writes the promoted artifact) used plain
`Path.write_text`, so a crash mid-write could leave a half-formed file in
`strategies/experimental/` or `strategies/`. The loader would either reject
that file as invalid or — worse — parse a syntactically valid prefix as a
half-strategy on the next pass.

## Fix

- `_promote_file` now branches on `source_path.suffix.lower()`. The `.md`
  branch keeps the existing frontmatter rewrite. The `.py` branch routes
  through a new `_rewrite_py_status_to_active` that uses `ast` to find the
  `TECHNIQUE_INFO` assignment, locate the `"status"` value, and replace only
  that source span — preserving formatting, comments, and quote style. Surfaces
  syntax errors at promotion time instead of letting them masquerade as
  "loader rejected" later.
- Both `_promote_file` and `StrategyImprover._save` now route through
  `src.utils.io.atomic_write_text` so torn writes can't ship.

## Files Changed

- `src/feedback/loop.py`
- `src/ai/improver.py`
- `tests/test_feedback_loop.py`
- `tests/test_ai_improver.py`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`
  (backlog refresh)
- `aidlc-docs/construction/plans/consistency-hardening-code-generation-py-promotion-atomic-plan.md`

## Tests / Checks Run

- `uv run pytest tests/test_feedback_loop.py tests/test_ai_improver.py
  tests/test_feedback_audit.py tests/test_feedback_promotion_lab.py` — 87/87
  passed (5 new tests).
- `uv run ruff check` on the four changed files — clean.
- `uv run black` applied (one test file reformatted).
- `uv run mypy src/feedback/loop.py src/ai/improver.py` — clean for both;
  the unrelated `src/backtest/harness.py:113` mypy error is pre-existing and
  belongs to CH-09.

## Decisions

- Did not switch to `ast.unparse` for the `.py` rewrite — it would reformat
  the entire file, which is unnecessary churn for a generated artifact and
  would also force tests/diffs to track unrelated formatting. The
  column-bounded source replacement keeps the diff exactly one literal wide.
- `_rewrite_py_status_to_active` raises `FeedbackLoopError` on invalid Python
  rather than silently leaving the file unchanged. Surfacing the failure at
  promotion time keeps it observable in audit/state instead of hiding inside
  the loader's per-file `try/except` at the next pass.
- Idempotent on already-`active` files (returns input unchanged). Avoids a
  spurious diff on a re-promoted artifact.

## Risks

- Low. The `.md` path is unchanged. The `.py` path was previously broken — the
  fix is provably correct against an existing test fixture (`write_experimental_py`)
  and a new end-to-end approve-of-`.py` regression test asserts both
  `ast.parse` succeeds and `"status": "active"` is present.

## Debt Added / Resolved

- No new tech-debt entries opened. CH-02 is closed; the remaining
  consistency-hardening backlog (CH-03–CH-25) remains queued in
  `aidlc-docs/construction/consistency-hardening/functional-design/spec.md`.

## Follow-up

- CH-03: sub-account cycle failure isolation + notifier backend failure
  visibility (`src/runtime/engine.py`, `src/proposal/notification.py`).
