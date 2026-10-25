# Page Loading Watcher Evidence, 2026-10-25

Source `d86f76f` is deployed as Fly v62 with exactly four dashboard file overlays
on the v61 dependency image. Reader/source/service hashes match v61. All 2823
full tests, 92 focused tests, six-file Black/Ruff and 129-file mypy pass; source
fingerprints and the full suite log are recorded here.

The current machine remains shared CPU 1 / 2048 MiB with its original volume
and paper/Codex/Claude controls. Source verification checks all 175 runtime
inputs. `v62-current-runtime-verification.json` also records the first full
post-deployment engine cycle (03:47:14.646139Z–03:47:52.451427Z), plus later cycles.
Actual image/instance configuration is in `deployed-release.json`.

The first observed application navigation after this restart completes Home in
12.180s and Trading in 1.149s. Home registers exactly one background watcher;
Trading needs none in that pair. This is one observed pair, with HTTP server
startup before the measured navigation, not twenty process-cold observations.
Cold readiness is not accepted. Native Browser remains independently blocked.

`v62-20s-*` is the exact final four-session server protocol scenario. It alternates
Home/Trading every twenty seconds, retains full-script completion/failures,
meaningful metric/coverage/table/chart checks, read-only process/guest sampling,
public health and whole engine-cycle evidence. Its protocol also counts actual
background watcher registrations. It is not native browser acceptance or the
original declared 1 GiB guest qualification.

**Important measured condition:** `v62-cpu-metrics-initial.json` shows about
459 CPU-seconds of burst balance and no throttling at the initial checkpoint,
following a long idle application period. v61's failures had depleted burst.
These are not controlled CPU-availability or data-identical A/B trials. Any
passing buffered run does not prove baseline/depleted shared-CPU acceptance or
that watcher coalescing alone caused a performance improvement. Earlier failures
remain in [v61 evidence](../cold-readiness-20261025/README.md).

## Final observed result: acceptance not passed

The four-session twenty-second scenario lasts **1415.830s (23m36s)**. It records
**276/280 complete views** (138/140 on each page), plus four genuine **30s page
timeouts** during the engine cycle. All **280 health samples pass**, maximum
**1.286s**. Successful-only p95 Home **0.620s** / Trading **0.829s** is not a
passing readiness series because the failures remain. This is server-protocol
observation, not native viewport acceptance.

The full paper cycle runs **09:52:48.578812Z–09:53:33.020625Z** with twelve monitor
passes and a completed proposal path, without an errored event in the captured
cycle. Engine/dashboard PIDs stay 654/655. Actual background watchers never
exceed **one**. Dashboard RSS/HWM growth is **21.652 MiB**, below its 256 MiB
criterion; whole-guest peak is **1293.313 MiB**, above **768 MiB**, on the actual
2 GiB allocation. Engine RSS peaks at **899748 KiB (878.660 MiB)** during the run,
which alone exceeds that whole-guest budget. Do not sum process RSS to derive
VM use; the guest figure uses MemTotal minus MemAvailable.

Host metrics retain roughly 459 CPU-seconds initially and 410 seconds finally,
with **zero host throttle throughout this observation**. This run therefore
shows that quota exhaustion is not a sufficient explanation for every timeout.
It does not isolate source mutation, allocator or scheduling causes, and is not
a depleted-CPU A/B. The positive watcher/health observations do not close the
cold, failed-view, memory, native or original 1 GiB acceptance gaps.

At the deliberate normal end the harness cancels unfinished requests; this
version records completed/timeout views but may omit such boundary-censored
requests. They are not counted as successes. The four independent 30s timeouts
are retained, so this limitation cannot turn the failed run into acceptance.
The raw driver exits 1 for incomplete views; `qualification-verdict.json` also
checks the original memory ceiling rather than relying on process exit alone.

After load stops, a separate single-client recovery pair completes Home **0.597s**
and Trading **0.515s**, with no incomplete alert/exception. Final source checks
still match all 175 inputs, original volume/capacity/paper/Codex settings and
continued engine cycles. Public health is HTTP200. Existing v62 is retained;
no further engine algorithm, storage, allocation or trading-policy change is made.

