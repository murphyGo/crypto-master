# Frontend Components: Funding+OI Crowding Filter

## Component hierarchy

```text
Engine / Market Regime
  FundingOiCrowdingSummary
    CurrentClassificationTable
    AccountPolicyTable
    ShadowImpactMetrics
    RecentShadowEventsTable
    EvidenceStatusPanel
```

## Read models

- Current classification: symbol, state, settled Funding, p05/p95, OI delta,
  observed time.
- Account policy: sub-account, enabled, action, last decision.
- Shadow impact: evaluated, would-block, skipped, with percentages and sample
  labels.
- Recent events: proposal, signal, crowding state, would-block, reason.
- Evidence status: `not_run`, `insufficient_evidence`, `failed`, `qualified`.

## Interaction and safety

The initial dashboard is read-only. It exposes no veto toggle. All shadow
surfaces display `SHADOW — NOT ENFORCING`. Missing fields render as unavailable
without inventing zeros. Event parsing uses an allowlist and ignores unrelated
activity rows.

## Future veto control

A later evidence-qualified slice may add a confirmation-gated action change.
That control must show evidence identity and qualification before allowing
`veto`; a page rerun must not repeat the mutation.
