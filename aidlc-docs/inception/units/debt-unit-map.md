# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `ai-feedback-loop` | DEBT-014, DEBT-023, DEBT-049 | 1 Medium, 2 Low | Strategy generation and auto-research regression coverage. |
| `backtesting-validation` | DEBT-014, DEBT-022, DEBT-049 | 1 Medium, 2 Low | Robustness sensitivity, circuit breaker completeness, code-type trade path. |
| `proposal-runtime` | DEBT-016, DEBT-017, DEBT-018, DEBT-052 | 4 Low | Runtime counters/events/tests and notification attribution. |
| `strategy-framework` | DEBT-023, DEBT-026 | 1 Medium, 1 Low | Output-contract preservation and experimental artefact hygiene. |
| `notifications-ops` | DEBT-052 | 1 Low | Per-sub-account routing is deferred. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-014 | Medium | `backtesting-validation` | `ai-feedback-loop` | Design strategy-owned parameter grid or bridge pick-level `param_grid`, then pin sensitivity gate behavior. |
| DEBT-016 | Low | `proposal-runtime` | | Document `CycleResult` accepted/rejected counter semantics. |
| DEBT-017 | Low | `proposal-runtime` | | Remove redundant stale-quote payload key in next dashboard/runtime event pass. |
| DEBT-018 | Low | `proposal-runtime` | | Add `proposals_accepted == 1` assertions to stale-quote rejection tests. |
| DEBT-022 | Low | `backtesting-validation` | | Add cumulative/rate-based parse failure breaker when a real workload needs it. |
| DEBT-023 | Low | `ai-feedback-loop` | `strategy-framework` | Add regression test for preserving `## Output Contract` during improvement. |
| DEBT-026 | Medium | `strategy-framework` | | Restore/regenerate or archive the truncated Donchian experimental artefact; clarify tracking policy. |
| DEBT-049 | Low | `ai-feedback-loop` | `backtesting-validation` | Add code-type integration fixture that emits a trade-producing long/short signal. |
| DEBT-052 | Low | `proposal-runtime` | `notifications-ops` | Add optional per-sub-account notification routing config when operationally needed. |

## Promotion Candidates

The strongest near-term candidates are:

1. **DEBT-014** (`backtesting-validation`, Medium): makes robustness admission
   more trustworthy by restoring the sensitivity gate.
2. **DEBT-026** (`strategy-framework`, Medium): cleans up a broken experimental
   artefact and clarifies whether generated strategies should be tracked.
3. **DEBT-016 + DEBT-018** (`proposal-runtime`, Low pair): cheap documentation
   and test pin for runtime proposal counter semantics.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.
