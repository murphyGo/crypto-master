# Strategy improvement production deployment

## Scope and authorization

The operator requested deployment after the five individually pushed fixes:
DEBT-084, DEBT-085, DEBT-078, DEBT-074 and DEBT-086. Deployment used the existing
isolated worktree and a clean context containing only tracked build inputs.
The original dirty checkout was preserved.

## Release identity

- Runtime commit: `3f4864f69d3fea3d5b3347375438a8644c2f0440`.
- Fly app/region: `crypto-master` / `nrt`.
- Release: **v56**, following the observed v55.
- Machine: `6835752b711958`; instance `01M4GJM39E4M24R3WWBB4QD7NQ`.
- Image: `registry.fly.io/crypto-master:git-3f4864f69d3fea3d5b3347375438a8644c2f0440`.
- Image digest: `sha256:a1d4e132479109300fe9432a04df21feb1efc8ebe50e463ee3e5bfac0b11cdd0`.
- Deployed source verified on 2026-10-09 around 14:56 UTC.

Before deployment, 167 running application artifact hashes were compared with
the intended source. Differences were confined to the approved corrections;
the new rolling-evidence module brings the deployed artifact count to 168.
After deployment, all 168 hashes matched the clean build context exactly.

## Deployment and configuration

```sh
flyctl deploy /private/tmp/crypto-master-deploy-3f4864f-20261009 \
  --app crypto-master --remote-only --ha=false --vm-memory 2048 \
  --strategy rolling \
  --image-label git-3f4864f69d3fea3d5b3347375438a8644c2f0440 \
  --label org.opencontainers.image.revision=3f4864f69d3fea3d5b3347375438a8644c2f0440 \
  --yes
```

The VM override deliberately preserves the running **2048 MB** allocation;
the deployed source commit's `fly.toml` declares 1024 MB. Concurrent upstream
commit `fab4e86` subsequently records the same 2048 MB capacity in `fly.toml`;
that configuration/documentation update is preserved when integrating this
deployment record. The single shared CPU and existing encrypted
1 GiB `/data` volume `vol_4m3l58dkk29y19zv` remain in place. Runtime stays
`TRADING_MODE=paper`, `LLM_PROVIDER=codex`, `CODEX_CLI_MODEL=gpt-6-astra`.
No credential, provider, account policy, or data migration was performed.

## Verification

- Predeployment source gate: **2669 tests passed**, Black/Ruff on 30 changed
  Python files, and mypy on 123 source files passed.
- Remote build, image push, rolling update, Fly smoke checks and DNS check passed.
- The initial status snapshot briefly reported `waiting for status update`;
  the refreshed service check reports **passing / ok**, with the same instance.
- Internal and public `/_stcore/health` both returned HTTP 200 / `ok`.
- Exactly one `python -m src.main` and one Streamlit dashboard process run.
- Runtime import/assertion smoke confirms unknown-only funnel rows do not count
  as accepted and the recovered-bound provenance field is present.
- First cycle `9e400295-3a87-4213-91f3-f0315d71fba2` completed at
  `2026-10-09T14:56:30.498990Z`: 12 monitor passes, then sleeping; zero proposal,
  accepted/rejected, opened or closed counts. No error events were observed
  between rollout and this completed cycle.
- New observed-attempt counters are present in 12 strategy metric files.

These checks establish rollout and initial runtime health. They do not establish
future profitability or exercise every SL/TP recovery branch in production;
those behavior boundaries are covered by the recorded regression tests.

The prior implementation sessions' “deployment not performed” statements
describe their earlier source-only checkpoints. This follow-up closes deployment
for the five listed corrections without closing unrelated operational debt.
