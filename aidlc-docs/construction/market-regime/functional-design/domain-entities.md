# Domain Entities: Funding+OI Crowding Filter

## Crowding classification

`FundingOiCrowdingClassification` is an immutable decision-time value:

| Field | Meaning |
|---|---|
| `state` | `crowded_long`, `crowded_short`, `neutral`, or `unavailable` |
| `as_of` | UTC proposal decision boundary |
| `funding_rate` | Latest settled rate, never predicted Funding |
| `funding_low_threshold` / `funding_high_threshold` | Deterministic nearest-rank thresholds |
| `funding_point_count` | Settled observations used |
| `oi_latest` / `oi_reference` | Current and 24h reference OI value |
| `oi_delta` | `oi_latest - oi_reference` |
| `reason` | Stable explanation for neutral/unavailable outcomes |

The value contains no raw response, credential, URL, or exception text.

## Account policy

`FundingOiFilterPolicy` belongs to one `SubAccount` and is immutable.

| Field | Default | Rule |
|---|---:|---|
| `enabled` | `false` | No evaluation or behavior change when false |
| `action` | `shadow` | Initial release supports observation only |
| `funding_window_days` | `30` | Whole days, bounded by retained history |
| `funding_low_percentile` | `0.05` | Below 0.5 |
| `funding_high_percentile` | `0.95` | Above 0.5 and above low percentile |
| `oi_lookback_hours` | `24` | Positive whole hours |

`proposal.symbol` is always the data reference. The policy does not introduce
another symbol-routing field.

## Evidence result

`FundingOiEvidenceResult` joins proposal replay and pinned snapshot evidence.
It reports `qualified`, `insufficient_evidence`, or `failed`, the two
expectancy deltas, sample sizes, represented regime buckets, snapshot replay
identity, and stable failure reasons. A runtime veto may reference only a
validated `qualified` result; operator assertion alone is not evidence.

## Relationships

```text
SubAccount 1 -- 1 FundingOiFilterPolicy
Proposal 1 -- 0..1 FundingOiCrowdingClassification
Classification 1 -- 1 ShadowActivityEvent
EvidenceResult 1 -- 1 ProposalReplayReport
EvidenceResult 1 -- 1 PinnedSnapshotReport
```
