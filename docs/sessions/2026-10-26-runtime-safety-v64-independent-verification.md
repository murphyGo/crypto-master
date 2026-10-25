# Runtime safety: concurrent implementation reconciliation and v64 verification

## Delivery decision

The user approved runtime-first continuation with `진행시켜`, retaining the
earlier per-item commit/push and operational verification intent. While this
session implemented and independently tested the runtime slice from `4b714fd`,
another authorized worktree pushed `dca38fbf25a9b96ec91400b628bc71513cf3357d`
and deployed Fly v64. That change already contains the runtime stream, failure
isolation and separately approved dashboard checkpoints.

Keep that deployed implementation. The independent candidate is preserved as
`8053ae0c916cc4e71a3ff2f0d25f83b5dd4dc2d8` on
`codex/runtime-safety-review-20261026`; it is **not merged or deployed**. Local
main was fast-forwarded to `dca38fb` without modifying unrelated `.claude`
settings/lock. This follow-up changes documentation only and performs no new
deployment, canonical-data mutation, exchange action or production engine cycle.

The candidate's 3,008 tests and million-row 7.451s measurement qualify that
separate tree only. They must not be presented as v64 results. A later comparison
also found that its broad JSON `ValueError` catch skips oversized integer rows
which the old implementation rejected. This supersedes the candidate's earlier
parity review for that edge. Do not blindly merge the alternative reader.

## Independent verification of the adopted source

- `uv run pytest -q tests/test_runtime_safety_reader.py tests/test_runtime_safety_score.py tests/test_runtime_engine.py tests/test_dashboard_segment_checkpoints.py`:
  **306 passed in 6.19s**.
- `uv run pytest -q`: **2,916 passed in 59.36s** on `dca38fb`.
- Black and Ruff pass for the eleven Python files changed by that commit;
  `uv run mypy src` passes **134 source files**.
- Independent frozen-old-helper comparison: **184 cases pass**. Both pre-order
  calls await the bounded reader; typed failures stop remaining proposals while
  normal monitoring/snapshot continues. Exact scalar/recency scoring and the
  fundamental state, key, time and byte limits are present.
- The 5,000-digit integer reproduction preserves the old hard failure as a typed
  `input_unavailable`, rather than accepting an incomplete healthy score.
  No verified high-impact defect requires a source port or duplicate deployment.

## Direct production evidence

Read-only capture at **2026-10-25T17:41:02Z** (October 26 KST):

- Fly **v64**, source **dca38fb**, image digest
  `a0e1bd753ba92935c7227bb7c1c5f52fa267eebe2784d1ece99c0a1fab070786`.
- **180/180** deployed runtime/configuration/strategy input hashes match that
  Git source. Public/internal health both return **200 / ok**.
- Existing machine `6835752b711958`, volume `vol_4m3l58dkk29y19zv`, shared CPU 1 /
  2048 MiB, paper/Codex `gpt-6-astra`, cadence and dependency versions remain.
- First cycle `4e40fc4d-6ad3-47e4-bc6a-0bf307cc51f9` completes from
  **17:39:25.480138Z to 17:39:40.574350Z**, with **12 monitor passes and zero errors**.
  It generates no proposal: this is continuity evidence, not natural execution
  coverage of a safety-read/pause decision.
- Deployed read-only replay preserves prior DEBT-087/088/089 behavior: 18
  account/version score checks match, seven open-cap rows remain monitorable,
  funding is explicitly unknown, and 24 persisted-input hashes remain unchanged.
  These replay checks are separate from naturally emitted trading events.

Exact hashes, versions, cycle boundaries and review details are in
[`v64-independent-check-20261026`](../../aidlc-docs/construction/runtime-safety-score/code/v64-independent-check-20261026/).

## Why prerequisite defects kept appearing

Earlier checks covered page-level consumers and reported metrics. Expanded
whole-cycle/shared-VM observation exposed a separate engine full-history
allocator. Tracing the real failure path then exposed the broad account guard
that skipped protective monitoring. Tests of isolated helpers did not prove
those downstream paths. This time the source-to-score and source-to-monitor
paths, unchanged legacy edge behavior, deployed source identity and actual
monitor cycle are checked explicitly.

The concurrent implementation was a coordination collision, not another
strategy defect. Before future work, reconcile active worktree/unit ownership
and current remote state; repeat that check before push and deployment. Preserve
failed observations and qualify the exact selected source instead of merging
two independently tested implementations by assumption.

DEBT-083 remains Critical/active. Runtime containment is delivered; original
cold/warm page percentiles, native browser, four-session/full-cycle,
depleted-CPU and declared 1 GiB / 768 MiB guest acceptance remain separate.
The current 2 GiB deployment and this first-cycle check do not close them. The
parallel dashboard operational qualification must retain its own observations.
