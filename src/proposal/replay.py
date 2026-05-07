"""Proposal replay input models.

This module defines the replay dataset contract before simulation logic lands:
historical proposal records are paired with explicit candle windows so threshold
and exit-assumption experiments can stay deterministic.

Related Requirements:
- FR-013: User Accept/Reject
- FR-014: Proposal History Management
- FR-025: Backtesting and performance feedback
- FR-043: Proposal replay simulator
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.models import OHLCV
from src.proposal.interaction import ProposalDecision, ProposalHistory, ProposalRecord
from src.utils.time import ensure_utc
from src.utils.trading_math import pnl_for_trade


class ProposalReplayInputError(ValueError):
    """Raised when proposal replay input cannot be built safely."""


class ProposalReplayExitAssumption(str, Enum):
    """How to resolve ambiguous same-candle TP/SL touches."""

    STOP_FIRST = "stop_first"
    TAKE_PROFIT_FIRST = "take_profit_first"


class ProposalReplayCase(BaseModel):
    """One historical proposal plus the candle window used to replay it."""

    record: ProposalRecord
    candles: list[OHLCV] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_candle_window(self) -> ProposalReplayCase:
        timestamps = [ensure_utc(candle.timestamp) for candle in self.candles]
        if timestamps != sorted(timestamps):
            raise ValueError("candles must be sorted by timestamp ascending")

        created_at = ensure_utc(self.record.proposal.created_at)
        if all(timestamp < created_at for timestamp in timestamps):
            raise ValueError(
                "candle window must include data at or after proposal time"
            )
        return self

    @property
    def proposal_id(self) -> str:
        return self.record.proposal.proposal_id

    @property
    def created_at(self) -> datetime:
        return ensure_utc(self.record.proposal.created_at)


class ProposalReplayInput(BaseModel):
    """Deterministic replay input built from proposal history and candles."""

    cases: list[ProposalReplayCase] = Field(min_length=1)

    @classmethod
    def from_records(
        cls,
        records: list[ProposalRecord],
        candle_windows: Mapping[str, list[OHLCV]],
    ) -> ProposalReplayInput:
        """Build replay input from loaded proposal records and candle windows."""
        if not records:
            raise ProposalReplayInputError("no proposal records available for replay")

        cases: list[ProposalReplayCase] = []
        sorted_records = sorted(
            records,
            key=lambda item: ensure_utc(item.proposal.created_at),
        )
        for record in sorted_records:
            proposal_id = record.proposal.proposal_id
            candles = candle_windows.get(proposal_id)
            if candles is None:
                raise ProposalReplayInputError(
                    f"missing candle window for proposal {proposal_id}"
                )
            try:
                cases.append(ProposalReplayCase(record=record, candles=candles))
            except ValueError as exc:
                raise ProposalReplayInputError(
                    f"invalid candle window for proposal {proposal_id}: {exc}"
                ) from exc
        return cls(cases=cases)

    @classmethod
    def from_history(
        cls,
        history: ProposalHistory,
        candle_windows: Mapping[str, list[OHLCV]],
        *,
        decision: ProposalDecision | None = None,
    ) -> ProposalReplayInput:
        """Build replay input from a ``ProposalHistory`` store."""
        return cls.from_records(history.list_all(decision=decision), candle_windows)

    def case_for(self, proposal_id: str) -> ProposalReplayCase:
        """Return the replay case for a proposal id."""
        for case in self.cases:
            if case.proposal_id == proposal_id:
                return case
        raise ProposalReplayInputError(f"proposal {proposal_id} is not in replay input")


class ProposalReplayScenario(BaseModel):
    """One replay scenario over approval threshold and exit assumption."""

    min_score: float = Field(default=0.0, ge=0.0)
    exit_assumption: ProposalReplayExitAssumption = (
        ProposalReplayExitAssumption.STOP_FIRST
    )

    @property
    def scenario_id(self) -> str:
        return f"score>={self.min_score:.4f}:{self.exit_assumption.value}"


class ProposalReplayOutcome(BaseModel):
    """Replay result for one proposal under one scenario."""

    proposal_id: str
    approved: bool
    exit_reason: Literal["filtered", "take_profit", "stop_loss", "end_of_data"]
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    gross_pnl: Decimal = Decimal("0")
    pnl_percent: Decimal = Decimal("0")


class ProposalReplayScenarioResult(BaseModel):
    """Aggregate replay result for one scenario."""

    scenario: ProposalReplayScenario
    outcomes: list[ProposalReplayOutcome]
    approved_count: int
    total_gross_pnl: Decimal
    average_pnl_percent: Decimal


def compare_replay_scenarios(
    replay_input: ProposalReplayInput,
    scenarios: list[ProposalReplayScenario],
) -> list[ProposalReplayScenarioResult]:
    """Compare alternate approval thresholds and exit assumptions."""
    if not scenarios:
        raise ProposalReplayInputError("at least one replay scenario is required")
    return [_run_scenario(replay_input, scenario) for scenario in scenarios]


def render_replay_report(results: list[ProposalReplayScenarioResult]) -> str:
    """Render scenario results as a Markdown report for operator tuning."""
    if not results:
        raise ProposalReplayInputError("at least one scenario result is required")

    ranked = sorted(
        results,
        key=lambda result: (result.average_pnl_percent, result.total_gross_pnl),
        reverse=True,
    )
    best = ranked[0]
    lines = [
        "# Proposal Replay Report",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Approved | Total Gross PnL | Average PnL % |",
        "|----------|----------|-----------------|---------------|",
    ]
    for result in ranked:
        lines.append(
            "| "
            f"{result.scenario.scenario_id} | "
            f"{result.approved_count} | "
            f"{_format_decimal(result.total_gross_pnl)} | "
            f"{_format_decimal(result.average_pnl_percent)} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Scenario",
            "",
            (
                f"`{best.scenario.scenario_id}` with "
                f"{best.approved_count} approved proposals, "
                f"{_format_decimal(best.total_gross_pnl)} total gross PnL, "
                f"and {_format_decimal(best.average_pnl_percent)} average PnL %."
            ),
            "",
            "## Outcome Detail",
            "",
            "| Scenario | Proposal | Decision | Exit | Gross PnL | PnL % |",
            "|----------|----------|----------|------|-----------|-------|",
        ]
    )
    for result in ranked:
        for outcome in result.outcomes:
            decision = "approved" if outcome.approved else "filtered"
            lines.append(
                "| "
                f"{result.scenario.scenario_id} | "
                f"{outcome.proposal_id} | "
                f"{decision} | "
                f"{outcome.exit_reason} | "
                f"{_format_decimal(outcome.gross_pnl)} | "
                f"{_format_decimal(outcome.pnl_percent)} |"
            )
    return "\n".join(lines)


def _run_scenario(
    replay_input: ProposalReplayInput,
    scenario: ProposalReplayScenario,
) -> ProposalReplayScenarioResult:
    outcomes = [_replay_case(case, scenario) for case in replay_input.cases]
    approved = [outcome for outcome in outcomes if outcome.approved]
    total_gross_pnl = sum((outcome.gross_pnl for outcome in outcomes), Decimal("0"))
    if approved:
        average_pnl_percent = sum(
            (outcome.pnl_percent for outcome in approved),
            Decimal("0"),
        ) / Decimal(len(approved))
    else:
        average_pnl_percent = Decimal("0")
    return ProposalReplayScenarioResult(
        scenario=scenario,
        outcomes=outcomes,
        approved_count=len(approved),
        total_gross_pnl=total_gross_pnl,
        average_pnl_percent=average_pnl_percent,
    )


def _replay_case(
    case: ProposalReplayCase,
    scenario: ProposalReplayScenario,
) -> ProposalReplayOutcome:
    proposal = case.record.proposal
    if proposal.score.composite < scenario.min_score:
        return ProposalReplayOutcome(
            proposal_id=case.proposal_id,
            approved=False,
            exit_reason="filtered",
        )

    eligible_candles = [
        candle
        for candle in case.candles
        if ensure_utc(candle.timestamp) >= case.created_at
    ]
    exit_price, exit_time, exit_reason = _resolve_exit(
        case,
        eligible_candles,
        scenario.exit_assumption,
    )
    gross_pnl = pnl_for_trade(
        proposal.entry_price,
        exit_price,
        proposal.quantity,
        proposal.signal,
    )
    pnl_percent = _pnl_percent(
        proposal.entry_price,
        exit_price,
        proposal.signal,
    )
    return ProposalReplayOutcome(
        proposal_id=case.proposal_id,
        approved=True,
        exit_reason=exit_reason,
        exit_time=exit_time,
        exit_price=exit_price,
        gross_pnl=gross_pnl,
        pnl_percent=pnl_percent,
    )


def _resolve_exit(
    case: ProposalReplayCase,
    candles: list[OHLCV],
    assumption: ProposalReplayExitAssumption,
) -> tuple[Decimal, datetime, Literal["take_profit", "stop_loss", "end_of_data"]]:
    proposal = case.record.proposal
    for candle in candles:
        if ensure_utc(candle.timestamp) <= case.created_at:
            continue
        tp_hit = _touches_take_profit(candle, proposal.signal, proposal.take_profit)
        sl_hit = _touches_stop_loss(candle, proposal.signal, proposal.stop_loss)
        if not tp_hit and not sl_hit:
            continue
        exit_reason: Literal["take_profit", "stop_loss"]
        exit_price: Decimal
        if tp_hit and sl_hit:
            if assumption is ProposalReplayExitAssumption.TAKE_PROFIT_FIRST:
                exit_reason = "take_profit"
                exit_price = proposal.take_profit
            else:
                exit_reason = "stop_loss"
                exit_price = proposal.stop_loss
        elif tp_hit:
            exit_reason = "take_profit"
            exit_price = proposal.take_profit
        else:
            exit_reason = "stop_loss"
            exit_price = proposal.stop_loss
        return exit_price, ensure_utc(candle.timestamp), exit_reason

    last = candles[-1]
    return last.close, ensure_utc(last.timestamp), "end_of_data"


def _touches_take_profit(
    candle: OHLCV,
    side: Literal["long", "short"],
    price: Decimal,
) -> bool:
    if side == "long":
        return candle.high >= price
    return candle.low <= price


def _touches_stop_loss(
    candle: OHLCV,
    side: Literal["long", "short"],
    price: Decimal,
) -> bool:
    if side == "long":
        return candle.low <= price
    return candle.high >= price


def _pnl_percent(
    entry_price: Decimal,
    exit_price: Decimal,
    side: Literal["long", "short"],
) -> Decimal:
    if side == "long":
        return ((exit_price - entry_price) / entry_price) * Decimal("100")
    return ((entry_price - exit_price) / entry_price) * Decimal("100")


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


__all__ = [
    "ProposalReplayExitAssumption",
    "ProposalReplayCase",
    "ProposalReplayInput",
    "ProposalReplayInputError",
    "ProposalReplayOutcome",
    "ProposalReplayScenario",
    "ProposalReplayScenarioResult",
    "compare_replay_scenarios",
    "render_replay_report",
]
