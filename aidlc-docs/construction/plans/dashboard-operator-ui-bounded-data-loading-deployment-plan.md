# Deployment Plan: Bounded Dashboard Loading

- **Unit/debt:** `dashboard-operator-ui` / DEBT-083, Critical and active
- **Authorization:** Operator explicitly requested `배포도 해줘` after local implementation/verification and disclosure of the failed cold latency target.
- **Scope:** Deploy the verified bounded UI source to existing Fly app `crypto-master`; preserve the existing machine, `/data` volume, 2048 MiB recovery capacity, paper mode and Codex configuration. Commit the scoped source/documentation so the image and acceptance evidence have a reproducible source identity.
- **Baseline:** Fly v56, machine `6835752b711958`, image source `3f4864f69d3fea3d5b3347375438a8644c2f0440`, digest `sha256:a1d4e132479109300fe9432a04df21feb1efc8ebe50e463ee3e5bfac0b11cdd0`; HTTP check passing. Origin adds only the existing v56 strategy deployment records at `85a560c`.
- **Acceptance boundary:** This rollout does not waive the cold p95 target or close DEBT-083. Native page/shared-session/guest/engine evidence must be distinguished from static HTTP and query-only checks. The current 2 GiB recovery allocation cannot certify the original 1 GiB resource target.

## Steps

1. [x] Record deployment authorization; commit only the approved UI source/tests/design/evidence and related unit records, preserving unrelated local configuration.
2. [x] Integrate current origin records in an isolated worktree, resolve documentation conflicts narrowly and verify the final source against the passed 2719-test revision. Final checkout focused checks pass; the rollout correction also has 2721 full passes.
3. [x] Build/deploy from the clean isolated checkout with a source-SHA image label, existing Fly topology/capacity and health checks. Final v58 source `785374b`; v56 image identity retained for rollback.
4. [x] Verify 175 deployed artifacts, machine/volume/settings, processes and bounded queries. Record complete Home/Trading protocol responses and native Browser bootstrap limitation; viewport acceptance remains unqualified.
5. [x] Observe post-rollout health/memory and the first completed engine cycle; session/cross-check/unit/debt record actual evidence and pending NFR criteria. DEBT-083 remains active.

## Rollback

### Rollout correction

- [x] Preserve the requested root's expired encoded projections for generation-verified reuse. The 30s stale **display** deadline is not a reason to discard the compact projection and reread the archive after a slow batch. Other inactive roots may still be evicted for the two-root limit; freshness, stale display, cache bytes and entry caps remain unchanged.
- [x] Verify unchanged-source reuse after >30s, damaged-source rejection and other-root admission. Focused service/default-page tests: 16 passed; full regression: 2721 passed in 245.42s; Black/Ruff and source mypy (129 files) pass. Redeployment is recorded below.
- [x] Redeploy the validated correction with a new source identity: `785374b`, Fly v58.
- [x] Record the v57 protocol retry failures and actual corrected-release evidence; native browser and complete latency acceptance remain pending.

If the replacement release fails health/startup or causes a new UI/process
regression, redeploy the captured v56 image with the existing `fly.toml` and
the same 2048 MiB allocation. Do not mutate `/data`, credentials, trading
mode or provider to make a health check pass. Do not infer failure solely
from the already disclosed cold latency miss.

## Completion

- [x] Scoped source and remote identity recorded
- [x] Fly release/artifacts verified
- [x] Actual protocol/process/health evidence recorded, with native UI limitations
- [x] Session/cross-check/state/debt reflect deployment and open acceptance

See the [deployment session](../../../docs/sessions/2026-10-10-dashboard-operator-ui-bounded-data-loading-deployment.md).
