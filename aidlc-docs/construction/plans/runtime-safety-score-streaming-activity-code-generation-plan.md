# Runtime safety: bounded streaming implementation

- Unit/stage: `runtime-safety-score` / Code Generation and Build & Test.
- Queue: DEBT-083 Critical; implement the runtime slice before dashboard checkpoints.
- Requirements: FR-014/015/042, NFR-007, original BDL-NFR-01..08; US-020.
- Baseline: main `4b714fd`, runtime source `f0f3e52`, Fly v63; 2,865 passing tests.
- Authority: after the concrete review was linked and runtime-first work was
  recommended, the user said `진행시켜` on 2026-10-26 KST. This approves the
  presented runtime NFR design and failure-isolation amendment for implementation.
  Prior same-capacity rollout intent persists after verification. CPU/cost,
  credentials, account policies and unrelated dashboard activation are unchanged.
- Designs: `runtime-safety-score/nfr-design/streaming-activity-inputs/` and
  `functional-design/streaming-activity-inputs/failure-isolation-amendment.md`.

## Contract

Keep fixed-UTC safety math, bands, thresholds, legacy parser/retention and
None-versus-explicit-extra cache semantics. One process-owned daemon worker,
one active/zero queued jobs, bounded rows/manifests/state/extras and per-read/
cycle time and byte budgets; late/cancelled/stale results cannot be published.
Typed input failure stops the account's remaining proposals while preserving
one normal monitor/snapshot pass. No canonical history mutation or market call
is introduced by the reader. Dashboard strict readers and chronological APIs
remain compatible. The optional negative metadata cache may be omitted unless
its complete-generation/readability/default-time proof can be maintained.

## Work and verification

- [x] Record current operator approval and the bounded runtime-first scope.
- [x] Refactor safety aggregation for one-shot inputs with independent old-code
      fixed-time oracle, scalar/distinct-key semantics and bounded lifetime tests.
- [x] Implement bounded runtime legacy forward source, source-version/membership
      verification and deterministic closure without changing dashboard policy.
- [x] Implement shared worker, admission, budgets, timeout/quarantine/cancellation,
      sanitized failures and bounded shutdown; verify limits and mutations.
- [x] Integrate both engine score sites, cycle budgets/cache and failure isolation;
      test paper/live policy variants, no extra execution and continued monitoring.
- [x] Run targeted reader/safety/engine/main/notification/dashboard tests, full
      pytest, changed-file Black/Ruff and mypy; independently review risk semantics.
- [x] Qualify incident and >=1M inputs for exact parity and reader memory/time;
      retain misses/failures, distinguish local checks from original guest targets.
- [x] Update session/cross-check/debt/state. Keep DEBT-083 active until its full
      dashboard/native/concurrency/guest acceptance is actually satisfied.
- [ ] Commit/push the bounded implementation and perform authorized same-capacity
      exact-dependency rollout only after source verification; capture hashes,
      health, complete engine cycle and observed coverage limits.

## Delegation

Senior implementation lanes own the pure reducer and bounded source/service
separately. The lead owns engine integration/tests/docs and final verification.
Independent quant/QA reviews must inspect actual paths and an old-code oracle.
Preserve unrelated `.claude` settings/lock and all runtime/operator data.

## Source verification checkpoint

Local independent checks pass 184 fixed-time cases, 12 legacy source cases,
read-only archived 229,677-row parity and a 1,000,000-row / 431,750,000-byte source.
The archived fixture is the 2026-10-25 v62 snapshot, not the original incident
inventory or current production. Evidence is under
`runtime-safety-score/code/streaming-qualification-20261026/`.
Final independent reader/reducer/integration suite passes 143 tests after the
legacy-helper compatibility correction. Strict bounds stay in the runtime
accumulator; exported helpers preserve their prior uncapped/hashable-key behavior.
Nine changed files pass Black/Ruff and 132 source files pass mypy. Final
`uv run pytest -q`: **3,008 passed in 61.62s**, including the compatibility
correction (+143 against the baseline). Source review has no remaining defect;
same-capacity exact-dependency rollout remains pending.
The final-source million-row service rerun takes 7.451s with 4,495-byte state and
4,448-byte manifest; local process high-water is 149.77 MiB, not reader RSS growth.
No local result certifies
native browser, depleted CPU, dashboard readiness or declared 1 GiB guest acceptance.

## Approval record

Question: proceed with the concrete runtime NFR and failure-isolation amendment?
[Answer]: user `진행시켜`, following the runtime-first recommendation and linked
concrete review. No repeat approval is needed for this bounded implementation.
