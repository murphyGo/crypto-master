# Session: exchange-integration derivatives-data requirements addendum

## Unit and Stage

- **Unit**: `exchange-integration`
- **Stage**: Functional Design — requirements addendum
- **Task**: Register the funding-rate/open-interest product contract before
  the derivatives-data NFR pass and code generation.
- **Related Requirements**: FR-016 - FR-020, FR-046, NFR-006, NFR-009,
  NFR-011, CON-002.
- **Related Stories**: US-025.
- **Related Plan**:
  `aidlc-docs/construction/plans/exchange-integration-functional-design-plan.md`.

## Changes

- Added detailed FR-046 for current/historical perpetual funding and open
  interest, optional decision-time-bounded `MarketContext`, deterministic
  snapshot replay, and explicit missing/unsupported data.
- Added FR-046 to the canonical requirements index and linked it to the five
  owning/consumer units from the functional design.
- Added US-025 and synchronized the story map, unit ownership, component
  catalog, and verification questions.
- Marked the existing functional-design plan's requirements-addendum step
  complete. No runtime behavior or application code changed.

## Verification

- `rg -n "FR-046|US-025" docs/requirements.md aidlc-docs/inception aidlc-docs/construction/plans/exchange-integration-functional-design-plan.md`
- `git diff --check`
- Application tests were not run because this bounded step changes
  requirements and traceability documentation only.

## Decisions

- One functional requirement (FR-046) owns the end-to-end user-visible
  capability; rate-limit budgets, cache TTLs, backoff, availability, and
  partial-outage policies remain for the mandatory NFR Requirements stage.
- Binance-only v1, optional `MarketContext`, snapshot schema v2, and
  regime-filter-first sequencing remain the operator-approved functional
  design decisions from 2026-07-17.

## Risks and Debt

- No new technical debt was added.
- NFR requirements/design is still required before source changes. Under the
  AI-DLC NFR rule, ambiguity questions and explicit approval are mandatory.
