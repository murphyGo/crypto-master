# Session: clean-architecture-hardening CAH-10 — TIER 4 AI / FEEDBACK DIP CLUSTER (LLMClient PORT + ai/exceptions DECOUPLING + prompts.py EXTRACTION + _run_cycle PARAM OBJECT)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-10 (Tier 4 ports / typed contracts: LLMClient port [AI-F1/LAYER-F1] + `ai/exceptions` decoupling [LAYER-F2] + `prompts.py` extraction [AI-F4] + `_run_cycle` param object [AI-F5]).

> TENTH unit shipped from the `clean-architecture-hardening` plan, and the FIRST of the Tier 4 ports /
> typed-contracts units. It follows the standalone Tier 0 bugfix CAH-01, the three Tier 1 quick wins
> (CAH-02 order-side helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-dedup sweep), the three
> Tier 2 method extractions (CAH-05 `_handle_proposal` finalize helpers / CAH-06 long-function splits /
> CAH-07 LSP uniform `analyze()` signatures), and the two Tier 3 module splits (CAH-08 `performance.py`
> split + replay relocation / CAH-09 dashboard decomposition). Like CAH-04, CAH-10 is ONE unit comprising
> FOUR defined sub-items, shipped together as one commit (the project's one-unit-one-commit pattern). It is
> trading-domain-adjacent but carries no trading math — DIP / structural plumbing only — so it carried no
> quant review; qa-reviewer alone. CAH-11…CAH-15 remain planned.

## Scope

CAH-10 is the AI / feedback Dependency-Inversion cluster: it inverts the domain→edge dependency where the
strategy loader and improver previously news-up the concrete `ClaudeCLI` adapter, moves the shared
`StrategyError` base to a neutral module so `ai/exceptions` no longer imports `src.strategy`, extracts the
pure prompt-text builders out of `improver.py`, and collapses the `_run_cycle` parameter list into a frozen
context object. All four sub-items are CAH-10's defined scope and shipped in a single commit.

### Sub-item 1 — AI-F1 / LAYER-F1: `LLMClient` port (DIP)

New `src/ai/ports.py` defines an `@runtime_checkable` `LLMClient` Protocol with `async analyze(prompt) -> dict`
and `async complete(prompt) -> str`, exported from `ai/__init__.py`. `StrategyImprover.__init__(claude: LLMClient | None)`
accepts the port (keeping the `claude or ClaudeCLI()` default so existing callers are unaffected). `PromptStrategy`
now accepts an injected `*, llm_client: LLMClient | None`; its `analyze()` uses the injected client if present
and otherwise falls back to constructing `ClaudeCLI` (the per-strategy timeout override is preserved on the
fallback path). This fixes the domain→edge violation: the loader no longer unconditionally news up the
concrete adapter — the abstraction can be injected, and the concrete `ClaudeCLI` is only the default.

### Sub-item 2 — LAYER-F2: `ai/exceptions` decoupling (neutral exceptions module)

The `StrategyError` base was moved to a NEW neutral `src/exceptions.py`. `strategy/base.py` re-exports it as
the SAME class object — verified by `src.strategy.base.StrategyError is src.exceptions.StrategyError`. With
the base now living in a neutral module, `ai/exceptions.py` imports it from `src.exceptions` and **no longer
imports `src.strategy`**, removing the edge→domain back-edge. `ClaudeTimeoutError`'s catch behavior at
`proposal/engine.py:534` and `:728` is unchanged (same class identity through the re-export).

### Sub-item 3 — AI-F4: `prompts.py` extraction

The 7 pure prompt-text builder functions were extracted **verbatim** from `improver.py` into a new
`src/ai/prompts.py`. No prompt text changed — this is a pure relocation of the text-builders out of the
improver, narrowing `improver.py` to orchestration.

### Sub-item 4 — AI-F5: `BacktestContext` param object

A new frozen `BacktestContext` dataclass was added in `feedback/loop.py`. `_run_cycle` now takes
`(generated, kind, context, sub_account_id)` instead of an exploded parameter list, and the 4 entry points
build the context once and pass it through. Behavior-preserving collapse of a long parameter list into a
cohesive value object.

### Round-2 — circular-import fix (regression caught by qa)

The round-1 design work introduced a circular import: importing `LLMClient` at module level in `loader.py`
and `improver.py` formed a cycle through `src.ai`. The fix guards the `LLMClient` import under
`TYPE_CHECKING` in BOTH `loader.py` and `improver.py` (annotation-only — both modules already carry
`from __future__ import annotations`, so the type names resolve as strings at runtime and the import is
never executed). A new `tests/test_import_hygiene.py` cold-imports `src.dashboard.app`, `src.strategy.loader`,
and `src.strategy` in FRESH subprocesses and asserts `rc == 0`, pinning the fix against regression.

## Process / verdicts

senior-developer implemented all four sub-items → qa-reviewer round-1 🟢 design-correctness on all four →
qa-reviewer round-2 confirmed the circular-import fix + all gates green. No quant escalation: CAH-10 is
DIP / structural plumbing with no trading-math, signal, gate, or sizing path touched.

### QA round-1 🟢

qa-reviewer round-1 returned 🟢 on design-correctness for all four sub-items: the `LLMClient` port inverts
the loader/improver domain→edge dependency correctly (port injected, `ClaudeCLI` only the default); the
`StrategyError` move preserves class identity through the `strategy/base.py` re-export; the 7 prompt builders
are verbatim; the `BacktestContext` collapse is behavior-preserving with all 4 entry points building the
context once.

### QA round-2 🟢 (scope-attribution 🟡 resolved by the lead)

qa-reviewer round-2 confirmed the circular-import blocker is fixed (cold imports `rc == 0`) and re-confirmed
all four design items. The round-2 🟡 was a **scope-attribution misread, NOT a defect**: the round-2 brief
was a fix-round-trip ("only 2 files changed since last review"), and qa interpreted that 2-file delta as the
whole CAH-10 scope rather than as the incremental circular-import fix on top of the already-approved
four-sub-item bundle. The lead resolved it: the bundled four sub-items ARE CAH-10's defined scope (consistent
with CAH-04, which bundled four micro-fixes), so the cycle is treated as 🟢. No code defect was implied by
the 🟡.

## Files Changed

- **Created**:
  - `src/ai/ports.py` — NEW `@runtime_checkable` `LLMClient` Protocol (`async analyze(prompt) -> dict` +
    `async complete(prompt) -> str`); the DIP seam for the AI cluster.
  - `src/ai/prompts.py` — NEW module holding the 7 pure prompt-text builders extracted **verbatim** from
    `improver.py`.
  - `src/exceptions.py` — NEW neutral module holding the `StrategyError` base, so `ai/exceptions` no longer
    has to import `src.strategy` to reach it.
  - `tests/test_ai_ports.py` — port / design tests for `LLMClient` (runtime-checkable conformance + injection).
  - `tests/test_import_hygiene.py` — cold-import regression test: imports `src.dashboard.app`,
    `src.strategy.loader`, `src.strategy` in fresh subprocesses, asserts `rc == 0` (pins the circular-import fix).
- **Modified**:
  - `src/ai/__init__.py` — exports `LLMClient` from `ports.py`.
  - `src/ai/exceptions.py` — imports `StrategyError` from `src.exceptions` (no longer imports `src.strategy`).
  - `src/ai/improver.py` — `StrategyImprover.__init__(claude: LLMClient | None)` (keeps `claude or ClaudeCLI()`);
    prompt builders removed (now in `prompts.py`); `LLMClient` import `TYPE_CHECKING`-guarded.
  - `src/feedback/loop.py` — NEW frozen `BacktestContext` dataclass; `_run_cycle(generated, kind, context, sub_account_id)`;
    4 entry points build the context once.
  - `src/strategy/base.py` — re-exports `StrategyError` from `src.exceptions` as the SAME class object.
  - `src/strategy/loader.py` — `PromptStrategy` accepts injected `*, llm_client: LLMClient | None`; `analyze()`
    uses it if present else falls back to constructing `ClaudeCLI` (per-strategy timeout override preserved);
    `LLMClient` import `TYPE_CHECKING`-guarded.
  - `tests/test_ai_improver.py` — updated for the `LLMClient`-typed `__init__` + relocated prompt builders.
  - `tests/test_feedback_loop.py` — updated for the `BacktestContext` param object.

No trading-math, signal, gate, or sizing path was touched — the changes are DIP / structural plumbing only.

## Key Decisions

| Decision | Rationale |
|---|---|
| Define `LLMClient` as an `@runtime_checkable` Protocol in a new `src/ai/ports.py` | A Protocol (vs an ABC) inverts the dependency without forcing `ClaudeCLI` to inherit; `@runtime_checkable` lets injection-site `isinstance` checks work. Placing it in a dedicated `ports.py` gives the AI cluster a clear DIP seam. |
| Keep `claude or ClaudeCLI()` default in `StrategyImprover.__init__` and the `ClaudeCLI` fallback in `PromptStrategy.analyze` | Inverting the dependency must not break existing callers — the concrete adapter stays the default so behavior is preserved when nothing is injected; the per-strategy timeout override is preserved on the fallback path. |
| Move `StrategyError` to a NEW neutral `src/exceptions.py`; re-export from `strategy/base.py` as the SAME class object | Putting the base in a neutral module lets `ai/exceptions` import it without importing `src.strategy` (removing the edge→domain back-edge). Re-exporting the SAME class object from `strategy/base.py` keeps every existing `except StrategyError` / `except ClaudeTimeoutError` site working — verified `src.strategy.base.StrategyError is src.exceptions.StrategyError`. |
| Extract the 7 prompt builders **verbatim** to `src/ai/prompts.py` | Pure relocation narrows `improver.py` to orchestration with zero behavioral risk; keeping the text byte-identical lets the existing improver suites stand as the behavior-preservation proof. |
| Collapse `_run_cycle`'s parameter list into a frozen `BacktestContext` dataclass | A cohesive frozen value object replaces a long exploded parameter list; the 4 entry points build it once. Frozen = immutable, no accidental mutation mid-cycle. |
| Guard the `LLMClient` import under `TYPE_CHECKING` in `loader.py` + `improver.py` (round-2 fix) | The module-level `LLMClient` import formed a circular import through `src.ai`. Both modules already carry `from __future__ import annotations`, so the annotation-only `TYPE_CHECKING` guard resolves the type names as strings at runtime and never executes the import — breaking the cycle with no runtime cost. |
| Add `tests/test_import_hygiene.py` cold-import regression test | A circular import only manifests on a cold module load order; cold-importing `src.dashboard.app` / `src.strategy.loader` / `src.strategy` in fresh subprocesses (`rc == 0`) is the only reliable way to pin the fix against a future re-introduction. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2270 passed**, 0 failed (+9 design tests + 3 import-hygiene tests = the cluster's net new
  over the 2258 CAH-09 baseline).
- `ruff check`: clean.
- `mypy`: clean — 98 source files.
- Class-identity invariant: `src.strategy.base.StrategyError is src.exceptions.StrategyError` (LAYER-F2
  re-export preserves the SAME class object).
- Cold-import regression: `src.dashboard.app`, `src.strategy.loader`, `src.strategy` each cold-import in a
  fresh subprocess with `rc == 0` (circular-import fix confirmed).
- NFR-002 preserved: Claude is still reached only via the CLI (`ClaudeCLI`) — the `LLMClient` port abstracts
  the call surface, the concrete adapter remains `ClaudeCLI`, and it stays the default. No direct Anthropic
  API use was introduced.

## Potential Risks

- **The `StrategyError` re-export is the identity contract that keeps every `except StrategyError` /
  `except ClaudeTimeoutError` site working.** `strategy/base.py` re-exports the SAME class object from
  `src.exceptions`; if a future edit shadows or re-defines `StrategyError` in `strategy/base.py` instead of
  re-exporting it, the identity invariant breaks and the `proposal/engine.py:534,728` catch sites (and every
  other catcher) would silently stop catching the neutral-module class. The `src.strategy.base.StrategyError
  is src.exceptions.StrategyError` assertion is the guard.
- **The `TYPE_CHECKING` guards on the `LLMClient` import are load-bearing for the acyclic import graph.** If
  a later edit hoists the `LLMClient` import to module level in `loader.py` or `improver.py` (e.g. to use it
  at runtime rather than only in annotations), the circular import the guard exists to break would return.
  `tests/test_import_hygiene.py` is the regression net, but the reason the imports are `TYPE_CHECKING`-only
  is recorded here so a later reader understands it is deliberate.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-10. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the first Tier 4 ports / typed-contracts unit: four
bundled DIP / structural sub-items + the round-2 circular-import fix, +12 net tests, all gates green).

## Remaining Work

CAH-11…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-11 (Tier 4: `CcxtExchange` base adapter dedup)** — de-duplicates the Binance/Bybit ccxt adapter
bodies (the `None`-timestamp fix CAH-01 had to apply identically to both adapters is one motivating
example). It depends on CAH-01 (already shipped) and is trading-domain, so it gets a quant-trader-expert
review.

No ADR needed — CAH-10 is the planned Tier 4 AI / feedback DIP cluster. While it introduces the `LLMClient`
port, that port is a structural seam delivered as routine planned work against the clean-architecture
review's findings (AI-F1/LAYER-F1/LAYER-F2/AI-F4/AI-F5), not a contested design decision with competing
long-term options: the Protocol-vs-ABC, neutral-exceptions-module, prompt-extraction, and param-object
choices are local DIP / cohesion judgements recorded in the Key Decisions table, NFR-002 (Claude via CLI)
is preserved rather than re-litigated, and the `ClaudeCLI` default keeps existing callers unaffected. The
audit value lives in this session log and the Change-History row, not in an ADR.
