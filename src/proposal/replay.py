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

from pydantic import BaseModel, Field, model_validator

from src.models import OHLCV
from src.proposal.interaction import ProposalDecision, ProposalHistory, ProposalRecord
from src.utils.time import ensure_utc


class ProposalReplayInputError(ValueError):
    """Raised when proposal replay input cannot be built safely."""


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


__all__ = [
    "ProposalReplayCase",
    "ProposalReplayInput",
    "ProposalReplayInputError",
]
