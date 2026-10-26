# DEBT-083: measured dashboard CPU cost correction

- Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
- Queue: Critical DEBT-083, v66 failed operational observation.
- Baseline: main `2eae9cf`, runtime `ce5c4f5`, Fly v66.
- Task: profile the existing read/render paths, reproduce one avoidable CPU
  cost and correct it while preserving all source-proof and operator semantics.
- Stage: diagnosis, existing NFR design refinement, Code Generation, Build/Test,
  then same-configuration deployment and operational verification.
- Requirements: BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
  NFR-003/007/008/011/012. Stories: US-012/014/020/023.
- Authorization: user asks to fix the remaining problem; earlier individual
  commit/push and deployment/operational verification instructions persist.
- Isolation: `/private/tmp/crypto-master-cpu-cost-20261027`; preserve root
  `.claude` changes and all canonical runtime data.

## Constraints and interpretation

[Answer]: Keep one shared CPU/2048 MiB, original volume/dependencies/config,
engine cadence and trading behavior. No capacity/cost/credential change.
[Answer]: Keep one reader/four admitted jobs, bounded memory, 4 s foreground,
2 s complete freshness, 30 s explicit stale, full generation validation and
manual terminal retry. No success criterion relaxation or hidden failures.
[Answer]: The v66 health guard and four aborted outcomes remain FAIL_SAMPLE.
Positive CPU throttle overlaps failure, but existing counters do not identify
the responsible function or prove that the watcher correction caused it.
Profile/replay locally first; any production collection must be bounded,
read-only and nonoverlapping, without synthetic engine cycles.
[Answer]: Existing cold/native/depleted/original 1024 MiB gates remain open
unless separately qualified. This is one evidence-led correction cycle.

## Ownership and sequence

- [x] Lead: verify source/remote/runtime, context and preserve prior failures.
- [x] Developer: profile baseline dashboard source/read/render work locally;
  report reproducible hotspot and narrow optimization design before editing.
- [x] QA: independently inspect workload, generation/freshness compatibility
  and safe bounds; separate benchmark claims from production acceptance.
- [x] Lead: choose one supported correction; record design and exact files.
- [x] Developer: implement with regression/parity/bounds checks.
- [x] QA/lead: targeted tests, full suite, formatting, typing and unchanged-input
  before/after CPU/output comparison.
- [ ] Lead: commit/push exact correction; deploy same config and verify source,
  health, natural engine cycle and one bounded concurrent observation.
- [ ] Docs: session/cross-check/state/debt map and final evidence, with all
  failures retained; separate operational commit/push and remote confirmation.

Likely source scope: dashboard projections, discovery/read services or rendering,
selected only after measurement. Engine paths are inspected read-only for
contention context. Trading-domain edits require a separate domain review.

## Selected correction and existing NFR applicability

The frozen Fly snapshot has 13,084 proposal files. Five instrumented unchanged
proposal refreshes take 2.135 s; 1.215 s is the optional checkpoint average-file
size sum, which reconstructs 65,420 `Source`/`Path` objects before unchanged
payload reuse and even without a checkpoint store. Other unchanged query kinds
cost much less. These are local CPU profiles, not production attribution.

Move only this optional checkpoint-admission heuristic after unchanged-digest
reuse, and evaluate it only when checkpoint use was prepared. Source scope is
`src/dashboard/projections.py` and relevant regression tests. Discovery, digest,
full file/directory verification, time-window refresh and result/state budgets
remain on every required path. Changed-source checkpoint selection and its
16 KiB average threshold remain identical. No source-proof shortcut, new cache,
component, interface, deployment setting or trading interpretation is added.

This implements the already-approved NFR performance design rather than opening
a new design approval: resilience/terminal retry unchanged; scalability retains
existing limits; performance targets unchanged; security exposes no new data;
logical components and infrastructure unchanged. A single bounded worker still
owns the projection. Compare canonical payloads and changed-source behavior,
then measure unprofiled CPU separately from cProfile before deployment.

Final source gate: 3,021 tests pass in 228.36 s on Python 3.13.0; all 262
source/test/script hashes remain unchanged. Independent QA passes 175 targeted
tests, Black/Ruff two files and mypy all 135 sources. Twenty alternating local
pairs retain identical payloads and frozen inputs. Median CPU falls 34.38/35.16%
for direct disabled/enabled checkpoint refresh and 30.20/29.70% for controlled
Home/Trading query-service replays. These are not full-page/native or production
latency measurements; independent arithmetic/method review is GREEN. Retain the
initial incorrectly labelled store measurement with its correction supplement.
