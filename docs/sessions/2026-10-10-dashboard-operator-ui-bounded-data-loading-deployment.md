# Session: Bounded Dashboard Loading Deployment

- **Unit/debt:** `dashboard-operator-ui` / DEBT-083, Critical and active
- **Authorization:** Operator requested `배포도 해줘` after local implementation and disclosure of the unmet cold latency target.
- **Result:** Fly v58 deployed and verified at runtime source `785374bebd12ab18b145b3a1f3de6238b3fe4d4b`. Source commit and deployment records are pushed to main.

## Release identity and scope

| Field | Verified value |
|-------|----------------|
| App / URL | `crypto-master` / <https://crypto-master.fly.dev/trading> |
| Final release | v58, release id `rel_v0or2wn0ddx629gx` |
| Runtime source | `785374bebd12ab18b145b3a1f3de6238b3fe4d4b` |
| Image digest | `sha256:51eccbe5df64c17b63d8b37da21d1013032d6c3b42d466c4df02f219de7d3184` |
| Machine / instance | `6835752b711958` / `01M4GVRWNBGQJ1JSJ116BRDE8R` |
| Machine start | 2026-10-09T17:36:09Z |
| Region / capacity | nrt, shared CPU 1, 2048 MiB |
| Persistent volume | Existing encrypted `vol_4m3l58dkk29y19zv`, mounted `/data`, 1 GiB |
| Runtime settings | paper mode; Codex provider; Streamlit 1.65.0 |
| Artifact verification | 175 tracked runtime input hashes match the committed source; zero mismatches |

The initial bounded source was committed as `24bfb85`. The isolated worktree
merged origin's concurrent v56 deployment documentation at `85a560c`, producing
`af72d87`. It changed no additional runtime files. Build/deployment used that
clean checkout and then the verified correction below. Unrelated local
`.claude` configuration and lock files remained outside the commits/build.

No trading-mode/provider/credential/volume/capacity changes or manual runtime-data
migration were performed. The engine continues its ordinary paper writes.

## Rollout correction

Initial v57 used `af72d87`, image digest
`sha256:e28e50e4d5bc634d008d43117d92349492c52baead9dad2591570e7815bc2aef`.
It passed health, source/process verification and five individual read queries,
but repeated protocol refreshes exposed long pending/queue-full states. Trading
eventually completed after about 110s in one manual-retry observation; a Home
manual-retry observation remained incomplete after 153s. A separate batch
diagnostic remained in its first activity build across twelve four-second waits.

Review identified avoidable eviction of the requested root's compact projections
after the 30s stale **display** deadline. This forced a new archive read when a
slow batch had outlived that deadline. `785374b` retains those projections for
full generation-verified reuse. Freshness (2s), stale display (30s), byte/entry
limits, root limits and changed/damaged-source rejection are preserved. Two
regression cases verify old unchanged-source reuse, damaged-source rejection and
eviction of another inactive root to admit a new root.

The correction has 16 focused passes, 2721 full regression passes (245.42s),
changed-file Black/Ruff passes and source mypy success (129 files). v58 was
built from the clean corrected commit. Other causes of the observed latency,
including scheduling/CPU effects, were not established. The v57 manual-retry
and v58 advertised-fragment observations use different refresh methods and are
not a controlled performance comparison.

## Post-deployment evidence

At 17:40:14Z, all 175 runtime hashes match. Engine/dashboard processes are
present. Dashboard RSS is 290852 KiB, engine RSS 203868 KiB and guest available
memory 1367128 KiB. These are point observations on the retained 2 GiB VM,
not the original 1 GiB/four-session acceptance.

The post-rollout paper cycle `f874c90d-3670-4790-9f72-fd8df390e78f` started at
17:36:18.051196Z and completed at 17:36:29.337333Z. Independent health requests
returned `ok` / HTTP 200, including 0.120s and 0.128s after v58.

| v58 individual query | Completion | Captured coverage |
|---------------------|-----------:|-------------------|
| Activity | 7.074s; foreground pending after 4.004s | 215034 events, 7 files / 90231892 bytes |
| Paper ledger, 13 accounts | 0.207s | 13 files / 889808 bytes |
| Snapshots, 13 accounts | 11.338s; foreground pending after 4.005s | 13 files / 30295334 bytes |
| Proposals, 24h | 1.887s | 12184 files / 15121006 bytes |
| Home candidates | 0.001s | 1 file / 856 bytes |

All five completed with verified source coverage and no transient failure in
this series. The separate verification process used one worker, five encoded
cache entries / 469965 charged bytes and a peak RSS of 224236 KiB.

The Streamlit protocol probe obtains the canonical page hash from the server's
navigation and decodes with the deployed 1.65.0 schema. It follows the advertised
availability fragment refresh. Home produced a complete twelve-card response
on its second full render; total from connection/discovery through background
work was 32.742s. That complete render took 2.041s. Trading then produced its
six populated metrics plus table/chart elements with no exception or incomplete
availability; render 3.125s, total connection/discovery 3.866s. These are single
protocol observations, not twenty-sample native browser readiness percentiles.

A later single repeat, after the cache display deadline had elapsed, received
complete Home/Trading responses on the first full render in 1.338s / 1.253s;
connection/discovery totals were 1.758s / 2.009s. No exception or incomplete
availability was observed. This confirms useful unchanged-source reuse in the
observed warm sequence; it does not certify the required warm percentile.

Native Browser bootstrap failed because its runtime service module was missing
under the local plugin cache. No viewport/screenshot/four-native-session
acceptance is claimed. Protocol integration is recorded separately from
browser visual verification; the successful static health check is separate too.

## Evidence and remaining acceptance

- [Final source/process/query verification](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v58-source-process-query-verification.json)
- [Final protocol observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v58-protocol-verification.json)
- [Later warm protocol observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v58-warm-protocol-verification.json)
- [v57 manual observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v57-manual-protocol-observation.json)
- [v57 Home retry observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v57-home-manual-retry-observation.json)
- [v57 batch diagnostic](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/deployment/v57-batch-diagnostic.json)
- [Cross-check](../cross-checks/2026-10-10-dashboard-operator-ui-bounded-data-loading-deployment.md)

Deployment/source/process/engine checks pass and Home/Trading complete protocol
responses are observed. DEBT-083 remains Critical/active: complete cold readiness
still exceeds 5s, exact-final twenty-sample performance and four native sessions
for at least ten minutes remain pending, and the retained 2 GiB capacity cannot
certify the original shared-VM budget. Continue cold bootstrap, changed-source
and metadata-revalidation cost work without relaxing the semantic/resource limits.
