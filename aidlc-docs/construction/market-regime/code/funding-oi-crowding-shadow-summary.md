# Code Summary: Funding+OI Crowding Shadow Filter

## Outcome

The `market-regime` unit now has a disabled-by-default, per-sub-account
Funding+OI crowding observer. It classifies the Funding-paying side from
settled 30-day Funding percentiles plus rising 24-hour OI, records the
side-aware decision as sanitized activity telemetry, and shows the result in
the Engine dashboard. The release is structurally shadow-only: configuration
cannot select a veto action and runtime never changes a proposal, position,
order, balance, or execution counter because of this signal.

## Generated application code

- `src/runtime/funding_oi_filter.py`
  - immutable classification and evidence models;
  - pure nearest-rank Decimal percentile classifier;
  - side-aware `would_block` helper;
  - fail-closed dual-lane evidence qualifier for a future veto slice.
- `src/trading/sub_account.py`
  - frozen `FundingOiFilterPolicy`, disabled by default;
  - only `action="shadow"` is accepted in the initial schema.
- `src/runtime/activity_events.py`
  - allowlisted observed and skipped event types.
- `src/runtime/engine.py`
  - observation after correlation/OHLCV regime gates and before sizing/risk;
  - existing in-memory `DerivativesContextService` read at proposal `as_of`;
  - missing/stale/short/error context fails open with sanitized telemetry.
- `src/dashboard/pages/engine_market_regime.py` and `engine.py`
  - pure summary/table read models and an explicit
    `SHADOW — NOT ENFORCING` surface.

## Safety properties

- No new network or filesystem read occurs in the proposal gate. Runtime uses
  the already-refreshed process-local derivatives context cache.
- Predicted Funding is excluded. Every settled Funding/OI input is bounded by
  `MarketContext.as_of`.
- Missing context never blocks. Provider exceptions serialize only their
  class name, not the message, raw response, URL, path, or credential.
- A future veto is not a configuration switch. The model rejects `action=veto`
  and evidence qualification requires both proposal-history replay and a
  pinned Snapshot-v2 lane with identity, digest, seed, nonzero samples,
  non-negative expectancy deltas, and regime diversity.

## Verification at generation completion

- Changed-file Black/Ruff: pass.
- Focused classifier/gate-reason/policy/runtime/dashboard suite: 317 passed.
- Classifier envelope: 90 Funding + 500 OI, 100 runs, p95 0.000064s against
  the 0.005s requirement.
- Focused module coverage: 91% for `src/runtime/funding_oi_filter.py`.
- Complete repository: 2604 passed in 45.09s.
- `mypy src`: 114 source files, zero issues.
- Lock, compile, offline import, whitespace, dependency, deployment, and
  runtime-data scope checks: pass.

No new technical debt was found. Existing repository-wide format/lint drift
remains DEBT-081 and does not overlap this slice.
