# Functional Design Plan: market-regime

## Task

Define a first-class market-regime unit that can classify the current market as
bull, bear, or sideways and let each sub-account decide whether to apply regime
gating.

## Related Context

- Unit: `market-regime`
- Stage: Functional Design
- Requirements: FR-045 (proposed), FR-036, FR-029, FR-031, NFR-003, NFR-007,
  NFR-008
- Stories: US-024 (proposed)
- Related units: `proposal-runtime`, `sub-account-capital-segmentation`,
  `dashboard-operator-ui`, `backtesting-validation`

## Steps

- [x] Capture functional requirements and account-level policy semantics.
- [x] Create a construction functional-design artifact for future
      implementation.
- [x] Sync inception indexes:
      `aidlc-docs/inception/requirements/requirements.md`,
      `aidlc-docs/inception/user-stories/stories.md`,
      `aidlc-docs/inception/application-design/unit-of-work-story-map.md`,
      `aidlc-docs/inception/units/unit-of-work.md`, and
      `aidlc-docs/aidlc-state.md`.
- [ ] Implement runtime classification, per-account config, dashboard
      visibility, and tests in a later code-generation stage.

## Verification

- [ ] Implementation stage should run targeted tests covering regime
      classification, account policy defaults, proposal gating, and dashboard
      rendering.

## Completion Checklist

- [x] Specification created.
- [x] AI-DLC plan created.
- [x] Inception indexes synced.
- [ ] Code intentionally deferred.
