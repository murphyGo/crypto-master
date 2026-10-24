# Business Rules: Verified Segment Checkpoints

1. Canonical activity/proposal/trade/snapshot files and retention remain the source
   of truth. Checkpoint writes are confined to their new derived namespace;
   no canonical file is migrated, rewritten, deleted or supplemented with guessed
   trade facts. No exchange or live-trading action is added.
2. A checkpoint is disposable acceleration. Its integrity, reducer/model version,
   source generation and query contract must match before use. It does not certify
   that current source files are unchanged merely because it was once complete.
3. Discover and verify every selected source, including directory membership.
   Modified files require full validation; size growth alone never authorizes an
   append cursor. Replacing/truncating a source, rollover and retention changes
   invalidate or exclude affected checkpoints.
4. Preserve all original metric periods and account/mode/source isolation.
   Exact totals cannot come from sampled detail rows or a recent-only source tail.
5. Cross-file cycles preserve first/start/terminal UTC and tie behavior. Store
   source-relative record offsets so a new file or rollover cannot silently reuse
   obsolete global ordinal ranks. Rebase ranks against current membership.
6. Apply rejection/companion dedup globally once, before presenting rejection
   counts. If exact cross-file membership cannot fit or be recovered, perform
   the existing bounded canonical pass or report incomplete coverage.
7. Safety inputs and inclusive window boundaries are re-evaluated using the
   current evaluation time. Missing expiry state requires a rebuild. Prior
   checkpoint evaluation times are not replaced with fabricated freshness.
8. Group/key/state/result limits remain process-wide across live work and reused
   states. Persistent storage does not authorize an unbounded in-memory decode.
   Capacity misses may use the existing reader; no approximate total substitutes
   for an exact one and no budget exception is hidden.
9. A partial/failed source prevents a dependent complete or healthy claim.
   Verified ledger/snapshot siblings remain usable. Stale views keep their label.
10. Checkpoint corruption, permission denial, full disk, interrupted publication
    and schema upgrades are recoverable misses, never operator-data repairs.
    Cleanup may remove only owned derived files within its quota.
11. Preserve paper/Codex defaults and explicit live intent. Do not introduce a
    new external endpoint, credential, notification or paid infrastructure.
12. Native viewport, complete-page latency and shared-guest/four-session resource
    acceptance remain required; a durable cache hit is not proof of uncached cold
    readiness. The earlier five-second stress failure remains recorded.
