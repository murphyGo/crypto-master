# NFR Requirements: Bounded Dashboard Data Loading

**Status:** Formalization of the operator-approved functional targets;
implementation and measured acceptance pending. DEBT-083 remains active.

## Requirement Baseline

The operator approved the presented Functional Design and its BDL-NFR targets
with `진행시켜`, authorizing NFR Requirements/Design continuation. Numbers
below carry that baseline forward. New reader/cache constants are a proposed
NFR Design and are not evidence that these requirements are achieved.

| ID | Requirement | Required evidence |
|----|-------------|-------------------|
| BDL-NFR-01 | Home, Trading, Engine, Ops and standalone Funnel must not materialize every retained activity event. Remove full-history calls from their default paths and bound Home's proposal-only funnel loader. Limits apply before raw/model accumulation. | Default-path tests prohibit `ActivityLog.read_all()`, `tail()`/`filter()` wrappers around it, full rich proposal enumeration and full snapshot arrays where bounded projections are required. |
| BDL-NFR-02 | Dashboard peak RSS increase <=256 MiB over warmed idle; shared VM use <=768 MiB on a declared 1024 MiB allocation. | Process peak RSS and guest memory sampling under incident-scale, >=1M-event and one/four-session scenarios. |
| BDL-NFR-03 | Complete default Home/Trading data readiness p95 <=5s cold and <=2s warm. If a budget prevents completeness, show a clearly incomplete shell within 5s. | At least 20 cold and 20 warm observations per page/scenario; incomplete runs are reported and cannot count as successful complete-data measurements. |
| BDL-NFR-04 | Four concurrent sessions alternating Home/Trading for 10 minutes preserve the memory targets, health response <5s, and engine continuity without dashboard-attributable errors. | Health, process/VM memory, page completion, worker counts and complete engine-cycle evidence. |
| BDL-NFR-05 | At 214,686 incident-scale and >=1,000,000 activity events, resident payload size is bounded rather than proportional to all retained events. | Isolated representative fixtures, resource profiles and negative controls; production files are not fixture storage. |
| BDL-NFR-06 | Cap process-wide cached bytes/entries, retained record/detail bytes, reducer/dedup state, source metadata, queued work and simultaneous rebuilds. | NFR Design specifies constants/accounting and exhaustion behavior; adversarial capacity and scope-churn tests verify them. |
| BDL-NFR-07 | Complete results preserve existing metric periods, UTC/tie selection, cycle/rejection and safety deduplication, reconciliation severity, account inclusion and consumer-specific equity, including Home's latest-per-account aggregate. | Complete-fixture parity with current pure builders and verified IO contracts. |
| BDL-NFR-08 | Partial writes, corrupt/oversized rows, replacement/truncation, rollover, restart and work-budget exhaustion carry explicit coverage/freshness and never imply healthy/empty data. | Reader state-transition, AppTest and cold-start tests; independently valid ledger positions remain visible. |

## Measurement Definitions

- **VM use:** `(MemTotal - MemAvailable) / 2**20` MiB at the guest level,
  sampled alongside actual `MemTotal`. Do not sum process RSS and guest use,
  or count all reclaimable page cache as irrecoverably used memory. The
  incident guest reported about 962 MiB usable memory despite 1024 MiB
  configured; the <=768 MiB guest-use ceiling remains unchanged.
- **Dashboard increase:** peak process RSS minus the warmed, idle dashboard
  baseline. Include the new cache, readers, reducer state, DataFrames and
  serialization. Record process/container peaks; use high-water evidence and
  frequent sampling so a transient peak is not missed.
- **Readiness:** from a page rerun/navigation request to complete required
  data plus `script_finished`, confirmed by meaningful displayed values and
  coverage. A health GET, HTML shell or page title alone does not count.
  Required Home data includes latest cycle, safety/incidents, exposure/equity
  and default 24h funnel; Trading includes reconciliation, ledger/snapshot
  summaries, threshold count, history and equity presentation.
- **Cold scenarios:** report a new query/cache generation and a restarted
  process separately. Process-cold timings include import/bootstrap work;
  do not present a warm process/cache as process-cold. Both must pass the
  applicable complete-readiness target before asserting full acceptance.
- **p95:** nearest-rank `ceil(0.95 * n)` over recorded successful complete
  observations. Retain every timeout/partial/failure and its completion ratio;
  a set with failures does not pass by excluding them from its p95.
- **Health and continuity:** require all sampled responses <5s. A 10-minute
  run alone is not engine-cycle evidence at the existing 1800s cycle interval:
  arrange the run across an isolated cycle boundary or extend observation to
  capture a full cycle, without changing production timing to manufacture a pass.

## Scope and Data Meaning

Existing Home safety/incident extraction uses the 24-hour cutoff; Funnel uses
inclusive 24h/7d/30d/lifetime windows against `decision_at`, falling back to
`proposal.created_at`. Preserve each helper's actual boundary behavior rather
than imposing one universal window rule. Lifetime means the same eligible
store/retention as today; archived proposals remain excluded where the
current reader excludes them.

Latest reconciliation/cycle state is independent of the incident window.
Cycle start and terminal selection, equal-timestamp stability, global versus
account events, companion rejection suppression and kill-switch deduplication
must be reproduced exactly on complete data. Financial win-rate, recommendation
window and legacy funnel-classification repairs in DEBT-084/085/086 are
separate tasks; this repair does not change their business definitions.

Recent-row caps and chart sampling must not change exact aggregate periods.
Insufficient coverage is an unavailable value, not a numeric zero. A proven
empty source and an unreadable/incomplete source are different states. Cache
age, source time and read coverage remain distinct.

## Availability, Recovery and Security

Readers are isolated from the engine's hot path. The UI does not mutate
runtime data, create missing runtime directories, shorten retention, repair
trades or invoke exchange/Claude actions. Cache/reducer state can be discarded
and rebuilt after restart; no durable derived database is selected in this
design. Qualification must not claim that a fast partial fallback meets full
cold readiness; failure keeps acceptance and DEBT-083 open.

Runtime diagnostics allow query kind/page, stable reason codes, aggregate
counts/bytes/timing and coverage status. Exclude credentials, URLs, resolved
paths, raw payloads, exception text and account/trade/proposal identifiers from
metric labels/log summaries. Existing detail views can show their authorized
persisted records within bounded query coverage.

Deployment, VM resizing/restart and production qualification are separate
operator actions. Earlier incident facts remain a historical snapshot; this
NFR documentation does not recheck or claim current production health.
