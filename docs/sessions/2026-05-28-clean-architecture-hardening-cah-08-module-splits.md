# Session: clean-architecture-hardening CAH-08 — TIER 3 MODULE SPLITS (PURE FILE MOVES + BACK-COMPAT RE-EXPORTS, NO LOGIC CHANGE)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-08 (Tier 3 module splits: `performance.py` → `performance.py` + `trade_history.py` [STRAT-F1]; replay shared logic `tools` → `proposal/replay.py` [LAYER-F5]).

> EIGHTH unit shipped from the `clean-architecture-hardening` plan, and the FIRST of the Tier 3 module
> splits (after the standalone Tier 0 bugfix CAH-01, the three Tier 1 quick wins CAH-02 order-side
> helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-dedup sweep, and the three Tier 2 method
> extractions CAH-05 `_handle_proposal` finalize helpers / CAH-06 long-function splits / CAH-07 LSP
> uniform `analyze()` signatures). This unit is a pure Tier-3 relocation — byte-identical moved bodies,
> zero logic change — so it carried no quant review; qa-reviewer alone. CAH-09…CAH-15 remain planned.

## Scope

CAH-08 is a behavior-preserving module decomposition: it splits two oversized modules along their natural
seams, moving symbols verbatim and preserving every old import path via back-compat re-exports. No logic
changed; the moved bodies are byte-identical to their pre-move form.

### Part A — STRAT-F1: split `src/strategy/performance.py` (1313 lines)

`TradeHistory` + `TradeHistoryTracker` + `DEFAULT_TRADES_DIR` were moved **verbatim** into a NEW
`src/strategy/trade_history.py`. `TradeOutcome` was **KEPT** in `performance.py` — a usage analysis found
it referenced 10× in `performance.py` and 0× in the trade-history code, so moving it would have created
churn with no cohesion gain. This deviates from the plan's wording (which grouped `TradeOutcome` with the
history symbols) but is usage-justified and recorded in Key Decisions.

Back-compat re-exports were added in BOTH `strategy/__init__.py` and `performance.py`: `performance.py`
re-imports the trio (`TradeHistory`, `TradeHistoryTracker`, `DEFAULT_TRADES_DIR`) from `trade_history`
at module end (`# noqa: E402`), so all three old import paths resolve to the SAME class objects:

- `from src.strategy.performance import TradeHistory, ...` (legacy path)
- `from src.strategy import TradeHistory, ...` (package path)
- `from src.strategy.trade_history import TradeHistory, ...` (new canonical path)

No circular import: `trade_history` imports only `DEFAULT_SUB_ACCOUNT_ID` from `performance`, and
`performance`'s re-import of the trio sits at module end after that symbol is defined. Zero production
importer edits were required — the re-exports absorb the move entirely.

### Part B — LAYER-F5: move replay shared logic out of `tools`

`build_scenarios` + `load_replay_input` were moved **verbatim** from `src/tools/proposal_replay.py` to
`src/proposal/replay.py` (the proper layer — shared logic belongs in `proposal/`, not in an operator CLI
tool). Both importers were updated: the dashboard page `src/dashboard/pages/replay.py` and the CLI tool
`src/tools/proposal_replay.py` itself. The CLI tool was thinned to import the relocated functions; its
`argparse` `main` entry point is intact.

## Process / verdicts

senior-developer implemented → qa-reviewer 🟢. No quant escalation: this is a pure Tier-3 relocation with
byte-identical moved bodies and zero logic change (no trading math, no signal / gate / sizing path touched).

### QA 🟢

qa-reviewer returned 🟢: **2258 passed, unchanged** (0 test delta — pure relocation, the existing suites
are the behavior-preservation proof); ruff + mypy clean across 91 source files. The moved bodies are
byte-identical. A runtime identity check confirms `from src.strategy.performance import TradeHistory...`,
`from src.strategy import ...`, and `from src.strategy.trade_history import ...` all resolve to the SAME
class objects. All 13 importers verified unbroken; no import cycle. The `TradeOutcome`-stays decision is
usage-justified (10× in `performance.py`, 0× in trade-history). Part B functions relocated and BOTH
importers updated; the CLI `argparse` entry point is intact.

## Files Changed

- **Created**:
  - `src/strategy/trade_history.py` — NEW module holding the verbatim `TradeHistory` +
    `TradeHistoryTracker` + `DEFAULT_TRADES_DIR` (imports only `DEFAULT_SUB_ACCOUNT_ID` from
    `performance`, so no cycle).
- **Modified**:
  - `src/strategy/performance.py` — trio removed (now lives in `trade_history.py`); back-compat
    re-import of the trio from `trade_history` appended at module end (`# noqa: E402`); `TradeOutcome`
    KEPT here (usage-justified).
  - `src/strategy/__init__.py` — back-compat re-export so the package path still resolves the trio.
  - `src/proposal/replay.py` — received the verbatim `build_scenarios` + `load_replay_input`.
  - `src/tools/proposal_replay.py` — `build_scenarios` / `load_replay_input` removed; now imports them
    from `proposal/replay.py`; CLI thinned, `argparse` `main` intact.
  - `src/dashboard/pages/replay.py` — importer updated to the new `proposal/replay.py` location.
  - `tests/test_tools_proposal_replay.py` — mechanically-necessary import path update (Part B move).
  - `tests/test_strategy_performance.py` — mechanically-necessary import path update (Part A move).

Two test files carry import-path edits only — they are mechanically necessary because the symbols moved
modules, not behavioral test changes. No `src/` LOGIC was touched (only the relocations + re-exports).

## Key Decisions

| Decision | Rationale |
|---|---|
| Keep `TradeOutcome` in `performance.py` rather than move it with the history symbols | Usage analysis: `TradeOutcome` is referenced 10× in `performance.py` and 0× in the trade-history code. Moving it would create import churn (and a back-reference into `performance`) with no cohesion gain. This deviates from the plan's wording, which grouped it with the history trio, but the deviation is usage-justified — the cohesive unit that moves is `TradeHistory` + `TradeHistoryTracker` + `DEFAULT_TRADES_DIR`. |
| Back-compat re-exports in BOTH `strategy/__init__.py` and `performance.py` | The trio had multiple legacy import paths in use. Re-exporting from both the package and the old module keeps every old path resolving to the SAME class objects, so zero production importers needed editing — the move is invisible to callers. |
| Re-import the trio at `performance.py` module end with `# noqa: E402` | The re-import must follow the definition of `DEFAULT_SUB_ACCOUNT_ID` (which `trade_history` imports from `performance`), so it sits at module end; `# noqa: E402` documents the deliberate late import and silences the import-not-at-top lint. This is what guarantees no circular import. |
| Move `build_scenarios` + `load_replay_input` to `proposal/replay.py`, thin the CLI tool | Shared replay logic belongs in the `proposal/` layer, not buried in an operator CLI tool that the dashboard also had to reach into. Both importers (dashboard page + the CLI tool itself) were updated; the CLI `argparse` entry point stays in `tools`. |
| Verbatim moves — byte-identical bodies | The whole point of a Tier-3 split is relocation without behavioral risk. Keeping the bodies byte-identical lets the existing suites stand as the behavior-preservation proof and keeps this out of quant scope. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2258 passed (no net change from the 2258 CAH-07 baseline)**, 0 failed.
- `ruff check`: clean.
- `mypy`: clean — 91 source files.
- Runtime identity check: the three import paths
  (`from src.strategy.performance import TradeHistory...`, `from src.strategy import ...`,
  `from src.strategy.trade_history import ...`) all resolve to the SAME class objects.
- Import-graph: all 13 importers verified unbroken; no import cycle introduced
  (`trade_history` imports only `DEFAULT_SUB_ACCOUNT_ID` from `performance`).

## Potential Risks

- **The back-compat re-exports are the contract that keeps old import paths alive.** Removing the
  re-import at the end of `performance.py` or the re-export in `strategy/__init__.py` would silently break
  the legacy `from src.strategy.performance import TradeHistory` and `from src.strategy import TradeHistory`
  paths for any importer not yet migrated to the canonical `src.strategy.trade_history` path. The 13
  importers are unbroken today via these shims; a future cleanup that drops the shims must first migrate
  every importer to the canonical path.
- **The `TradeOutcome`-stays decision is usage-driven and could drift.** If future work adds
  `TradeOutcome` consumers inside `trade_history.py`, the cohesion calculus that justified keeping it in
  `performance.py` flips, and the symbol may want to move (or be hoisted to a shared module). It is
  recorded here so a later reader understands why it deviates from the plan's grouping.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-08. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` for the audit trail (the first Tier 3 module split: pure verbatim file
moves + back-compat re-exports, byte-identical bodies, 0 test delta).

## Remaining Work

CAH-09…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-09 (Tier 3 dashboard module decomposition)** — split `src/dashboard/pages/engine.py` (1864 lines)
into sibling panel modules + move the `app.py` Home command-center to `pages/home.py`; pure moves +
re-export, with import-cycle care (`trading.py` imports 3 reconciliation symbols from `engine.py`).

No ADR needed — CAH-08 is a focused Tier 3 module split. It introduces no new component boundary in the
architectural sense (the moved symbols keep their existing contracts via verbatim relocation + back-compat
re-exports; callers are unaffected), locks in no new constraint future work must respect beyond the
pre-existing public symbol surface, and chooses between no competing long-term designs (the
`TradeOutcome`-stays call and the re-export shims are local cohesion / back-compat judgements recorded in
the Key Decisions table). The audit value lives in this session log and the Change-History row, not in an
ADR.
