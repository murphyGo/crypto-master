# Strategy evidence integrity: DEBT-087/088/089 and recurrence analysis

## Request and scope

The user approved registration and correction of the three concrete findings
from the Fly strategy review, and asked why prerequisite issues keep appearing.
This is an implementation slice of `strategy-improvement`, following
`dev-crypto` construction tracking. No strategy entry/exit logic, account policy,
credentials, live activation, deployment, or runtime data was changed.

Primary units: `proposal-runtime`, `proposal-funnel-audit`, `strategy-framework`.
Requirements: FR-005/011/014/021/036, NFR-006/007/008; US-005/009/012/019/023.

## Evidence custody

- Baseline repository HEAD: `070fa966a82399a1f189076b9cdd891bd7609e8f`.
- Fly source v62: `d86f76fda1b91bc337b06db2050722379c3f8701`, machine
  `6835752b711958`; 12 relevant source/config hashes matched local files.
- Shared snapshot: `/private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z`.
- Archive SHA256: `304a58e28df110bd410e503d1b0be5b6b73f3016a76ee1c38fe46e359e4e4c5d`.
- 13,165 JSON, 9 JSONL / 240,922 lines: zero parse failures.
- Active accounts: 1,247 closed trades, 13 opens. All closed rows reverse-link
  to performance outcomes; null forward IDs are a supported lifecycle.
- No re-snapshot, repair, migration, backfill, or input rewrite during this slice.

## Implementation

### DEBT-087: account-scoped historical reads

`PerformanceTracker.get_performance` accepts an explicit per-call account and
creates a local reader using the injected data root. Shared writer/default scope
is not mutated. BTC/altcoin single/multi strategy paths carry the account through
selection, scoring, and the live cold-start check. A separate
`closed_real_trade_count` excludes pending and synthetic observations without
redefining the existing record-count property. The existing score formula and
approval thresholds remain unchanged.

Fourteen new tests use real persisted opposing account histories, version and
pending/synthetic controls, concurrent requests, and default/injected-root
compatibility. Two lifecycle cases close a real TradeHistory, persist via
SnapshotRecorder, then generate the next proposal: beta sample 0→1, another
account stays 0. A production `src.main.build_engine` case uses the real tracker
and settings data root: beta sample 3 / EV +4, default sample 7 / EV -6.

Decision-time replay includes only outcomes exited before the stored proposal:

| Account | Sample before → after | Composite before → after |
|---------|-----------------------|--------------------------|
| MA | 0 → 221 | 0.0288405791 → 0.0556430131 |
| Raschke | 0 → 262 | 0.2959090837 → 0.5927339306 |
| RSI15m | 0 → 224 | 0.0101018542 → 0.0208197241 |

Full pointers and input hashes:
`aidlc-docs/construction/proposal-runtime/code/debt-087-snapshot-replay.json`.
This replays evidence/score arithmetic, not alternate fills, top-K selection,
or a claim that historical returns would improve.

### DEBT-088: structural monitorability is separate from provenance

Cap payloads mark both MONITORABLE and LEGACY_NO_PERF_LINK as structurally
monitorable and expose `reconciliation_state` additively. Missing bounds/core
data remain false. The boolean does not certify a live heartbeat, fresh quote,
exchange availability, or guaranteed fill. Actual cap and close behavior stays
unchanged. Seven new event-path cases cover symbol/total cap, persisted no-link
bounds, linked rows, and degraded/unrecoverable controls.

### DEBT-089: cost coverage without invented settlement charges

Evidence and persisted observations carry `pnl_basis` and `funding_coverage`.
Current evidence is fee-net excluding funding; old observations default to
legacy-unspecified basis and funding unknown. Dashboard summary/evidence text
exposes the boundary. `economic_complete` retains its existing fee-net/window/
account meaning; recommendations and applied states are not changed by metadata.

`src.strategy.cost_coverage.adverse_carry_sensitivity` joins real closed
performance records to actual TradeHistory fills/timestamps. It computes an
explicit constant adverse carry scenario using fractional holding intervals,
with no extra leverage or trading-fee deduction. Actual funding stays unknown.
Missing, duplicate, mismatched, nonfinite, or reversed-time inputs cannot produce
a complete result; mixed accounts are rejected. Partial sums are labeled and a
complete adjusted scenario PnL is absent when inputs are incomplete.

Read-only CLI example:

```bash
uv run python -m src.tools.report_strategy_costs \
  --snapshot /private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z \
  --sub-account rsi_universal --strategy rsi_universal \
  --rate-per-interval 0.0001 --interval-hours 8
```

This 1bp/8h scenario is not an estimate of historical signed funding and does
not certify profitability. All twelve account reports matched prior arithmetic
and retained input hashes. The 1,247 joined closes are covered; actual funding
is null throughout. Evidence:
`aidlc-docs/construction/strategy-framework/code/debt-089-snapshot-verification.json`.

## Why prerequisite issues recur

The main gap was cross-component evidence continuity, not a lack of individual
unit tests. Earlier fixes verified the component they changed; they did not
always verify the complete path from a real account's close, through persistence,
to the next proposal and operator interpretation. A large passing suite therefore
did not establish these specific end-to-end invariants.

| Finding | Historical evidence | Why earlier tests could miss it |
|---------|---------------------|--------------------------------|
| 087 | `0403166` (2026-05-03) split account storage but omitted scope in historical selectors/live checks; `85a33b0` (05-08) fixed account-scoped close writes | Proposal fixtures keyed mocked performance only by strategy name. Writer tests asserted beta file creation/direct beta read, not the next proposal read. Composition tests existed, but patched PerformanceTracker for other concerns. This is an old latent defect, not evidence of a recent regression. |
| 088 | `8ad28a8` (05-13) reduced classification to `state == monitorable` | Classifier tests correctly covered legacy-no-link; cap tests supplied a performance ID and checked payload field presence. They did not connect the supported state to the operator boolean. |
| 078 | `6d15fe4` inferred repaired bounds from absent forward ID; `97f8c36` replaced that proxy with actual recovery provenance | An artificial perf-ID fixture made a healthy old row unlike normal runtime opens. This was a real overbroad follow-up correction. The October regression now creates normal paper/live opens. |
| 073→084 | June fee-net work explicitly excluded reclassifying outcome/win rate | The scope exclusion is recorded in `docs/sessions/2026-06-26-strategy-framework-fee-inclusive-edge-metrics.md`. A follow-up economic win-rate contract is distinct, not proof the fee correction failed. |
| 085 vs 087 | Correct rolling/account-denominator arithmetic was added to tuning evidence | Correct aggregate math cannot compensate for a different consumer reading the wrong account. The source and consuming path both need validation. |
| 074 / 086 | Analyze attempts were treated as candidates; unknown gate enum rows were treated as score-accepted | Tests encoded the same interpretation as the implementation. Exhaustive branch/enum coverage cannot validate an incorrect data meaning. Later neutral-stage/unknown-coverage corrections fixed the semantics. |
| 089 | Derivatives-data v1 explicitly excluded funding-cost accounting | This is a known measurement boundary needing honest reporting, not a newly observed cash loss or accounting regression. See the 2026-07-19 derivatives snapshot/replay session. |

Previous analysis also over-grouped newly discovered defects, historical
limitations, and statistical uncertainty as universal prerequisites. That can
make useful strategy research wait for unrelated reporting improvements.
This slice distinguishes them and does not claim that all unknowns can be fixed
by changing code.

## Finite prevention and completion criteria

1. Preserve the three actual-path invariants in regression tests: close→scoped
   score, real no-link open→cap telemetry, persisted fee-net evidence→coverage UI.
2. Record fixed-snapshot values with source/input provenance, not only test counts.
3. At the next analysis, classify observations as new defect, existing open item,
   known historical limitation, or sample/regime uncertainty before opening debt.
4. Do not reopen repaired legacy data gaps without evidence of a new defect.
   June recovery artifacts, old missing regime tags, and absent past funding
   settlements remain declared limitations; they are not silently repaired here.
5. Freeze a prospective cohort after operator-approved deployment. A family's
   clean evidence can proceed to predeclared chart hypotheses and independent
   chronological OOS/walk-forward/regime/sensitivity checks without waiting for
   unrelated UI work. Never tune repeatedly against the same selection window.
6. Operational qualification is separate: verify deployed source SHA and compare
   new proposals' sample counts to actual prior same-account/version closes.
   That original source-only checkpoint had no deployment authorization and made
   no production-fix claim; the subsequent authorized rollout is recorded below.

## Review and verification

- Independent DEBT-087 scope/live-gate QA: no blockers.
- Independent DEBT-088 lead review: additive telemetry only, no risk consumer.
- Quant review of DEBT-089 found mixed-account helper and invalid Decimal CLI
  edge cases; both were corrected and regression-tested, then accepted.
- Focused suites: 087 initial 241 passes plus final 14-test regression file;
  088 13 passes; 089 72 passes (overlapping sets, not an additive total).
- Changed-file Black/Ruff: clean; mypy: 131 source files clean.
- First full run: 2,864 passed, one unrelated Codex child-process cleanup test
  failed with PermissionError. Its isolated rerun passed. Original failure
  retained at `/private/tmp/crypto-master-debt087-089-pytest.log`; no AI runtime
  or test was changed to suppress it.
- Final full rerun: **2,865 passed in 52.83s**, recorded in
  `/private/tmp/crypto-master-debt087-089-pytest-rerun.log`. The first transient
  failure was not reproduced; its exact OS cause is not established.
- All three debts resolved in the approved source/test scope, not deployed.

## Boundaries

The original source-only checkpoint did not include commit, push, deployment,
trading policy activation, a new strategy, or mainnet promotion. Existing
`.claude/settings.local.json` and scheduled-task lock changes are unrelated and
preserved. DEBT-083 and its explicit design/activation gates remain independent.
Actual funding accounting is still outside this slice.

## Subsequent commit and rollout authorization

The user subsequently requested separate commits and pushes, then explicitly
requested deployment and operational verification after all three were complete.
Fetched upstream `1855781` adds only dashboard/runtime-read design documents;
those concurrent documents are preserved. Each correction includes its own
source/tests, plan and debt registration. The final series commit also includes
this combined verification and recurrence record.

The authorized rollout used a clean tracked-source context and preserved the
existing machine, volume, shared CPU / 2048 MiB and paper/Codex settings. It
verified deployed hashes and health, then inspected the first engine cycle and
replayed persisted account-scoped scores read-only.
No trading policy or unrelated DEBT-083 design is activated by this deployment.
The operational follow-up records the final source and observed runtime results.
Deployment completed as Fly v63 / `f0f3e52` on 2026-10-26 KST, with 177 matching
runtime hashes, health/first-cycle pass and read-only deployed-method verification.
See [production rollout](2026-10-26-strategy-evidence-production-rollout.md) for
the exact scope, including no natural proposal/cap event in the first cycle.
