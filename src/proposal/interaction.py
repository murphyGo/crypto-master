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

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel

from src.config import get_settings
from src.logger import get_logger
from src.proposal.engine import Proposal
from src.utils.io import atomic_write_text
from src.utils.pydantic_mixins import UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.proposal.interaction")


# Relative-path marker; the live default is derived from
# ``Settings.data_dir`` at construction time so proposal history
# survives container recycles on managed hosts (Phase 10.5).
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


class ProposalFinalState(str, Enum):
    """Terminal funnel-state for a proposal.

    See ``aidlc-docs/construction/proposal-funnel-audit/functional-design/spec.md``
    §1 for the canonical funnel taxonomy. ``decision`` (above) records
    the *score-time* outcome; ``final_state`` records the *funnel
    terminal* — a proposal can carry ``decision=ACCEPTED`` *and*
    ``final_state=gate_rejected_symbol_cap`` once a post-acceptance
    gate fires.

    Legacy-record backfill policy (resolved 2026-05-13): forward-only
    with ``gate_rejected_unknown`` as the fallback bucket for any
    on-disk record that pre-dates this field. The funnel aggregator
    inspects the persisted ``final_state`` (defaulting to
    ``GENERATED`` on the model) and re-maps legacy rows whose
    ``decision`` is set but ``final_state`` is still the default into
    ``GATE_REJECTED_UNKNOWN`` — we do *not* walk history to infer the
    original gate. New rows always carry the precise terminal state.
    """

    GENERATED = "generated"
    SCORED = "scored"
    SCORE_ACCEPTED = "score_accepted"
    SCORE_REJECTED = "score_rejected"
    GATE_REJECTED_MARKET_REGIME = "gate_rejected_market_regime"
    GATE_REJECTED_CORRELATION = "gate_rejected_correlation"
    GATE_REJECTED_TREND_FILTER = "gate_rejected_trend_filter"
    GATE_REJECTED_SIBLING_FAMILY = "gate_rejected_sibling_family"
    GATE_REJECTED_RUNTIME_SAFETY_PAUSE = "gate_rejected_runtime_safety_pause"
    GATE_REJECTED_TOTAL_CAP = "gate_rejected_total_cap"
    GATE_REJECTED_SYMBOL_CAP = "gate_rejected_symbol_cap"
    GATE_REJECTED_STALE_QUOTE = "gate_rejected_stale_quote"
    # cross-account-risk-policy (2026-05-13): four new terminals for
    # the risk-policy gate stack. Per the spec resolutions, paper-mode
    # behaviour for the aggregate-cap / stale-block / risk-sizing
    # rejections is advisory — the proposal record still lands in the
    # appropriate ``gate_rejected_*`` bucket so the funnel surfaces
    # it, but live mode is the only place that hard-blocks. The
    # bucket itself is shared across both modes for funnel accounting.
    GATE_REJECTED_ACCOUNT_AGGREGATE_CAP = "gate_rejected_account_aggregate_cap"
    GATE_REJECTED_STALE_POSITION_BLOCK = "gate_rejected_stale_position_block"
    GATE_REJECTED_RISK_SIZING = "gate_rejected_risk_sizing"
    GATE_REJECTED_UNKNOWN = "gate_rejected_unknown"
    PROPOSAL_OPENED = "proposal_opened"
    TRADE_OPENED = "trade_opened"
    OUTCOME_LINKED = "outcome_linked"
    OPEN_ERRORED = "open_errored"


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


class ProposalRecord(UtcTimestampMixin, BaseModel):
    """A proposal plus the user's decision and (later) realized outcome.

    Attributes:
        proposal: The full ``Proposal`` payload as ranked by the engine.
        sub_account_id: Capital bucket mirror of
            ``proposal.sub_account_id``. Defaults to ``"default"`` for
            legacy records.
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
    sub_account_id: str = "default"
    decision: ProposalDecision = ProposalDecision.PENDING
    decision_at: datetime | None = None
    actor: str | None = None
    rejection_reason: str | None = None
    trade_id: str | None = None
    outcome_pnl_percent: float | None = None
    outcome_recorded_at: datetime | None = None
    # proposal-funnel-audit (2026-05-13): terminal funnel state for the
    # record. Defaults to ``GENERATED`` so legacy rows (pre-cutover)
    # load successfully; the funnel aggregator buckets any legacy row
    # whose ``decision`` is non-PENDING but ``final_state`` is still
    # ``GENERATED`` into ``GATE_REJECTED_UNKNOWN``.
    final_state: ProposalFinalState = ProposalFinalState.GENERATED

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
    one ``{proposal_id}.json`` file per record, written via the
    project-wide ``atomic_write_text`` helper after Pydantic
    serializes the whole record (DEBT-028 / Phase 22.1).

    The directory is created lazily on first ``save``; tests should pass
    ``tmp_path`` so the real ``data/proposals/`` is left untouched.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize the history.

        Args:
            data_dir: Directory to read/write under. When omitted,
                defaults to ``<Settings.data_dir>/proposals`` so the
                history lands on the persistent volume operations has
                mounted (Phase 10.5).
        """
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            self.data_dir = get_settings().data_dir / "proposals"

    def save(self, record: ProposalRecord) -> None:
        """Persist a record, overwriting any earlier snapshot."""
        record = record.model_copy(
            update={"sub_account_id": record.proposal.sub_account_id}
        )
        path = self._path_for(
            record.proposal.proposal_id,
            sub_account_id=record.sub_account_id,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        # DEBT-028 (Phase 22.1): the engine's stale-quote rejection
        # path does load → model_copy → save against this same file
        # in the same cycle that ``ProposalInteraction.present`` first
        # wrote it; atomic write prevents a crash between the two
        # writes from leaving a truncated record on disk.
        atomic_write_text(path, record.model_dump_json(indent=2))
        logger.debug(
            f"Saved proposal record {record.proposal.proposal_id} "
            f"decision={record.decision} → {path}"
        )

    def load(
        self,
        proposal_id: str,
        *,
        sub_account_id: str | None = None,
    ) -> ProposalRecord:
        """Load a single record by proposal_id.

        Raises:
            ProposalHistoryError: If no file exists for that id.
        """
        path = self._path_for(proposal_id, sub_account_id=sub_account_id)
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
        for path in self._iter_record_paths():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(ProposalRecord(**payload))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping unreadable proposal file {path}: {e}")

        def _sort_key(r: ProposalRecord) -> datetime:
            return ensure_utc(r.proposal.created_at)

        records.sort(key=_sort_key)

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
                "outcome_recorded_at": now_utc(),
                # proposal-funnel-audit §1 State 7: outcome linkage is
                # the funnel terminal once a closed trade is paired
                # back to its originating proposal record.
                "final_state": ProposalFinalState.OUTCOME_LINKED.value,
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

    def _path_for(self, proposal_id: str, sub_account_id: str | None = None) -> Path:
        if sub_account_id is not None:
            return self.data_dir / sub_account_id / f"{proposal_id}.json"

        default_path = self.data_dir / "default" / f"{proposal_id}.json"
        if default_path.exists():
            return default_path

        legacy_path = self.data_dir / f"{proposal_id}.json"
        if legacy_path.exists():
            return legacy_path

        matches = [
            path
            for path in sorted(self.data_dir.glob(f"*/{proposal_id}.json"))
            if "archive" not in path.relative_to(self.data_dir).parts
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            accounts = ", ".join(path.parent.name for path in matches)
            raise ProposalHistoryError(
                f"Proposal id={proposal_id} exists in multiple sub-accounts: "
                f"{accounts}. Pass sub_account_id to load the exact record."
            )
        return default_path

    def _iter_record_paths(self) -> list[Path]:
        paths = list(self.data_dir.glob("*.json"))
        paths.extend(self.data_dir.glob("*/*.json"))
        return sorted(
            path
            for path in paths
            if "archive" not in path.relative_to(self.data_dir).parts
        )

    # =========================================================================
    # Retention (Phase 10.4)
    # =========================================================================

    def purge_old(
        self,
        now: datetime | None = None,
        retention_months: int | None = None,
    ) -> list[Path]:
        """Move records older than the retention window to an archive subdir.

        Walks ``<data_dir>/*.json``, parses each proposal's
        ``created_at``, and for any record older than
        ``now - relativedelta(months=retention_months)`` (true calendar
        months — DEBT-036 / Phase 26.2 — not the legacy ``30 *
        retention_months`` day approximation, which drifted ~5 days
        per year) moves the file to
        ``<data_dir>/archive/<YYYY-MM>/<original_filename>`` where
        ``YYYY-MM`` is the proposal's *own* creation month (so the
        archive is naturally bucketed alongside the matching audit /
        activity rotations).

        Idempotent — re-running with the same retention does nothing
        because the archive lives under a subdirectory the top-level
        glob ignores.

        Operator-callable: the engine does *not* call this on every
        write. A startup hook or CLI command can invoke it; for Phase
        10.4 the method exists, is tested, and is left wired up to
        nothing.

        Args:
            now: Wall-clock reference. Defaults to ``now_utc()``.
                Tests pass a fixed datetime to make the cutoff
                deterministic. Naive inputs are coerced to UTC so the
                comparison against on-disk records (which may carry
                aware timestamps post-Phase 21.2) doesn't raise.
            retention_months: Window in months. Defaults to
                ``Settings.log_retention_months``.

        Returns:
            The list of archived file paths (post-move). Empty when
            nothing was old enough.
        """
        if not self.data_dir.exists():
            return []

        if now is None:
            now = now_utc()
        else:
            now = ensure_utc(now)
        if retention_months is None:
            retention_months = get_settings().log_retention_months
        # DEBT-036 (Phase 26.2): true calendar months. The legacy
        # ``timedelta(days=30 * retention_months)`` approximation
        # drifted ~5 days/year — for ``retention_months=12`` from
        # 2026-01-15 it produced 2025-01-20 instead of the calendar-
        # correct 2025-01-15.
        cutoff = now - relativedelta(months=retention_months)

        archived: list[Path] = []
        for path in self._iter_record_paths():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = ProposalRecord(**payload)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    f"Skipping unreadable proposal file during purge {path}: {e}"
                )
                continue

            created_at = ensure_utc(record.proposal.created_at)
            if created_at >= cutoff:
                continue

            month_token = created_at.strftime("%Y-%m")
            sub_account_id = record.sub_account_id or record.proposal.sub_account_id
            archive_dir = self.data_dir / sub_account_id / "archive" / month_token
            archive_dir.mkdir(parents=True, exist_ok=True)
            destination = archive_dir / path.name
            path.replace(destination)
            archived.append(destination)
            logger.info(
                f"Purged proposal {record.proposal.proposal_id} "
                f"(created {created_at.isoformat()}) → {destination}"
            )
        return archived


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

    def set_decision_callback(self, callback: ProposalDecisionCallback) -> None:
        """Swap the decision callback in place.

        DEBT-041 (Phase 26.2): the ``RuntimeEngine`` previously reached
        into ``self._decision_callback`` directly to inject its
        auto-decide path. This public setter pins the contract so the
        engine (and any future caller) can swap the callback without
        a private-attribute access + ``# type: ignore[attr-defined]``.

        Args:
            callback: Async callable returning a
                :class:`ProposalDecisionInput` for a given proposal.
        """
        self._decision_callback = callback

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
        record = await self.decide(proposal, actor=actor)
        self.history.save(record)
        logger.info(f"Proposal {proposal.proposal_id} {record.decision} by {actor}")
        return record

    async def decide(
        self,
        proposal: Proposal,
        actor: str = "user",
    ) -> ProposalRecord:
        """Return a decision record without persisting it."""
        decision_input = await self._decision_callback(proposal)

        if decision_input.accepted:
            decision = ProposalDecision.ACCEPTED
            rejection_reason = None
        else:
            decision = ProposalDecision.REJECTED
            rejection_reason = decision_input.reason

        return ProposalRecord(
            proposal=proposal,
            sub_account_id=proposal.sub_account_id,
            decision=decision,
            decision_at=now_utc(),
            actor=actor,
            rejection_reason=rejection_reason,
        )

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
    "ProposalFinalState",
    "ProposalHistory",
    "ProposalHistoryError",
    "ProposalInteraction",
    "ProposalRecord",
    "default_decision_prompt",
    "format_proposal",
]
