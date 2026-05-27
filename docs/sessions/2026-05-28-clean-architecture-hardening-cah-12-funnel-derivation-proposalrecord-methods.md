# Session: clean-architecture-hardening CAH-12 — TIER 4 FUNNEL STATE DERIVATION + `ProposalRecord` TRANSITION METHODS (PROP-F1 + PROP-F8)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-12 (Tier 4 ports / typed contracts: funnel state-to-field derivation + gate-total iteration [PROP-F1] + `ProposalRecord.reject` / `.mark` transition methods [PROP-F8]).

> TWELFTH unit shipped from the `clean-architecture-hardening` plan, and the THIRD of the Tier 4 ports /
> typed-contracts units (after CAH-10's AI / feedback DIP cluster and CAH-11's `CcxtExchange` base adapter
> dedup). It follows the standalone Tier 0 bugfix CAH-01, the three Tier 1 quick wins (CAH-02 order-side
> helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-dedup sweep), the three Tier 2 method
> extractions (CAH-05 `_handle_proposal` finalize helpers / CAH-06 long-function splits / CAH-07 LSP uniform
> `analyze()` signatures), and the two Tier 3 module splits (CAH-08 `performance.py` split + replay relocation
> / CAH-09 dashboard decomposition). CAH-12 IS trading-domain — it touches the proposal funnel accounting and
> the `ProposalRecord` finalize path — so it carried a quant-trader-expert review in addition to qa-reviewer.
> CAH-13…CAH-15 remain planned.

## Scope

CAH-12 is a behavior-preserving refactor that removes two pieces of Shotgun-Surgery-prone duplication from the
proposal funnel + finalize path: the hand-maintained `funnel._STATE_TO_FIELD` mapping and gate-total summation
(PROP-F1), and the `model_copy`-by-hand reject/mark transitions scattered across `engine.py` (PROP-F8). The
funnel mapping and the gate-bucket list were both transcriptions of the `ProposalFinalState` enum that had to be
kept in sync by hand; the reject/mark sites were each a hand-written `model_copy` that had to set the same
`final_state` / `decision` / `reason` / `at` shape identically every time. CAH-12 derives the first from the
enum and lifts the second into two `ProposalRecord` methods, leaving the contract byte-identical.

### Sub-item 1 — PROP-F1: funnel state-to-field derivation + gate-total iteration

`funnel._STATE_TO_FIELD` is now **derived** as `{s: s.value for s in ProposalFinalState}` instead of a
hand-maintained dict. qa verified against git HEAD that the old hand dict had **29 entries**, that `field ==
enum.value` for every one of them, and that the derivation reproduces it **exactly** (zero mismatches).
`gate_rejected_total` now **sums the 20 `GATE_REJECTED_*` members via iteration** over the enum rather than
listing the buckets by hand — the exact same 20 buckets, with no non-gate leakage. The explicit `FunnelCounts`
fields are KEPT (the dashboard contract reads them by name), so the derivation changes only how the mapping +
total are computed, not the public shape. Three new coverage tests guard the invariant: a field-coverage subset
check, a gate-sum check with non-gate noise injected, and a derivation-identity check.

### Sub-item 2 — PROP-F8: `ProposalRecord.reject` / `.mark` transition methods

Added `ProposalRecord.reject(final_state, reason, *, at=None)` and `ProposalRecord.mark(final_state)` to
`src/proposal/interaction.py`. Migrated **15 reject sites + 5 mark sites** in `engine.py` to the new methods.
**3 sites were correctly left inline** because they are genuinely different shapes:

- the **shadow** path (a 5-field copy plus `shadow=True`),
- the **operator-freeze** path (a fresh `ProposalRecord(...)` *construction*, not a copy of an existing record),
- the **attach_outcome** path (an outcome-bundle copy, not a plain reject/mark).

Because the model runs `use_enum_values=True`, the methods pass `.value` internally, making the result
**byte-identical** to the inline `model_copy` they replace (proven via `==` plus `model_dump_json()` equality).
**No transition-validation state machine was added** — that was explicitly out of scope; the methods only
encapsulate the existing copy shape.

## Process / verdicts

senior-developer implemented both sub-items as one behavior-preserving commit → quant-trader-expert 🟢 (this is
a trading-domain unit — funnel accounting + finalize path) → qa-reviewer 🟢. The two risks both reviewers
chased explicitly: (a) that deriving `_STATE_TO_FIELD` or the gate total from the enum could silently add, drop,
or leak a bucket vs the hand dict, and (b) that the reject/mark methods could drift the persisted record shape
away from the inline `model_copy` they replace.

### quant-trader-expert 🟢

Funnel total integrity holds: the gate total sums **exactly 20 `GATE_REJECTED` buckets** with no add / drop /
leak, and `_STATE_TO_FIELD` maps **every terminal identically** to the old hand dict. The 15 reject migrations
preserve `final_state` / `decision` / `reason` / `at or now_utc()` at each site; the 5 mark sites only ever set
`final_state` before, so `.mark` is the faithful encapsulation; the 3 inline sites are genuinely different
shapes (shadow 5-field, operator-freeze fresh construction, attach_outcome outcome-bundle) and were correctly
left alone. The `.value` preservation is real — the migrated records are byte-identical to the inline copies.

### qa-reviewer 🟢

Full suite **2297 passed** (+8 from the 2289 CAH-11 baseline — exactly 8 new test functions, **no existing test
modified**). qa verified the derivation identity **against git HEAD directly** — and noted that the in-suite
identity test is *tautological* (it compares the derivation to itself), so it independently checked the **real
old hand dict** to confirm the 29-member, field-==-enum.value identity. The coverage guard genuinely **fails**
on a deliberately-missing field (i.e. it is a real guard, not a no-op). The byte-identity proofs (`==` +
`model_dump_json()`) are real. Both remaining `model_copy` sites in `engine.py` are **risk-sizing quantity
resizes** — not reject/mark transitions — and were correctly left untouched.

## Files Changed

- **Modified**:
  - `src/proposal/funnel.py` — PROP-F1: `_STATE_TO_FIELD` now derived `{s: s.value for s in
    ProposalFinalState}`; `gate_rejected_total` now sums the 20 `GATE_REJECTED_*` members via enum iteration
    (no hand-listed buckets). Explicit `FunnelCounts` fields kept (dashboard contract).
  - `src/proposal/interaction.py` — PROP-F8: added `ProposalRecord.reject(final_state, reason, *, at=None)` +
    `ProposalRecord.mark(final_state)`; both pass `.value` under `use_enum_values=True` → byte-identical to the
    inline `model_copy`.
  - `src/runtime/engine.py` — PROP-F8: migrated 15 reject sites + 5 mark sites to `.reject` / `.mark`; 3 sites
    correctly left inline (shadow 5-field + `shadow=True`; operator-freeze fresh `ProposalRecord(...)`
    construction; attach_outcome outcome-bundle). The two remaining `model_copy` sites are risk-sizing quantity
    resizes, intentionally untouched.
  - `tests/test_proposal_funnel.py` — PROP-F1 coverage tests: field-coverage subset, gate-sum with non-gate
    noise, derivation-identity.
  - `tests/test_proposal_interaction.py` — PROP-F8 tests: `.reject` / `.mark` byte-identity vs inline
    `model_copy` (`==` + `model_dump_json()`).

The changes are a behavior-preserving derivation + encapsulation on the proposal funnel + finalize path; no
trading-math, sizing, gate-ordering, or signal path was touched.

## Key Decisions

| Decision | Rationale |
|---|---|
| Derive `funnel._STATE_TO_FIELD` as `{s: s.value for s in ProposalFinalState}` instead of a hand-maintained 29-entry dict | The hand dict was a transcription of the enum that had to be kept in sync by hand (Shotgun Surgery on every new terminal). qa proved `field == enum.value` for all 29 entries against git HEAD, so the derivation reproduces it exactly while making the mapping self-maintaining. |
| Sum `gate_rejected_total` by iterating the 20 `GATE_REJECTED_*` enum members instead of a hand-listed bucket set | Same Shotgun-Surgery hazard: a new gate bucket previously had to be added to the total by hand. Iteration over the enum's `GATE_REJECTED_*` members yields the exact same 20 buckets with no non-gate leakage, verified by a gate-sum-with-noise test. |
| Keep the explicit `FunnelCounts` fields (do NOT collapse them to a dict) | The dashboard contract reads the counts by field name; collapsing them would break the read side. The derivation changes only how the mapping + total are *computed*, not the public shape. |
| Add `ProposalRecord.reject(final_state, reason, *, at=None)` + `ProposalRecord.mark(final_state)`; migrate 15 reject + 5 mark sites | The reject/mark transitions were 20 hand-written `model_copy` calls each re-setting the same field shape — the encapsulation removes the duplication. `use_enum_values=True` means the methods pass `.value`, so the result is byte-identical to the inline copy (proven via `==` + `model_dump_json()`). |
| Leave 3 sites inline (shadow, operator-freeze, attach_outcome) | Genuinely different shapes: shadow is a 5-field copy + `shadow=True`; operator-freeze constructs a *fresh* `ProposalRecord`; attach_outcome copies an outcome-bundle. Forcing them through `.reject` / `.mark` would have distorted those shapes — Rule-of-Three / honest-encapsulation judgement. |
| Do NOT add a transition-validation state machine | Out of scope for CAH-12. The methods encapsulate the existing copy shape only; adding validated transitions would be a behavior change, not a behavior-preserving refactor. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2297 passed**, 0 failed (+8 from the 2289 CAH-11 baseline — exactly 8 new test functions, no
  existing test modified).
- `ruff check`: clean.
- Behavior-preservation proof (PROP-F1): qa verified the derivation against git HEAD directly — the old hand
  dict had 29 entries, `field == enum.value` for all, zero mismatches; the gate total sums exactly 20
  `GATE_REJECTED_*` buckets with no non-gate leakage. The in-suite identity test is tautological, so qa
  checked the real old dict independently.
- Behavior-preservation proof (PROP-F8): the `.reject` / `.mark` results are byte-identical to the inline
  `model_copy` (`==` + `model_dump_json()` equality); the 15 reject migrations preserve `final_state` /
  `decision` / `reason` / `at or now_utc()`; the 5 mark sites only set `final_state` before; the 3 inline sites
  are genuinely different shapes.
- The coverage guard genuinely fails on a deliberately-missing field (real guard, not a no-op).
- Both remaining `model_copy` sites in `engine.py` are risk-sizing quantity resizes, correctly untouched.

## Potential Risks

- **The funnel mapping + gate total are now derived from `ProposalFinalState`, so the enum is the single source
  of truth for funnel accounting.** This is the extensibility win — but it also means a careless edit to the
  enum (e.g. a `GATE_REJECTED_*`-prefixed member that is NOT actually a gate bucket, or a terminal whose
  `.value` does not match its intended `FunnelCounts` field) would silently distort the totals. The three
  coverage tests (field-coverage subset, gate-sum-with-noise, derivation-identity) are the guard, and the
  prefix convention for gate buckets is now load-bearing — recorded here so a later reader treats the
  `GATE_REJECTED_` prefix as a contract, not an incidental naming choice.
- **`ProposalRecord.reject` / `.mark` rely on `use_enum_values=True` for the byte-identity guarantee.** The
  methods pass `.value` precisely because the model config coerces enums to their values; if that config were
  ever flipped, the persisted record shape would change underneath the methods. The byte-identity tests are the
  net, but the dependency on `use_enum_values=True` is the reason the methods are byte-identical to the inline
  copies — not an incidental detail.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-12. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the third Tier 4 ports / typed-contracts unit: funnel state
derivation + gate-total iteration [PROP-F1] + `ProposalRecord.reject` / `.mark` transition methods [PROP-F8],
+8 tests, all gates green).

## Extensibility win

Adding a new `ProposalFinalState` terminal is now a **one-line add** — declare the `FunnelCounts` field and the
enum member, and the derived `_STATE_TO_FIELD` mapping + (for a gate bucket) the iterated gate total pick it up
automatically, guarded by the coverage test. Previously a new terminal was **Shotgun Surgery across 3+ sites**
(the hand dict, the hand-listed gate-total set, and any reject/mark site that produced it). The reject/mark
encapsulation similarly collapses 20 hand-written `model_copy` shapes into two methods, so the finalize-shape
contract lives in one place.

## Remaining Work

CAH-13…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-13 (Tier 4: `GateReason` enum for the `gate_reason` vocabulary + bounded `safety_score` typed accessors +
`activity_events.py` extraction [LAYER-F4])** — trading-domain-adjacent, so quant for the safety-score consumer.

No ADR needed — CAH-12 is the planned Tier 4 funnel-derivation + `ProposalRecord` transition-methods unit, a
behavior-preserving refactor delivered as routine planned work against the clean-architecture review's findings
(PROP-F1 / PROP-F8). It is not a contested design decision with competing long-term options: the
`ProposalFinalState` enum and the `ProposalRecord`/`FunnelCounts` contracts already existed, and CAH-12 only
derives from / encapsulates them (it introduces no new abstraction boundary, and explicitly declines the
transition-validation state machine as out of scope). The decisions are local DRY / honest-encapsulation
judgements recorded in the Key Decisions table; the audit value lives in this session log and the Change-History
row, not in an ADR.
