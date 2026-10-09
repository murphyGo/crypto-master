# Implementation session: DEBT-084

- Unit: `strategy-framework`
- Requirements / stories: FR-005, FR-029, NFR-007; US-002, US-012, US-019
- Plan: `aidlc-docs/construction/plans/strategy-framework-debt-084-plan.md`
- Authorization: operator requested implementation of the five registered findings, a separate worktree, and commit/push after each completed item.

## Result

Added separate fee-net economic win/loss/breakeven/unknown counts and win rate, and switched strategy-summary and recommendation win-rate consumers to them while retaining historical exit-label statistics.

## Verification

211 focused tests; 2628 full-suite tests; changed-file Black/Ruff and mypy (122 source files) pass. Frozen Fly RSI15m replay reproduces 104/201 net winners (51.7413%) versus the retained exit-label rate 2.4876%, with zero unknown economic outcomes.

## Scope and remaining work

The focused tests cover time-stop gains/losses/zero, fee-flipped TP, actual-entry notional, legacy unknown fees, pending/synthetic exclusion, old-summary loading, dashboard labels and recommendation thresholds. Historical percent/PF metrics remain compatible; DEBT-085 owns rolling/account-base recommendation corrections. Original worktree, configuration, runtime data and deployment were untouched.

DEBT-084 is resolved in source. Deployment is outside this task; no current production behavior change is claimed.
