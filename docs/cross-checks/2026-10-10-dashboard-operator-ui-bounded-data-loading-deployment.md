# Cross-check: Bounded Dashboard Loading Deployment

**Verdict:** Deployment/source/process checks PASS; complete Home/Trading protocol
responses observed; full latency/resource/native-browser qualification PARTIAL.

| Contract | Evidence / verdict |
|----------|--------------------|
| Intended runtime source | Fly v58 source `785374bebd12ab18b145b3a1f3de6238b3fe4d4b`, image digest `sha256:51eccbe5df64c17b63d8b37da21d1013032d6c3b42d466c4df02f219de7d3184`; 175 input hashes match. PASS. |
| Current-root reuse after slow batch | Source eviction corrected; unchanged >30s reuse, damaged source and other-root admission tests pass. Fresh/stale display limits and byte/root caps preserved. PASS. |
| Local regression | 16 focused tests; 2721 full tests in 245.42s; Black/Ruff and source mypy (129 files) pass. |
| Published service | Fly HTTP check passing; independent HTTP 200 / `ok` responses, including 0.120s and 0.128s. PASS at health scope. |
| Actual persisted reads | Five queries complete with verified coverage, 13 paper accounts and 215034 activity events. PASS for the observed series. |
| Page integration | Deployed-version protocol decoder/canonical navigation/availability fragment refresh receives complete Home cards and Trading metrics/table/chart elements without exceptions. PASS at protocol scope. |
| Trading intent and data | Paper/Codex/2048 MiB/original volume retained; no manual runtime-data migration. PASS. |
| Engine continuity | v58 first paper cycle started 17:36:18.051196Z, completed 17:36:29.337333Z; both processes present. PASS for this cycle, not the full four-session acceptance. |
| Complete readiness target | Cold Home total 32.742s; a later warm pair renders in 1.338s/1.253s. These single observations do not pass/qualify the required cold 5s/warm 2s twenty-sample percentiles. DEBT-083 stays active. |
| Browser / guest stress | Native Browser bootstrap missing runtime module; viewport and four native sessions >=10min unverified. Point memory observations on 2 GiB cannot certify the original 1 GiB target. PARTIAL. |

The [deployment session](../sessions/2026-10-10-dashboard-operator-ui-bounded-data-loading-deployment.md)
records exact release/source/evidence, v57 failures and the rollout correction.
The v57 and v58 protocol refresh methods differ; no controlled causal speedup
claim or complete NFR closeout is made.
