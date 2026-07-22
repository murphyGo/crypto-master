# Logical Components: Funding+OI Crowding Filter

## Components

1. `FundingOiCrowdingClassifier`
   - Pure domain calculation over `MarketContext`.
2. `FundingOiFilterPolicy`
   - Frozen per-sub-account disabled-by-default configuration.
3. Runtime shadow gate
   - Retrieves proposal-symbol context at proposal `as_of`, projects one safe
     event, and passes the proposal through unchanged.
4. Dashboard read model
   - Produces current classifications, aggregate shadow impact, and recent
     observation tables.
5. Evidence validator
   - Combines proposal-replay and pinned-snapshot summaries and returns an
     explicit qualification status.

## Dependency direction

```text
exchange normalized models
  -> pure classifier
  -> runtime shadow gate -> activity log -> dashboard read model
  -> replay/backtest consumers -> evidence validator
```

The classifier never imports runtime engine, dashboard, storage, or exchange
adapters. Policy models do not import the runtime layer.

## Failure mapping

| Failure | Result |
|---|---|
| Provider absent/throws | pass through + sanitized skip |
| Insufficient Funding/OI | pass through + unavailable classification |
| Classifier validation error | pass through + sanitized skip |
| Dashboard malformed row | ignore row; preserve page rendering |
| Evidence missing/mixed/unpinned | `insufficient_evidence` |
| Negative expectancy delta | `failed` |

## Infrastructure decision

N/A. All components are in-process and reuse existing context, activity-log,
snapshot, and dashboard surfaces.
