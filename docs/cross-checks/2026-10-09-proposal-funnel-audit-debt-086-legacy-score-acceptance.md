# Unit cross-check: DEBT-086

- Unit: `proposal-funnel-audit`
- Requirements / stories: FR-013, FR-014, FR-029, FR-043, NFR-007, NFR-012; US-005, US-006, US-012
- Plan: `aidlc-docs/construction/plans/proposal-funnel-audit-debt-086-plan.md`
- Authorization: operator requested implementation of the five registered findings, a separate worktree, and commit/push after each completed item.

## Result

Legacy unknown states no longer count as observed score acceptance. Dashboard summaries share the canonical acceptance total, include every record once in the generated denominator, and show unknown coverage separately; stored history and the legacy raw gate total remain unchanged.

## Verification

32 focused funnel/dashboard tests and the final 2669-test full suite pass (226.93s). Black/Ruff pass on all 30 Python files changed across the five corrections; mypy passes for 123 source files. Frozen default replay verifies 1796 account-directory unknowns (1739 explicit score rejections), plus 112 root legacy rows: 1908 unknown and zero observed acceptance. Mixed/shadow/scored denominators, all enum terminals, unknown-only data and read-only history are covered.

## Scope and remaining work

The five approved corrections (DEBT-084, DEBT-085, DEBT-078, DEBT-074, DEBT-086) were reviewed together and pass final regression. Existing opened/fill semantics remain outside DEBT-086. No historical terminal is guessed or rewritten, and no operator runtime data or production deployment was changed. Work is isolated from the original dirty checkout; unrelated DEBT-082 and dashboard design work are preserved.

DEBT-086 is resolved in source. Deployment is outside this task; no current production behavior change is claimed.
