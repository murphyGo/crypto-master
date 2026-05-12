"""Per-strategy proposal-engine fail-closed-rate metrics (DEBT-061).

Tracks two cumulative counters per ``(sub_account, technique)`` pair:

* ``proposals_emitted`` — every time a strategy got far enough that the
  engine actually invoked ``strategy.analyze()``. This is the
  denominator for "of the times the strategy fired, what fraction got
  rejected at a downstream gate?". Cooldown skips, prompt-trigger
  filters, missing OHLCV, and "no applicable technique" short-circuits
  happen *before* this point and are deliberately NOT counted as
  emissions — they're not "the strategy fired and the gate killed it",
  they're "the strategy never got a chance to fire".

* ``proposals_fail_closed`` — of the emissions, how many were rejected
  after the strategy had a chance to produce a candidate:

  - the strategy itself raised :class:`StrategyError` (e.g.
    LLM timeout, missing indicator data) — the seed pointer at
    ``src/proposal/engine.py:650``;
  - position sizing raised :class:`TradingValidationError` — the
    canonical "R/R floor / sizing-failed" case named in DEBT-061's
    description (this is the case that silently dropped ~50% of RSI
    proposals for 12 days during DEBT-060).

  Neutral analysis results are **not** counted as fail-closed: the
  strategy emitted, looked at the data, and said "no setup here" —
  that's a normal no-signal day, not a gate rejection.

Persistence mirrors :mod:`src.strategy.performance` — one JSON file per
``(sub_account_id, technique_name)`` under
``data/performance/<sub_account_id>/<technique_name>/fail_closed.json``
so this metric lives alongside the existing per-strategy summary that
the Strategies dashboard already reads. Reuses
:func:`src.utils.io.atomic_write_text` so the load-all → mutate →
save-all shape inherits DEBT-028's crash safety.

The tracker is restart-safe: counters survive runtime restart by
reading the on-disk snapshot back into memory on every read. This is
the whole point — operators need *cumulative* fail-closed rates, not
per-process figures that reset every redeploy.

The ``sub_account_id`` is a **per-call argument** on
:meth:`FailClosedMetricsTracker.record_emitted`,
:meth:`FailClosedMetricsTracker.record_fail_closed`, and
:meth:`FailClosedMetricsTracker.get` — not baked in at construction.
The single runtime-owned tracker instance is shared across every
sub-account in the engine (paper-default, paper_alt, etc.) and each
call routes to its own ``<sub_account_id>/<technique>/`` namespace.
Picking a sub-account at construction time would aggregate every
sub-account's emissions under the constructor's sub-account, which
defeats the per-sub-account observability the dashboard reads.

Related Requirements:
- DEBT-061: Per-strategy proposal-engine fail-closed-rate metric for
  dashboard observability.
- DEBT-060: silent ~50% RSI throughput collapse after the 1.5→2.0 R/R
  floor bump — the failure mode this counter pair surfaces.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.strategy.performance import DEFAULT_SUB_ACCOUNT_ID
from src.utils.io import atomic_write_text
from src.utils.time import now_utc

logger = get_logger("crypto_master.proposal.fail_closed_metrics")


class StrategyFailClosedCounts(BaseModel):
    """Cumulative fail-closed counters for one ``(sub_account, technique)``.

    Attributes:
        sub_account_id: Sub-account this snapshot belongs to. Sub-accounts
            run different strategy slates (see ``src/trading/paper.py``)
            so counters are scoped per sub-account.
        technique_name: Strategy name.
        technique_version: Last-seen technique version. Recorded for
            forensic value (which version produced the cumulative
            counts) but not used as a partition key — version bumps
            *do not* reset counters because operators reading the
            dashboard care about "this strategy is fail-closing
            silently right now", which is a name-level question.
        proposals_emitted: How many times the strategy got to the
            point of producing a proposal candidate (i.e. analyze()
            was invoked).
        proposals_fail_closed: Of the emissions, how many were
            rejected by a downstream gate (StrategyError raised, or
            TradingValidationError raised during sizing).
        last_updated: ISO timestamp of the most recent counter
            increment.
    """

    sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID
    technique_name: str
    technique_version: str = ""
    proposals_emitted: int = Field(default=0, ge=0)
    proposals_fail_closed: int = Field(default=0, ge=0)
    last_updated: str = Field(default_factory=lambda: now_utc().isoformat())

    @property
    def fail_closed_rate(self) -> float:
        """``proposals_fail_closed / proposals_emitted`` in ``[0, 1]``.

        Returns ``0.0`` when ``proposals_emitted == 0`` — a strategy
        that never emitted has no observed fail-closed rate, and
        showing ``NaN`` on the dashboard would just confuse operators.
        """
        if self.proposals_emitted == 0:
            return 0.0
        return self.proposals_fail_closed / self.proposals_emitted


class FailClosedMetricsTracker:
    """Persist per-strategy ``proposals_emitted`` / ``proposals_fail_closed``.

    Storage layout mirrors :class:`PerformanceTracker` — one JSON file
    per ``(sub_account_id, technique_name)`` so a strategy's metrics
    file sits in the same directory as its ``records.json`` /
    ``summary.json``:

    ::

        data/performance/<sub_account_id>/<technique_name>/fail_closed.json

    Atomic writes (via :func:`src.utils.io.atomic_write_text`) keep the
    file from being observable in a half-written state.

    The tracker is intentionally minimal — it only owns the increment
    + persistence + read-back surface. Composition with the dashboard
    happens in :mod:`src.dashboard.pages.strategies`, not here.

    The ``sub_account_id`` is supplied per call on
    :meth:`record_emitted`, :meth:`record_fail_closed`, :meth:`get`,
    and :meth:`list_techniques` — a single tracker instance routes
    every sub-account's counters into the correct
    ``<sub_account_id>/<technique>/`` namespace. The constructor still
    accepts a ``default_sub_account_id`` purely as a fallback for
    callers that don't supply one (legacy tests; the
    :class:`PerformanceTracker` mirror), but the per-call argument
    always takes precedence.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID,
    ) -> None:
        """Initialize the tracker.

        Args:
            data_dir: Directory for performance data. Defaults to the
                settings-derived ``data/performance/`` so this tracker
                writes alongside the existing performance summaries.
            sub_account_id: Default sub-account namespace for callers
                that do not pass one per-call. The per-call argument on
                :meth:`record_emitted` / :meth:`record_fail_closed` /
                :meth:`get` / :meth:`list_techniques` always takes
                precedence — this default exists for backward
                compatibility with pre-multi-sub-account callsites.
        """
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "performance"
        else:
            self.data_dir = data_dir
        self.default_sub_account_id = sub_account_id

    def _resolve_sub_account(self, sub_account_id: str | None) -> str:
        """Per-call sub-account wins; fall back to constructor default."""
        return sub_account_id if sub_account_id is not None else self.default_sub_account_id

    def _path_for(self, technique_name: str, sub_account_id: str) -> Path:
        return self.data_dir / sub_account_id / technique_name / "fail_closed.json"

    def get(
        self,
        technique_name: str,
        sub_account_id: str | None = None,
    ) -> StrategyFailClosedCounts:
        """Read the current snapshot for ``(sub_account_id, technique_name)``.

        Returns a zero-valued snapshot when no file exists yet — the
        "this strategy has never emitted" case is just the
        ``proposals_emitted == 0`` snapshot, not a missing-key
        condition.
        """
        sub_account = self._resolve_sub_account(sub_account_id)
        path = self._path_for(technique_name, sub_account)
        if not path.exists():
            return StrategyFailClosedCounts(
                sub_account_id=sub_account,
                technique_name=technique_name,
            )
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load fail-closed metrics from %s: %s; "
                "returning zero snapshot",
                path,
                exc,
            )
            return StrategyFailClosedCounts(
                sub_account_id=sub_account,
                technique_name=technique_name,
            )
        return StrategyFailClosedCounts(**data)

    def _save(self, counts: StrategyFailClosedCounts) -> None:
        path = self._path_for(counts.technique_name, counts.sub_account_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, counts.model_dump_json(indent=2))

    def record_emitted(
        self,
        technique_name: str,
        technique_version: str,
        sub_account_id: str | None = None,
    ) -> None:
        """Increment ``proposals_emitted`` by 1 for the given sub-account.

        Called every time the proposal engine commits to invoking
        ``strategy.analyze()`` — see
        :meth:`src.proposal.engine.ProposalEngine._build_proposal_for_strategy`.
        The ``sub_account_id`` routes the counter to its own
        ``<sub_account_id>/<technique>/fail_closed.json`` so emissions
        from different sub-accounts running the same strategy stay
        isolated.
        """
        sub_account = self._resolve_sub_account(sub_account_id)
        counts = self.get(technique_name, sub_account)
        # Re-validate (instead of model_copy) so Field(ge=0) re-runs on
        # the updated counters. model_copy(update=...) bypasses
        # validators in Pydantic v2.
        updated = StrategyFailClosedCounts.model_validate(
            {
                **counts.model_dump(),
                "sub_account_id": sub_account,
                "technique_version": technique_version,
                "proposals_emitted": counts.proposals_emitted + 1,
                "last_updated": now_utc().isoformat(),
            }
        )
        self._save(updated)

    def record_fail_closed(
        self,
        technique_name: str,
        technique_version: str,
        sub_account_id: str | None = None,
    ) -> None:
        """Increment ``proposals_fail_closed`` by 1 for the given sub-account.

        Called when an emission is rejected by a downstream gate —
        currently :class:`StrategyError` raised inside ``analyze()``
        and :class:`TradingValidationError` raised by position sizing.
        Per DEBT-061's MVP scope, the per-reason breakdown is
        deliberately not wired today; the single counter is enough to
        surface "throughput collapsed" on the dashboard.
        """
        sub_account = self._resolve_sub_account(sub_account_id)
        counts = self.get(technique_name, sub_account)
        updated = StrategyFailClosedCounts.model_validate(
            {
                **counts.model_dump(),
                "sub_account_id": sub_account,
                "technique_version": technique_version,
                "proposals_fail_closed": counts.proposals_fail_closed + 1,
                "last_updated": now_utc().isoformat(),
            }
        )
        self._save(updated)

    def list_techniques(self, sub_account_id: str | None = None) -> list[str]:
        """List techniques that have a fail-closed snapshot on disk.

        Args:
            sub_account_id: Sub-account namespace to list. Falls back
                to the constructor default when omitted.

        Returns:
            Sorted list of technique names with at least one recorded
            emission or fail-closed event for the given sub-account.
            Techniques with no snapshot file are absent — callers that
            want a row per *known* strategy (regardless of emission
            history) should iterate their own strategy registry and
            call :meth:`get` per name.
        """
        sub_account = self._resolve_sub_account(sub_account_id)
        sub_account_dir = self.data_dir / sub_account
        if not sub_account_dir.exists():
            return []
        names: list[str] = []
        for child in sub_account_dir.iterdir():
            if not child.is_dir():
                continue
            if (child / "fail_closed.json").exists():
                names.append(child.name)
        return sorted(names)


__all__ = [
    "FailClosedMetricsTracker",
    "StrategyFailClosedCounts",
]
