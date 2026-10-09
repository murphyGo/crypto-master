# Business Rules: Bounded Dashboard Data Loading

**Status:** Operator-approved Functional Design (`진행시켜`, 2026-10-09); DEBT-083.

1. **Preserve source data.** No runtime history deletion, migration, retention
   reduction, or rewrite is part of this design. Preserve legacy unrotated
   JSONL and monthly archive compatibility.
2. **Bound work before allocation.** A row limit applied after `read_all()`,
   `json.load()` plus full model creation, or `list_all()` does not satisfy the
   resource requirement. Budget scan bytes, record bytes, retained payloads,
   cache storage, and rebuild concurrency, not just rendered table rows.
3. **Keep latest state separate from recent history.** A latest red
   reconciliation report or health-check failure can be older than 24 hours.
   A recent-event slice must not erase it or turn it into the no-report state.
4. **Preserve timestamp meaning.** Use current UTC normalization and latest-by-
   timestamp semantics. Append order, file month, and record timestamp are
   not interchangeable; out-of-order/legacy records must be accounted for or
   coverage declared incomplete. Do not silently stop scanning at the first
   old timestamp without a validated ordering contract.
5. **Incomplete is not healthy.** A failed, limited, or truncated query cannot
   yield a fresh SAFE score, zero incidents, zero rejections, or an authoritative
   no-open-positions claim. Preserve red/yellow last-known status with a stale
   label where available; otherwise present unavailable/unknown state.
6. **Genuine empty state remains distinct.** A completely checked empty source
   may use the existing initial empty/no-report presentation. Missing paths,
   read failure, incomplete bootstrap, and budget exhaustion are distinct
   conditions and carry their own source coverage.
7. **Preserve reconciliation protection.** The ledger remains authoritative
   for open trades. The existing nonzero reconciliation open count still
   suppresses a misleading cash-only/no-position message. Failure to obtain
   reconciliation must not suppress successfully loaded ledger positions.
8. **Keep scope explicit.** Cache and query keys include resolved data root,
   mode, account scope, window, query kind, and projection version as relevant.
   Global events and per-account events follow existing inclusion semantics;
   no cached paper/live or account data may leak into another selection.
9. **Preserve aggregates.** Lifetime metrics keep lifetime meaning. A bounded
   sample or partial scan must be labeled partial/unavailable, not substituted
   as the full value. Existing safety deduplication and score thresholds do
   not change. Home aggregate equity sums the latest snapshot of each account.
   Qualify each consumer's current contract; this memory repair does not
   silently convert Trading's current single-latest-snapshot summary into a
   new financial metric. Its consumer-specific behavior is explicit in NFR Design.
10. **Preserve freshness.** Show source timestamps independently of cache
    refresh time. Apply a reviewable invalidation/TTL policy; never serve a
    stale reconciliation/safety result as fresh. Month rollover, append,
    replacement/truncation, and selected-scope changes must be considered.
11. **Bound the whole process.** Four sessions must share a bounded cache and
    rebuild policy. Eviction, expired keys, scope churn, and concurrent misses
    must not accumulate unbounded payload copies or start duplicate scans.
12. **Handle damaged input explicitly.** Complete earlier rows may survive a
    partial final append. Corruption that can hide required state invalidates
    completeness for that query. Diagnostics disclose skipped/oversized rows
    and coverage without logging secrets or arbitrary payloads.
13. **Preserve trading controls.** This UI remediation never fetches live
    prices, changes risk gates/credentials, submits orders, promotes strategies,
    or changes Claude CLI integration.
14. **Prove recovery separately.** Code/tests passing, increasing memory,
    restarting, and a passing health check each have limited meanings. Debt
    closure requires qualified page data, bounded resources, engine continuity,
    and an authorized production acceptance record.
