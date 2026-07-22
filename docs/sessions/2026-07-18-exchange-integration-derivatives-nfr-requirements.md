# Session: exchange-integration Derivatives NFR Requirements

**Date:** 2026-07-18

**Unit:** `exchange-integration`

**Stage:** NFR Requirements
**Status:** Approved; NFR Requirements complete

## Scope

Defined the measurable non-functional requirements and technology constraints
for FR-046 / US-025 funding-rate and open-interest collection, runtime
`MarketContext`, snapshot-v2 persistence, and deterministic replay.

## Operator decisions

The operator answered **all recommended**, selecting option (a) for Q1-Q11:

- four-symbol validation plus a 20-symbol ceiling;
- p95 derivatives latency <= 5s at four symbols and <= 15s at 20;
- funding 9h, OI 2h, and predicted-funding one-cycle cache limits;
- partial per-series context;
- two transient retries and a one-cycle circuit after three failed refreshes;
- ccxt rate limiting plus concurrency four, request dedupe, and <=50% venue
  allowance;
- OHLCV-only fail-open runtime and atomic last-known-good snapshots;
- structured activity events and existing Ops Diagnostics;
- public unauthenticated normalized data only;
- no new production dependency and offline deterministic CI;
- complete settled funding plus the explicit contiguous OI retained suffix,
  with no interpolation.

## Primary-source verification

Reviewed current Binance USDⓈ-M market-data documentation and the ccxt Manual.
The documented funding-history allowance, OI history one-month retention,
supported 1h period, page maxima, current-OI weight, ccxt rate limiter, and
unified derivatives methods were used to bound the NFRs.

## Artifacts

- `aidlc-docs/construction/plans/exchange-integration-nfr-requirements-plan.md`
- `aidlc-docs/construction/exchange-integration/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/exchange-integration/nfr-requirements/tech-stack-decisions.md`

## Validation

- Documentation traceability and answer-count checks.
- Markdown/whitespace validation with `git diff --check` plus explicit checks
  for the untracked NFR artifacts.
- No application tests: this stage changes documentation only.
- No new technical-debt item: Binance retention and adjusted funding intervals
  are explicit v1 constraints with required safe behavior.
- Unit cross-check remains deferred until the complete derivatives-data unit
  has implementation evidence.

## Next step

The operator approved progression with `다음 단계 진행` at
2026-07-18 05:24:01 KST. The NFR audit record and AI-DLC state were updated;
proceed to NFR Design.
