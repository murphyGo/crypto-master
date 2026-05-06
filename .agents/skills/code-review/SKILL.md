---
name: code-review
description: Review Crypto Master code changes for correctness, trading safety, data integrity, and maintainability.
---

# Crypto Master Code Review Skill

## Arguments

- `$ARGUMENTS`
  - `git`: review changed files
  - `files:<paths>`: review explicit files
  - `dir:<path>`: review a directory
  - `unit:<unit>`: review files owned by a brownfield unit

## Objective

Find real issues in changed code, prioritizing correctness, trading safety,
data integrity, failure modes, and test gaps.

## Pre-Review

Read:

1. `aidlc-docs/inception/requirements/requirements.md`
2. `aidlc-docs/inception/requirements/requirement-verification-questions.md`
3. `aidlc-docs/inception/user-stories/stories.md`
4. `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
5. `aidlc-docs/inception/units/unit-of-work.md`
6. `aidlc-docs/inception/units/legacy-phase-map.md` when old phases or
   historical components are referenced
7. `aidlc-docs/inception/units/debt-unit-map.md` when reviewing debt-related
   changes
8. related detailed requirement text in `docs/requirements.md`
9. related design in `DESIGN.md`
10. current debt in `docs/TECH-DEBT.md`

For `git`, identify changed files with:

```bash
git diff --name-only HEAD
git diff --name-only --cached
```

## Review Focus

1. **Trading correctness**: position sizing, leverage, fees, liquidation, PnL,
   stale quotes, acceptance gates.
2. **Data integrity**: atomic writes, JSON/JSONL contracts, timestamp timezone,
   backward compatibility with existing runtime files.
3. **Exchange safety**: credentials, live-vs-paper separation, rate limits,
   explicit live trading intent.
4. **AI boundary**: Claude CLI timeouts, parsing, prompt contracts, generated
   strategy validation.
5. **Backtest validity**: snapshot determinism, robustness gates, leakage,
   OOS/walk-forward/regime assumptions.
6. **Operator visibility**: dashboard and notification states for failures.
7. **Tests**: targeted tests for success, error, and compatibility paths.

## Output

Lead with findings, ordered by severity. Use file and line references. If no
issues are found, say so and note residual test or operational risk.

For actionable unresolved findings, suggest whether they should be fixed now or
tracked in `docs/TECH-DEBT.md`.
