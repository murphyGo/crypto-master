# v72 operational evidence — initial-read cost

Source `71c87874222bb8b385583651f8c2b124e108fa05` was committed and pushed before
delivery. The three-file build context overlays only `src/utils/bounded_read.py`
on the exact v71 exchange-containment image. Dependency layers stay unchanged.

- Fly release: 72, machine `6835752b711958`, instance
  `01M74PWMT73VFHZ56MGPRRK7ZM`.
- Image: `sha256:7f66519b0490a1610299ac2c75b44b2129201f97a8a71a55b60d4352294224ed`.
- Rollback image: `registry.fly.io/crypto-master@sha256:32d706b6e7ea5ef9ba725749d429eca79a47cb8e5667837ce7c12c1016f27552`.
- Shared CPU 1 / 2048 MiB, one existing machine and `/data` volume, paper/Codex,
  1800-second engine cadence. Settings and all 183 runtime hashes verified.
- Startup cycle `d94aa070-a8e2-4d2c-a0e6-ca0633846045`, 07:07:06.425660–
  07:07:29.340962 UTC: 12 distinct monitors, no cycle error, zero opens/closes.
  One proposal was generated/accepted then rejected by the existing downstream
  gate. This cycle predates the four-session observation window.

`native-visual-smoke.md` records the separate untimed Chrome inspection. The
protocol warmup follows that inspection and is not cold evidence. The bounded
observer uses four real Streamlit sessions, Home/Trading alternation at 20-second
cadence, five-second health checks and one-second memory samples. Minimum length
is 600 seconds plus a complete naturally scheduled engine cycle, maximum 2100
seconds. Temporary local idle-sleep prevention is owned by the wrapper and ends
in its finally block. No refresh/cache reset, engine trigger, capacity change or
canonical-data mutation is performed by the observation tools.

Final audit: **PASS_BOUNDED_PROTOCOL_SAMPLE**, 07:15:26.468132–07:38:33.542820
UTC (1387.074688 s). All277 starts have277 complete outcomes, no shape failure,
no timeout/reconnect. Home138/138, p95 0.584077 s; Trading139/139, p95 0.678392 s.
All275 health checks pass, max0.192669 s. Guest peak655.273438 MiB; dashboard
RSS growth14.933594 MiB from a warmed baseline (HWM difference20.175781 MiB).
Collection gaps remain bounded: health5.194804 s, memory1.021827 s, memory tail
0.700241 s. Engine/dashboard PIDs and start ticks remain unchanged.

Four requests started around the engine write wave took13.191730–15.184764 s,
including transient incomplete shells at4.168837–4.374500 s and one background
watcher each. They eventually completed automatically; all are retained in
`audit.json` and original outcomes. The p95 gate passes; this is not a claim that
every request completes within2 s. Diagnostic overlap includes activity/snapshot
source-change retries and admission waits; it does not identify a specific causal
writer. These tail delays remain part of DEBT-083.

Natural cycle `76ee8fdb-8bb9-4bb7-82a6-f1f032f25a11` spans
07:37:29.424312–07:37:48.671272 UTC (19.246960 s), with12 distinct monitor accounts,
zero errors/opens/closes. One proposal was accepted then rejected downstream.
CPU has93 in-window points at15 s spacing plus both brackets: burst balance
26.157164–51.077178 CPU-seconds, zero sampled throttle increments. Balance never
reaches zero; depleted-CPU qualification remains open.

Runner, observer, diagnostic collector, CPU collection and postflight exit0.
Local observer/collector/temporary guard and exact remote task sampler are absent.
Sandbox restrictions delayed the final cleanup/CPU checks until after the
observation; they are separate evidence, not part of the continuous window.
`after-final-audit-*` freshly reconfirms v72, all183 hashes, unchanged settings,
image/instance/process continuity and health after that delay.

Evidence entry points:

- `before-*`, `postdeploy-*`, `after-*`: runtime, machine/configuration, sources,
  process identity, dependency versions and bounded cycle metadata.
- `expected-runtime.json`: the deployed source and hashes, independent of later
  documentation commits.
- `observation/`: original starts, outcomes, warmup, memory, health and final
  summary. Failed outcomes are retained without excluding them from the verdict.
- `audit.json`: offline reconciliation and full-page protocol-shape audit.
- `cpu-history.json`, `cpu-window-supplement.json`: recorded Fly CPU balance,
  baseline and throttle counters. Raw balance/throttle units are centiseconds;
  divide by 100 for CPU-seconds. Bracket coverage is reported separately.
- `post-observation-verification.json`: natural cycles and task sampler cleanup.
- `diagnostics.jsonl`: allowlisted dashboard diagnostic messages; no credentials
  or full operator payloads. Overlap alone does not prove request causation.

`deploy.log` contains captured terminal output, including a tool truncation
marker in the layer-upload progress; it is not represented as a complete raw
build transcript. Trailing whitespace in terminal logs is normalized before
hashing; JSON/JSONL observations are copied byte-for-byte. Image, release, runtime
hashes and configuration are verified
independently in the postdeployment captures.

Reproduction helpers expect the repository root and task scratch paths. The
wrapper references the retained historical diagnostics and CPU collector scripts
under `home-recovery-20261026/operations/`. Do not rerun collectors into sealed
artifact paths; use a new scratch directory. The parser source in build-context
is delivery evidence; application ownership remains `src/utils/bounded_read.py`.

DEBT-083 remains Critical. This operational sample is on 2 GiB and cannot qualify
the original 1 GiB allocation. Native percentile, process/cache-cold, depleted-CPU
and deferred capacity/cost decisions remain separate. Earlier failed or stopped
observations remain unchanged.
