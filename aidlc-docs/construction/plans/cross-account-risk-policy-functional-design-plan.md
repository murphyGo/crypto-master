# Functional Design Plan: cross-account-risk-policy

## Task

Define portfolio-level risk controls across strategy-isolated paper accounts:
risk-based sizing, cross-account symbol/side exposure caps, stale-position age
limits, account/global drawdown pauses, and account-tier risk modes.

## Related Context

- Unit: `cross-account-risk-policy`
- Stage: Functional Design
- Requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012
- Source evidence: 2026-05-13 Fly snapshot showed 49,000 USDT gross open
  notional, concentrated ETH longs / BNB shorts / AVAX shorts across many
  accounts, fixed 1,000 USDT sizing, and stop-risk dispersion by strategy.
- Related units: `sub-account-capital-segmentation`,
  `strategy-correlation-governor`, `runtime-safety-score`, `proposal-runtime`

## Steps

- [x] Specify risk-based sizing formula using account risk budget and stop
      distance.
- [x] Specify per-account open-position/notional caps and global symbol/side
      concentration caps.
- [x] Specify stale-position age caps and cap-release behavior.
- [x] Specify account/global kill switches for daily loss, open stop-risk, and
      open unrealized drawdown.
- [x] Create implementation plan covering config schema, policy resolution,
      runtime gates, activity events, dashboard exposure views, and tests.

## Verification

- [x] Design artifact under `aidlc-docs/construction/cross-account-risk-policy/`.
- [x] Target tests identified for sub-account policy parsing, runtime gating,
      and dashboard exposure summaries.

## Completion Checklist

- [x] Functional design complete.
- [ ] Code-generation plan created.
- [ ] Session log and cross-check added when implemented.
