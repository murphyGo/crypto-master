# DEBT-085 rolling account-base recommendation evidence

- Unit: `strategy-tuning`; secondary strategy-framework, dashboard-operator-ui.
- Requirements: FR-005, FR-029, FR-036, NFR-007; US-002, US-012, US-019.
- Stages: bounded Functional Design, NFR/data-integrity notes, Code Generation, Build and Test.
- Legacy: DEBT-069, DEBT-073; dependency DEBT-084.
- Authorization: operator approved the bounded registered fixes and requested implementation/commit/push per item.
- [Answer]: use configured account initial quote capital; preserve thresholds and applied policy; do not infer capital from summed trade returns.

- [x] Specify the rolling-window, capital-base and incomplete-evidence contracts.
- [x] Build record-based net quote-PnL/PF/win-rate/drawdown evidence and wire dashboard/observation consumers.
- [x] Test last-N overrides, ordering, fees/notional/capital variation, missing data, synthetic/open exclusion, recommendation boundaries and frozen Raschke replay.
- [x] Run focused pytest, changed-file Black/Ruff, source mypy.
- [x] Close debt/map/state with session and cross-check evidence.
