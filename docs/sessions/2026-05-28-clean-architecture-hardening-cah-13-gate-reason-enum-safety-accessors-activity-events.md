# Session: clean-architecture-hardening CAH-13 — TIER 4 `GateReason` ENUM + BOUNDED `safety_score` ACCESSORS + `activity_events.py` EXTRACTION (gate_reason vocabulary + LAYER-F4)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-13 (Tier 4 ports / typed contracts: `GateReason` enum for the closed `gate_reason` vocabulary + bounded `safety_score` typed accessors over `event.details` + pure `ActivityEvent` / `ActivityEventType` extraction to `activity_events.py` [LAYER-F4]).

> THIRTEENTH unit shipped from the `clean-architecture-hardening` plan, and the FOURTH of the Tier 4 ports /
> typed-contracts units (after CAH-10's AI / feedback DIP cluster, CAH-11's `CcxtExchange` base adapter dedup,
> and CAH-12's funnel-derivation + `ProposalRecord` transition methods). It follows the standalone Tier 0
> bugfix CAH-01, the three Tier 1 quick wins (CAH-02 order-side helpers / CAH-03 `build_engine` inlining /
> CAH-04 dead-code-dedup sweep), the three Tier 2 method extractions (CAH-05 `_handle_proposal` finalize
> helpers / CAH-06 long-function splits / CAH-07 LSP uniform `analyze()` signatures), and the two Tier 3 module
> splits (CAH-08 `performance.py` split + replay relocation / CAH-09 dashboard decomposition). CAH-13 IS
> trading-domain-adjacent — it touches the runtime-pausing `safety_score` consumer and the `gate_reason`
> vocabulary that the activity-log JSONL persists — so it carried a quant-trader-expert review in addition to
> qa-reviewer. CAH-14…CAH-15 remain planned.

## Scope

CAH-13 is a behavior-preserving refactor with a hard on-disk constraint: the activity-log JSONL is a persisted
contract, so every byte written must be identical to the historical literal. The unit has three parts — a typed
`GateReason` vocabulary for the `gate_reason` key, bounded typed accessors for the 5 keys `safety_score` reads
off `event.details`, and a pure-leaf extraction of `ActivityEvent` / `ActivityEventType` into a new module so
`safety_score` no longer transitively pulls the activity-log IO machinery.

### Sub-item 1 — `GateReason` enum (closed `gate_reason` vocabulary)

New `src/runtime/gate_reason.py` defines `GateReason(str, Enum)` with **20 values** — the closed vocabulary the
`gate_reason` key takes. **21 producer sites in `engine.py`** now write `GateReason.X.value`; the consumers
(`safety_score`, dashboard `proposals.py` + `engine_cross_account_risk.py`) compare via the enum values. Every
`.value` is **byte-identical** to the historical string literal it replaces — verified against git HEAD, because
the activity-log JSONL is a persisted contract that downstream tooling and replay read back. The `.value` pin is
guarded by a **hand-written** (not tautological) test plus `test_no_member_is_missing_from_the_pin`, which forces
any future enum member to be pinned to an explicit expected literal rather than silently passing.

### Sub-item 2 — bounded `safety_score` typed accessors

Added bounded accessors `event_advisory` / `event_cycle_id` / `event_gate_reason` / `event_sub_account_id` /
`event_reason` (plus the `GLOBAL` sentinel) that centralize the **5 keys** `safety_score` reads off
`event.details`, preserving the exact `.get(default)` semantics at each site. `_count_kill_switch_conditions` and
`_is_stale_quote` were refactored onto them. The whole `details` dict was **deliberately NOT typed** — it is
intentionally polymorphic across event types, so only the 5 keys `safety_score` actually consumes were given
bounded accessors.

### Sub-item 3 — LAYER-F4: pure `activity_events.py` extraction

The pure `ActivityEvent` / `ActivityEventType` definitions were extracted **verbatim** (0-line class-body diff)
from `activity_log.py` into a new `src/runtime/activity_events.py`. `activity_log.py` now re-exports them as the
SAME class objects (identity-equal — `activity_log.ActivityEvent is activity_events.ActivityEvent`), so every
existing importer is unbroken. `safety_score` now imports the pure types from `activity_events`, and therefore no
longer transitively pulls in the activity-log IO machinery (the rotator / file-append side) to read an event.

## Process / verdicts

senior-developer implemented all three parts as one behavior-preserving commit → quant-trader-expert 🟢 (this is
a trading-domain-adjacent unit — the `safety_score` consumer drives the runtime-pausing path) → qa-reviewer 🟢.
The central risk both reviewers chased: that retyping the `gate_reason` producers or relocating the consumer
keys could shift a written byte or change the runtime-pausing judgment.

### quant-trader-expert 🟢

All 20 `gate_reason` values are byte-identical to HEAD. The safety-score consumer fidelity is preserved: the
dedup tuple order `(cycle_id, gate_reason, sub_account_id)`, the advisory exclusion, the cycle_id fallback, and
the `__global__` sentinel are all identical, so the runtime-pausing path is unchanged. The `operator_freeze`
judgment is correct — it uses the `reason` key plus an `OPERATOR_FREEZE_ENGAGED` event-type match, and **never**
the `gate_reason` path, so leaving the producer literal in place (rather than routing it through `GateReason`) was
the right call. The LAYER-F4 extraction is a 0-line class-body diff.

### qa-reviewer 🟢

Full suite **2312 passed** (+15 from the 2297 CAH-12 baseline — gate_reason +4, safety +9, import-hygiene +2);
ruff + mypy clean across 101 files. The `.value` pin test is hand-written, not tautological, and
`test_no_member_is_missing_from_the_pin` forces any future member to be pinned. No raw `"gate_reason":"..."`
literal remains in `engine.py`. The accessor defaults reproduce the prior `.get(default)` semantics. The LAYER-F4
identity (`activity_log.ActivityEvent is activity_events.ActivityEvent`) is asserted at runtime. Test changes are
additions-only plus 1 mechanical clock-patch-target move.

## Files Changed

- **Created**:
  - `src/runtime/gate_reason.py` — `GateReason(str, Enum)`, the 20-value closed `gate_reason` vocabulary;
    consumers compare via enum values, producers write `GateReason.X.value` byte-identically to the historical
    literal.
  - `src/runtime/activity_events.py` — LAYER-F4: pure `ActivityEvent` / `ActivityEventType` moved here
    verbatim (0-line class-body diff) so the leaf types are importable without the activity-log IO machinery.
  - `tests/test_runtime_gate_reason.py` — the hand-written `.value` pin test +
    `test_no_member_is_missing_from_the_pin` (forces future members to be pinned).
- **Modified**:
  - `src/runtime/activity_log.py` — re-exports `ActivityEvent` / `ActivityEventType` from `activity_events` as
    the SAME class objects (identity-equal); IO machinery stays here.
  - `src/runtime/engine.py` — 21 `gate_reason` producer sites now write `GateReason.X.value`; no raw
    `"gate_reason":"..."` literal remains.
  - `src/runtime/safety_score.py` — added the 5 bounded accessors (`event_advisory` / `event_cycle_id` /
    `event_gate_reason` / `event_sub_account_id` / `event_reason`) + `GLOBAL` sentinel;
    `_count_kill_switch_conditions` / `_is_stale_quote` refactored onto them; imports the pure event types from
    `activity_events`, no longer transitively pulling the IO machinery.
  - `src/dashboard/pages/proposals.py` — gate_reason comparison via the enum values.
  - `src/dashboard/pages/engine_cross_account_risk.py` — gate_reason comparison via the enum values.
  - `tests/test_runtime_safety_score.py` — accessor + consumer-fidelity tests (additions; 1 mechanical
    clock-patch-target move).
  - `tests/test_import_hygiene.py` — LAYER-F4 import-hygiene additions.
  - `tests/test_runtime_activity_log.py` — LAYER-F4 identity assertion additions.

The changes are a behavior-preserving retyping + leaf extraction on the activity-log / safety-score path; the
on-disk JSONL bytes, the dedup ordering, the advisory exclusion, the cycle_id fallback, the `__global__`
sentinel, and the operator_freeze judgment were all left exactly as they were.

## Key Decisions

| Decision | Rationale |
|---|---|
| Introduce `GateReason(str, Enum)` (20 values) and route the 21 `engine.py` producers through `GateReason.X.value` | The `gate_reason` vocabulary was a set of bare string literals scattered across producers + consumers with no single source of truth. A `str`-Enum closes the vocabulary and makes consumers compare against named members, while `.value` keeps every written byte identical to the historical literal — the activity-log JSONL is a persisted contract read back by replay / tooling. |
| Pin every `.value` to its historical literal with a hand-written (non-tautological) test + `test_no_member_is_missing_from_the_pin` | The byte-identity guarantee is the whole point; a tautological test comparing the enum to itself would not catch a drifted literal. The hand-written pin checks against the real historical strings, and the missing-member test forces a future enum addition to be deliberately pinned rather than silently passing. |
| Add 5 bounded accessors over `event.details` (`event_advisory` / `event_cycle_id` / `event_gate_reason` / `event_sub_account_id` / `event_reason`) + `GLOBAL` sentinel; do NOT type the whole `details` dict | `safety_score` reads only 5 keys off the polymorphic `details` dict; bounding those 5 with accessors that preserve the exact `.get(default)` semantics centralizes the read surface without forcing a type onto a dict that is intentionally polymorphic across every event type. |
| Leave the `operator_freeze` producer literal inline (do NOT route it through `GateReason`) | The operator-freeze judgment uses the `reason` key plus an `OPERATOR_FREEZE_ENGAGED` event-type match — it never reads the `gate_reason` path. Routing its producer literal through `GateReason` would imply a coupling that does not exist; quant confirmed leaving it inline was correct. |
| LAYER-F4: extract `ActivityEvent` / `ActivityEventType` verbatim into `activity_events.py`, re-export from `activity_log.py` as the SAME class objects | The pure leaf types were entangled with the activity-log IO machinery, so importing them (e.g. into `safety_score`) dragged in the rotator / file-append side. Moving them to a pure module (0-line class-body diff) + identity-equal re-export drops that transitive IO pull for the consumer while keeping every existing importer unbroken. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2312 passed**, 0 failed (+15 from the 2297 CAH-12 baseline — gate_reason +4, safety +9,
  import-hygiene +2).
- `ruff check` + `mypy`: clean across 101 files.
- Behavior-preservation proof (gate_reason): all 20 `GateReason` values are byte-identical to git HEAD; no raw
  `"gate_reason":"..."` literal remains in `engine.py`; the `.value` pin test is hand-written (not tautological)
  and `test_no_member_is_missing_from_the_pin` forces future members to be pinned.
- Behavior-preservation proof (safety_score): the dedup tuple order `(cycle_id, gate_reason, sub_account_id)`,
  the advisory exclusion, the cycle_id fallback, and the `__global__` sentinel are all identical → the
  runtime-pausing path is unchanged; the accessor defaults reproduce the prior `.get(default)` semantics; the
  operator_freeze judgment (the `reason` key + `OPERATOR_FREEZE_ENGAGED` match, never the gate_reason path) is
  preserved, so leaving its producer literal inline was correct.
- Behavior-preservation proof (LAYER-F4): 0-line class-body diff on the moved types; the identity
  `activity_log.ActivityEvent is activity_events.ActivityEvent` is asserted at runtime; `safety_score` imports
  the pure types and no longer transitively pulls the IO machinery.
- Test changes are additions-only plus 1 mechanical clock-patch-target move.

## Potential Risks

- **The `gate_reason` vocabulary is now load-bearing on byte-identity to the on-disk JSONL.** `GateReason` is a
  `str`-Enum precisely so `.value` reproduces the historical literal exactly; the activity-log JSONL is a
  persisted contract read back by replay / downstream tooling, so a future edit that renames a `.value` (rather
  than adding a new member) would silently break already-written logs. The hand-written `.value` pin +
  `test_no_member_is_missing_from_the_pin` are the guard, and the byte-identity-to-history constraint is now a
  contract, not an incidental detail — recorded here so a later reader treats the enum values as frozen
  on-disk strings.
- **The `safety_score` consumer fidelity depends on the dedup tuple order + advisory exclusion + cycle_id
  fallback + `__global__` sentinel staying exactly as relocated.** These feed the runtime-pausing judgment, so a
  careless change to the accessor defaults or the dedup key would alter when the engine pauses. The accessors
  centralize those reads, but the `.get(default)` semantics they reproduce are load-bearing — the consumer-
  fidelity tests are the net.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-13. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the fourth Tier 4 ports / typed-contracts unit: `GateReason`
enum + bounded `safety_score` accessors + `activity_events.py` extraction [LAYER-F4], +15 tests, all gates
green).

## Follow-up note (WATCH-ITEM — NOT filed as DEBT)

`src/runtime/__init__.py` eagerly imports `correlation_governor`, which transitively pulls `config` + `strategy`,
so even a pure-leaf cold-import of a `runtime` module drags those in. This is a candidate for a future
import-hygiene slice — the LAYER-F4 win of dropping the `activity_log` / `jsonl_rotator` transitive pull from the
`safety_score` consumer still holds; this watch-item is about the broader `runtime/__init__.py` eager-import
surface, not a regression in CAH-13's extraction. Recorded as a session-log watch-item, not a DEBT entry.

## Remaining Work

CAH-14…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-14 (Tier 4: de-globalize `strategy/performance.py` reads — constructor-inject the data dir + route raw
`open()` through `utils/io` [LAYER-F3]; no new repository port)**.

No ADR needed — CAH-13 is the planned Tier 4 `GateReason` / safety-accessor / `activity_events.py` unit, a
behavior-preserving refactor delivered as routine planned work against the clean-architecture review's findings
(the `gate_reason` vocabulary + LAYER-F4). It is not a contested design decision with competing long-term
options: the `gate_reason` literals, the `safety_score` consumer, and the `ActivityEvent` types already existed,
and CAH-13 only types / bounds / relocates them (it introduces no new abstraction boundary, and explicitly
declines typing the polymorphic `details` dict). The decisions are local typing / honest-encapsulation
judgements recorded in the Key Decisions table; the audit value lives in this session log and the Change-History
row, not in an ADR.
