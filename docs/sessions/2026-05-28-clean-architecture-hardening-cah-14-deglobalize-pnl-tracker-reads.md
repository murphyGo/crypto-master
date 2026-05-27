# Session: clean-architecture-hardening CAH-14 — TIER 4 DE-GLOBALIZE THE FS READS IN THE CORE P&L TRACKERS (`utils/io.read_text` IO-seam unification + constructor `data_dir` injection seam [LAYER-F3])

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-14 (Tier 4 ports / typed contracts: de-globalize `strategy/performance.py` reads — constructor-inject the data dir + route the raw `open()` reads through `utils/io` [LAYER-F3]; no new repository port).

> FOURTEENTH unit shipped from the `clean-architecture-hardening` plan, and the FIFTH of the Tier 4 ports /
> typed-contracts units (after CAH-10's AI / feedback DIP cluster, CAH-11's `CcxtExchange` base adapter dedup,
> CAH-12's funnel-derivation + `ProposalRecord` transition methods, and CAH-13's `GateReason` enum + bounded
> `safety_score` accessors + `activity_events.py` extraction). It follows the standalone Tier 0 bugfix CAH-01,
> the three Tier 1 quick wins (CAH-02 order-side helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-
> dedup sweep), the three Tier 2 method extractions (CAH-05 `_handle_proposal` finalize helpers / CAH-06 long-
> function splits / CAH-07 LSP uniform `analyze()` signatures), and the two Tier 3 module splits (CAH-08
> `performance.py` split + replay relocation / CAH-09 dashboard decomposition). **CAH-14 is the LAST bounded
> turn-key unit before the CAH-15 directional epic** (the `TradingEngine` God-Object decomposition). CAH-14 is
> IO / config plumbing with no trading math, so it carried qa-reviewer only — no quant escalation.

## Scope

CAH-14 is a behavior-preserving refactor that de-globalizes the filesystem reads in the two core P&L trackers —
`PerformanceTracker` (`strategy/performance.py`) and `TradeHistoryTracker` (`strategy/trade_history.py`). The
unit turned out **lighter than the plan anticipated**: the plan framed it as "constructor-inject the data dir +
route raw `open()` through `utils/io`", but the constructor `data_dir: Path | None = None` injection seam was
**already present from prior work**, so the live work was (a) unifying the IO seam — the writes already went
through `atomic_write_text`, but the reads were still 2 raw `open()` calls — and (b) proving the trackers are
testable through the existing injection seam without monkeypatching `get_settings()`. No new repository port was
introduced (YAGNI per the plan — the trackers are the only consumers, no Rule-of-Three pressure for a port). No
aggregation or P&L math changed.

### Sub-item 1 — `utils/io.read_text` (write-counterpart to `atomic_write_text`)

Added a small `read_text(path, *, encoding="utf-8") -> str` to `src/utils/io.py` (extending `__all__`). It is a
thin wrapper over `pathlib.Path.read_text` — no locking, no existence pre-check — and is the read counterpart to
the existing `atomic_write_text`. Its purpose is to be the single FS-read seam for the persistence-layer
modules, so all filesystem access in those modules is routed through one place rather than scattered raw
`open(...)` calls. Critically, the docstring records that the underlying `OSError` propagates **unchanged** on a
missing file — that propagation is load-bearing for the callers' existing `except (JSONDecodeError, OSError)`
handling (see Sub-item 2).

### Sub-item 2 — route the 2 raw `open()` reads through `read_text`

The 2 remaining raw `open(...)` reads were swapped for `read_text`:

- `performance.py:568` — `with open(records_path, encoding="utf-8") as f: data = json.load(f)` →
  `data = json.loads(read_text(records_path))`.
- `trade_history.py:445` — `with open(trades_path, encoding="utf-8") as f: data = json.load(f)` →
  `data = json.loads(read_text(trades_path))`.

After the swap, **all** FS access in both modules goes through the single `utils/io` seam (writes via
`atomic_write_text`, reads via `read_text`). The swap is byte-for-byte behavior-preserving: `read_text` reads
the same UTF-8 bytes the raw `open()` did, `json.loads(...)` parses the identical string `json.load(f)` would
have parsed, and — because `read_text` lets `OSError` propagate unchanged — the surrounding
`except (json.JSONDecodeError, OSError)` → return `[]` missing-file handling is intact (a missing file still
raises `OSError`, still falls through to the handler, still yields an empty list).

### Sub-item 3 — the already-present constructor `data_dir` injection seam (kept default)

The constructor `data_dir: Path | None = None` injection seam already existed on both trackers from prior work.
CAH-14 kept it as-is, including the `get_settings()`-derived default: `data_dir is None` resolves to
`data/performance` (PerformanceTracker) / `data/trades` (TradeHistoryTracker), byte-identical to the prior
behavior. The unit's contribution here was to **prove testability through the seam** — the 2 new DIP-seam tests
construct the trackers with an injected `tmp_path` and no `get_settings()` monkeypatch, demonstrating that the
read path is now exercisable end-to-end through the injected `data_dir` + the unified `read_text` seam.

## Process / verdicts

senior-developer implemented the IO-seam unification + the 2 DIP-seam tests as one behavior-preserving commit →
qa-reviewer 🟢. No quant escalation — this is IO / config plumbing with no trading math (no aggregation, no PnL
computation, no gross-win/loss, no profit-factor, no win-rate, no drawdown touched).

### qa-reviewer 🟢

Full suite **2317 passed** (+5 from the 2312 CAH-13 baseline); ruff + mypy clean across 101 files. `git diff
-U0` confirms the ONLY source edits are the `read_text` import + the `open()`→`read_text()` swap:
`from_records` / `calculate_pnl` / `_max_drawdown_pct` / gross-win-loss / profit-factor / win-rate are
byte-for-byte unchanged; the `get_settings()`-derived default path is unchanged; `read_text` preserves
`OSError`-propagation so the `except (JSONDecodeError, OSError)` → `[]` missing-file handling is intact. The 2
DIP-seam tests construct the trackers with an injected `tmp_path` and no settings monkeypatch.

## Files Changed

- **Created**: (none — `read_text` is added to an existing module)
- **Modified**:
  - `src/utils/io.py` — added `read_text(path, *, encoding="utf-8") -> str`, the read counterpart to
    `atomic_write_text`; extended `__all__`. Thin wrapper over `Path.read_text`; docstring records that `OSError`
    propagates unchanged (load-bearing for the callers' `except OSError` handling).
  - `src/strategy/performance.py` — import `read_text` alongside `atomic_write_text`; the raw `open()` read at
    `:568` swapped for `json.loads(read_text(records_path))`. All FS access in the module now goes through the
    `utils/io` seam.
  - `src/strategy/trade_history.py` — import `read_text` alongside `atomic_write_text`; the raw `open()` read at
    `:445` swapped for `json.loads(read_text(trades_path))`. All FS access in the module now goes through the
    `utils/io` seam.
  - `tests/test_strategy_performance.py` — the 2 DIP-seam tests (construct trackers with an injected `tmp_path`,
    no `get_settings()` monkeypatch) + read-path coverage.
  - `tests/test_utils_atomic_write.py` — `read_text` coverage (round-trip with `atomic_write_text`, encoding,
    `OSError`-propagation on a missing file).

The changes are a behavior-preserving IO-seam unification: the read bytes, the `json.loads` parse, the
missing-file `[]` fallback, the `get_settings()`-derived default `data_dir`, and every aggregation / PnL
computation were left exactly as they were.

## Key Decisions

| Decision | Rationale |
|---|---|
| Add `read_text(path, *, encoding="utf-8")` to `utils/io` as the write-counterpart to `atomic_write_text`, and route the 2 raw `open()` reads through it | The trackers' writes already went through `atomic_write_text`, but the reads were still raw `open()` calls — so FS access was only half-centralized. A small `read_text` seam unifies all FS access in both modules into one place, which is the LAYER-F3 goal (one FS seam, testable via a single patch point), without inventing a heavier abstraction. |
| Keep `read_text` a thin `Path.read_text` wrapper with no existence pre-check, letting `OSError` propagate unchanged | The callers already guard with `path.exists()` and wrap the read in `except (JSONDecodeError, OSError)` → `[]`. Pre-checking inside `read_text` or swallowing `OSError` there would change that load-bearing missing-file semantics; propagating `OSError` unchanged keeps the callers' existing handling byte-identical. |
| Do NOT introduce a new repository port (YAGNI per plan) | The two trackers are the only consumers; there is no Rule-of-Three pressure for a port abstraction. The plan explicitly scoped CAH-14 as IO-seam unification + the existing `data_dir` injection seam, not a new port. |
| Keep the already-present constructor `data_dir: Path \| None = None` injection seam + its `get_settings()`-derived default unchanged | The injection seam already existed from prior work, so CAH-14's contribution was unification + proving testability through it, not re-introducing it. The `data_dir is None` → `data/performance` \| `data/trades` default is byte-identical to prior behavior; changing it would be an out-of-scope behavior change. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2317 passed**, 0 failed (+5 from the 2312 CAH-13 baseline).
- `ruff check` + `mypy`: clean across 101 files.
- Behavior-preservation proof (qa `git diff -U0`): the ONLY source edits are the `read_text` import + the
  `open()`→`read_text()` swap; `from_records` / `calculate_pnl` / `_max_drawdown_pct` / gross-win-loss /
  profit-factor / win-rate are byte-for-byte unchanged.
- Behavior-preservation proof (default path): `data_dir is None` still resolves to `data/performance` /
  `data/trades` via the `get_settings()`-derived default — unchanged.
- Behavior-preservation proof (error semantics): `read_text` preserves `OSError`-propagation, so the surrounding
  `except (json.JSONDecodeError, OSError)` → `[]` missing-file handling is intact (a missing file still raises
  `OSError`, still falls through, still yields an empty list).
- The 2 DIP-seam tests construct the trackers with an injected `tmp_path` and no `get_settings()` monkeypatch,
  exercising the read path end-to-end through the injection seam + the unified `read_text`.

## Potential Risks

- **`read_text`'s `OSError`-propagation is now a load-bearing contract for the trackers' missing-file handling.**
  The callers rely on a missing file raising `OSError` so their `except (JSONDecodeError, OSError)` → `[]`
  fallback fires; `read_text` is deliberately a thin `Path.read_text` wrapper with no existence pre-check and no
  `OSError` swallowing precisely to preserve that. A future edit that adds an existence pre-check inside
  `read_text` (or otherwise suppresses `OSError`) would silently change the trackers' missing-file behavior —
  recorded here so a later reader treats the unchanged-`OSError` propagation as a contract, not an incidental
  detail. The `read_text` coverage test (missing-file → `OSError`) is the guard.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-14. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the fifth Tier 4 ports / typed-contracts unit and the last
bounded unit before the CAH-15 directional epic: `utils/io.read_text` IO-seam unification of the 2 P&L-tracker
reads + the already-present constructor `data_dir` injection seam [LAYER-F3], +5 tests, all gates green).

## Remaining Work

CAH-15 remains planned in `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`.
Next action: **CAH-15 (Tier 5: `TradingEngine` God-Object decomposition)**.

**IMPORTANT — CAH-15 is a DIRECTIONAL EPIC, NOT a turn-key unit.** The plan gates it on a design ADR first
(reviewed by quant-trader-expert) BEFORE any code, then staged collaborator extraction — `SnapshotRecorder`
first, then `PositionMonitor`, then the gate-chain — each its own behavior-preserving slice. CAH-15 should
**START with an ADR / design step, not direct implementation**; the lead will decide whether to proceed.

No ADR needed for CAH-14 itself — it is the planned Tier 4 LAYER-F3 IO-seam unit, a behavior-preserving refactor
delivered as routine planned work against the clean-architecture review's findings. It introduces no new
abstraction boundary (no repository port — YAGNI per plan), the constructor injection seam already existed, and
`read_text` is a small honest-encapsulation helper, not a contested design decision with competing long-term
options. The decisions are local IO / config-plumbing judgements recorded in the Key Decisions table; the audit
value lives in this session log and the Change-History row, not in an ADR. (The design ADR that IS warranted
belongs to CAH-15, per the plan's gate.)
