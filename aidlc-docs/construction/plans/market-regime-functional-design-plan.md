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

---

# Task 2: Funding+OI Combo Crowding Filter (Derivatives Data — first consumer)

Added 2026-07-22. Priority-matrix rank 1 (composite 19); the Q4-locked first
consumer of the sealed FR-046 derivatives context (Slices 1-4).

- **Primary Unit**: `market-regime` (owns proposal allow/block decisions and
  per-sub-account gating policy)
- **Secondary Units**: `proposal-runtime` (gate wiring),
  `exchange-integration` (context source), `dashboard-operator-ui`
  (visibility), `proposal-replay-simulator` (evidence gate)
- **Related Requirements**: FR-045, FR-046, FR-029, FR-031, NFR-003, NFR-007
- **Related Stories**: US-025; new story to be added for crowding-gated
  proposals
- **Stage**: Functional Design
- **Constraints inherited**: business-rules R3 (missing context → fail-open +
  `gate_skipped_missing_market_context` telemetry), R7 (hypothesis-first — no
  enforcement without predeclared hypothesis + replay evidence), existing
  `market_regime` policy-block precedent (`enabled: false` default,
  per-sub-account opt-in).

## Hypothesis (predeclared, per Phase 5.3a / R7)

At funding-rate extremes with rising open interest, the perp market is
crowded in the funding-paying direction; new entries **with** the crowd carry
asymmetric squeeze risk (the crowded side supplies the fuel for adverse
cascades). Blocking (or down-weighting) with-crowd entries at extremes should
improve portfolio entry quality without touching strategy logic.
Falsifiability: replayed over recorded proposal history and snapshot-v2
backtest windows, with-crowd-at-extreme entries do NOT underperform other
entries → the filter adds nothing and must not ship enforcement.

## Open Questions

### Q1 — Enforcement rollout

- (a) Shadow-first: ship classification + would-have-blocked telemetry only
  (no vetoes); per-account veto enabled later, after the evidence gate passes
  on recorded shadow data. Recommended — measurable funnel deltas with zero
  behavior risk, mirrors CON-003 conservatism.
- (b) Veto immediately on per-account opt-in (skips the observation period).
- (c) Score down-weight instead of veto (softer, but muddies attribution).

[Answer]: (a) shadow-first — confirmed by operator 2026-07-22. (a) Shadow-first. Classification and would-block telemetry ship
first; veto remains unavailable until the evidence gate passes. Selected under
the operator's 2026-07-22 directive to continue with all recommended options.

### Q2 — Crowding signal definition

- (a) Relative: funding rate at a rolling-percentile extreme (default: 30-day
  window, ≥95th percentile = crowded-long, ≤5th = crowded-short) AND
  OI-rising confirmation (default: OI above its value N=24h ago). Recommended
  — symbol-adaptive, round defaults, thresholds config-tunable for the
  sensitivity gate.
- (b) Absolute funding threshold (e.g. |rate| ≥ 5bp/8h) — simpler but
  symbol/era-dependent.
- (c) Require both relative and absolute conditions.

[Answer]: (a) rolling-percentile extreme + OI-rising confirmation — confirmed by operator 2026-07-22. (a) Relative 30-day Funding percentiles (95th/5th) with an OI value
strictly above its 24-hour reference. Settled Funding only; predicted Funding
is excluded. Selected under the operator's 2026-07-22 recommended-options
directive.

### Q3 — Gate semantics and scope

- (a) Side-aware, per-sub-account policy block mirroring `market_regime`:
  crowded-long extreme blocks NEW long proposals only (shorts unaffected),
  mirror for crowded-short; `enabled: false` default; policy fields
  `reference: proposal.symbol`, thresholds, action (`shadow` | `veto`).
  Recommended.
- (b) Block both sides at any extreme (blunter).
- (c) Exempt `counter_trend` strategies from the block (they trade against
  the crowd by design) — can be layered on (a) later with evidence.

[Answer]: (a) side-aware per-sub-account block, default off — confirmed by operator 2026-07-22. (a) Side-aware, proposal-symbol referenced, per-sub-account policy;
disabled by default and shadow before veto. A crowded-long state applies only
to new long proposals, and crowded-short only to new short proposals.

### Q4 — Evidence gate before any account enables veto

- (a) BOTH: proposal-history replay (proposal-replay-simulator surface) AND
  a snapshot-v2 pinned backtest comparison must show non-negative expectancy
  delta for filtered vs unfiltered entries, with sample-size labels; plus ≥1
  regime bucket diversity. Recommended — mirrors the robustness-gate bar.
- (b) Proposal-history replay only (faster, single-window risk).
- (c) Operator judgment on shadow telemetry alone.

[Answer]: (a) both replay and snapshot-v2 backtest evidence — confirmed by operator 2026-07-22. (a) Both proposal-history replay and pinned Snapshot-v2 backtest
evidence are mandatory, with sample-size labels and at least two observed
market-regime buckets (one bucket plus `unknown` does not qualify).

## Plan Steps

- [x] Q1-Q4 answered; ambiguities resolved.
- [x] Extend `aidlc-docs/construction/market-regime/functional-design/spec.md`
      with the crowding-filter section: classification algorithm, policy
      schema, gate-reason/activity-event contract, shadow telemetry shape,
      evidence-gate procedure, dashboard surface.
- [x] Inception sync: new user story, story-map row, unit-of-work trigger
      note.
- [x] Hand off to code generation (bounded slices: classifier + policy →
      gate wiring + telemetry → dashboard → evidence-gate tooling).
- [x] Completion checklist: aidlc-state, session log, audit entry.
