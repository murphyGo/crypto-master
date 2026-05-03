# AI-DLC State Tracking

## Project Information

- **Project Name**: Crypto Master
- **Project Type**: Brownfield
- **Overlay Created**: 2026-05-03
- **Current Stage**: CONSTRUCTION - Brownfield Ready
- **Workspace Root**: `/Users/user/Desktop/Projects/crypto-master`

## Workspace State

- **Existing Code**: Yes
- **Primary Language**: Python 3.10+
- **Build System**: `pyproject.toml`, `uv.lock`, `requirements.txt`
- **Application Shape**: Modular monolith with Streamlit dashboard, runtime
  engine, exchange adapters, strategy framework, backtest engine, proposal
  workflow, and local JSON/JSONL persistence.
- **Reverse Engineering Needed**: No for baseline overlay; rerun when major
  module boundaries change.

## Code Location Rules

- **Application Code**: Workspace root (`src/`, `strategies/`, `scripts/`,
  `tests/`)
- **AI-DLC Documentation**: `aidlc-docs/`
- **Legacy Documentation**: `docs/`, `DESIGN.md`, `CLAUDE.md`
- **Runtime Data**: `data/` is operator/runtime data and must not be migrated
  or deleted by AI-DLC overlay tasks.

## Inception Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Workspace Detection | Complete | `aidlc-docs/aidlc-state.md` |
| Reverse Engineering | Complete | `aidlc-docs/inception/reverse-engineering/` |
| Unit Breakdown | Complete | `aidlc-docs/inception/units/unit-of-work.md` |
| Legacy Phase Crosswalk | Complete | `aidlc-docs/inception/units/legacy-phase-map.md` |
| Debt Unit Map | Complete | `aidlc-docs/inception/units/debt-unit-map.md` |
| Execution Plan | Complete | `aidlc-docs/inception/plans/execution-plan.md` |

## Construction Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Construction Workspace | Ready | `aidlc-docs/construction/` |
| Construction Plan Queue | Ready | `aidlc-docs/construction/plans/` |
| Build and Test Workspace | Ready on demand | `aidlc-docs/construction/build-and-test/` |

Construction artifacts are created just in time for new work. Existing Phase
1-26 implementation is not replayed through construction plans.

## Unit Progress

| Unit | Existing Implementation | AI-DLC State | Next Action |
|------|-------------------------|--------------|-------------|
| `exchange-integration` | Complete | Brownfield-complete; construction-ready | Track future exchange changes in construction plans |
| `strategy-framework` | Complete | Brownfield-complete; construction-ready | Track future strategy loader/indicator changes in construction plans |
| `trading-core` | Complete | Brownfield-complete; construction-ready | Track future paper/live/risk math changes in construction plans |
| `backtesting-validation` | Complete | Brownfield-complete; construction-ready | Track future robustness/baseline changes in construction plans |
| `ai-feedback-loop` | Complete | Brownfield-complete; construction-ready | Track future Claude/improver loop changes in construction plans |
| `proposal-runtime` | Complete | Brownfield-complete; construction-ready | Track future proposal/runtime cycle changes in construction plans |
| `dashboard-operator-ui` | Complete | Brownfield-complete; construction-ready | Track future Streamlit/operator UI changes in construction plans |
| `notifications-ops` | Complete | Brownfield-complete; construction-ready | Track future notification/deployment changes in construction plans |
| `sub-account-capital-segmentation` | Complete | Brownfield-complete; construction-ready | Track future capital isolation changes in construction plans |
| `persistence-data-integrity` | Complete | Brownfield-complete; construction-ready | Track future timestamp/atomic persistence changes in construction plans |
| `quality-governance` | Complete | Brownfield-complete; construction-ready | Track future AI-DLC hygiene, debt, and review changes in construction plans |

## Construction Stage Policy

Existing Phase 1-26 work is not replayed through construction stages. It is
registered as brownfield-complete and mapped into units. New work should be
planned against one or more units using this stage order:

1. Functional Design, if behavior or contracts change.
2. NFR Requirements / NFR Design, if reliability, security, operations,
   latency, persistence, or trading safety changes.
3. Infrastructure Design, if deployment, credentials, runtime process, or
   external service topology changes.
4. Code Generation.
5. Build and Test.
6. Unit cross-check and session log.

New work is tracked in `aidlc-docs/construction/plans/` and unit-specific
subdirectories under `aidlc-docs/construction/`.
`docs/legacy/development-plan.md` is legacy chronology, not the active queue.

## Legacy References

- Chronological plan archive: `docs/legacy/development-plan.md`
- Development plan pointer: `docs/development-plan.md`
- Legacy phase to unit map: `aidlc-docs/inception/units/legacy-phase-map.md`
- Debt to unit map: `aidlc-docs/inception/units/debt-unit-map.md`
- Requirements: `docs/requirements.md`
- Architecture: `DESIGN.md`
- Project guide: `CLAUDE.md`
- Debt registry: `docs/TECH-DEBT.md`
- Session logs: `docs/sessions/`
- Cross-checks: `docs/cross-checks/`
