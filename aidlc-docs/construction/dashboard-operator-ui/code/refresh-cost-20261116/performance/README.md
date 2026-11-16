# Checkpoint reconstruction performance evidence

Production source remains v72 during all probes. `production-baseline.json`
retains the complete direct projection/profile report. The checkpoint profile
completed successfully; `checkpoint-baseline-summary.json` explicitly contains
selected fields transcribed from its tool output, including all eight trial
times and output hashes, rather than claiming a complete raw profile transcript.

`production-comparison.json` retains all twelve alternating baseline/candidate
trials on fixed evaluation time and verified generations. Each trial creates an
isolated disposable checkpoint store under `/tmp`; canonical `/data` and the
application's checkpoint store are unchanged. Candidate methods are compiled only
in the separate probe process. Direct/empty-store/reused-store measurements are
different scenarios, all with warm imports/OS. They are not browser/cold p95.

Activity empty-store median improves3.076233→2.665976s (13.34%,0.410258s).
Snapshot median3.235357→3.195256s is effectively unchanged; no material snapshot
speedup is claimed. All six hashes per kind match. Process high-water229364KiB
includes imports, both implementations and both query kinds; it is not an idle
RSS delta or original1GiB shared-guest qualification.

`differential.json` records242 seeded comparisons against frozen v72 methods:
112 byte matches and130 matching errors across121 cases/two caps, including
shared values, Decimal/time/bytes/sets/dataclasses, nonfinite data and depth limit.
No comparison failed. Unit tests separately verify monotone threshold decisions,
recursive/shared graphs, early stopping and exact default budget exhaustion.

To reproduce helper scripts, run from the repository root, create a new task
scratch directory, and recover the frozen `projections.py` and `checkpoint_store.py`
from source71c8787 into the documented `*_baseline.py` scratch paths. Do not rerun
against or overwrite sealed outputs. The helper's two baseline source hashes
must match the running image before an in-memory production comparison is valid.
