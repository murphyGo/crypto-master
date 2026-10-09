# Cross-Check: Dashboard Bounded Data Loading Design

- **Date:** 2026-10-09
- **Unit:** `dashboard-operator-ui` with `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`
- **Scope:** Original documentation/traceability PASS; Functional Design subsequently approved
- **Runtime verdict:** Not assessed by this documentation stage; DEBT-083 active

## Traceability

| Requirement/story | Design coverage | Future verification |
|-------------------|-----------------|---------------------|
| FR-029, FR-031; US-012 | Ledger positions, reconciliation protection, latest/account equity, exact historical metric meaning | Trading/Home parity and incomplete-source UI tests |
| FR-032, NFR-003; US-012 | Existing Streamlit navigation; promptly available shell and explicit data coverage | AppTest plus full data-readiness measurements |
| FR-036; US-023 | Mode/account/root cache isolation and latest-per-account aggregate equity | Scope-switch and concurrent-session parity tests |
| FR-042; US-020, US-023 | Existing safety window/thresholds/deduplication; unknown input cannot become SAFE | Recent-window and partial-data safety cases |
| NFR-007, NFR-008 | Original runtime history, UTC/legacy/monthly compatibility, exact cumulative values | JSONL/history parity, rollover, malformed input and resource profiling |
| NFR-011, NFR-012; US-014 | Sanitized evidence and preserved trading/credential controls | Source boundary review and authorized operational qualification |

Canonical links are the requirement index, story map, unit definition, and
construction plan. BDL-NFR-01..08 are task-local proposed acceptance targets,
not new approved canonical requirements.

## Documentation Checks

- [x] `git diff --check`, plus new/untracked artifact whitespace checks.
- [x] New Markdown relative links resolve.
- [x] Sanitized metrics JSON parses and matches the selected original series;
      source digest and memory-drop values verified.
- [x] Monthly line/byte sums match the incident inventory.
- [x] DEBT-083 is active Critical in debt, map, state, and plan; statistics
      retain active DEBT-082 and do not increment resolved count.
- [x] Generated artifacts and required plan links exist; stage approval/code/
      qualification remain pending.
- [x] No UI/source/runtime-data edits were introduced by this documentation slice.

The preserved source response digest is
`579c74fda7d3f02ddf30c38c350049cf56dab428b5854c024be935f3cdfe7c9c`.
Selected-series parity was checked against the original response; the
09:50:30 UTC available-memory sample is 531,603,456 bytes (506.98 MiB),
followed by zero at 09:51:00 UTC. At this documentation checkpoint, debt
statistics are 2 active (1 Critical, 1 Medium), with 75 resolved unchanged.
Planned targeted test paths were checked for existence. No Python suite or
candidate latency/memory qualification was run for this docs-only change.

## Evidence Limits and Outstanding Acceptance

The recorded WebSocket render was Home. Direct Trading readiness, a post-stall
stack trace, and an OOM kill were not captured. The retained metrics prove
guest available memory exhaustion; the full-history loading trigger is the
source/timing-supported hypothesis. Documentation does not prove a fix.

Proposed latency/RSS/concurrency criteria have not been measured for an
implementation. The next stages require bounded reader and cache design,
functional parity, adversarial input cases, exact candidate qualification, and
authorized production acceptance before resolving DEBT-083.

## Approval Follow-Up

The subsequent `진행시켜` approved Functional Design and the presented
BDL-NFR targets and authorized NFR Requirements/Design preparation. The new
NFR cross-check records that progression and the still-pending NFR Design
approval/code/qualification. The original two-active-debt statistic above is
the earlier checkpoint, not the current registry; other debt was added later.
Home's nested funnel helper is proposal-only, corrected during source recheck.
