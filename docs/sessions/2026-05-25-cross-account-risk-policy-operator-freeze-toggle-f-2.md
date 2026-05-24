# Session: cross-account-risk-policy OPERATOR-FREEZE TOGGLE WRITE SIDE (DEBT-068(f-2) write-side)

Date: 2026-05-25
Units: `cross-account-risk-policy` / `dashboard-operator-ui`
Stage: Code Generation
Related debt: DEBT-068(f) — the dashboard slice was SPLIT into (f-1) read-only
panel [SHIPPED 2026-05-24] and (f-2) operator-freeze toggle WRITE side
[SHIPPED, this log]. **This log COMPLETES DEBT-068(f).**
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Same-unit dashboard sibling to the nine runtime/policy/dashboard
> `cross-account-risk-policy` logs that precede it (DEBT-068(b) opt-in caps,
> (c-1)/(c-2) kill switches, (c-arb) cap arbitration, (d) operator-freeze runtime
> READ side, (e) stale actions, (g) risk event types, (f-1) read-only panel).
> (d) shipped the runtime read side; (f-1) shipped the read-only freeze-STATE
> indicator; this log covers the WRITE side — the interactive toggle that
> persists `trading_freeze` back to `config/runtime_flags.yaml`. Uncommitted on
> `main` at the time of writing; committed immediately after.

## Scope

DEBT-068(f-2) is the operator-freeze toggle WRITE side — the writer half of the
freeze surface. The runtime READ side (`read_trading_freeze`) shipped under (d);
the read-only freeze-STATE indicator shipped under (f-1). What remained was the
writer: an interactive, confirmation-gated widget that persists `trading_freeze`
back to `config/runtime_flags.yaml` so the operator can engage a freeze from the
dashboard rather than hand-editing the file on disk.

The write side is the deliberate LOUD-fail inverse of the (d) reader's
never-crash fail-safe. The reader must never freeze or crash on a malformed file;
the writer must REFUSE to overwrite a malformed/unreadable existing file rather
than silently clobber unrelated operator state. It is a read-merge-write that
PRESERVES unrelated keys and writes atomically via the canonical
`src.utils.io.atomic_write_text` (DEBT-028 single source of truth).

## Changes — DEBT-068(f-2) operator-freeze toggle write side

Runtime flags write side, in `src/runtime/runtime_flags.py`:

- **`write_trading_freeze(value, path)`** — read-merge-write that PRESERVES
  unrelated keys: loads the existing document (if any), sets `trading_freeze` to
  the new value, and writes the merged document atomically via the canonical
  `src.utils.io.atomic_write_text` (DEBT-028 single source of truth). Missing /
  empty file = fresh-start (a new document with only `trading_freeze`).
- **`RuntimeFlagsWriteError`** — raised when the existing file is malformed /
  unreadable. The writer REFUSES to overwrite it; the file is left byte-for-byte
  untouched. The guard raises BEFORE `atomic_write_text`, so a malformed file is
  never clobbered.
- **`_load_existing_document`** — the read-half of the read-merge-write; parses
  the existing document for the merge, distinguishing missing/empty (fresh-start)
  from malformed (refuse).

Dashboard, in `src/dashboard/pages/engine.py`:

- **`FreezeTogglePlan`** + pure **`build_freeze_toggle_plan`** — the pure planner
  that decides what the toggle should do given current state.
- **`render_operator_freeze_toggle`** — thin confirmation-gated render wrapper
  that REPLACES the (f-1) read-only indicator. It now also renders on the
  quiet-log path so a freeze can still be engaged when no risk-gate events have
  fired. **Rerun-safe**: the write is gated inside `if submitted and
  acknowledged:` (`st.form` + `st.form_submit_button` + mandatory ack checkbox,
  `clear_on_submit`), so a page refresh cannot re-toggle the flag.

## Review

- qa-reviewer: 🟢. Full suite **2181 passed (+12)**, 0 failed; `ruff` + `mypy`
  clean. Verified the **round-trip** (write then read returns the written value),
  **key-preservation** (unrelated keys survive the merge), **malformed-file
  refusal** (file genuinely untouched — the guards raise BEFORE
  `atomic_write_text`), **atomicity** (no temp file left behind, parent dir
  created), **rerun-safety** (the write is gated behind `submitted and
  acknowledged`, so a refresh cannot re-toggle), the **pure / thin split**, and
  **no (f-1) regression**.
- No quant escalation — no trading-math and no `src/trading` code was touched
  (runtime-flags write side + dashboard widget over already-emitted state).

## Verification

- Full suite: 2181 passed, 0 failed (was 2169; net +12, zero regressions).
- New tests: 10 runtime_flags write-side + 2 dashboard plan.
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

- **Post-write OSError wrap branch is untested (KEY KNOWN GAP — qa 🟡).** The
  branch in `runtime_flags.py` (~line 204) that wraps a post-`atomic_write_text`
  `OSError` into `RuntimeFlagsWriteError` is not exercised by a test. The
  pre-write guards (malformed-file refusal) ARE tested; what is uncovered is the
  case where `atomic_write_text` itself raises after the guards pass (e.g. a
  disk-full / permission failure during the atomic write). A monkeypatch test that
  makes `atomic_write_text` raise `OSError` and asserts the wrap would close it.
  Low priority. Filed as DEBT-068(f-2-note-test-gap).

- **Dashboard widget wraps the reader in a broad `except Exception` (qa 🟡, no
  fix needed).** The widget wraps `read_trading_freeze` in a broad
  `except Exception` (`engine.py` ~line 1543). This is justified — the widget must
  never crash the UI, and the reader is itself fail-safe — so it is noted per the
  error-handling checklist rather than fixed. Filed as
  DEBT-068(f-2-note-broad-except).

## TECH-DEBT Items

DEBT-068(f-2) is marked **SHIPPED**, and with both (f-1) read-only panel and
(f-2) toggle write-side now shipped, **DEBT-068(f) is COMPLETE**. Two new
non-blocking follow-ups filed as sub-bullets: (f-2-note-test-gap) — the
post-`atomic_write_text` `OSError`→`RuntimeFlagsWriteError` wrap branch
(`runtime_flags.py` ~L204) is untested; and (f-2-note-broad-except) — the
dashboard widget's broad `except Exception` around `read_trading_freeze`
(`engine.py` ~L1543) is justified (never crash the UI; reader is itself
fail-safe), noted per the error-handling checklist, no fix needed. DEBT-068
umbrella remains Active.

## Remaining Work

DEBT-068 remains Active. With (f) complete, the umbrella's only remaining
SUBSTANCE is:

- **(h)** `runtime-safety-score` kill-switch + stale-event integration — feed
  kill-switch triggers into the runtime-safety-score signal. **Candidate next
  slice.**

Plus the previously-filed minor follow-up notes that ride along to be addressed
opportunistically: (c-2-note-fee-timing), (e-note-close-stale-quote),
(f-1-note-snapshot-event), (c-arb-note-overshoot-units), and the two new f-2
notes above.

No ADR needed — this slice ships the writer half of an already-decided freeze
surface (the read side and the read-only indicator are in place; the
read-merge-write-via-`atomic_write_text` and confirmation-gated-toggle shapes
follow directly from established project patterns — DEBT-028 single-source
atomic write, the reconciliation-banner pure-`build_*` / thin-`render_*` split,
and the (f) umbrella description). It introduces no new component boundary and no
new long-term constraint, so no architecture decision record is warranted.
