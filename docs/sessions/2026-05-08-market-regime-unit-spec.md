# Session: market-regime unit specification

## Unit

`market-regime`

## Scope

Created the initial functional-design specification for a future market-regime
unit. No runtime code was changed.

## Related Requirements

- Proposed FR-045: classify current market regime and allow per-sub-account
  regime gating.
- Existing FR-036: isolate capital, positions, history, and equity by
  sub-account.
- Existing FR-029 / FR-031 / NFR-003: dashboard visibility.

## Files Changed

- `aidlc-docs/construction/plans/market-regime-functional-design-plan.md`
- `aidlc-docs/construction/market-regime/functional-design/spec.md`
- `aidlc-docs/inception/requirements/requirements.md`
- `aidlc-docs/inception/user-stories/stories.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/inception/units/unit-of-work.md`
- `aidlc-docs/aidlc-state.md`
- `docs/sessions/2026-05-08-market-regime-unit-spec.md`

## Decisions

- The unit should provide a shared regime classification instead of relying on
  per-strategy hidden filters.
- Sub-accounts opt in independently with `market_regime.enabled`.
- Disabled policy preserves current behavior.
- `unknown` blocks by default when gating is enabled unless explicitly allowed.

## Verification

- Documentation-only change. No code tests run.

## Notes

Implementation is intentionally deferred. The next stage should add classifier,
sub-account policy parsing, proposal gating, activity events, dashboard
visibility, and targeted tests.
