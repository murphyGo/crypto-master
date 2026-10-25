# Strategy evidence production rollout: DEBT-087/088/089

## Authorization and separate commits

The user requested each correction be committed and pushed separately, then
explicitly requested deployment and operational verification after all three.
Each push was confirmed against `refs/heads/main` with `git ls-remote`:

| Debt | Commit | Change |
|------|--------|--------|
| DEBT-087 | `052764e64f155dd0849c7ae4e7d486b2a1660343` | Account-scoped proposal performance and closed-history eligibility |
| DEBT-088 | `79ef547056f34e7085b37d6b3b0c5e36da80f048` | Structural cap-blocker monitorability and separate reconciliation state |
| DEBT-089 | `f0f3e524eda0ac8b5dcab0b0aad9dfaf8e100291` | Funding coverage metadata and separate read-only carry sensitivity |

Fetched upstream `1855781` contained dashboard/runtime-read design documentation
only. It was fast-forwarded and preserved before the three commits. Unrelated
`.claude/settings.local.json` and `.claude/scheduled_tasks.lock` remain outside
the commits, with their original hashes verified unchanged.

## Build and release identity

- Source: `f0f3e524eda0ac8b5dcab0b0aad9dfaf8e100291`.
- Fly app/region: `crypto-master` / `nrt`; release **v63**.
- Machine: `6835752b711958`; instance `01M5T02W3GG7MM2FDXTJ9BN41P`.
- Machine start/update: `2026-10-25T17:00:27Z` (October 26, 02:00:27 KST).
- Image: `registry.fly.io/crypto-master:git-f0f3e524eda0ac8b5dcab0b0aad9dfaf8e100291`.
- Digest: `sha256:106055713d985c44720c6386de719c500dff8113dfdc894dab8b2b0b54fc3187`.

The source gate remains **2,865 tests passed**, changed-file Black/Ruff clean and
131-file mypy clean. Since that run, application/test code has not changed;
only documentation, commit separation and the clean deployment context changed.

Before rollout, all 175 existing runtime artifact hashes matched deployed v62
source `d86f76f`. The final source adds two modules and changes seven existing
files; strategy definitions, account policy, startup, dependencies and Fly
runtime configuration have no source changes.

A clean context was exported from tracked Git inputs. The initial standard
Dockerfile build was canceled before deployment to prevent unrestricted pip
requirements from refreshing dependencies. A second build was also canceled
when the Fly `[build].dockerfile` setting took precedence over the CLI override.
Neither attempt updated the running machine. The successful build sets the
Dockerfile in the temporary context's Fly configuration and overlays only the
nine changed/new source files on the verified v62 image digest. The existing
dependency stack is inherited; no package installation occurs in that build.

The rolling deployment, machine smoke checks, service health and DNS check passed.
No strategy/account policy, live promotion, credentials, volume migration,
DEBT-083 checkpoint, or runtime-safety design was activated.

## Operational qualification

- [x] Three separate source commits pushed and remote SHAs confirmed.
- [x] Clean tracked source and permitted runtime delta verified before rollout.
- [x] Image built and deployed; Fly release/source label and health confirmed.
- [x] Verify all 177 running artifact hashes and preserved process/configuration.
- [x] Observe a completed post-rollout engine cycle and inspect its errors.
- [x] Inspect fresh proposal/cap events; record their absence and separately
      verify the deployed methods against persisted evidence read-only.
- [x] Exercise funding coverage/reporting read-only on deployed code and data.
- [x] Preserve evidence and update debt/state for the operational closeout.

All **177 artifact hashes** match the deployed source. Python 3.13.16,
Streamlit 1.65.0, pandas 3.0.6, Pydantic 2.14.0/core 2.50.0 and NumPy 2.5.4
match predeployment versions. One engine process and one dashboard process run.
The same shared CPU 1 / 2048 MiB, encrypted 1 GiB volume
`vol_4m3l58dkk29y19zv`, paper mode, Codex provider/Astra model and 1800-second
cycle interval remain. Both internal and public health return HTTP 200 / `ok`.

First cycle `d7ab88db-f2e9-447a-a315-0bb6768139d6` runs from
`2026-10-25T17:00:35.283242Z` to `17:00:50.270313Z`: **12 monitor passes**,
zero generated/accepted/rejected proposals, zero opens/closes, then sleeping.
No post-rollout activity errors or malformed captured activity lines were found.
The follow-up at `17:02:22Z` confirms the same instance/processes and health.

Because the first cycle generated no proposals, it did not exercise a new
proposal score or cap rejection event. That natural-event coverage is explicitly
unobserved, not reported as a passing event test. No extra trading cycle or order
was triggered for validation. The deployed methods were separately exercised
read-only using current `/data` inputs:

- DEBT-087: both single/multi selectors and scoring match **18 account/version
  combinations across 12 enabled accounts**, while the shared reader remains
  default-scoped. Examples: MA 224, Raschke 263 and RSI15m v1.1.0 227 eligible
  closed real samples; the default account has zero for those strategies.
- DEBT-088: the actual cap payload method renders all **7 current open trades**
  as `legacy_no_perf_link` and structurally `monitorable=true`. The replay
  omits proposal joins and leaves market marks unknown; it does not emit an
  event or establish an exchange-close guarantee.
- DEBT-089: deployed evidence formatting reports fee-net/funding unknown. A
  separate adverse-carry smoke covers MA's **224/224 closed records**, reports
  actual funding as null and retains input hashes. The rendering uses an
  explicitly declared 10,000 USDT capital assumption only for a format smoke.
- All **24 read input files** have identical before/after hashes. No data
  repair, trade write, market-data fetch or policy application was performed by
  these probes.

Evidence is under
[`debt087-089-rollout-20261026`](../../aidlc-docs/construction/proposal-runtime/code/debt087-089-rollout-20261026/).
The record includes pre/post source hashes and runtime identity, the read-only
replay, permitted source delta, the exact overlay Dockerfile and qualification
assertions. Unrelated historical predeployment exchange errors are retained as
timestamps/types, distinct from the empty post-rollout error list.

This completes deployment and initial operational qualification for the three
corrections. It does not qualify strategy profitability, actual funding
settlement, a future natural proposal/cap event, or the independent DEBT-083
dashboard performance/design gates.
