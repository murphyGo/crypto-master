# Streaming Runtime Safety Inputs: Approved Functional Design

**Status:** Base Functional Design approved by operator `나머지도 계속 진행해줘`
on 2026-10-25. User `진행시켜` on 2026-10-26 approves the concrete runtime NFR
and explicit failure-isolation amendment for runtime-first implementation.
Source implementation passes 3,008 tests and independent review; production remains v63 /
`f0f3e52` until the separately evidenced same-capacity rollout. The dashboard
checkpoint slice remains a separate next bounded step. See the
[implementation plan](../../../plans/runtime-safety-score-streaming-activity-code-generation-plan.md).

## Evidence and responsibility

The v62 final four-session test records engine RSS up to **899,748 KiB** while
whole-guest use reaches **1293.313 MiB**. Dashboard growth is only 21.652 MiB.
The pre-change engine `_current_runtime_safety_score` calls `ActivityLog.read_all()`, then
filters to the recent 24h inputs. The rotator first collects/sorts all raw rows;
ActivityLog then constructs all rich models. This is a concrete retained-history
allocation path consistent with the observed peak, although no exhausted-state
stack or isolated allocation profile proves it is the only source.

The resulting safety score is consumed by notifications **and the actual
`_runtime_safety_pause_gate`**. An engine change therefore needs its own reviewed
safety contract; a dashboard/cache approval is not permission to alter this gate.

## Approved behavior

1. At each safety evaluation, capture one explicit UTC evaluation instant.
2. Stream the existing eligible retained activity sources in source order. Validate
   one canonical ActivityEvent at a time. Keep `read_all()` and its chronological
   API intact for other callers; only order-independent safety reduction uses the
   new iterator.
3. Apply the same inclusive `timestamp >= evaluated_at - 24h` rule. Preserve
   unbounded-lookback behavior when explicitly selected, and existing treatment
   of future timestamps. Fold the same counts and live kill-condition identities
   in one pass, without retaining an archive or list of rich recent events.
4. Include the same supplied replay/extra events, retain their current duplicate
   semantics, and preserve cache behavior for `None` versus an explicit list.
5. Compute the existing score, factors, clipping, bands and configured pause/
   advisory decision from these exact inputs. Do not alter weights, thresholds,
   mode separation, live intent, position sizing, fees or exchange actions.
6. Release source handles on completion, cancellation and any failure. No derived
   persistence, credential, paid service or CPU/capacity change is selected.

## Approved explicit timing decision

Before this change the default 24h cutoff is acquired **after** full-history materialization.
A lazy read captures it at evaluation entry unless another contract is selected.
This proposal intentionally selects a request-time snapshot and makes its time
explicit. On ordinary nondecreasing UTC, it may retain a penalty incident at the
24h boundary that the prior completion-time cutoff would already expire. It can
therefore conservatively pause a proposal that the prior path might admit.
This boundary difference is explicitly approved rather than presented as
behavior-preserving. Exact fixed-time inputs must still match the old helper on
every event/condition case. The approved NFR design defines clock reversal,
maximum evaluation age and unavailable-input failure behavior.

## Failure and compatibility boundary

Preserve the current canonical model and legacy malformed-row skip/warning policy
in this slice; do not silently broaden data acceptance. Hard source errors or a
new exhausted safety-read budget must not fabricate SAFE/zero inputs. The
approved amendment uses a typed failure at the account proposal boundary to stop
remaining new entries while preserving one existing monitor/snapshot pass.
Verify that no risk-dependent entry proceeds and no automatic paper/live switch
occurs. The approved runtime NFR supplies numeric read/state/dedup budgets;
legacy dashboard/direct helper compatibility remains a separate obligation.

## Required next evidence

- Independent old-helper parity at fixed UTC for every type, window boundary,
  advisory flag, fallback cycle/account identity, distinct kill trip, duplicate
  replay and extra-event/cache case.
- A one-shot stream, constant rich-event lifetime and deterministic handle close,
  including malformed input and failure; no fallback to full materialization.
- Notification and pause-gate tests in paper/live/configured-disabled paths,
  explicit timing-boundary cases, unreadable source and budget exhaustion.
- Representative incident and >=1M-event resource/CPU measurements; actual Fly
  engine/Dashboard/guest sampling and four sessions through a whole cycle.

The candidate is expected to remove the archive-sized retention path. It does
not promise the whole-guest or readiness targets will pass; repeated reads,
other engine allocators and mutable source verification still need measurement.

## Approved failure-isolation amendment

Subsequent source inspection showed the broad per-account exception guard also
skips that account's monitor/snapshot. The separately labelled
[failure-isolation amendment](failure-isolation-amendment.md) blocks risk entries
while keeping existing position management. This failure-flow change received
explicit 2026-10-26 approval with the runtime NFR; it was not inferred from the
earlier base-design approval. Source and operational verification remain distinct.
