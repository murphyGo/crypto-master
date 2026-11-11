# Dashboard initial snapshot read cost — 2026-11-11

Unit dashboard-operator-ui, related persistence-data-integrity and operator-command-center.
DEBT-083 remains Critical. FR-028–032/036/038/042; NFR-003/007/008/011/012;
BDL-NFR-02–08; US-012/014/020/023; legacy 7/8.2/19.3.
The user's “진행시켜” continues the initial-latency work and established same-capacity
commit/push/deployment workflow. No capacity, cost, trading, credential or data change.

## Measured bottleneck and implementation

A standalone read-only process on v71 measures an initial snapshot projection over
13 files, 37,038,485 bytes and 98,830 rows at 3.854591 s wall/3.825856 s CPU.
A separate cProfile trial attributes 8.484 of 11.364 instrumented seconds to
json_array_bytes, including 4,330,745 regex searches. Profile overhead is separate
from latency. Activity costs 4.771 s wall/2.663 s CPU and is unchanged in this slice.

`src/utils/bounded_read.py` now recognizes an entire unescaped JSON string as one
C regex token. Escaped/block-split strings retain explicit state tracking. A span
in the fixed-size input block replaces repeated bytearray copying for each token;
one-block objects need one slice, while crossing objects retain the bounded pending
buffer. Record limits are checked before copying. No nested regex repetition or
unbounded search buffer is introduced.

Full JSON and Pydantic validation still applies to every historical row. Exact raw
record bytes, separators/trailing content, 64 KiB cooperative block checkpoints,
1 MiB default record cap, close/file release and source-generation checks remain.
Latest/tie/equity calculations, error categories, caches, schemas and recovery are
unchanged. The all-source compatibility digest changes naturally on deployment.

## Comparative evidence

Production comparison loads the candidate **only into a separate probe process's
memory**; deployed source and running applications stay v71 during that experiment.
Order is baseline/candidate/candidate/baseline/baseline/candidate, with one fixed
evaluation time, no checkpoints or previous-result reuse. All six trials have the
same generation digest, verified coverage and identical 227,965-byte output hash.

| Direct snapshot projection | Wall seconds, all trials | Median |
|---|---|---|
| Baseline | 3.786125, 3.892276, 3.782769 | 3.786125 |
| Candidate | 2.411901, 2.493991, 2.411751 | 2.411901 |

Median improvement is about 36.3% (1.374 s). These are warm-import/OS-cache initial
projection trials, not browser, process-cold or 20-sample p95 qualification.
Probe process high-water RSS is 124,440 KiB including both implementations/imports;
it does not prove the original shared-guest/idle-delta memory gate.

The local fixed fixture has 98,800 varied snapshots in 13 files/30,912,648 bytes.
Two opposite-order process runs per implementation preserve identical 90,696-byte
output across all 12 trials. All timings and process high-water values are retained,
including slower reverse-order baseline trials and the candidate's first-trial
outlier. The harness uses built-in resource accounting after an initial optional
psutil import failed; no dependency was added. Results are local evidence only.

## Validation and review

- 9,000 seeded differential comparisons against baseline21142a7 cover valid and
  damaged data, six block sizes, record budgets, raw/object readers, exact yielded
  records/checkpoints and stable failure reasons; all match.
- 34 new tests cover nested/Unicode/escaped strings, exact limits and long records,
  malformed UTF-8/control/escape/nesting, and append/truncate/replace after a yield.
- 602 targeted dashboard/parser/portfolio/rotator tests pass.
- **3,161 full tests pass**, five existing JUnit warnings, 55.16 s. The approved
  unsandboxed environment supports existing CLI process-cleanup tests.
- Changed-file Black/Ruff, mypy across 136 source files and diff checks pass.

Implementing-agent review used the code-review skill; it is not independent review.
Reviewed malformed-string fallback, split escapes/UTF-8, source changes, bounded
pending spans, yield/close ordering and exact output parity. No blocking finding.

## Delivery and remaining gates

Source commit, same-capacity v71 overlay and operational verification are pending.
Only `src/utils/bounded_read.py` is a runtime change. Existing exchange containment
stays in the base image; all 183 runtime paths must match the source after deployment.
The new construction plan is `dashboard-initial-read-cost-plan.md`.

DEBT-083 cannot close from this optimization alone. Retain prior failed samples,
5 s cold/2 s warm complete-readiness targets, 20-sample native/cold/depleted cases,
original 1 GiB memory gates and the deferred CPU-cost decision. Browser access-host
discovery currently fails, but native Chrome app control is available to attempt
visual confirmation. Protocol and native evidence must be reported separately.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/initial-read-cost-20261111/`.
