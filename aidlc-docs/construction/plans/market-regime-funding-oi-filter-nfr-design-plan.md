# NFR Design Plan: Funding+OI Crowding Filter

## Context

- Unit: `market-regime`
- Stage: NFR Design
- Input: `aidlc-docs/construction/market-regime/nfr-requirements/`

## Approved recommendations

- Resilience: fail-open adapter around a pure classifier; stable skip event.
  [Answer]: Approved.
- Scalability: reuse per-cycle context and bounded inputs; no extra I/O.
  [Answer]: Approved.
- Performance: linear bounded selection plus `O(n log n)` sort at n<=90.
  [Answer]: Approved.
- Security: derived-field allowlist and no raw exception serialization.
  [Answer]: Approved.
- Logical components: classifier, policy, shadow gate, read model, evidence
  validator. [Answer]: Approved.

## Steps

- [x] Define resilience, performance, security, and determinism patterns.
- [x] Define logical components and ownership boundaries.
- [x] Confirm Infrastructure Design N/A.
- [x] Hand off to Code Generation.
