# Incident Evidence: Dashboard Memory Exhaustion

**Date:** 2026-10-09

**Debt:** DEBT-083

**Evidence scope:** Earlier read-only diagnosis in this conversation; no new
production page load or recovery is performed during documentation.

## Operational Snapshot

| Item | Observed value |
|------|----------------|
| Application / region | `crypto-master` / `nrt` |
| Machine / release | `6835752b711958` / v51 |
| Instance | `01M4G0GET0VZFE9XNM63BMVZ6X` |
| Configured resources | 1 shared CPU, 1024 MiB memory, no guest swap |
| Runtime | Python 3.13; deployed Streamlit 1.65.0; local Streamlit 1.57.0 |
| Local source baseline | HEAD `16eef0d`; unrelated local Claude/Node remediation was being edited concurrently |
| Trading source SHA-256 | `dbd2b1b485b31041b4a4afda4a362818d9ef8df9797c91b7203c0941bcbcdeb4`, identical locally and in the deployed image during diagnosis |
| Volume | 974 MiB filesystem; 178 MiB used, 730 MiB available in the diagnostic snapshot |
| Runtime activity files | April–October 2026; 214,686 counted lines; sampled sizes total 90,064,921 bytes (85.89 MiB) |
| Other stored history sizes | proposals ~49 MiB; portfolio ~29 MiB; trades ~1.1 MiB; performance ~1.3 MiB |

File sizes and line counts were sampled separately while the engine could
append data. They describe the incident workload, not an immutable exported
production snapshot. Do not reuse these values as a current inventory.

| Activity month | Counted lines | Sampled bytes |
|----------------|--------------:|--------------:|
| 2026-04 | 1,989 | 697,885 |
| 2026-05 | 75,690 | 32,565,913 |
| 2026-06 | 46,196 | 20,539,330 |
| 2026-07 | 29,784 | 11,889,501 |
| 2026-08 | 29,760 | 11,683,240 |
| 2026-09 | 28,504 | 11,132,814 |
| 2026-10 | 2,763 | 1,556,238 |

## Observed Sequence and Limits

1. Initial external `/_stcore/health` and `/trading` GET requests returned
   HTTP 200 in about 0.13 seconds. The latter was the Streamlit HTML shell,
   not proof that Trading data rendered.
2. A read-only WebSocket probe connected in 0.33 seconds. At about 5.6
   seconds it received the Home title and controls, then received no further
   page messages for 15 seconds and no `script_finished` before disconnect.
   Its first requested hash used MD5, while the running navigation used a
   different hash. **The captured render was Home, not a confirmed direct
   Trading render.** A later Trading attempt timed out before connection.
3. Earlier process sampling showed engine RSS ~202 MiB and idle dashboard
   RSS ~64 MiB, with guest available memory ~530 MiB. Guest cgroup
   `oom_kill=0` was sampled before the later exhaustion.
4. Fly Prometheus samples subsequently reported available memory falling
   from 506.98 MiB at **09:50:30 UTC / 18:50:30 KST** to **0 at 09:51:00
   UTC / 18:51:00 KST**, remaining zero through the captured interval.
5. External health/static-asset requests, SSH commands, and a 15-second
   management exec subsequently timed out. Fly reported the same instance
   `started` with a `critical` HTTP check; the check's last-update timestamp
   was `2026-10-09T09:50:49.241Z`.

The memory metric confirms exhaustion. The code path and render timing make
full activity materialization the principal triggering hypothesis. No Python
stack or peak per-process RSS was captured during the exhausted state; no
post-exhaustion OOM-kill event was verified. Do not claim a proven kernel kill,
successful direct Trading render, completed engine cycle during the stall, or
exclusive attribution to a Streamlit version change.

## Code Mechanism and Reach

- `src/dashboard/pages/trading.py:472` and `src/dashboard/pages/home.py:265`
  call `ActivityLog.read_all()` during data loading.
- `JsonlRotator.read_all()` builds and sorts a `merged` collection containing
  every retained JSON payload before yielding any record. Its iterator return
  type does not make this operation streaming.
- `ActivityLog.read_all()` then accumulates validated `ActivityEvent` objects
  while the generator retains the merged raw payloads. Both collections can
  coexist; the 86 MiB file size is not the peak Python heap size.
- `ActivityLog.tail(n)` calls `read_all()` and slices afterward. `filter()`
  similarly filters after full materialization.
- Engine, Ops, and the standalone Proposal Funnel page use the same
  full-history activity reader. Home additionally calls
  `proposals.load_funnel_summary("24h")`, which reads full proposal history
  before applying its window; it does not read activity. This was corrected
  during the NFR source recheck without changing the diagnostic metrics.
- Trading's threshold counter calls `ProposalHistory.list_all()`; account
  snapshots are loaded in full and reread for equity curves. These are
  additional growth risks, not independently proven incident triggers.

## Reproducible Evidence

The original Prometheus response was read from
`/private/tmp/crypto-master-ui-metrics.json`. A sanitized subset is preserved in
[metrics-evidence.json](metrics-evidence.json), with metric names, values,
timestamps, query interval, and source digest. Credential values, cookies,
trade payloads, and personal account information are excluded.

Original read-only tools: `flyctl status --json`, `flyctl logs --no-tail
--json`, SSH file/process summaries, bounded `curl` requests, a single active
WebSocket diagnostic session, and the organization Prometheus `query_range`
API. The original temporary probe is diagnostic evidence, not a regression
test or a procedure to repeatedly run against the exhausted production VM.

At the end of diagnosis the server had not recovered. This document records
that snapshot; it does not assert the server's current state or restore it.
