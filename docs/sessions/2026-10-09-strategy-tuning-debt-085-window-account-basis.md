# Implementation session: DEBT-085

- Unit: `strategy-tuning`
- Requirements / stories: FR-005, FR-029, FR-036, NFR-007; US-002, US-012, US-019
- Plan: `aidlc-docs/construction/plans/strategy-tuning-debt-085-plan.md`
- Authorization: operator requested implementation of the five registered findings, a separate worktree, and commit/push after each completed item.

## Result

Recommendations now use UTC-ordered last-N closed real records, net quote-amount PF/win rate, initial-account-capital return and equity-peak drawdown. Dashboard and observations share the per-strategy window and explicit capital/currency/coverage contract; incomplete economic evidence cannot drive economic recommendations.

## Verification

391 strategy/dashboard tests pass, including account-capital and window boundaries, unknown records, legacy aggregate rejection and persisted basis metadata. Changed-file Black/Ruff and source mypy pass (123 files). Frozen Raschke last-30 replay gives +1.7761413511% on 10000 USDT, PF 1.741436 and net win rate 60%.

## Scope and remaining work

The initial-capital benchmark does not reconstruct window-opening cash equity or deposits. Legacy labels/percent aggregates remain readable, and old observation records are marked as lacking an economic basis. Fail-closed-rate pause and seed guidance remain available. No policy thresholds, applied actions, runtime data, account funds, live orders or deployment changed. The full 2628-test baseline passed for DEBT-084; this item ran all dashboard/tuning/performance consumers rather than repeating unrelated expensive backtest scenarios.

DEBT-085 is resolved in source. Deployment is outside this task; no current production behavior change is claimed.
