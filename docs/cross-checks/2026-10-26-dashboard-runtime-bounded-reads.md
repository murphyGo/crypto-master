# Cross-check: Runtime safety streaming / dashboard checkpoints

**Verdict:** Approved implementation/source gate passes; operational and original
acceptance are recorded separately. DEBT-083 stays Critical/active.

| Contract | Evidence |
|---|---|
| Approval | Operator `gogo`, audit and combined NFR/amendment/code sequence. |
| Safety math | Independent old multipass oracle, all42 types and fixed-time edges; score weights/pause thresholds unchanged. |
| Runtime ownership | One process daemon/occupied slot/zero queue, typed failure, quarantined timeout/cancel, bounded state/IO/cycle work and exact source proof. |
| Trading | Both pre-order sites await current inputs. Failed reads create no entry/fill/duplicate notice and preserve monitor/snapshot/later accounts. Real cancellation propagates. |
| Storage | Optional64 MiB global derived namespace, owner/suffix/marker boundary, SHA/typed codec, lock/COW publication, capacity/free floor and unknown-file preservation. |
| Exact outputs | Cache restart and changed-source parity; global companion join, raw unfinalized cycles/ties/windows, whole-account snapshot curves and ledger sequential floats. |
| Optional performance | Framed leaves and per-query lock; small-proposal negative performance excluded through canonical admission, not hidden in p95. |
| Source gate | 2916 full tests, Black/Ruff11 files, mypy134. Three million-input memory pairs and20-pair projection evidence retain source boundaries. |
| Operations | v63 parent image and exact dependency stack; same-capacity overlay and post-rollout hashes/health/cycle required, no extra live/cost authority. |
| Remaining targets | Unseeded million11.143s still fails5s; native unavailable, original1GiB/depleted and final concurrency pending until measured. No debt closure. |

See [session](../sessions/2026-10-26-dashboard-runtime-bounded-reads.md) and
[implementation](../../aidlc-docs/construction/dashboard-operator-ui/code/verified-segment-checkpoints/implementation.md).

## Independent v64 follow-up (2026-10-26 KST)

Adopted `dca38fb` is deployed on v64 with 180 matching runtime hashes,
internal/public health and a complete first 12-account monitor cycle with zero
errors. Independent source recheck: 2,916 tests, Black/Ruff11 and mypy134 pass.
The cycle has zero proposals; it does not prove natural safety-gate execution.
The separately preserved candidate8053ae0 is not merged/deployed and its results
are not v64 evidence. Original performance/native/depleted/guest qualification
remains open. See [independent verification](../sessions/2026-10-26-runtime-safety-v64-independent-verification.md).


## Observation closeout

v64/dca38fb is deployed and current180 hashes match. All2916 source tests pass.
Four-session349 starts/outcomes reconcile:347 complete, two Home incomplete,
Trading175/175, all347 health checks pass;708.25 MiB guest peak is measured on2GiB.
The complete engine cycle is captured. Full-readiness acceptance therefore
**fails**, with native/depleted/declared1GiB still unqualified. No debt closure.
Independent audit/cold-path findings in5fcad54 are preserved. A later deployed
230271-row read-only score probe exactly matches its independent oracle in2.541s
with0.625 MiB added peak RSS; it is outside the concurrent observation. Current
natural paper proposal/order events and source identity are separately verified.
