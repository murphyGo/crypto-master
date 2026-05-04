# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `ai-feedback-loop` | DEBT-023, DEBT-049 | 2 Low | Strategy generation and auto-research regression coverage. |
| `backtesting-validation` | DEBT-022, DEBT-049 | 2 Low | Circuit breaker completeness and code-type trade path. |
| `proposal-runtime` | DEBT-052 | 1 Low | Notification attribution/routing. |
| `strategy-framework` | DEBT-023 | 1 Low | Output-contract preservation. |
| `notifications-ops` | DEBT-052 | 1 Low | Per-sub-account routing is deferred. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-022 | Low | `backtesting-validation` | | Add cumulative/rate-based parse failure breaker when a real workload needs it. |
| DEBT-023 | Low | `ai-feedback-loop` | `strategy-framework` | Add regression test for preserving `## Output Contract` during improvement. |
| DEBT-049 | Low | `ai-feedback-loop` | `backtesting-validation` | Add code-type integration fixture that emits a trade-producing long/short signal. |
| DEBT-052 | Low | `proposal-runtime` | `notifications-ops` | Add optional per-sub-account notification routing config when operationally needed. |

## Promotion Candidates

No Medium-or-higher active debt remains in this map. The next candidates are
Low-priority hardening items selected by operational need.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.
