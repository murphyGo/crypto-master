# v64 dashboard qualification cross-check — 2026-10-26 KST

Unit: `dashboard-operator-ui`; requirements BDL-NFR-01..08, with the unchanged
FR/NFR/story mapping in the continuation construction plan. Application source
is `dca38fb` on Fly v64. This is an acceptance-status audit, not a new source or
deployment gate.

| Requirement / scenario | Evidence and disposition |
|---|---|
| BDL-NFR-01: bounded default paths | Source/test evidence retained from adopted v64 gate; no code changes in this cycle. |
| BDL-NFR-02: memory envelope | Current 2048 MiB production run is a measured subset; declared 1024 MiB, incident/million and one/four-session matrix remains unqualified. |
| BDL-NFR-03: complete readiness | Canonical no-store million query p95 7.817 s exceeds 5 s. Seeded 0.695 s does not certify cold page/bootstrap. Per-page cold/warm scenario matrix and native rendering remain open. |
| BDL-NFR-04: four sessions + full engine cycle | Failed complete readiness: 347/349 complete, two Home incomplete during the natural 20.267 s cycle. Health 347/347; guest 708.25 MiB and dashboard growth 83.902 MiB pass observed numeric limits on 2048 MiB. Original guest/native conditions remain unqualified. |
| BDL-NFR-05: scale | Existing representative local incident/million evidence remains; new million profile is CPU diagnosis only, not the complete resource scenario set. |
| BDL-NFR-06: global limits | Existing capacity/admission/state/fallback tests retained; no cap relaxation or codec changes here. |
| BDL-NFR-07: meaning | Existing complete-fixture parity retained. New no-store/fresh-store full payloads match; exact labels/placeholders are separate from a table-cell/native oracle. |
| BDL-NFR-08: failures | Existing reader/mutation/fault coverage retained; no raw record or canonical validation is skipped. |
| CPU depletion | Later separately frozen full-window 15 s samples show positive balance and zero throttle. Depleted qualification remains unqualified; CPU exhaustion is not observed and the failure cause remains unproven. |
| Native Browser | Blocked before navigation by missing packaged service. Operator recovery pending; application rendering not assessed by that failure. |

## Independent reviews

QA freezes sixteen raw/context artifacts and reconciles all 349 request starts
with their outcomes, with no duplicate/orphan records or summary differences.
Home completes 172/174; Trading 175/175. Successful-response p95 is
0.761/0.724 s, but the two 12.094/11.335 s Home incomplete responses prevent a
pass. Their first-shell time and alert reason text were not retained. A complete
natural engine cycle and stable PIDs are observed; CPU snapshots only through
17:48:21 UTC do not explain the later failures. The result is reproduced from
the immutable local freeze.

The later CPU supplement covers the full run and leaves the failed concurrency
result unchanged. A post-run operational check verifies all 180 source hashes,
the same v64 instance/configuration, 200/ok public/internal health and the
cycle's twelve monitor events with no errors. No fresh proposal/safety decision
occurred; the prior strategy fixes retain their separate pure replay coverage.

The implementation specialist profiled exact source with frozen source/fixture
hashes. Quant review independently checked all nine copied artifact hashes and
thirteen source hashes. Both corrected profile variants produce the same full
payload. The fresh store was initially absent and reported zero hits.

The reliable profile uses one single-thread instrumented run per variant after
equal lazy-import warm-up and hash reads that warm the OS cache. Do not present
10.538/14.665 s as cold-page p95. Original threaded attribution is rejected and
retained. Codec-node sizing 1.636 s is nested in encoding 2.124 s and total sizing
3.190 s; adding them would double count. A threshold predicate would affect new
checkpoint encoding, not the canonical `store=None` path. Any future candidate
must preserve strict `>32 KiB`, identity/alias handling, codec bytes/schema,
full admission accounting and all depth/row/budget/fallback semantics.

DEBT-083 remains **Critical / active**. Historical failures and gates stay
visible. Native/depleted/original-guest acceptance and the cold target are not
waived. No new strategy action item is registered for these existing debt gates.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/qualification-continuation-20261026/`.
Session: `docs/sessions/2026-10-26-dashboard-v64-qualification-continuation.md`.
