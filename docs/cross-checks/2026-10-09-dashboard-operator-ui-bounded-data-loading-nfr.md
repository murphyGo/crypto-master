# Cross-Check: Dashboard Bounded Loading NFR

- **Date:** 2026-10-09
- **Unit/debt:** `dashboard-operator-ui` / DEBT-083
- **Documentation verdict:** PASS; NFR Design approval pending
- **Stage:** Functional Design/targets approved; NFR Requirements formalized; new NFR Design approval pending
- **Implementation/runtime verdict:** Not assessed; no fix or recovery claim

## Coverage

| Requirement | NFR artifact coverage |
|-------------|-----------------------|
| BDL-NFR-01 / FR-032, NFR-003 | Streaming readers/reducers, all activity pages, bounded proposal-only Home funnel and explicit integration seams. |
| BDL-NFR-02, 05, 06 | Global cache/reducer/manifest/record/worker/admission caps; logical bytes versus measured RSS distinction; representative incident and >=1M-event qualification. |
| BDL-NFR-03, 04 / US-012, US-014 | Full versus partial readiness, cold/process-cold/warm definitions, p95/completion ratio, four-session health/engine evidence including the 1800s interval constraint. |
| BDL-NFR-07 / FR-029, FR-031, FR-036, FR-042; US-020, US-023 | Source rank/UTC ties, cycle/companion/safety rules, exact window/lifetime counts, existing consumer-specific scope/equity/card behavior. |
| BDL-NFR-08 / NFR-007, NFR-008 | Captured source coverage, corruption/oversize/replacement/rollover/restart, stale and unknown state, independently valid ledger data. |
| NFR-011, NFR-012 | Allowlisted telemetry, readonly IO, no new trade/credential/provider/runtime-writer action. |

## Documentation Verification

- [x] Tracked and new-artifact whitespace and Markdown relative links pass.
- [x] BDL-NFR-01..08 and approved 256/768 MiB, cold/warm 5/2s, four-session
      10-minute, >=1M-event targets remain represented without weaker substitutions.
- [x] New numeric budgets agree across plans/artifacts; caps are process-wide
      and logical byte measures are not mislabeled as RSS guarantees.
- [x] Home nested funnel source claim is corrected; pure consumer contracts
      and partial-versus-complete readiness are explicit.
- [x] Functional approval and requested NFR progression are recorded; NFR
      Design implementation budgets and Code Generation approval remain pending.
- [x] DEBT-083/map/state links exist and keep Critical active; current registry
      totals and unrelated debt were not reset to the older two-item snapshot.
- [x] This slice's edits are documentation only; earlier metric evidence is
      preserved and no fresh production query/qualification is claimed.

Validation checked relative links and new-file whitespace, all eight targets
and budget constants, approval/traceability/pending-code state, current source
contracts and the unchanged evidence digest. At this NFR checkpoint, debt
statistics are 7 active (1 Critical, 5 Medium, 1 Low), 75 resolved; totals and
categories agree. This task did not reset other debt or count documentation
as a resolved incident. No application parser, Python suite, performance run,
native page test or production acceptance was executed in this stage.

## Qualification Gaps

The 4s cooperative timeout cannot interrupt a blocked kernel read; the one
worker slot remains occupied without spawning replacements. Encoded-size
limits do not prove peak Python heap/RSS. Cold full readiness at large fixtures
may still fail and must be measured; partial fallbacks are safe failure, not
qualification success. These practical limits are explicit review inputs.

Before closing DEBT-083: approve the concrete NFR Design, implement meaningful
parser/cache/semantic tests, pass declared resource/latency/engine criteria,
and record authorized native/production acceptance. Existing DEBT-082 and
DEBT-084/085/086 retain independent image/metric scopes.
