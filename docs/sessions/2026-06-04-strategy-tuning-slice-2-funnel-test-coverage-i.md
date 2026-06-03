# Session: strategy-tuning Slice 2 (i) — funnel unit-test coverage gaps

Date: 2026-06-04
Unit: `proposal-runtime` (DEBT-069 `strategy-tuning` Slice 2, sub-task (i))
Stage: Code Generation (test-only)
Related: DEBT-069(i) QA follow-up; PROP-F1/CAH-12 enum-derived funnel totals.

## Scope

Close the QA follow-up (i): the two end-to-end funnel-aggregator tests used
hand-picked subsets of `ProposalFinalState`, so the full `compute_funnel_counts`
→ `_classify` → `_STATE_TO_FIELD` → derived-total path was never exercised for
`GATE_REJECTED_STRATEGY_ACTION_PAUSE` (gate-bucket sum) or `SHADOW_RECORDED`
(post-score sum). Test-only change — no production code touched (the totals were
already enum-derived and correct since CAH-12).

## What shipped (`tests/test_proposal_funnel.py`)

Rather than the originally-specced "append the two named members", both tests now
**iterate the enum** so they are exhaustive and stay so as terminals are added:

- `test_gate_rejected_total_sums_every_gate_bucket` — builds one ACCEPTED record
  in EVERY `GATE_REJECTED_*` bucket (all 20) via
  `[s for s in ProposalFinalState if s.name.startswith("GATE_REJECTED_")]` and
  asserts `gate_rejected_total == len(gate_states)` **and** `total ==
  len(gate_states)` (every record routed to its own bucket, no leak into
  non-gate fields). The test name finally matches its behaviour ("every gate
  bucket" — previously only 4).
- `test_score_accepted_total_sums_every_post_score_state` — derives the
  post-score set as `{all GATE_REJECTED_*} ∪ _NON_GATE_POST_SCORE_STATES`, where
  the new module-level `_NON_GATE_POST_SCORE_STATES` frozenset includes the
  previously-missing `SHADOW_RECORDED` alongside `SCORE_ACCEPTED` /
  `PROPOSAL_OPENED` / `TRADE_OPENED` / `OUTCOME_LINKED` / `OPEN_ERRORED`. Adds a
  **partition-completeness guard**: `post_score ∪ _NON_SCORE_ACCEPTED_STATES ==
  set(ProposalFinalState)` and the two sets are disjoint — so a future terminal
  that is neither post-score nor explicitly non-counting fails loudly instead of
  silently under-counting `score_accepted_total`.

Two small module-level helpers added: `_NON_GATE_POST_SCORE_STATES`,
`_NON_SCORE_ACCEPTED_STATES`, `_gate_rejected_states()`.

## Why stronger than the spec

The specced subset-append would have covered the two named members at a fixed
point in time but re-introduced the same gap for the next terminal. Enum
iteration + the partition guard makes the end-to-end coverage self-maintaining
and complements the existing `FunnelCounts`-field derivation guard
(`test_gate_rejected_total_derivation_sums_exactly_the_gate_members`).

## Tests / checks

- `tests/test_proposal_funnel.py`: 16 passed.
- Full suite: **2330 passed** (net 0 — two tests rewritten in place), 0 failed.
- `ruff check tests/test_proposal_funnel.py` clean. No source change → no mypy delta.

## Debt

DEBT-069(i) resolved. Remaining-open DEBT-069 sub-tasks after this cycle: (c)
observation store, (f) pause-reason split, (g) post-evidence threshold
calibration.
