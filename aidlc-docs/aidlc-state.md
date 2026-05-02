# AI-DLC State Tracking

## Project Information

- **Project Name**: Crypto Master
- **Project Type**: Brownfield
- **Overlay Created**: 2026-05-03
- **Current Stage**: INCEPTION - Brownfield Reverse Engineering Complete
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
| Execution Plan | Complete | `aidlc-docs/inception/plans/execution-plan.md` |

## Unit Progress

| Unit | Existing Implementation | AI-DLC State | Next Action |
|------|-------------------------|--------------|-------------|
| `exchange-integration` | Complete | Reverse-engineered | Track future exchange changes here |
| `strategy-framework` | Complete | Reverse-engineered | Track future strategy loader/indicator changes here |
| `trading-core` | Complete | Reverse-engineered | Track future paper/live/risk math changes here |
| `backtesting-validation` | Complete | Reverse-engineered | Track future robustness/baseline changes here |
| `ai-feedback-loop` | Complete | Reverse-engineered | Track future Claude/improver loop changes here |
| `proposal-runtime` | Complete | Reverse-engineered | Track future proposal/runtime cycle changes here |
| `dashboard-operator-ui` | Complete | Reverse-engineered | Track future Streamlit/operator UI changes here |
| `notifications-ops` | Complete | Reverse-engineered | Track future notification/deployment changes here |
| `sub-account-capital-segmentation` | Complete | Reverse-engineered | Track future capital isolation changes here |
| `persistence-data-integrity` | Complete | Reverse-engineered | Track future timestamp/atomic persistence changes here |
| `quality-governance` | Complete | Reverse-engineered | Track future AI-DLC hygiene, debt, and review changes here |

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

## Legacy References

- Chronological plan: `docs/development-plan.md`
- Requirements: `docs/requirements.md`
- Architecture: `DESIGN.md`
- Project guide: `CLAUDE.md`
- Debt registry: `docs/TECH-DEBT.md`
- Session logs: `docs/sessions/`
- Cross-checks: `docs/cross-checks/`

