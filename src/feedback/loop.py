"""Automated feedback loop orchestrator.

Wires together the four building blocks produced in Phase 5:

* ``StrategyImprover``  — Claude generates a candidate technique.
* ``Backtester``        — the candidate runs against historical data.
* ``PerformanceAnalyzer`` — produces metrics attached to the audit row.
* ``RobustnessGate``    — out-of-sample / walk-forward / regime /
  parameter-sensitivity gates decide if the candidate is worth keeping.

The orchestrator does **not** perform automatic promotion: even a
candidate that survives every gate stops at ``AWAITING_APPROVAL``
until ``approve()`` is called explicitly. That separation is the
mechanical implementation of CON-003 (no new technique adoption
without user approval).

Every state transition is recorded in the audit log so a future
operator can answer "why is this technique active?" or "what made us
discard that one?" without spelunking the codebase.

Related Requirements:
- FR-026: Automated Feedback Loop
- FR-027: Technique Adoption (user approval required)
- FR-034: Robustness Validation Gate
- CON-003: User Approval Required
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.ai.improver import GeneratedTechnique, StrategyImprover
from src.backtest.analyzer import PerformanceAnalyzer
from src.backtest.engine import Backtester, BacktestResult
from src.backtest.validator import (
    AsyncStrategyFactory,
    RobustnessGate,
    RobustnessReport,
    StrategyFactory,
)
from src.config import get_settings
from src.feedback.audit import AuditEvent, AuditEventType, AuditLog
from src.logger import get_logger
from src.models import OHLCV
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.strategy.loader import load_strategy, load_technique_info_from_py
from src.strategy.performance import PerformanceRecord, TechniquePerformance
from src.trading.profiles import TradingProfile
from src.utils.io import atomic_write_text
from src.utils.pydantic_mixins import UtcTimestampMixin
from src.utils.time import now_utc

logger = get_logger("crypto_master.feedback.loop")


DEFAULT_EXPERIMENTAL_DIR = Path("strategies/experimental")
DEFAULT_ACTIVE_DIR = Path("strategies")
# Relative-path marker; the live default is derived from
# ``Settings.data_dir`` at construction time so candidate state survives
# container recycles on managed hosts (Phase 10.5).
DEFAULT_STATE_DIR = Path("data/feedback/state")


# Same shape as the improver's frontmatter regex, but locally owned so
# the loop doesn't depend on the improver's private name.
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)


# =============================================================================
# Public types
# =============================================================================


class FeedbackLoopError(Exception):
    """Base exception for feedback-loop errors."""


CandidateKind = Literal["improvement", "new_idea", "user_idea", "reevaluation"]


class LoopStatus(str, Enum):
    """Lifecycle states of a single candidate.

    Transitions::

        GENERATED → BACKTESTED → AWAITING_APPROVAL → PROMOTED
                              ↘ DISCARDED         ↘ DISCARDED
        (any step) → ERRORED
    """

    GENERATED = "generated"
    BACKTESTED = "backtested"
    AWAITING_APPROVAL = "awaiting_approval"
    PROMOTED = "promoted"
    DISCARDED = "discarded"
    ERRORED = "errored"


class CandidateRecord(UtcTimestampMixin, BaseModel):
    """Snapshot of one candidate's progress through the loop.

    Persisted as JSON under ``state_dir/<candidate_id>.json`` after
    every state change. The audit log holds the full event history;
    this model holds only the latest snapshot.
    """

    candidate_id: str
    kind: CandidateKind
    parent_technique: str | None = None
    technique_name: str
    technique_version: str
    source_path: Path
    status: LoopStatus
    backtest_run_id: str | None = None
    robustness_passed: bool | None = None
    robustness_summary: str | None = None
    failed_gates: list[str] = Field(default_factory=list)
    decision_reason: str = ""
    sub_account_id: str = "default"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(use_enum_values=True)


# =============================================================================
# Orchestrator
# =============================================================================


class FeedbackLoop:
    """End-to-end orchestration of the technique evolution cycle.

    A single instance is reusable across many candidates; instances
    hold no per-candidate state — every per-candidate bit lives in the
    audit log and the state file.
    """

    def __init__(
        self,
        improver: StrategyImprover,
        backtester: Backtester,
        analyzer: PerformanceAnalyzer,
        gate: RobustnessGate,
        audit_log: AuditLog | None = None,
        experimental_dir: Path | None = None,
        active_dir: Path | None = None,
        state_dir: Path | None = None,
        *,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the loop.

        Args:
            improver: Pre-built ``StrategyImprover``. Owns Claude calls
                and the experimental-dir filename convention.
            backtester: Pre-built ``Backtester``. Used for the baseline
                run; sub-runs done by the gate share its config.
            analyzer: ``PerformanceAnalyzer`` used to attach summary
                metrics to the ``BACKTESTED`` audit event.
            gate: ``RobustnessGate`` used to decide promotion eligibility.
            audit_log: Where to write event history. Defaults to a
                fresh ``AuditLog()`` rooted under ``Settings.data_dir``.
            experimental_dir: Where candidates are saved before
                approval. Defaults to ``strategies/experimental``.
            active_dir: Where candidates are moved on approval. Defaults
                to ``strategies/`` (matches existing layout).
            state_dir: Where ``CandidateRecord`` snapshots are persisted.
                When omitted, defaults to
                ``<data_dir>/feedback/state``.
            data_dir: Optional override for the loop data root. Used
                only to derive ``state_dir`` when no explicit
                ``state_dir`` is supplied. Defaults to
                ``Settings().data_dir`` so state lands on the
                persistent volume operations has mounted (Phase 10.5).
        """
        self.improver = improver
        self.backtester = backtester
        self.analyzer = analyzer
        self.gate = gate
        self.audit_log = audit_log or AuditLog()
        self.experimental_dir = experimental_dir or DEFAULT_EXPERIMENTAL_DIR
        self.active_dir = active_dir or DEFAULT_ACTIVE_DIR
        if state_dir is not None:
            self.state_dir = state_dir
        else:
            base = data_dir if data_dir is not None else get_settings().data_dir
            self.state_dir = base / "feedback" / "state"

    # ------------------------------------------------------------------
    # Generation entry points (each runs the full cycle)
    # ------------------------------------------------------------------

    async def improve_existing(
        self,
        technique: TechniqueInfo,
        original_source: str,
        performance: TechniquePerformance,
        records: list[PerformanceRecord],
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
    ) -> CandidateRecord:
        """Improve an existing technique and run it through the gate.

        Multi-TF candidates: pass ``ohlcv_by_timeframe`` and use
        ``timeframe`` as the primary TF key. The backtester and gate
        dispatch on ``strategy.info.requires_multi_timeframe``.
        """
        generated = await self.improver.suggest_improvement(
            technique=technique,
            original_source=original_source,
            performance=performance,
            records=records,
            save=True,
        )
        return await self._run_cycle(
            generated=generated,
            kind="improvement",
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            strategy_factory=strategy_factory,
            param_grid=param_grid,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
        )

    async def propose_new(
        self,
        context: str,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        code_type: bool = False,
        sub_account_id: str = "default",
    ) -> CandidateRecord:
        """Generate a brand-new technique and run it through the gate.

        Phase 17.5 / DEBT-019 Option B — when ``code_type=True`` the
        improver emits a Python ``BaseStrategy`` subclass instead of a
        markdown prompt, so the resulting backtest never invokes the
        Claude CLI per bar. Defaults to ``False`` so existing callers
        keep the historical prompt-type path.
        """
        generated = await self.improver.generate_idea(
            context=context, save=True, code_type=code_type
        )
        if strategy_factory is None and code_type and param_grid:
            strategy_factory = self._strategy_factory_for_generated_code(generated)
        return await self._run_cycle(
            generated=generated,
            kind="new_idea",
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            strategy_factory=strategy_factory,
            param_grid=param_grid,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
            sub_account_id=sub_account_id,
        )

    @staticmethod
    def _strategy_factory_for_generated_code(
        generated: GeneratedTechnique,
    ) -> StrategyFactory | None:
        """Build a sensitivity factory for generated Python strategies.

        Code-type auto-research prompts require generated strategies to
        expose tunables as ``__init__`` keyword arguments. Once the file
        is saved, the loop can load the strategy class and provide the
        ``RobustnessGate`` with a factory that instantiates variants for
        each parameter-grid combination.
        """
        if generated.saved_path is None or generated.saved_path.suffix != ".py":
            return None

        info, strategy_class = load_technique_info_from_py(generated.saved_path)

        def _factory(**params: Any) -> BaseStrategy:
            return strategy_class(info=info, **params)

        return _factory

    async def from_user_idea(
        self,
        user_idea: str,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
    ) -> CandidateRecord:
        """Turn a free-form user idea into a candidate and gate it."""
        generated = await self.improver.generate_from_user_idea(
            user_idea=user_idea, save=True
        )
        return await self._run_cycle(
            generated=generated,
            kind="user_idea",
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            strategy_factory=strategy_factory,
            param_grid=param_grid,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
        )

    async def reevaluate(
        self,
        experimental_path: Path,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
        parent_technique: str | None = None,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
    ) -> CandidateRecord:
        """Re-run the gate on an already-saved experimental file.

        Useful after a robustness-config change, after fresh OHLCV is
        available, or to re-verify a candidate the operator deferred.
        Skips the improver entirely.
        """
        if not experimental_path.exists():
            raise FeedbackLoopError(f"Experimental file not found: {experimental_path}")
        # Load just for metadata; the file content already lives on disk.
        strategy = load_strategy(experimental_path)
        synthetic = GeneratedTechnique(
            name=strategy.info.name,
            version=strategy.info.version,
            description=strategy.info.description,
            kind="user_idea",  # placeholder; actual kind is below.
            parent_technique=parent_technique,
            content=experimental_path.read_text(encoding="utf-8"),
            suggested_filename=experimental_path.name,
            saved_path=experimental_path,
        )
        return await self._run_cycle(
            generated=synthetic,
            kind="reevaluation",
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            strategy_factory=strategy_factory,
            param_grid=param_grid,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
        )

    # ------------------------------------------------------------------
    # User decision API (CON-003)
    # ------------------------------------------------------------------

    def approve(self, candidate_id: str, approver: str) -> CandidateRecord:
        """Promote a candidate from ``experimental/`` to ``active_dir``.

        The candidate must currently be in ``AWAITING_APPROVAL``. Any
        other state is a usage error: the operator should re-evaluate
        first if the candidate has gone stale.
        """
        record = self.load_state(candidate_id)
        if record.status != LoopStatus.AWAITING_APPROVAL.value:
            raise FeedbackLoopError(
                f"Candidate {candidate_id} is in status "
                f"{record.status!r}; only AWAITING_APPROVAL candidates "
                "can be approved."
            )

        new_path = self._promote_file(record.source_path)

        record = record.model_copy(
            update={
                "status": LoopStatus.PROMOTED,
                "source_path": new_path,
                "decision_reason": f"Approved by {approver}",
                "updated_at": now_utc(),
            }
        )
        self.save_state(record)

        self._audit(
            record,
            AuditEventType.APPROVED,
            actor=approver,
            details={"new_path": str(new_path)},
        )
        self._audit(
            record,
            AuditEventType.PROMOTED,
            actor=approver,
            details={"new_path": str(new_path)},
        )
        return record

    def reject(self, candidate_id: str, approver: str, reason: str) -> CandidateRecord:
        """Discard a candidate awaiting approval.

        The file stays in ``experimental/`` so the operator can inspect
        or improve it again later. Only the lifecycle state changes.
        """
        record = self.load_state(candidate_id)
        if record.status != LoopStatus.AWAITING_APPROVAL.value:
            raise FeedbackLoopError(
                f"Candidate {candidate_id} is in status "
                f"{record.status!r}; only AWAITING_APPROVAL candidates "
                "can be rejected."
            )

        record = record.model_copy(
            update={
                "status": LoopStatus.DISCARDED,
                "decision_reason": f"Rejected by {approver}: {reason}",
                "updated_at": now_utc(),
            }
        )
        self.save_state(record)

        self._audit(
            record,
            AuditEventType.REJECTED,
            actor=approver,
            details={"reason": reason},
        )
        self._audit(
            record,
            AuditEventType.DISCARDED,
            actor=approver,
            details={"reason": reason},
        )
        return record

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def save_state(self, record: CandidateRecord) -> None:
        """Persist a candidate's snapshot to ``state_dir``.

        Routed through :func:`src.utils.io.atomic_write_text` (Phase
        26.1 / DEBT-044) so a crash mid-write leaves the previous
        snapshot intact rather than truncating it. Same load → mutate
        → save shape as the Phase 22.1 sites; the helper guarantees
        readers observe either the prior payload or the new one,
        never a half-written file.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / f"{record.candidate_id}.json"
        atomic_write_text(path, record.model_dump_json(indent=2))

    def load_state(self, candidate_id: str) -> CandidateRecord:
        """Load a candidate by ID."""
        path = self.state_dir / f"{candidate_id}.json"
        if not path.exists():
            raise FeedbackLoopError(
                f"No saved state for candidate {candidate_id} at {path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CandidateRecord(**payload)

    def list_pending(self) -> list[CandidateRecord]:
        """Return every candidate currently awaiting approval."""
        if not self.state_dir.exists():
            return []
        records: list[CandidateRecord] = []
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = CandidateRecord(**payload)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping unreadable state file {path}: {e}")
                continue
            if record.status == LoopStatus.AWAITING_APPROVAL.value:
                records.append(record)
        return records

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_cycle(
        self,
        generated: GeneratedTechnique,
        kind: CandidateKind,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None,
        param_grid: dict[str, list[Any]] | None,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        sub_account_id: str = "default",
    ) -> CandidateRecord:
        """Run the full backtest → gate cycle for a fresh candidate."""
        if generated.saved_path is None:
            raise FeedbackLoopError(
                "Generated technique has no saved_path; the improver "
                "must be invoked with save=True."
            )

        record = CandidateRecord(
            candidate_id=str(uuid.uuid4()),
            kind=kind,
            parent_technique=generated.parent_technique,
            technique_name=generated.name,
            technique_version=generated.version,
            source_path=generated.saved_path,
            status=LoopStatus.GENERATED,
            sub_account_id=sub_account_id,
        )
        self.save_state(record)
        self._audit(
            record,
            AuditEventType.GENERATED,
            details={
                "kind": kind,
                "saved_path": str(generated.saved_path),
                "hypothesis": generated.hypothesis,
                "sub_account_id": sub_account_id,
            },
        )

        try:
            strategy = load_strategy(generated.saved_path)
            backtest = await self.backtester.run_for_strategy(
                strategy=strategy,
                ohlcv=ohlcv,
                symbol=symbol,
                timeframe=timeframe,
                profile=profile,
                ohlcv_by_timeframe=ohlcv_by_timeframe,
            )
            record = self._after_backtest(record, backtest)

            report = await self.gate.evaluate(
                strategy=strategy,
                ohlcv=ohlcv,
                symbol=symbol,
                timeframe=timeframe,
                profile=profile,
                strategy_factory=strategy_factory,
                param_grid=param_grid,
                ohlcv_by_timeframe=ohlcv_by_timeframe,
            )
            return self._after_gate(record, report)

        except Exception as exc:
            errored = record.model_copy(
                update={
                    "status": LoopStatus.ERRORED,
                    "decision_reason": f"Errored: {exc!s}",
                    "updated_at": now_utc(),
                }
            )
            self.save_state(errored)
            self._audit(
                errored,
                AuditEventType.ERRORED,
                details={"error": str(exc), "type": type(exc).__name__},
            )
            raise

    def _after_backtest(
        self, record: CandidateRecord, backtest: BacktestResult
    ) -> CandidateRecord:
        """Update state after a baseline backtest finishes."""
        metrics = self.analyzer.analyze(backtest)
        record = record.model_copy(
            update={
                "status": LoopStatus.BACKTESTED,
                "backtest_run_id": backtest.run_id,
                "updated_at": now_utc(),
            }
        )
        self.save_state(record)
        self._audit(
            record,
            AuditEventType.BACKTESTED,
            details={
                "run_id": backtest.run_id,
                "total_trades": backtest.total_trades,
                "return_percent": backtest.return_percent,
                "win_rate": metrics.win_rate,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown_percent": metrics.max_drawdown_percent,
            },
        )
        return record

    def _after_gate(
        self, record: CandidateRecord, report: RobustnessReport
    ) -> CandidateRecord:
        """Update state after the robustness gate finishes."""
        failed = [g.name for g in report.gates if g.status == "failed"]
        details = {
            "overall_passed": report.overall_passed,
            "summary": report.summary,
            "baseline_sharpe": report.baseline_sharpe,
            "baseline_trades": report.baseline_trades,
            "gates": [
                {
                    "name": g.name,
                    "status": g.status,
                    "reason": g.reason,
                    "score": g.score,
                    "threshold": g.threshold,
                }
                for g in report.gates
            ],
        }

        if report.overall_passed:
            updated = record.model_copy(
                update={
                    "status": LoopStatus.AWAITING_APPROVAL,
                    "robustness_passed": True,
                    "robustness_summary": report.summary,
                    "failed_gates": [],
                    "decision_reason": (
                        "Robustness gate PASSED; awaiting user approval"
                    ),
                    "updated_at": now_utc(),
                }
            )
            self.save_state(updated)
            self._audit(updated, AuditEventType.GATE_PASSED, details=details)
            return updated

        updated = record.model_copy(
            update={
                "status": LoopStatus.DISCARDED,
                "robustness_passed": False,
                "robustness_summary": report.summary,
                "failed_gates": failed,
                "decision_reason": (
                    f"Discarded: gate FAILED on {', '.join(failed) or 'unknown'}"
                ),
                "updated_at": now_utc(),
            }
        )
        self.save_state(updated)
        self._audit(updated, AuditEventType.GATE_FAILED, details=details)
        self._audit(
            updated,
            AuditEventType.DISCARDED,
            details={"failed_gates": failed, "summary": report.summary},
        )
        return updated

    def _promote_file(self, source_path: Path) -> Path:
        """Move an experimental file to ``active_dir`` with status flipped.

        Re-reads the file, rewrites it so ``status`` becomes ``active``
        — frontmatter for ``.md`` techniques, in-source ``TECHNIQUE_INFO``
        literal for ``.py`` techniques — then writes to
        ``active_dir / filename`` atomically and unlinks the source. The
        ``.py`` path used to call the markdown rewriter and prepend a
        YAML frontmatter block, which made the file unparsable as Python
        and broke load-time strategy registration (consistency-hardening
        CH-02).

        Returns:
            The new path under ``active_dir``.
        """
        if not source_path.exists():
            raise FeedbackLoopError(
                f"Cannot promote: source file missing at {source_path}"
            )

        original = source_path.read_text(encoding="utf-8")
        suffix = source_path.suffix.lower()
        if suffix == ".py":
            rewritten = self._rewrite_py_status_to_active(original)
        else:
            rewritten = self._rewrite_frontmatter_status(original)

        self.active_dir.mkdir(parents=True, exist_ok=True)
        target = self.active_dir / source_path.name
        if target.exists():
            raise FeedbackLoopError(
                f"Refusing to overwrite existing active technique at "
                f"{target}; rename and retry."
            )

        # Atomic write protects against half-written promotions on crash —
        # otherwise a torn `.py` file would either fail `ast.parse` or, worse,
        # parse as a half-strategy at the next loader pass (CH-02).
        atomic_write_text(target, rewritten)
        try:
            source_path.unlink()
        except OSError as e:
            target.unlink(missing_ok=True)
            raise FeedbackLoopError(
                "promotion partially failed: active target was written but "
                f"source could not be removed at {source_path}"
            ) from e
        return target

    @staticmethod
    def _rewrite_py_status_to_active(content: str) -> str:
        """Flip ``TECHNIQUE_INFO["status"]`` to ``"active"`` in a .py file.

        Walks the AST to locate the ``TECHNIQUE_INFO = {...}`` assignment
        and replaces only the ``status`` value's source span. Preserves
        original formatting and comments outside that span. Raises
        :class:`FeedbackLoopError` if the file cannot be parsed or does
        not declare ``TECHNIQUE_INFO`` as a top-level dict literal — the
        loader rejects those files anyway, so failing here makes the
        problem visible at promotion time instead of at the next runtime
        load.
        """
        import ast

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            raise FeedbackLoopError(
                f"Cannot promote .py technique: invalid Python syntax: {e}"
            ) from e

        status_node: ast.Constant | None = None
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if not any(t.id == "TECHNIQUE_INFO" for t in targets):
                continue
            if not isinstance(node.value, ast.Dict):
                raise FeedbackLoopError(
                    "Cannot promote .py technique: TECHNIQUE_INFO must be a "
                    "dict literal"
                )
            for key_node, value_node in zip(
                node.value.keys, node.value.values, strict=True
            ):
                if (
                    isinstance(key_node, ast.Constant)
                    and key_node.value == "status"
                    and isinstance(value_node, ast.Constant)
                    and isinstance(value_node.value, str)
                ):
                    status_node = value_node
                    break
            break

        if status_node is None:
            # No status key (or already non-string) — leave the file as-is and
            # let the loader's TechniqueInfo validator surface the issue. The
            # source/target rename is the load-bearing part of promotion.
            return content

        current_value = status_node.value
        assert isinstance(current_value, str)
        if current_value == "active":
            return content

        new_source = ast.get_source_segment(content, status_node)
        if new_source is None:
            raise FeedbackLoopError(
                "Cannot promote .py technique: unable to locate the "
                "TECHNIQUE_INFO['status'] source span"
            )

        # ``ast.get_source_segment`` returns the literal incl. quotes, e.g.
        # ``"experimental"``; preserve the original quote style by replacing
        # only the inside.
        replacement = new_source.replace(current_value, "active", 1)
        lines = content.splitlines(keepends=True)
        # ``lineno``/``col_offset`` are 1-/0-indexed respectively.
        line_idx = status_node.lineno - 1
        line = lines[line_idx]
        col = status_node.col_offset
        end_col = (
            status_node.end_col_offset
            if status_node.end_col_offset is not None
            else col + len(new_source)
        )
        lines[line_idx] = line[:col] + replacement + line[end_col:]
        return "".join(lines)

    @staticmethod
    def _rewrite_frontmatter_status(content: str) -> str:
        """Set ``status: active`` and ``updated_at`` in YAML frontmatter.

        If the file has no frontmatter, prepend a minimal one. This
        keeps the loader happy (``load_technique_info_from_md`` requires
        frontmatter) on the off chance a generated candidate omitted it.
        """
        match = _FRONTMATTER_PATTERN.match(content)
        now_iso = now_utc().isoformat()
        if match is None:
            new_frontmatter = (
                "---\n" f"status: active\n" f"updated_at: '{now_iso}'\n" "---\n"
            )
            return new_frontmatter + content

        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            raise FeedbackLoopError(
                f"Cannot promote: invalid YAML frontmatter: {e}"
            ) from e
        if not isinstance(metadata, dict):
            raise FeedbackLoopError("Cannot promote: frontmatter is not a YAML mapping")

        metadata["status"] = "active"
        metadata["updated_at"] = now_iso

        new_frontmatter_body = yaml.safe_dump(
            metadata, sort_keys=False, allow_unicode=True
        ).strip()
        try:
            reparsed = yaml.safe_load(new_frontmatter_body) or {}
        except yaml.YAMLError as e:
            raise FeedbackLoopError(
                f"Cannot promote: rewritten YAML frontmatter is invalid: {e}"
            ) from e
        if not isinstance(reparsed, dict):
            raise FeedbackLoopError(
                "Cannot promote: rewritten frontmatter is not a YAML mapping"
            )
        body = content[match.end() :]
        return f"---\n{new_frontmatter_body}\n---\n{body}"

    def _audit(
        self,
        record: CandidateRecord,
        event_type: AuditEventType,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Emit one audit event for this candidate."""
        self.audit_log.append(
            AuditEvent(
                event_type=event_type,
                candidate_id=record.candidate_id,
                technique_name=record.technique_name,
                technique_version=record.technique_version,
                actor=actor,
                details=details or {},
            )
        )


__all__ = [
    "CandidateRecord",
    "FeedbackLoop",
    "FeedbackLoopError",
    "LoopStatus",
    "DEFAULT_EXPERIMENTAL_DIR",
    "DEFAULT_ACTIVE_DIR",
    "DEFAULT_STATE_DIR",
]
