# Business Logic Model: Funding+OI Crowding Filter

## Runtime flow

```text
score accepted
  -> correlation gate
  -> existing OHLCV market-regime gate
  -> load proposal-symbol MarketContext at decision as_of
     -> unavailable: emit skip, pass through
     -> classify trailing settled Funding + 24h OI change
        -> emit shadow observation
        -> action=shadow: pass through
        -> future action=veto + qualified evidence + side match: reject
  -> existing sizing and risk gates
```

## Classifier algorithm

1. Validate UTC `as_of` and same-symbol normalized context.
2. Select settled Funding in `[as_of - window, as_of]`.
3. Require 90 observations for the default 30-day/8h window.
4. Compute nearest-rank p05 and p95 over sorted rates.
5. Select latest OI and the latest point at or before `as_of - 24h`; require
   the reference within one 1h interval.
6. `oi_rising = latest > reference`.
7. Positive `latest_funding >= p95` plus `oi_rising` => `crowded_long`.
8. Negative `latest_funding <= p05` plus `oi_rising` => `crowded_short`.
9. Otherwise return `neutral`; incomplete inputs return `unavailable` with a
   stable reason.

## Evidence flow

```text
predeclared configuration
  -> proposal-history replay report
  -> pinned Snapshot-v2 comparison report
  -> validate identities, sample labels, expectancy deltas, regime diversity
  -> qualified | insufficient_evidence | failed
  -> only qualified may unlock a later veto configuration
```

## Error paths

- Context provider absent/throws: fail open, sanitized skip telemetry.
- Short Funding/OI history: fail open as unavailable.
- Snapshot identity absent/mixed: evidence insufficient.
- Negative expectancy delta in either lane: evidence failed.
- Unsupported policy envelope: configuration validation fails at startup.
