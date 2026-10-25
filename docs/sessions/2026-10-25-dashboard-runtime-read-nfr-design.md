# Dashboard / runtime read NFR design checkpoint

## Outcome and authority

Operator `나머지도 계속 진행해줘` approves the previously presented base
runtime streaming/request-time and dashboard checkpoint Functional Designs for
continuation. Their existing NFR requirements are formalized without a new
acceptance threshold. Two concrete NFR candidates and a newly discovered
Functional failure-isolation amendment are prepared; explicit approval is still
required before application code or activation. See the [combined review](../../aidlc-docs/construction/plans/dashboard-runtime-read-followup-nfr-review.md).

## Findings and selected candidates

- `src/runtime/engine.py` safety inputs materialize full history; both explicit-extra
  call sites bypass the `None` cache. The score feeds an actual configured pause
  gate. Approved request-time anchoring can conservatively retain a 24h-edge event.
- `run_cycle` wraps scan/proposals/monitor/snapshot in one account guard. A safety
  read exception skips that account's monitoring. The new proposed typed-failure
  adapter stops remaining entries, records a sanitized existing error, then runs
  existing monitor/snapshot once. This can restore normal protective closes;
  no score weight, live intent or SL/TP condition is changed.
- Runtime candidate: one lazy daemon worker, one active/zero queued; 16 MiB active
  state +4 MiB source manifest +2 MiB optional validation summary; 30s/2 GiB per
  read and 60s/4 GiB per cycle. Quarantine never creates a replacement worker;
  late results cannot admit orders. Legacy parsing and fixed-time formulas stay.
- Dashboard candidate: globally 64 MiB disposable cache on the existing volume,
  max64 physical files/50k logical keys/two roots. Private bounded packs, typed
  lossless codec, integrity/source proof, nonblocking lock and atomic publication.
  Existing RAM/worker/freshness caps remain. Cache failure uses bounded canonical
  reads. No canonical writer lock, append shortcut or runtime disk-score cache.
- First checkpoint kinds are activity, unique per-account snapshots and proposals.
  Ledger uses the canonical sequential float calculation. Non-associative curves,
  missing dynamic defaults, nonfinite or unprovable states are cache misses.
- Read-only `/data` preflight: 731580 KiB available (~714.434 MiB). This is a
  snapshot, not reservation. Proposed write admission needs192 MiB free and
  preserves128 MiB reserve. No namespace was created or volume resized.

## Verification boundary

Reviewed actual engine call/guard paths, rotator universal-line/UTF-8/malformed
policies, cache bypass semantics, non-associative reductions, whole-cycle
companion joins, dynamic defaults and current shared-volume free space.
Documentation validation checks relative artifact links, JSON, stage status,
unchanged application inputs and whitespace. No source/test change occurs;
pytest/Black/Ruff/mypy are not rerun for this documentation-only checkpoint.
Historical 2823-test/source/hash evidence belongs to v62, not these unimplemented
candidates. Original cold/warm/guest/native/depleted acceptance remains unpassed.

Supported Browser bootstrap was retried and failed because its packaged service
module is missing. No browser fallback or private repair was used; native
acceptance remains open. Read-only evidence is
`aidlc-docs/construction/dashboard-operator-ui/nfr-design/verified-segment-checkpoints/evidence/read-only-preflight.json`.

## Repository and operations

Isolated branch starts from main070fa96. Root contains concurrent unrelated
strategy/proposal source, tests and overlapping documentation edits. Preserve all
of them; do not stash, reset, overwrite or fast-forward that dirty checkout.
Seal only this isolated documentation slice and verify the exact remote commit.
Fly v62/source d86f76f, shared CPU1/2048 MiB, original volume and paper/Codex remain.
No deployment occurs here. Performance CPU / additional cost remains deferred.
DEBT-083 remains Critical/active; no debt count, original target or acceptance is
waived. After explicit combined approval, runtime implementation/tests come
first, then checkpoint implementation and previously authorized same-capacity
rollout; new infrastructure/cost changes require their own applicable review.

## Final documentation checks

Scoped check passed:23 changed/new documents,9 relative links, valid evidence JSON,
whitespace clean and all application/runtime input paths unchanged from070fa96.
Public health returned `ok` during closeout. Approval request was presented for
both NFR candidates and the explicit monitoring amendment; no response is inferred.
