# Requirement Verification Questions

Use these questions when planning, reviewing, or cross-checking AI-DLC work.
They convert the brownfield requirements into practical verification prompts.

## Trading Safety

| Question | Related Requirements |
|----------|----------------------|
| Does the change preserve explicit operator intent before live trading? | FR-009, NFR-012, CON-003 |
| Does live mode fail fast when required credentials are missing? | FR-009, FR-037, NFR-011 |
| Does paper mode remain available without live credentials? | FR-010, FR-036 |
| Are position sizing, leverage, fees, and PnL calculations covered by targeted tests? | FR-006, FR-007, NFR-007 |
| Can a drawdown or rejected cap decision in one sub-account affect another sub-account? | FR-036 |

## Strategy Quality

| Question | Related Requirements |
|----------|----------------------|
| Does a generated technique declare a falsifiable market hypothesis? | FR-033 |
| Does promotion require the robustness gate and surface skipped or failed gates? | FR-034 |
| Does an improvement prompt start with structural failure analysis rather than adding conditions blindly? | FR-035 |
| Can a new technique be added as a file without changing the loader or factory? | FR-003, FR-004, NFR-010 |
| Is strategy performance recorded and attributable to the technique that produced it? | FR-005, FR-021 |

## Proposal and Runtime

| Question | Related Requirements |
|----------|----------------------|
| Are proposals persisted with accept/reject decisions and final outcomes? | FR-013, FR-014 |
| Does the runtime preserve stale-quote, cap, and operator gates before execution? | FR-011, FR-012, FR-026 |
| Are runtime activity events durable enough for dashboard and audit use? | FR-014, NFR-007, NFR-008 |
| Do notifications report actionable opportunities without bypassing approval gates? | FR-015, CON-003 |

## Persistence and Data Integrity

| Question | Related Requirements |
|----------|----------------------|
| Are writes atomic or otherwise safe against partial JSON/JSONL corruption? | NFR-006, NFR-007, NFR-008 |
| Are timestamps timezone-aware and consistent across runtime, trading, and audit records? | NFR-007, NFR-008 |
| Are runtime data paths compatible with legacy single-account state and sub-account state? | FR-036, NFR-008 |
| Is operator/runtime data under `data/` preserved during documentation or migration work? | NFR-006, NFR-007, NFR-008 |

## Exchange and Operations

| Question | Related Requirements |
|----------|----------------------|
| Does the exchange abstraction keep Binance and Bybit behavior consistent? | FR-016, FR-017, FR-019 |
| Would adding Tapbit require only an adapter and narrow tests? | FR-018, FR-019, NFR-009 |
| Are exchange credentials kept out of source and logs? | NFR-004, NFR-011 |
| Does deployment or startup behavior keep live trading conservative by default? | FR-009, NFR-012 |

## Dashboard and Operator Visibility

| Question | Related Requirements |
|----------|----------------------|
| Can the operator see active positions, balances, and PnL without reading raw files? | FR-029, FR-031 |
| Are strategy status and feedback-loop progress visible from the dashboard? | FR-028, FR-030 |
| Does the UI distinguish paper, live, and sub-account state clearly? | FR-010, FR-036, FR-038 |

## AI-DLC Governance

| Question | Related Requirements |
|----------|----------------------|
| Is the target unit identified before implementation begins? | All |
| Is the relevant construction stage selected before code changes? | All |
| Are session logs, cross-checks, and TECH-DEBT updated when the change warrants it? | All |
| Is any unresolved gap linked to `docs/TECH-DEBT.md` instead of left as an untracked TODO? | All |
