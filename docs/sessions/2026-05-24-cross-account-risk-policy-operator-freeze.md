# Session: cross-account-risk-policy OPERATOR MANUAL FREEZE (DEBT-068(d) runtime half)

Date: 2026-05-24
Units: `cross-account-risk-policy`
Stage: Code Generation
Related debt: DEBT-068(d) — runtime READ side SHIPPED; dashboard WRITE side remains DEBT-068(f)
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Fourth same-day session log on the `cross-account-risk-policy` unit, distinct
> from its three siblings:
> `docs/sessions/2026-05-24-cross-account-risk-policy-opt-in-global-caps.md`
> (DEBT-068(b), opt-in global exposure caps, commit `a088e17`),
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c1.md`
> (DEBT-068(c-1), the STATELESS kill-switch gates), and
> `docs/sessions/2026-05-24-cross-account-risk-policy-kill-switch-c2-daily-loss.md`
> (DEBT-068(c-2), the STATEFUL daily-loss kill switch that completed (c)). This
> log covers DEBT-068(d) — the **operator manual freeze**, runtime READ side.
> Uncommitted on `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(d) ships the **runtime READ side** of the operator manual freeze: a
file-based kill switch an operator can flip to reject all new-entry proposals
across every sub-account, in both paper and live modes, without restarting the
engine. The dashboard WRITE side — the toggle UI that writes back to
`config/runtime_flags.yaml` — is explicitly NOT in this slice and remains open
under DEBT-068(f).

The defining design choice is **fail-safe by construction**. The freeze is a
manual operator kill switch, so the read path must never freeze trading by
accident and must never crash the cycle: a missing flags file reads as
`False` (no freeze), and a malformed file or a non-bool value emits a loud
warning and falls back to `False`. The loader can neither silently freeze nor
take down the cycle on bad input — a typo in the YAML cannot halt trading and
cannot crash the engine.

The flag is read **once per cycle** at the top of `run_cycle` and cached to
`self._operator_freeze_active`, so flipping the file freezes a running engine
on the next cycle boundary without a restart, at a cost of one file read per
cycle. The gate sits at the **VERY TOP** of `_handle_proposal` — the earliest
reject, ahead of correlation / regime / kill-switch / sizing / caps — so a
frozen engine spends no work evaluating downstream gates. Unlike the
kill-switch gates, the freeze is a **hard block in BOTH paper and live** with
NO paper-advisory carve-out: it is a manual kill, so it halts paper labs too.

## Changes — DEBT-068(d) operator manual freeze (runtime READ side)

- `src/runtime/runtime_flags.py` (new)
  - **`read_trading_freeze(path)`** — fail-safe loader. Missing file ⇒
    `False` (no freeze); malformed / non-bool value ⇒ loud warning + `False`;
    never crashes, never silently freezes.
- `src/runtime/engine.py`
  - **`EngineConfig.runtime_flags_path`** — new config field, default
    `config/runtime_flags.yaml`.
  - The freeze flag is read **ONCE per cycle** at the top of `run_cycle` and
    cached to **`self._operator_freeze_active`** (flip the file ⇒ a running
    engine freezes next cycle, no restart).
  - The freeze is gated at the **VERY TOP of `_handle_proposal`** — the
    earliest reject, before all other gates. When `trading_freeze: true`, ALL
    proposals are rejected with `reason="operator_freeze"` and a new
    `ActivityEventType.OPERATOR_FREEZE_ENGAGED`. **Hard block in BOTH paper and
    live** (manual kill — no paper-advisory branch, unlike the kill-switch
    gates).
- `src/runtime/activity_log.py`
  - New **`ActivityEventType.OPERATOR_FREEZE_ENGAGED`**.
- `src/proposal/interaction.py`
  - New **`ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE`** terminal.
- `src/proposal/funnel.py`
  - Funnel count bucket + label/count wiring for the new terminal.
- `config/runtime_flags.yaml.example` (new)
  - Operator example flags file, documenting the freeze semantics.
- `tests/`
  - +17 tests (11 loader + 6 engine).

## Review

- qa-reviewer: 🟢. Full suite **2134 passed (+17)**, 0 failed; `ruff` + `mypy`
  clean. Verified the **fail-safe loader** (a typo can neither freeze nor
  crash), the **earliest-reject precedence** (freeze ahead of all downstream
  gates), the **both-mode hard-block** (paper and live), and **funnel
  completeness** for the new terminal.
- No quant escalation — no trading-math and no `src/trading` code was touched.

## Verification

- Full suite: 2134 passed, 0 failed (was 2117; net +17, zero regressions).
- `ruff check src tests`: clean.
- `mypy src`: clean.

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- **Freeze blocks new entries only; open positions are not freeze-gated.** The
  operator freeze rejects NEW-ENTRY proposals at the top of `_handle_proposal`.
  Open positions continue to wind down via the separate SL/TP polling path,
  which is NOT freeze-gated — consistent with the spec ("kill switches do not
  auto-close open positions; they only block new entries") and documented in
  `config/runtime_flags.yaml.example`. An operator who needs open positions
  closed must do so manually; the freeze is not an auto-flatten.
- **Read-side only.** There is no in-dashboard way to engage the freeze yet —
  the operator must edit `config/runtime_flags.yaml` on disk. The toggle UI is
  DEBT-068(f); until it ships, the freeze is a file-edit workflow.

## TECH-DEBT Items

DEBT-068(d) ships the **runtime READ side**; the dashboard **WRITE side** (the
toggle UI that persists `trading_freeze` back to `config/runtime_flags.yaml`)
remains open under DEBT-068(f). No DEBT item is fully resolved this cycle — the
DEBT-068 umbrella remains Active for (c-arb), (d)-WRITE-side-via-(f), (e), (f),
(g), (h). The DEBT-068(d) sub-item is annotated SHIPPED (runtime side) in the
umbrella; (f) keeps the dashboard write-side open.

No new follow-up notes filed this cycle.

## Remaining Work

DEBT-068 remains Active. Deferred follow-ups, all still open:

- **(c-arb)** `cap_resolution=lowest_priority_loses` arbitration for global
  `(symbol, side)` caps — separate slice, not bundled into (c). **Candidate
  next slice.**
- (e) stale `auto_close` / `alert_only` actions.
- **(f)** dashboard cross-account risk exposure panel **+ the operator-freeze
  toggle UI** that writes back to `config/runtime_flags.yaml` (runtime READ
  side now shipped by (d); dashboard WRITE side NOT built).
- (g) dedicated `RISK_KILL_SWITCH_TRIPPED` / `RISK_CAP_ADVISORY`
  `ActivityEventType`.
- (h) `runtime-safety-score` kill-switch integration.

No ADR needed — this slice implements the already-decided operator-freeze
contract from the cross-account-risk-policy functional-design spec
(`config/runtime_flags.yaml`, reject with `reason="operator_freeze"`). The
fail-safe-to-not-frozen read semantics and the both-mode hard-block (manual
kill, no paper-advisory carve-out) follow directly from the spec; they do not
introduce a new component boundary or a new long-term constraint, so no
architecture decision record is warranted.
