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
from src.feedback.audit import AuditEvent, AuditEventType, AuditLog
from src.logger import get_logger
from src.models import OHLCV
from src.strategy.base import TechniqueInfo
from src.strategy.loader import load_strategy
from src.strategy.performance import PerformanceRecord, TechniquePerformance
from src.trading.profiles import TradingProfile

logger = get_logger("crypto_master.feedback.loop")


DEFAULT_EXPERIMENTAL_DIR = Path("strategies/experimental")
DEFAULT_ACTIVE_DIR = Path("strategies")
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


class CandidateRecord(BaseModel):
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
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

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
                fresh ``AuditLog()`` (i.e. ``data/audit/feedback.jsonl``).
            experimental_dir: Where candidates are saved before
                approval. Defaults to ``strategies/experimental``.
            active_dir: Where candidates are moved on approval. Defaults
                to ``strategies/`` (matches existing layout).
            state_dir: Where ``CandidateRecord`` snapshots are persisted.
        """
        self.improver = improver
        self.backtester = backtester
        self.analyzer = analyzer
        self.gate = gate
        self.audit_log = audit_log or AuditLog()
        self.experimental_dir = experimental_dir or DEFAULT_EXPERIMENTAL_DIR
        self.active_dir = active_dir or DEFAULT_ACTIVE_DIR
        self.state_dir = state_dir or DEFAULT_STATE_DIR

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
    ) -> CandidateRecord:
        """Improve an existing technique and run it through the gate."""
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
    ) -> CandidateRecord:
        """Generate a brand-new technique and run it through the gate."""
        generated = await self.improver.generate_idea(context=context, save=True)
        return await self._run_cycle(
            generated=generated,
            kind="new_idea",
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            strategy_factory=strategy_factory,
            param_grid=param_grid,
        )

    async def from_user_idea(
        self,
        user_idea: str,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        strategy_factory: StrategyFactory | AsyncStrategyFactory | None = None,
        param_grid: dict[str, list[Any]] | None = None,
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
                "updated_at": datetime.now(),
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
                "updated_at": datetime.now(),
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
        """Persist a candidate's snapshot to ``state_dir``."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / f"{record.candidate_id}.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

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
        )
        self.save_state(record)
        self._audit(
            record,
            AuditEventType.GENERATED,
            details={
                "kind": kind,
                "saved_path": str(generated.saved_path),
                "hypothesis": generated.hypothesis,
            },
        )

        try:
            strategy = load_strategy(generated.saved_path)
            backtest = await self.backtester.run(
                strategy=strategy,
                ohlcv=ohlcv,
                symbol=symbol,
                timeframe=timeframe,
                profile=profile,
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
            )
            return self._after_gate(record, report)

        except Exception as exc:
            errored = record.model_copy(
                update={
                    "status": LoopStatus.ERRORED,
                    "decision_reason": f"Errored: {exc!s}",
                    "updated_at": datetime.now(),
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
                "updated_at": datetime.now(),
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
                    "updated_at": datetime.now(),
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
                "updated_at": datetime.now(),
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

        Re-reads the file, rewrites the frontmatter so ``status`` is
        ``active`` and ``updated_at`` reflects the promotion time, then
        writes to ``active_dir / filename`` and unlinks the source.

        Returns:
            The new path under ``active_dir``.
        """
        if not source_path.exists():
            raise FeedbackLoopError(
                f"Cannot promote: source file missing at {source_path}"
            )

        original = source_path.read_text(encoding="utf-8")
        rewritten = self._rewrite_frontmatter_status(original)

        self.active_dir.mkdir(parents=True, exist_ok=True)
        target = self.active_dir / source_path.name
        if target.exists():
            raise FeedbackLoopError(
                f"Refusing to overwrite existing active technique at "
                f"{target}; rename and retry."
            )

        target.write_text(rewritten, encoding="utf-8")
        source_path.unlink()
        return target

    @staticmethod
    def _rewrite_frontmatter_status(content: str) -> str:
        """Set ``status: active`` and ``updated_at`` in YAML frontmatter.

        If the file has no frontmatter, prepend a minimal one. This
        keeps the loader happy (``load_technique_info_from_md`` requires
        frontmatter) on the off chance a generated candidate omitted it.
        """
        match = _FRONTMATTER_PATTERN.match(content)
        now_iso = datetime.now().isoformat()
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
