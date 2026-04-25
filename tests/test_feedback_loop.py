"""Tests for the FeedbackLoop orchestrator."""

from __future__ import annotations

import textwrap
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.ai.improver import GeneratedTechnique, StrategyImprover
from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import Backtester, BacktestResult
from src.backtest.validator import (
    GateResult,
    GateStatus,
    RobustnessGate,
    RobustnessReport,
)
from src.feedback.audit import AuditEventType, AuditLog
from src.feedback.loop import (
    FeedbackLoop,
    FeedbackLoopError,
    LoopStatus,
)

# =============================================================================
# Helpers
# =============================================================================


def write_experimental_md(
    dir_: Path,
    name: str = "cand",
    version: str = "0.1.0",
) -> Path:
    """Write a minimal-but-valid experimental technique file."""
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{name}.md"
    path.write_text(
        textwrap.dedent(f"""\
            ---
            name: {name}
            version: {version}
            description: candidate technique
            technique_type: prompt
            status: experimental
            ---

            Body of the candidate prompt.
            """),
        encoding="utf-8",
    )
    return path


def make_generated(
    path: Path,
    kind: str = "improvement",
    parent: str | None = "parent_tech",
) -> GeneratedTechnique:
    return GeneratedTechnique(
        name=path.stem,
        version="0.1.0",
        description="candidate technique",
        hypothesis="placeholder hypothesis",
        kind=kind,  # type: ignore[arg-type]
        parent_technique=parent,
        content=path.read_text(encoding="utf-8"),
        suggested_filename=path.name,
        saved_path=path,
    )


def make_backtest_result(run_id: str = "run-1") -> BacktestResult:
    now = datetime.now()
    return BacktestResult(
        run_id=run_id,
        technique_name="cand",
        technique_version="0.1.0",
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=now,
        end_time=now,
        initial_balance=Decimal("10000"),
        final_balance=Decimal("11000"),
        total_trades=10,
        wins=6,
        losses=4,
        breakevens=0,
        total_pnl=Decimal("1000"),
        total_fees=Decimal("10"),
        win_rate=0.6,
        return_percent=10.0,
    )


def make_metrics() -> PerformanceMetrics:
    return PerformanceMetrics(
        total_trades=10,
        wins=6,
        losses=4,
        win_rate=0.6,
        return_percent=10.0,
        sharpe_ratio=1.2,
        max_drawdown_percent=5.0,
    )


def make_report(passed: bool = True) -> RobustnessReport:
    if passed:
        gates = [
            GateResult(
                name="oos",
                status=GateStatus.PASSED,
                score=0.8,
                threshold=0.7,
                reason="OOS Sharpe retained",
            ),
            GateResult(
                name="walk_forward",
                status=GateStatus.PASSED,
                score=0.8,
                threshold=0.6,
                reason="majority of windows profitable",
            ),
        ]
    else:
        gates = [
            GateResult(
                name="oos",
                status=GateStatus.FAILED,
                score=0.1,
                threshold=0.7,
                reason="OOS Sharpe collapsed",
            ),
            GateResult(
                name="walk_forward",
                status=GateStatus.PASSED,
                score=0.7,
                threshold=0.6,
                reason="majority of windows profitable",
            ),
        ]
    return RobustnessReport(
        overall_passed=passed,
        gates=gates,
        summary="Robustness verdict: test",
        baseline_sharpe=1.0,
        baseline_trades=10,
    )


def make_loop(
    tmp_path: Path,
    *,
    gate_passed: bool = True,
    improver_error: Exception | None = None,
    gate_error: Exception | None = None,
) -> tuple[FeedbackLoop, Path, AuditLog]:
    """Build a FeedbackLoop with all collaborators mocked."""
    experimental_dir = tmp_path / "strategies" / "experimental"
    active_dir = tmp_path / "strategies"
    state_dir = tmp_path / "state"
    audit_path = tmp_path / "audit.jsonl"

    md_path = write_experimental_md(experimental_dir, name="cand")

    improver = AsyncMock(spec=StrategyImprover)
    if improver_error is not None:
        improver.suggest_improvement.side_effect = improver_error
        improver.generate_idea.side_effect = improver_error
        improver.generate_from_user_idea.side_effect = improver_error
    else:
        generated = make_generated(md_path)
        improver.suggest_improvement.return_value = generated
        improver.generate_idea.return_value = generated
        improver.generate_from_user_idea.return_value = generated

    backtester = AsyncMock(spec=Backtester)
    backtester.run.return_value = make_backtest_result()

    analyzer = MagicMock(spec=PerformanceAnalyzer)
    analyzer.analyze.return_value = make_metrics()

    gate = AsyncMock(spec=RobustnessGate)
    if gate_error is not None:
        gate.evaluate.side_effect = gate_error
    else:
        gate.evaluate.return_value = make_report(passed=gate_passed)

    audit_log = AuditLog(path=audit_path)
    loop = FeedbackLoop(
        improver=improver,
        backtester=backtester,
        analyzer=analyzer,
        gate=gate,
        audit_log=audit_log,
        experimental_dir=experimental_dir,
        active_dir=active_dir,
        state_dir=state_dir,
    )
    return loop, md_path, audit_log


def sample_technique_info():
    from src.strategy.base import TechniqueInfo

    return TechniqueInfo(
        name="parent_tech",
        version="1.0.0",
        description="parent technique",
        technique_type="prompt",
    )


def sample_performance():
    from src.strategy.performance import TechniquePerformance

    return TechniquePerformance(
        technique_name="parent_tech",
        technique_version="1.0.0",
    )


# =============================================================================
# Cycle: gate PASSED
# =============================================================================


@pytest.mark.asyncio
async def test_improve_existing_gate_passed_awaits_approval(tmp_path: Path) -> None:
    loop, md_path, audit_log = make_loop(tmp_path, gate_passed=True)

    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original prompt body",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    assert record.status == LoopStatus.AWAITING_APPROVAL.value
    assert record.robustness_passed is True
    assert record.failed_gates == []
    assert record.parent_technique == "parent_tech"

    # Audit chain: GENERATED → BACKTESTED → GATE_PASSED.
    events = audit_log.read_all()
    types = [e.event_type for e in events]
    assert types == [
        AuditEventType.GENERATED.value,
        AuditEventType.BACKTESTED.value,
        AuditEventType.GATE_PASSED.value,
    ]

    # File should remain in experimental_dir until approved.
    assert md_path.exists()
    assert (tmp_path / "strategies" / md_path.name).exists() is False


@pytest.mark.asyncio
async def test_propose_new_gate_passed_awaits_approval(tmp_path: Path) -> None:
    loop, _, audit_log = make_loop(tmp_path, gate_passed=True)

    record = await loop.propose_new(
        context="focus on liquidation cascades",
        ohlcv=[],
        symbol="BTC/USDT",
    )

    assert record.status == LoopStatus.AWAITING_APPROVAL.value
    assert record.kind == "new_idea"
    types = [e.event_type for e in audit_log.read_all()]
    assert AuditEventType.GATE_PASSED.value in types


# =============================================================================
# Cycle: gate FAILED
# =============================================================================


@pytest.mark.asyncio
async def test_improve_existing_gate_failed_discards(tmp_path: Path) -> None:
    loop, md_path, audit_log = make_loop(tmp_path, gate_passed=False)

    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original prompt body",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    assert record.status == LoopStatus.DISCARDED.value
    assert record.robustness_passed is False
    assert "oos" in record.failed_gates
    assert "Discarded" in record.decision_reason

    # Audit chain ends with GATE_FAILED → DISCARDED.
    events = audit_log.read_all()
    types = [e.event_type for e in events]
    assert types[-2:] == [
        AuditEventType.GATE_FAILED.value,
        AuditEventType.DISCARDED.value,
    ]
    # File still exists in experimental — operator may want to inspect it.
    assert md_path.exists()


# =============================================================================
# Re-evaluate
# =============================================================================


@pytest.mark.asyncio
async def test_reevaluate_existing_file(tmp_path: Path) -> None:
    loop, md_path, audit_log = make_loop(tmp_path, gate_passed=True)

    record = await loop.reevaluate(
        experimental_path=md_path,
        ohlcv=[],
        symbol="BTC/USDT",
    )

    assert record.status == LoopStatus.AWAITING_APPROVAL.value
    assert record.kind == "reevaluation"
    # Improver should NOT be invoked for re-evaluation.
    loop.improver.suggest_improvement.assert_not_called()
    loop.improver.generate_idea.assert_not_called()
    loop.improver.generate_from_user_idea.assert_not_called()


@pytest.mark.asyncio
async def test_reevaluate_missing_file_raises(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    with pytest.raises(FeedbackLoopError, match="Experimental file not found"):
        await loop.reevaluate(
            experimental_path=tmp_path / "nope.md",
            ohlcv=[],
            symbol="BTC/USDT",
        )


# =============================================================================
# Approve
# =============================================================================


@pytest.mark.asyncio
async def test_approve_moves_file_and_flips_status(tmp_path: Path) -> None:
    loop, md_path, audit_log = make_loop(tmp_path, gate_passed=True)

    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )
    assert record.status == LoopStatus.AWAITING_APPROVAL.value

    promoted = loop.approve(record.candidate_id, approver="alice")

    assert promoted.status == LoopStatus.PROMOTED.value
    # Source file gone from experimental.
    assert md_path.exists() is False
    # Target file now in active dir with frontmatter status=active.
    target = tmp_path / "strategies" / md_path.name
    assert target.exists()
    body = target.read_text(encoding="utf-8")
    fm_block = body.split("---")[1]
    metadata = yaml.safe_load(fm_block)
    assert metadata["status"] == "active"
    assert "updated_at" in metadata

    # Audit chain ends with APPROVED → PROMOTED.
    events = audit_log.read_all()
    types = [e.event_type for e in events]
    assert types[-2:] == [
        AuditEventType.APPROVED.value,
        AuditEventType.PROMOTED.value,
    ]
    # Approver name recorded.
    assert events[-1].actor == "alice"


@pytest.mark.asyncio
async def test_approve_rejects_non_pending_candidate(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=False)
    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )
    assert record.status == LoopStatus.DISCARDED.value

    with pytest.raises(FeedbackLoopError, match="AWAITING_APPROVAL"):
        loop.approve(record.candidate_id, approver="alice")


# =============================================================================
# Reject
# =============================================================================


@pytest.mark.asyncio
async def test_reject_keeps_file_and_audits(tmp_path: Path) -> None:
    loop, md_path, audit_log = make_loop(tmp_path, gate_passed=True)

    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    rejected = loop.reject(
        record.candidate_id, approver="bob", reason="hypothesis weak"
    )

    assert rejected.status == LoopStatus.DISCARDED.value
    assert "Rejected by bob" in rejected.decision_reason
    # File stays in experimental for further inspection.
    assert md_path.exists()
    # No file appeared in active dir.
    assert (tmp_path / "strategies" / md_path.name).exists() is False

    events = audit_log.read_all()
    types = [e.event_type for e in events]
    assert types[-2:] == [
        AuditEventType.REJECTED.value,
        AuditEventType.DISCARDED.value,
    ]


# =============================================================================
# State persistence
# =============================================================================


@pytest.mark.asyncio
async def test_save_and_load_state_round_trip(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )
    loaded = loop.load_state(record.candidate_id)
    assert loaded.candidate_id == record.candidate_id
    assert loaded.status == record.status
    assert loaded.technique_name == record.technique_name
    assert loaded.parent_technique == record.parent_technique


def test_load_state_missing_raises(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    with pytest.raises(FeedbackLoopError, match="No saved state"):
        loop.load_state("does-not-exist")


@pytest.mark.asyncio
async def test_list_pending_returns_only_awaiting(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=True)

    # First candidate passes the gate.
    await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    # Second candidate fails the gate. Swap the gate's behavior
    # without rebuilding the whole loop.
    loop.gate.evaluate.return_value = make_report(passed=False)
    write_experimental_md(loop.experimental_dir, name="cand2")
    loop.improver.suggest_improvement.return_value = make_generated(
        loop.experimental_dir / "cand2.md", parent="parent_tech"
    )
    await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    pending = loop.list_pending()
    assert len(pending) == 1
    assert pending[0].status == LoopStatus.AWAITING_APPROVAL.value


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.asyncio
async def test_improver_error_propagates(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, improver_error=RuntimeError("Claude unreachable"))
    with pytest.raises(RuntimeError, match="Claude unreachable"):
        await loop.improve_existing(
            technique=sample_technique_info(),
            original_source="original",
            performance=sample_performance(),
            records=[],
            ohlcv=[],
            symbol="BTC/USDT",
        )


@pytest.mark.asyncio
async def test_gate_error_audits_errored_and_reraises(tmp_path: Path) -> None:
    loop, _, audit_log = make_loop(tmp_path, gate_error=RuntimeError("gate exploded"))

    with pytest.raises(RuntimeError, match="gate exploded"):
        await loop.improve_existing(
            technique=sample_technique_info(),
            original_source="original",
            performance=sample_performance(),
            records=[],
            ohlcv=[],
            symbol="BTC/USDT",
        )

    events = audit_log.read_all()
    types = [e.event_type for e in events]
    # Generated + backtested ran successfully before the gate blew up.
    assert AuditEventType.GENERATED.value in types
    assert AuditEventType.BACKTESTED.value in types
    assert types[-1] == AuditEventType.ERRORED.value

    # And the candidate's persisted state should reflect the failure.
    candidate_id = events[-1].candidate_id
    record = loop.load_state(candidate_id)
    assert record.status == LoopStatus.ERRORED.value


# =============================================================================
# Promotion edge cases
# =============================================================================


def test_rewrite_frontmatter_status_preserves_other_fields(tmp_path: Path) -> None:
    """Direct unit test of the frontmatter rewrite helper."""
    original = textwrap.dedent("""\
        ---
        name: cand
        version: 0.1.0
        description: candidate technique
        technique_type: prompt
        status: experimental
        ---

        Body here.
        """)
    rewritten = FeedbackLoop._rewrite_frontmatter_status(original)
    fm_block = rewritten.split("---")[1]
    metadata = yaml.safe_load(fm_block)
    assert metadata["status"] == "active"
    assert metadata["name"] == "cand"
    assert metadata["version"] == "0.1.0"
    assert metadata["description"] == "candidate technique"
    assert "Body here." in rewritten


@pytest.mark.asyncio
async def test_approve_refuses_to_overwrite_existing_active(
    tmp_path: Path,
) -> None:
    loop, md_path, _ = make_loop(tmp_path, gate_passed=True)
    # Pre-create a file at the active target path to simulate a name clash.
    (tmp_path / "strategies").mkdir(parents=True, exist_ok=True)
    (tmp_path / "strategies" / md_path.name).write_text(
        "pre-existing", encoding="utf-8"
    )

    record = await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )

    with pytest.raises(FeedbackLoopError, match="Refusing to overwrite"):
        loop.approve(record.candidate_id, approver="alice")
    # Source file must remain in experimental on failed promotion.
    assert md_path.exists()
