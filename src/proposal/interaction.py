"""User-interaction layer for trading proposals (Phase 6.2).

Phase 6.1's ``ProposalEngine`` is intentionally headless: it returns
ranked ``Proposal`` objects but never speaks to the user or persists
anything. This module closes that gap with three concerns kept loosely
coupled so a future Streamlit dashboard can reuse pieces independently:

* ``format_proposal`` — pure render of a proposal to a CLI banner.
* ``default_decision_prompt`` — async stdin yes/no callback. Pluggable.
* ``ProposalHistory`` — per-proposal JSON files under ``data/proposals/``.
* ``ProposalInteraction`` — orchestrator that displays, prompts, and
  saves a ``ProposalRecord`` for every decision.

The persistence model also exposes ``attach_outcome`` so that once a
trade closes (Phase 7+ wiring), the realized P&L can be linked back to
the proposal that spawned it — fulfilling FR-014's "actual performance"
requirement.

Related Requirements:
- FR-013: User Accept/Reject
- FR-014: Proposal History Management
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from src.logger import get_logger
from src.proposal.engine import Proposal

logger = get_logger("crypto_master.proposal.interaction")


DEFAULT_HISTORY_DIR = Path("data/proposals")
_REASONING_PREVIEW_CHARS = 280


# =============================================================================
# Errors
# =============================================================================


class ProposalHistoryError(Exception):
    """Raised when a history operation fails (missing id, etc.)."""


# =============================================================================
# Decision types
# =============================================================================


class ProposalDecision(str, Enum):
    """User's verdict on a proposal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class ProposalDecisionInput:
    """Result returned by a ``ProposalDecisionCallback``.

    Attributes:
        accepted: True if the user wants to act on the proposal.
        reason: Optional free-form text. Conventionally a rejection
            reason; ignored when ``accepted`` is True.
    """

    accepted: bool
    reason: str | None = None


ProposalDecisionCallback = Callable[[Proposal], Awaitable[ProposalDecisionInput]]


# =============================================================================
# Persistence model
# =============================================================================


class ProposalRecord(BaseModel):
    """A proposal plus the user's decision and (later) realized outcome.

    Attributes:
        proposal: The full ``Proposal`` payload as ranked by the engine.
        decision: PENDING until the user responds; ACCEPTED or REJECTED
            after.
        decision_at: When the decision was recorded.
        actor: Who made the call. Defaults to ``"user"``; the dashboard
            or a multi-user setup can pass an account name.
        rejection_reason: Free-form text supplied at rejection time.
        trade_id: ``TradeHistory.id`` once an accepted proposal is
            actually executed. Filled by ``attach_outcome``.
        outcome_pnl_percent: Realized P&L for the executed trade, in
            percent of entry. Filled by ``attach_outcome``.
        outcome_recorded_at: When the outcome was attached.
    """

    proposal: Proposal
    decision: ProposalDecision = ProposalDecision.PENDING
    decision_at: datetime | None = None
    actor: str | None = None
    rejection_reason: str | None = None
    trade_id: str | None = None
    outcome_pnl_percent: float | None = None
    outcome_recorded_at: datetime | None = None

    model_config = {"use_enum_values": True}


# =============================================================================
# Display
# =============================================================================


def format_proposal(proposal: Proposal) -> str:
    """Render a ``Proposal`` as a multi-line CLI banner.

    Mirrors the bordered shape of ``src.trading.live.default_confirmation``
    so users see consistent framing across confirmation flows.

    Args:
        proposal: The proposal to render.

    Returns:
        A newline-joined string ready to ``print``.
    """
    score = proposal.score
    reasoning = proposal.reasoning or "(no reasoning provided)"
    if len(reasoning) > _REASONING_PREVIEW_CHARS:
        reasoning = reasoning[:_REASONING_PREVIEW_CHARS].rstrip() + "..."

    lines = [
        "",
        "=== TRADING PROPOSAL ===",
        f"Proposal ID:  {proposal.proposal_id}",
        f"Created:      {proposal.created_at.isoformat(timespec='seconds')}",
        f"Symbol:       {proposal.symbol}  ({proposal.timeframe})",
        f"Signal:       {proposal.signal.upper()}",
        f"Technique:    {proposal.technique_name} v{proposal.technique_version}",
    ]
    if proposal.profile_name:
        lines.append(f"Profile:      {proposal.profile_name}")
    lines.extend(
        [
            f"Entry:        {proposal.entry_price}",
            f"Stop Loss:    {proposal.stop_loss}",
            f"Take Profit:  {proposal.take_profit}",
            f"Quantity:     {proposal.quantity}",
            f"Leverage:     {proposal.leverage}x",
            f"R/R:          {proposal.risk_reward_ratio:.2f}",
            "--- Score ---",
            f"Composite:    {score.composite:.4f}",
            f"Confidence:   {score.confidence:.2f}",
            f"Sample size:  {score.sample_size}",
            f"Win rate:     {score.win_rate:.2%}",
            f"Expected EV:  {score.expected_value:.2f}%",
            "--- Reasoning ---",
            reasoning,
            "========================",
        ]
    )
    return "\n".join(lines)


# =============================================================================
# Default CLI prompt
# =============================================================================


async def default_decision_prompt(proposal: Proposal) -> ProposalDecisionInput:
    """Print the proposal banner and read accept/reject from stdin.

    Uses ``asyncio.to_thread`` so the event loop is not blocked while
    waiting for input — same approach as
    ``src.trading.live.default_confirmation``.

    Returns:
        ``ProposalDecisionInput`` with ``accepted`` reflecting the user's
        answer. On rejection, asks for an optional reason; an empty
        response means no reason was supplied.
    """
    print(format_proposal(proposal))

    answer = await asyncio.to_thread(input, "Accept proposal? (yes/no): ")
    accepted = answer.strip().lower() in ("yes", "y")
    if accepted:
        return ProposalDecisionInput(accepted=True)

    reason_raw = await asyncio.to_thread(
        input, "Rejection reason (optional, press Enter to skip): "
    )
    reason = reason_raw.strip() or None
    return ProposalDecisionInput(accepted=False, reason=reason)


# =============================================================================
# Persistence
# =============================================================================


class ProposalHistory:
    """JSON-per-proposal history under ``data/proposals/``.

    Same pattern as ``FeedbackLoop.save_state`` / ``load_state``:
    one ``{proposal_id}.json`` file per record, written atomically via
    ``Path.write_text`` after Pydantic serializes the whole record.

    The directory is created lazily on first ``save``; tests should pass
    ``tmp_path`` so the real ``data/proposals/`` is left untouched.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize the history.

        Args:
            data_dir: Directory to read/write under. Defaults to
                ``data/proposals/``.
        """
        self.data_dir = data_dir or DEFAULT_HISTORY_DIR

    def save(self, record: ProposalRecord) -> None:
        """Persist a record, overwriting any earlier snapshot."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(record.proposal.proposal_id)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        logger.debug(
            f"Saved proposal record {record.proposal.proposal_id} "
            f"decision={record.decision} → {path}"
        )

    def load(self, proposal_id: str) -> ProposalRecord:
        """Load a single record by proposal_id.

        Raises:
            ProposalHistoryError: If no file exists for that id.
        """
        path = self._path_for(proposal_id)
        if not path.exists():
            raise ProposalHistoryError(
                f"No proposal record for id={proposal_id} at {path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProposalRecord(**payload)

    def list_all(
        self,
        decision: ProposalDecision | None = None,
    ) -> list[ProposalRecord]:
        """Return every record, optionally filtered by decision.

        Records are sorted by ``proposal.created_at`` ascending so
        callers get a deterministic chronological view. Malformed files
        are skipped with a warning rather than aborting the listing.
        """
        if not self.data_dir.exists():
            return []

        records: list[ProposalRecord] = []
        for path in sorted(self.data_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(ProposalRecord(**payload))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping unreadable proposal file {path}: {e}")

        records.sort(key=lambda r: r.proposal.created_at)

        if decision is not None:
            wanted = (
                decision.value if isinstance(decision, ProposalDecision) else decision
            )
            records = [r for r in records if r.decision == wanted]
        return records

    def attach_outcome(
        self,
        proposal_id: str,
        *,
        trade_id: str,
        pnl_percent: float,
    ) -> ProposalRecord:
        """Link an executed trade's realized outcome back to a proposal.

        Called after a trade closes (paper or live) so the proposal
        history captures actual performance per FR-014.

        Args:
            proposal_id: ID of the proposal to update.
            trade_id: ``TradeHistory.id`` for the executed trade.
            pnl_percent: Realized P&L in percent of entry.

        Returns:
            The updated record (also persisted).

        Raises:
            ProposalHistoryError: If the proposal id is unknown.
        """
        record = self.load(proposal_id)
        updated = record.model_copy(
            update={
                "trade_id": trade_id,
                "outcome_pnl_percent": pnl_percent,
                "outcome_recorded_at": datetime.now(),
            }
        )
        self.save(updated)
        logger.info(
            f"Attached outcome to proposal {proposal_id}: "
            f"trade={trade_id} pnl={pnl_percent:.2f}%"
        )
        return updated

    def attach_trade(
        self,
        proposal_id: str,
        *,
        trade_id: str,
    ) -> ProposalRecord:
        """Link an executed trade at open time, before the outcome is known.

        Distinct from :meth:`attach_outcome` (which expects a realized
        P&L): the engine calls this immediately after
        ``PaperTrader.open_position`` so the proposal record carries
        the trade pointer right away. Realized P&L is filled in later
        by ``attach_outcome`` once the trade closes.

        Args:
            proposal_id: ID of the proposal to update.
            trade_id: ``TradeHistory.id`` for the just-opened trade.

        Returns:
            The updated record (also persisted).

        Raises:
            ProposalHistoryError: If the proposal id is unknown.
        """
        record = self.load(proposal_id)
        updated = record.model_copy(update={"trade_id": trade_id})
        self.save(updated)
        logger.info(
            f"Linked trade {trade_id} to proposal {proposal_id} (outcome pending)"
        )
        return updated

    def _path_for(self, proposal_id: str) -> Path:
        return self.data_dir / f"{proposal_id}.json"


# =============================================================================
# Orchestrator
# =============================================================================


class ProposalInteraction:
    """Display a proposal, ask for accept/reject, persist the decision.

    Glue between :func:`format_proposal`, a
    :data:`ProposalDecisionCallback`, and :class:`ProposalHistory`. CLI
    drivers and the eventual dashboard both go through here so the
    persistence shape stays consistent.
    """

    def __init__(
        self,
        history: ProposalHistory | None = None,
        decision_callback: ProposalDecisionCallback | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            history: Where to store records. Defaults to a fresh
                ``ProposalHistory()`` writing to ``data/proposals/``.
            decision_callback: Async callable that returns a
                :class:`ProposalDecisionInput`. Defaults to
                :func:`default_decision_prompt` which reads stdin.
        """
        self.history = history or ProposalHistory()
        self._decision_callback: ProposalDecisionCallback = (
            decision_callback or default_decision_prompt
        )

    async def present(
        self,
        proposal: Proposal,
        actor: str = "user",
    ) -> ProposalRecord:
        """Show one proposal, await a decision, persist the record.

        The callback is responsible for any UI; this method only
        translates its output into a :class:`ProposalRecord`. If the
        callback raises, no record is saved — the caller sees the
        exception and decides what to do.

        Args:
            proposal: Proposal to present.
            actor: Identifier for who is making the decision.

        Returns:
            The persisted :class:`ProposalRecord`.
        """
        decision_input = await self._decision_callback(proposal)

        if decision_input.accepted:
            decision = ProposalDecision.ACCEPTED
            rejection_reason = None
        else:
            decision = ProposalDecision.REJECTED
            rejection_reason = decision_input.reason

        record = ProposalRecord(
            proposal=proposal,
            decision=decision,
            decision_at=datetime.now(),
            actor=actor,
            rejection_reason=rejection_reason,
        )
        self.history.save(record)
        logger.info(f"Proposal {proposal.proposal_id} {decision.value} by {actor}")
        return record

    async def present_batch(
        self,
        proposals: Iterable[Proposal],
        actor: str = "user",
    ) -> list[ProposalRecord]:
        """Present each proposal in order; collect the resulting records.

        Useful for altcoin scans where the engine returns a top-K list
        and the user wants to walk through them sequentially.
        """
        records: list[ProposalRecord] = []
        for proposal in proposals:
            record = await self.present(proposal, actor=actor)
            records.append(record)
        return records


__all__ = [
    "DEFAULT_HISTORY_DIR",
    "ProposalDecision",
    "ProposalDecisionCallback",
    "ProposalDecisionInput",
    "ProposalHistory",
    "ProposalHistoryError",
    "ProposalInteraction",
    "ProposalRecord",
    "default_decision_prompt",
    "format_proposal",
]
