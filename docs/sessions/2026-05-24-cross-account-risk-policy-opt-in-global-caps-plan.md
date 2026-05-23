# 2026-05-24 Cross-Account Risk Policy Opt-In Global Caps Plan

## Unit

- `cross-account-risk-policy`

## Related Requirements

- FR-036, FR-037, FR-038, FR-044
- NFR-007, NFR-008, NFR-012

## Task

Clarify DEBT-068(b) before code generation: global symbol/side exposure caps
must be opt-in, default disabled, paper-mode advisory only, and live-mode
hard-blocking only when explicitly enabled.

## Decisions

- Global exposure caps default disabled to preserve existing behavior.
- Paper mode must not hard-block on global caps in v1 because paper accounts are
  used to measure strategy/account performance independently.
- If enabled in paper mode, the runtime should emit advisory / would-block
  evidence and continue execution.
- Live mode may hard-block global cap breaches only when the operator enables
  the global policy.

## Files Changed

- `aidlc-docs/construction/cross-account-risk-policy/functional-design/spec.md`
- `aidlc-docs/construction/plans/cross-account-risk-policy-code-generation-plan.md`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`

## Verification

- Documentation-only planning update; no runtime tests run.

## Next Slice

Implement DEBT-068(b) with targeted tests for:

- default-disabled behavior preserving current proposal flow,
- paper-mode advisory / pass-through behavior when enabled,
- live-mode hard-block behavior when enabled,
- config parsing for the new global policy opt-in fields.
