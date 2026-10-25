# v64 qualification continuation — 2026-10-26 KST

Application source: `dca38fbf25a9b96ec91400b628bc71513cf3357d`, deployed as
Fly v64. The local source checkout is `458ef7924165b54e9ae6791a5a9cb200c29d17d6`
(the additional commit records independent verification only). This cycle
reuses the existing four-session production observation and adds offline
profiling; it does not launch another load or change production capacity.

## Final concurrency audit

The existing 29m07s run is **failed complete-readiness acceptance**:
349 starts/outcomes reconcile, with 347 complete and two Home incomplete.
Home completes 172/174 (successful p95 0.761 s), Trading 175/175 (0.724 s).
The two Home failures take 12.094/11.335 s and expose two incomplete-data
alerts. Successful-only percentiles do not override those failures.

A full natural 20.267 s engine cycle is observed. Health passes 347/347
(max 0.269 s); sampled guest use peaks at 708.25 MiB, and dashboard RSS/HWM
increase is 83.902 MiB. The original 1024 MiB/native conditions remain open.
The failures overlap the cycle; raw evidence does not retain alert reason or
first-shell time, so this overlap does not prove a cause. Frozen CPU evidence
ends before the failures and cannot establish full-window or depleted behavior.

`concurrency-audit/` retains the independent audit, immutable raw/context copy,
provenance manifest and replay/hash verification. All summary fields were
independently reproduced; no request or failure was dropped.

The later `concurrency-audit/cpu-supplement/` preserves the initial freeze and
adds full-window CPU samples: positive observed balance and zero observed
throttle. It does not qualify depleted CPU or explain the incomplete requests.
`post-concurrency-operation.json` verifies the same v64 image/instance and all
180 source hashes after the load, healthy endpoints, twelve monitor events and
zero cycle errors/proposals. The three strategy fixes also retain pure replay
coverage with unchanged input hashes.

## Cold-path diagnosis

`cold-profile/diagnosis.json` and `core-profile-result.json` describe a frozen
1,000,000-row, 640,453,970-byte local fixture. Canonical no-checkpoint and new,
task-owned checkpoint paths produce the same complete 311,060-byte output:
`84777425c45acb6e70fe32f45554daabe08787278eb51543c789f8f08e1922e7`.
Thirteen source hashes and all ten fixture hashes/metadata remain unchanged.

Single-thread profiles drain the exact production projection generator after
equal lazy-import warm-up. They attribute CPU work; one instrumented run per
variant is **not** a cold-page latency percentile or a resource qualification.
The original threaded service profile is retained as `profile-result.json`,
but its function timings are rejected because worker/poll attribution was
contaminated. Both harnesses are retained as text for reproducibility.

| Profile observation | Canonical | New checkpoint |
|---|---:|---:|
| Instrumented elapsed time | 10.538 s | 14.665 s |
| `add_event` cumulative time | 5.682 s | 6.014 s |
| Canonical model validation | 2.134 s | 2.155 s |
| Structural sizing cumulative time | 0.498 s | 3.190 s |

Checkpoint encoding spends 1.636 s on 3,711 full size scans used to choose the
32 KiB frame-splitting branch. An exact threshold predicate that stops once
the threshold is exceeded is a bounded optimization candidate. It must keep
encoded bytes, schema, decode behavior, unsupported-state fallback and the
separate full `StateBudget` admission accounting unchanged. It does not remove
the common million-row validation/reduction cost and cannot by itself certify
the canonical cold target. A separate import-boundary candidate avoids importing
the Streamlit/pandas page only to obtain gate vocabulary. Neither candidate is
implemented or claimed as a speedup here.

## Acceptance boundaries

The original targets remain in
`../../nfr-requirements/bounded-data-loading/nfr-requirements.md` and the original
qualification plan. Existing v64 source/test evidence covers bounded readers,
global caps, semantic parity and failure coverage (BDL-NFR-01/06/07/08).
The million-row profile adds diagnosis, not the complete BDL-NFR-05 scenario set.

The existing twenty canonical no-store million queries have p95 **7.817 s**,
above the 5 s target; seeded restart p95 **0.695 s** excludes bootstrap and native
rendering. The legacy `first_unseeded` observation of **11.143 s** is preserved
but its harness did not prove an initially empty store. Do not silently upgrade
that observation to a verified pristine-cache experiment. The production warm-up
Home observation of **17.838 s** is also retained as a slow observation, not a
twenty-sample p95.

BDL-NFR-02/03/04 require the specified corpora, cold/warm samples and resource
conditions. A four-client protocol run on shared CPU 1 / 2048 MiB can qualify
its measured warm-concurrency subset. It cannot certify the declared 1024 MiB
guest, depleted CPU, twenty independent cold page loads or native viewport.
An engine cycle must start and finish inside the observation window.

## Native browser blocker

`browser-availability.json` records a supported runtime bootstrap failure before
page selection/navigation: the packaged `scripts/browser-service.mjs` is missing.
No native page was opened, and no dashboard rendering failure is inferred from
this setup failure. The available plugin tools do not provide a repair operation.
The operator has been asked to restore Browser through the application plugin
settings; readiness has not yet been confirmed. No replacement browser result
is presented as native acceptance.

DEBT-083 remains **Critical / active** until the original acceptance is met.
The deferred performance-CPU/cost decision is unchanged.
