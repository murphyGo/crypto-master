"""Approved bounded-read failures preserve position management, never new risk."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.proposal.interaction import ProposalRecord
from src.runtime.activity_log import ActivityEventType
from src.runtime.engine import EngineConfig
from src.runtime.safety_inputs import SafetyReadResult, SafetyReadUnavailable
from src.runtime.safety_score import (
    RuntimeSafetyInputs,
    compute_runtime_safety_score,
)
from src.trading.sub_account import SubAccount
from src.utils.time import now_utc
from tests.test_runtime_engine import (
    FakeSubAccountRegistry,
    build_engine,
    make_proposal,
    make_trade,
)


def _complete(now: datetime, *, elapsed: float = 0.0, size: int = 0):
    return SafetyReadResult(
        score=compute_runtime_safety_score(RuntimeSafetyInputs()),
        evaluated_at=now,
        elapsed_seconds=elapsed,
        bytes_read=size,
        diagnostics={},
    )


@pytest.mark.parametrize("mode", ["paper", "live"])
@pytest.mark.parametrize("pause_threshold", [None, 90])
@pytest.mark.parametrize("failed_call", [1, 2])
async def test_typed_failure_at_either_score_site_preserves_monitor_only(
    tmp_path: Path, mode: str, pause_threshold: int | None, failed_call: int
) -> None:
    proposal = make_proposal(proposal_id="first")
    later = make_proposal(proposal_id="must-not-attempt", symbol="ETH/USDT")
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=proposal,
        altcoin_proposals=[later],
        config=EngineConfig(
            auto_approve_threshold=1.0,
            runtime_safety_pause_min_score=pause_threshold,
        ),
    )
    engine.mode = mode
    # A pre-existing record must survive failure at either location unchanged.
    seed = ProposalRecord(proposal=proposal)
    mocks["history"].save(seed)
    before = {str(p): p.read_bytes() for p in (tmp_path / "proposals").rglob("*.json")}
    calls = 0

    async def read(log, extras, *, now, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failed_call:
            raise SafetyReadUnavailable(
                "safety_source_changed", elapsed_seconds=0.1, bytes_read=17
            )
        return _complete(now)

    service = MagicMock()
    service.evaluate = AsyncMock(side_effect=read)
    engine._safety_input_service = service
    engine._position_monitor.monitor = AsyncMock()
    engine._record_portfolio_snapshot = AsyncMock()

    result = await engine.run_cycle()

    assert calls == failed_call  # Account's later proposal was not attempted.
    mocks["trader"].open_position.assert_not_awaited()
    assert result.positions_opened == result.proposals_rejected == 0
    assert (
        mocks["notification_dispatcher"].notify_proposal.await_count == failed_call - 1
    )
    assert before == {
        str(p): p.read_bytes() for p in (tmp_path / "proposals").rglob("*.json")
    }
    engine._position_monitor.monitor.assert_awaited_once()
    engine._record_portfolio_snapshot.assert_awaited_once()
    assert len(result.errors) == 1
    stored = result.errors[0].exception
    assert isinstance(stored, SafetyReadUnavailable)
    assert stored.__traceback__ is stored.__context__ is stored.__cause__ is None
    errors = mocks["activity_log"].filter(event_type=ActivityEventType.CYCLE_ERRORED)
    assert len(errors) == 1
    assert (
        errors[0].details["error_message"]
        == "runtime_safety_unavailable:safety_source_changed"
    )


async def test_failed_accounts_keep_later_account_monitor_and_no_retry(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path)
    accounts = [
        SubAccount(id=name, name=name, mode="paper", exchange_ref="default")
        for name in ("alpha", "beta")
    ]
    engine.sub_account_registry = FakeSubAccountRegistry(
        accounts, {a.id: mocks["trader"] for a in accounts}
    )

    async def proposal(**kwargs):
        return make_proposal(proposal_id=kwargs["sub_account_id"]).model_copy(
            update={"sub_account_id": kwargs["sub_account_id"]}
        )

    mocks["proposal_engine"].propose_bitcoin.side_effect = proposal
    service = MagicMock()
    service.evaluate = AsyncMock(
        side_effect=SafetyReadUnavailable("safety_source_unreadable")
    )
    engine._safety_input_service = service
    engine._position_monitor.monitor = AsyncMock()
    engine._record_portfolio_snapshot = AsyncMock()
    result = await engine.run_cycle()

    assert len(result.errors) == 2
    assert mocks["proposal_engine"].propose_bitcoin.await_count == 2
    assert [c.args[2].id for c in engine._position_monitor.monitor.await_args_list] == [
        "alpha",
        "beta",
    ]
    assert [
        c.args[1].id for c in engine._record_portfolio_snapshot.await_args_list
    ] == ["alpha", "beta"]
    mocks["trader"].open_position.assert_not_awaited()


async def test_monitor_failure_after_read_failure_is_not_retried(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=make_proposal())
    service = MagicMock()
    service.evaluate = AsyncMock(
        side_effect=SafetyReadUnavailable("safety_read_timeout")
    )
    engine._safety_input_service = service
    engine._position_monitor.monitor = AsyncMock(
        side_effect=RuntimeError("monitor fault")
    )
    engine._record_portfolio_snapshot = AsyncMock()
    result = await engine.run_cycle()
    assert len(result.errors) == 2
    engine._position_monitor.monitor.assert_awaited_once()
    engine._record_portfolio_snapshot.assert_not_awaited()
    mocks["trader"].open_position.assert_not_awaited()


async def test_safety_failure_still_executes_existing_position_stop_loss(
    tmp_path: Path,
) -> None:
    trade = make_trade(trade_id="protected-position", entry_time=now_utc())
    closed = make_trade(
        trade_id="protected-position",
        status="closed",
        exit_price="47000",
        pnl_percent=-6.0,
    )
    engine, mocks = build_engine(
        tmp_path=tmp_path,
        btc_proposal=make_proposal(),
        open_trades=[trade],
        ticker_price=Decimal("47000"),
    )
    service = MagicMock()
    service.evaluate = AsyncMock(
        side_effect=SafetyReadUnavailable("safety_read_timeout")
    )
    engine._safety_input_service = service
    mocks["trader"].get_open_position.return_value = MagicMock()
    mocks["trader"].check_exit_conditions.return_value = (True, "stop_loss")
    mocks["trader"].close_position.return_value = closed
    engine._record_portfolio_snapshot = AsyncMock()

    result = await engine.run_cycle()

    assert len(result.errors) == 1
    assert result.positions_opened == 0
    assert result.positions_closed == 1
    mocks["trader"].open_position.assert_not_awaited()
    mocks["trader"].close_position.assert_awaited_once_with(
        "protected-position", Decimal("47000"), reason="stop_loss"
    )
    engine._record_portfolio_snapshot.assert_awaited_once()
    closed_events = mocks["activity_log"].filter(
        event_type=ActivityEventType.POSITION_CLOSED
    )
    assert len(closed_events) == 1


async def test_actual_cancellation_propagates_and_never_resumes_monitor(
    tmp_path: Path,
) -> None:
    engine, mocks = build_engine(tmp_path=tmp_path, btc_proposal=make_proposal())
    entered = asyncio.Event()

    async def read(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    service = MagicMock()
    service.evaluate = AsyncMock(side_effect=read)
    engine._safety_input_service = service
    engine._position_monitor.monitor = AsyncMock()
    engine._record_portfolio_snapshot = AsyncMock()
    task = asyncio.create_task(engine.run_cycle())
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    engine._position_monitor.monitor.assert_not_awaited()
    engine._record_portfolio_snapshot.assert_not_awaited()
    mocks["trader"].open_position.assert_not_awaited()
    assert not mocks["activity_log"].filter(event_type=ActivityEventType.CYCLE_ERRORED)


async def test_cycle_byte_exhaustion_includes_failed_reads_and_resets(
    tmp_path: Path,
) -> None:
    engine, _ = build_engine(tmp_path=tmp_path)
    service = MagicMock()
    service.evaluate = AsyncMock(
        side_effect=SafetyReadUnavailable(
            "safety_read_byte_limit", bytes_read=2 * 1024**3
        )
    )
    engine._safety_input_service = service
    for _ in range(2):
        with pytest.raises(SafetyReadUnavailable, match="safety_read_byte_limit"):
            await engine._current_runtime_safety_score([])
    with pytest.raises(SafetyReadUnavailable, match="safety_cycle_budget_exhausted"):
        await engine._current_runtime_safety_score([])
    assert service.evaluate.await_count == 2
    await engine.run_cycle()  # No proposals; resets the cycle-owned accounting.
    assert engine._safety_read_bytes == engine._safety_read_seconds == 0


async def test_cycle_time_budget_limits_next_read_and_no_failed_cache_fallback(
    tmp_path: Path,
) -> None:
    engine, _ = build_engine(tmp_path=tmp_path)
    service = MagicMock()

    async def success(log, extras, *, now, **kwargs):
        return _complete(now)

    service.evaluate = AsyncMock(side_effect=success)
    engine._safety_input_service = service
    cached = await engine._current_runtime_safety_score()
    captured = engine._runtime_safety_evaluated_at
    engine._safety_read_seconds = 59.5
    service.evaluate.side_effect = SafetyReadUnavailable(
        "safety_read_timeout", elapsed_seconds=0.5
    )
    with pytest.raises(SafetyReadUnavailable, match="safety_read_timeout"):
        await engine._current_runtime_safety_score([])
    assert service.evaluate.await_args.kwargs["max_seconds"] == 0.5
    with pytest.raises(SafetyReadUnavailable, match="safety_cycle_budget_exhausted"):
        await engine._current_runtime_safety_score([])
    assert await engine._current_runtime_safety_score() is cached
    assert engine._runtime_safety_evaluated_at == captured
