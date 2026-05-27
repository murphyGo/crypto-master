"""Tests for the FeedbackLoop orchestrator."""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
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
from src.config import reload_settings
from src.feedback.audit import AuditEventType, AuditLog
from src.feedback.loop import (
    BacktestContext,
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


def write_experimental_py(
    dir_: Path,
    name: str = "cand_code",
    version: str = "0.1.0",
) -> Path:
    """Write a minimal code-type strategy with a tunable constructor."""
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{name}.py"
    path.write_text(
        textwrap.dedent(f'''\
            """Code strategy fixture."""

            from datetime import datetime
            from decimal import Decimal

            from src.models import AnalysisResult, OHLCV
            from src.strategy.base import BaseStrategy, TechniqueInfo

            TECHNIQUE_INFO = {{
                "name": "{name}",
                "version": "{version}",
                "description": "candidate code technique",
                "author": "test",
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "status": "experimental",
            }}


            class CandidateCodeStrategy(BaseStrategy):
                def __init__(self, info: TechniqueInfo, period: int = 14) -> None:
                    super().__init__(info)
                    self.period = period

                async def analyze(
                    self,
                    ohlcv: list[OHLCV],
                    symbol: str,
                    timeframe: str = "1h",
                ) -> AnalysisResult:
                    del symbol, timeframe
                    price = Decimal(str(ohlcv[-1].close)) if ohlcv else Decimal("1")
                    return AnalysisResult(
                        signal="neutral",
                        confidence=0.0,
                        entry_price=price,
                        stop_loss=price,
                        take_profit=price,
                        reasoning=f"period={{self.period}}",
                        timestamp=datetime.now(),
                    )
            '''),
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
    # The loop dispatches via ``run_for_strategy`` (Phase 9.3); legacy
    # ``run`` is also stubbed for any test that constructs the
    # backtester directly.
    backtester.run.return_value = make_backtest_result()
    backtester.run_for_strategy.return_value = make_backtest_result()

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


@pytest.mark.asyncio
async def test_propose_new_code_type_builds_sensitivity_factory(
    tmp_path: Path,
) -> None:
    """DEBT-014: code-type generated strategies should provide the
    robustness gate with a factory when a param_grid is supplied."""
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    py_path = write_experimental_py(tmp_path / "strategies" / "experimental")
    generated = make_generated(py_path, kind="new_idea", parent=None)
    loop.improver.generate_idea.return_value = generated

    await loop.propose_new(
        context="code strategy",
        ohlcv=[],
        symbol="BTC/USDT",
        code_type=True,
        param_grid={"period": [10, 14, 20]},
    )

    gate_call = loop.gate.evaluate.await_args
    assert gate_call.kwargs["param_grid"] == {"period": [10, 14, 20]}
    factory = gate_call.kwargs["strategy_factory"]
    assert factory is not None
    variant = factory(period=20)
    assert variant.info.name == "cand_code"
    assert variant.period == 20


@pytest.mark.asyncio
async def test_improve_existing_threads_multi_tf_dict_to_backtester(
    tmp_path: Path,
) -> None:
    """Phase 9.3: ``ohlcv_by_timeframe`` reaches both the backtester
    and the gate via ``run_for_strategy`` / ``gate.evaluate``."""
    loop, _, _ = make_loop(tmp_path, gate_passed=True)

    multi_tf = {
        "4h": [],
        "1h": [],
        "15m": [],
        "5m": [],
    }
    await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original prompt body",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
        timeframe="5m",
        ohlcv_by_timeframe=multi_tf,
    )

    bt_call = loop.backtester.run_for_strategy.await_args
    assert bt_call.kwargs["ohlcv_by_timeframe"] is multi_tf
    assert bt_call.kwargs["timeframe"] == "5m"

    gate_call = loop.gate.evaluate.await_args
    assert gate_call.kwargs["ohlcv_by_timeframe"] is multi_tf
    assert gate_call.kwargs["timeframe"] == "5m"


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
async def test_promote_file_rolls_back_target_when_unlink_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop, md_path, _ = make_loop(tmp_path, gate_passed=True)

    await loop.improve_existing(
        technique=sample_technique_info(),
        original_source="original",
        performance=sample_performance(),
        records=[],
        ohlcv=[],
        symbol="BTC/USDT",
    )
    target = tmp_path / "strategies" / md_path.name
    original_unlink = Path.unlink

    def fail_source_unlink(
        path: Path,
        missing_ok: bool = False,
    ) -> None:
        if path == md_path:
            raise OSError("simulated unlink failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_source_unlink)

    with pytest.raises(FeedbackLoopError, match="promotion partially failed"):
        loop._promote_file(md_path)

    assert md_path.exists()
    assert not target.exists()


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


def test_load_state_corrupt_record_raises_feedback_loop_error(tmp_path: Path) -> None:
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    loop.state_dir.mkdir(parents=True, exist_ok=True)
    (loop.state_dir / "bad-cand.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(FeedbackLoopError, match="Failed to parse saved state"):
        loop.load_state("bad-cand")


def test_constructor_respects_settings_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default state_dir is rooted under Settings.data_dir (Phase 10.5)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reload_settings()
    try:
        loop = FeedbackLoop(
            improver=AsyncMock(spec=StrategyImprover),
            backtester=AsyncMock(spec=Backtester),
            analyzer=MagicMock(spec=PerformanceAnalyzer),
            gate=AsyncMock(spec=RobustnessGate),
            audit_log=AuditLog(path=tmp_path / "audit.jsonl"),
        )
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        reload_settings()

    assert loop.state_dir == tmp_path / "feedback" / "state"
    assert tmp_path in loop.state_dir.parents


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


def test_rewrite_py_status_to_active_keeps_file_parsable() -> None:
    """`.py` promotion must not inject markdown frontmatter (CH-02).

    Before consistency-hardening CH-02, ``_promote_file`` ran every file
    through ``_rewrite_frontmatter_status``. For a ``.py`` candidate the
    helper prepended a YAML ``---\\n status: active\\n---`` block, which
    made the file non-parseable Python and broke the loader.
    """
    import ast

    original = textwrap.dedent('''\
        """Code strategy fixture."""

        TECHNIQUE_INFO = {
            "name": "cand_code",
            "version": "0.1.0",
            "status": "experimental",
        }
        ''')

    rewritten = FeedbackLoop._rewrite_py_status_to_active(original)

    # Still valid Python.
    tree = ast.parse(rewritten)
    # status flipped.
    assigns = [n for n in tree.body if isinstance(n, ast.Assign)]
    info_dict = next(
        n.value
        for n in assigns
        if any(isinstance(t, ast.Name) and t.id == "TECHNIQUE_INFO" for t in n.targets)
    )
    assert isinstance(info_dict, ast.Dict)
    by_key = {
        k.value: v.value
        for k, v in zip(info_dict.keys, info_dict.values, strict=True)
        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
    }
    assert by_key["status"] == "active"
    # Other fields untouched.
    assert by_key["name"] == "cand_code"
    assert by_key["version"] == "0.1.0"
    # Module docstring preserved.
    assert '"""Code strategy fixture."""' in rewritten


def test_rewrite_py_status_idempotent_when_already_active() -> None:
    """Re-promoting an already-active .py is a no-op."""
    original = textwrap.dedent("""\
        TECHNIQUE_INFO = {
            "name": "cand_code",
            "status": "active",
        }
        """)
    assert FeedbackLoop._rewrite_py_status_to_active(original) == original


def test_rewrite_py_status_raises_on_invalid_python() -> None:
    """Surface syntax problems at promotion time, not at next runtime load."""
    with pytest.raises(FeedbackLoopError, match="invalid Python syntax"):
        FeedbackLoop._rewrite_py_status_to_active("def broken(:\n")


@pytest.mark.asyncio
async def test_approve_promotes_py_candidate_without_frontmatter_injection(
    tmp_path: Path,
) -> None:
    """End-to-end: approving a .py candidate yields a loadable .py file (CH-02)."""
    import ast

    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    py_path = write_experimental_py(loop.experimental_dir, name="cand_code_promo")

    # Re-point the improver to return the .py candidate instead of the .md one.
    loop.improver.suggest_improvement.return_value = make_generated(py_path)
    loop.improver.generate_idea.return_value = make_generated(py_path)
    loop.improver.generate_from_user_idea.return_value = make_generated(py_path)

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

    target = loop.active_dir / py_path.name
    assert target.exists()
    body = target.read_text(encoding="utf-8")
    # No YAML frontmatter prepended.
    assert not body.lstrip().startswith("---")
    # File is still valid Python.
    ast.parse(body)
    # Status flipped to active.
    assert '"status": "active"' in body


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


# =============================================================================
# Phase 21.2 — UTC-aware write-side + legacy tolerance at read boundary
# =============================================================================


def test_candidate_record_load_coerces_legacy_naive_timestamps(
    tmp_path: Path,
) -> None:
    """Legacy ``CandidateRecord`` JSON with naive timestamps loads UTC-aware.

    Phase 21.2: ``CandidateRecord`` ships a ``field_validator`` that
    coerces naive ``created_at`` / ``updated_at`` to UTC at the read
    boundary, so the dashboard sort by ``updated_at`` doesn't mix
    naive and aware after a partial rollout.
    """
    import json

    from src.feedback.loop import CandidateRecord, LoopStatus

    legacy = {
        "candidate_id": "legacy-cand",
        "kind": "improvement",
        "parent_technique": "rsi_4h",
        "technique_name": "rsi_v2",
        "technique_version": "0.2.0",
        "source_path": str(tmp_path / "x.md"),
        "status": LoopStatus.AWAITING_APPROVAL.value,
        "decision_reason": "",
        "created_at": "2026-01-01T00:00:00",  # naive
        "updated_at": "2026-01-02T00:00:00",  # naive
    }
    state_path = tmp_path / "legacy-cand.json"
    state_path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = CandidateRecord(**json.loads(state_path.read_text(encoding="utf-8")))

    assert loaded.created_at.tzinfo is not None
    assert loaded.updated_at.tzinfo is not None
    # Naive treated as UTC.
    assert loaded.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert loaded.updated_at == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_candidate_record_default_timestamps_are_utc_aware() -> None:
    """Phase 21.2: fresh ``CandidateRecord`` defaults are UTC-aware."""
    from src.feedback.loop import CandidateRecord, LoopStatus

    record = CandidateRecord(
        candidate_id="x",
        kind="improvement",
        technique_name="t",
        technique_version="0.1.0",
        source_path=Path("/tmp/x.md"),
        status=LoopStatus.GENERATED,
    )

    assert record.created_at.tzinfo is not None
    assert record.updated_at.tzinfo is not None


# =============================================================================
# Phase 26.1 / DEBT-044: atomic-write durability
# =============================================================================


def test_save_state_crash_preserves_prior_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 26.1 / DEBT-044: a mid-write crash leaves the prior snapshot intact.

    Mirrors the Phase 22.1 site tests in
    ``tests/test_proposal_interaction.py`` and ``tests/test_portfolio.py``:
    monkeypatch ``atomic_write_text`` to raise after the helper would
    have produced the temp file but before ``os.replace`` swaps it in,
    then assert the previously-saved JSON is still readable verbatim.
    """
    from src.feedback.loop import CandidateRecord, LoopStatus

    loop, _, _ = make_loop(tmp_path, gate_passed=True)

    seed = CandidateRecord(
        candidate_id="seed-cand",
        kind="improvement",
        technique_name="seed",
        technique_version="0.1.0",
        source_path=tmp_path / "seed.md",
        status=LoopStatus.GENERATED,
    )
    loop.save_state(seed)

    def boom(path: Path, text: str, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr("src.feedback.loop.atomic_write_text", boom)

    updated = seed.model_copy(update={"status": LoopStatus.PROMOTED})
    with pytest.raises(OSError, match="simulated mid-write crash"):
        loop.save_state(updated)

    # The on-disk snapshot is still the GENERATED seed; no truncation,
    # no half-written file.
    loaded = loop.load_state("seed-cand")
    assert loaded.status == LoopStatus.GENERATED.value
    assert loaded.technique_name == "seed"


# =============================================================================
# AI-F5: BacktestContext parameter object
# =============================================================================


def test_backtest_context_is_frozen() -> None:
    """AI-F5: the context is immutable so backtest + gate see the same inputs."""
    import dataclasses

    ctx = BacktestContext(ohlcv=[], symbol="BTC/USDT", timeframe="1h")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.symbol = "ETH/USDT"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_run_cycle_accepts_backtest_context(tmp_path: Path) -> None:
    """AI-F5: ``_run_cycle`` consumes a ``BacktestContext`` and threads it.

    Exercises the bundled-argument seam directly (rather than via an
    entry point) so the context-threading is pinned independently.
    """
    loop, _, _ = make_loop(tmp_path, gate_passed=True)
    generated = await loop.improver.suggest_improvement(
        technique=sample_technique_info(),
        original_source="original prompt body",
        performance=sample_performance(),
        records=[],
        save=True,
    )

    multi_tf = {"1h": [], "15m": []}
    ctx = BacktestContext(
        ohlcv=[],
        symbol="ETH/USDT",
        timeframe="15m",
        ohlcv_by_timeframe=multi_tf,
    )
    await loop._run_cycle(
        generated=generated,
        kind="improvement",
        context=ctx,
    )

    bt_call = loop.backtester.run_for_strategy.await_args
    assert bt_call.kwargs["symbol"] == "ETH/USDT"
    assert bt_call.kwargs["timeframe"] == "15m"
    assert bt_call.kwargs["ohlcv_by_timeframe"] is multi_tf

    gate_call = loop.gate.evaluate.await_args
    assert gate_call.kwargs["symbol"] == "ETH/USDT"
    assert gate_call.kwargs["ohlcv_by_timeframe"] is multi_tf
