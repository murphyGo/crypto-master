# Cross-check: Bounded Runtime Safety Inputs

**Unit / debt:** `runtime-safety-score`, related `proposal-runtime` and
`dashboard-operator-ui`; DEBT-083 Critical/active.

**Verdict:** Source implementation, independent compatibility/quant review,
lifecycle/integration, full regression and source-quality checks pass. Authorized
rollout is pending; no deployment, dashboard readiness or debt closure is certified.
Results apply to the reviewed local tree based on `4b714fd`. Concurrent remote
`dca38fb` includes overlapping runtime/dashboard checkpoint work and requires
reconciliation before integration/rollout; its implementation status is not
inferred from this local runtime checkpoint.

| Contract | Evidence / status |
|---|---|
| Approval | 2026-10-26 user `진행시켜` approves concrete runtime NFR and the explicit typed-failure monitoring amendment. Prior same-capacity rollout authority persists; dashboard checkpoint work remains a separate bounded step. |
| Fixed-time score | Independent frozen-`4b714fd` oracle: 184 cases / 2,396-row fixed corpus, exact inputs/score/factors/bands. Inclusive boundary, future timestamps, nonpositive lookback, stale reason OR message, duplicate counts and advisory exclusion preserved. |
| Kill identity | Raw scalar tuples preserve bool/int/float equality, shared/distinct NaN, enum/string equivalence, None-only cycle fallback and falsy-account sentinel. Unsupported objects fail rather than normalize. |
| Retention / compatibility | One-pass Iterable aggregation retains counters/keys, not event archives. List-returning recent helper and chronological legacy APIs remain. Twelve independent legacy source cases pass. Exported helpers retain uncapped/hashable-key compatibility; strict bounds apply only to runtime reads. 50,001-key and hashability regressions pass. |
| Bounds | 50k exact keys / 16 MiB active state, reserved extras included; 64 KiB blocks / 1 MiB rows / 4 MiB source manifest / 4096 extras within 2 MiB. Pre-retain accounting and rejection tests pass. Optional 2 MiB negative-summary cache is omitted. |
| Reader ownership | One lazy process-owned daemon, one active/zero queued; no event-loop disk IO, replacement worker, partial score or late publication. Source/service lifecycle suite: 39 passed, including mutation/readability/timeout/cancellation/closure. |
| UTC / cache / budgets | Approved request-time anchoring may retain a conservative edge penalty; clock reversal/expired results fail. `None` reuse differs from explicit `[]`; failed reads cannot admit via an old cache. 30s/2 GiB per read and 60s/4 GiB per cycle. Independent integration tests pass. |
| Failure isolation | Typed unavailable input stops remaining new proposals but keeps one existing monitor/snapshot pass, without fabricated order/fill/rejection/duplicate notice. Paper/live/configured-disabled, later-account, cancellation and real protective-stop regressions pass. |
| Archived evidence | Seven read-only v62 files, 229,677 rows / 95,961,644 bytes, hashes unchanged. Pinned 2026-10-25T10:50:02Z old/new full score equality: 70/degraded, correlation warnings 57. Local 2.785s→1.663s is one observation. |
| Million-event evidence | Reducer 10.407s, 4,455-byte state, maximum one sampled live model; final-source service rerun 7.451s over 431,750,000 bytes, 4,495-byte state / 4,448-byte manifest, exact outputs. Local 149.77 MiB process high-water is neither reader RSS delta nor guest acceptance. |
| Tests / source quality | `uv run pytest -q`: **3,008 passed in 61.62s**, +143 against baseline. Final independent focused suite: **143 passed in 2.49s**. Nine-file Black/Ruff, 132-file mypy and whitespace checks pass. |
| Runtime / data / financial scope | Baseline production v63 / `f0f3e52`; this source slice not deployed at draft time. Original machine/volume/shared CPU1/2048 MiB/paper/Codex remain. No runtime migration, funding charge or policy adjustment. |
| Acceptance still open | Original cold/warm/percentile/native/depleted/concurrency/declared 1 GiB guest targets remain. Existing failed production observations stay recorded. Dashboard checkpoints and deferred performance-CPU/cost are separate. |

The source-to-decision and source-to-monitor paths are the verification boundary:
earlier page-specific progress did not prove that every shared-process allocator
was bounded. Expanded whole-cycle production observation revealed this distinct
path; this check does not infer that its removal solves all resource failures.

See [session and exact evidence inventory](../sessions/2026-10-26-runtime-safety-streaming.md)
and [implementation plan](../../aidlc-docs/construction/plans/runtime-safety-score-streaming-activity-code-generation-plan.md).
The [independent review](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/independent_review_result.json)
records no remaining source defects after correction of the runtime-limit leak
into legacy helpers. Final full-suite evidence includes that correction;
deployment and DEBT-083 acceptance remain separate.
