"""Performance tracking for analysis techniques.

Tracks trade outcomes and calculates aggregate metrics like win rate
and profit rate for each analysis technique. Also provides trade history
tracking for complete trade lifecycle management.

Related Requirements:
- FR-004: Analysis Technique Storage/Management
- FR-005: Analysis Technique Performance Tracking
- NFR-006: Backtesting Result Storage (JSON format)
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.models import AnalysisResult
from src.strategy.base import TechniqueInfo
from src.utils.io import atomic_write_text, read_text
from src.utils.pydantic_mixins import DecimalFieldsMixin, UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.strategy.performance")

# Default performance data directory
DEFAULT_PERFORMANCE_DIR = Path("data/performance")
DEFAULT_SUB_ACCOUNT_ID = "default"


def resolve_bounds_from_performance_record(
    performance_root: Path,
    sub_account_id: str,
    record_id: str,
) -> tuple[Decimal, Decimal] | None:
    """Resolve ``(stop_loss, take_profit)`` for a perf record id, or ``None``.

    DEBT-071: in-process counterpart to ``backfill_paper_sl_tp._PerfIndex`` —
    used by ``PaperTrader`` / ``LiveTrader`` rehydration to recover the SL/TP
    bounds of an open trade whose persisted ledger row predates SL/TP
    persistence but which carries a ``performance_record_id`` link.

    Reads the on-disk ``records.json`` rows directly (a raw JSON walk) rather
    than going through :meth:`PerformanceTracker.load_records`, which would
    raise on legacy rows whose ``stop_loss`` / ``take_profit`` are null — the
    exact rows we want to skip gracefully. Returns ``None`` when the record is
    not found or either bound is unset, so the caller can fall back to leaving
    the trade unmonitorable (the monitor's age-backstop force-closes it).

    Args:
        performance_root: The ``<data_dir>/performance`` directory.
        sub_account_id: Sub-account whose perf records to search.
        record_id: The ``performance_record_id`` to resolve.

    Returns:
        ``(stop_loss, take_profit)`` as ``Decimal`` when both bounds resolve,
        else ``None``.
    """
    bounds = load_performance_record_bounds_index(
        performance_root,
        sub_account_id,
    ).get(record_id)
    if bounds is None:
        return None
    sl_raw, tp_raw = bounds
    if sl_raw is None or tp_raw is None:
        return None
    try:
        return Decimal(str(sl_raw)), Decimal(str(tp_raw))
    except (ArithmeticError, ValueError):
        return None


def load_performance_record_bounds_index(
    performance_root: Path,
    sub_account_id: str,
) -> dict[str, tuple[str | None, str | None]]:
    """Load raw ``record_id -> (stop_loss, take_profit)`` bounds.

    Shared raw-JSON index for rehydration and operator backfill tooling.
    ``PerformanceTracker.load_records`` intentionally is not used here because
    it parses strict ``PerformanceRecord`` rows and would raise on the legacy
    null-bound records that reconciliation tools need to skip safely.
    """
    index: dict[str, tuple[str | None, str | None]] = {}
    sub_root = performance_root / sub_account_id
    if not sub_root.exists():
        return index
    for technique_dir in sub_root.iterdir():
        if not technique_dir.is_dir():
            continue
        records_path = technique_dir / "records.json"
        if not records_path.exists():
            continue
        try:
            rows = json.loads(read_text(records_path))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read perf records at %s: %s", records_path, exc)
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            rec_id = row.get("id")
            if not isinstance(rec_id, str):
                continue
            sl_raw = row.get("stop_loss")
            tp_raw = row.get("take_profit")
            sl = str(sl_raw) if sl_raw is not None else None
            tp = str(tp_raw) if tp_raw is not None else None
            index[rec_id] = (sl, tp)
    return index


class TradeOutcome(str, Enum):
    """Outcome of a trade based on analysis."""

    WIN = "win"  # Hit take profit
    LOSS = "loss"  # Hit stop loss
    BREAKEVEN = "breakeven"  # Exited at entry price
    PENDING = "pending"  # Trade not yet closed


class PerformanceRecord(DecimalFieldsMixin, UtcTimestampMixin, BaseModel):
    """Single analysis/trade performance record.

    Stores the analysis result and its eventual trade outcome
    for performance tracking purposes.

    Attributes:
        id: Unique record identifier (UUID).
        technique_name: Name of the analysis technique.
        technique_version: Version of the technique used.
        symbol: Trading pair symbol (e.g., "BTC/USDT").
        timeframe: Candle timeframe (e.g., "1h", "4h").
        signal: Trading signal from analysis.
        entry_price: Suggested entry price.
        stop_loss: Stop loss price.
        take_profit: Take profit price.
        confidence: Confidence score (0.0-1.0).
        analysis_timestamp: When the analysis was performed.
        outcome: Trade outcome (win/loss/breakeven/pending).
        exit_price: Actual exit price if trade closed.
        exit_timestamp: When the trade was closed.
        pnl_percent: Profit/loss as percentage of entry.
        quantity: Position size (if trade executed).
        leverage: Leverage multiplier used.
        fees: Trading fees incurred.
        actual_entry_price: Actual fill price (may differ from signal).
        actual_exit_price: Actual exit fill price.
        mode: Trading mode (backtest/paper/live).
        trade_id: Link to TradeHistory record if executed.
        market_regime: Entry-time market regime label for per-regime expectancy.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    technique_name: str
    technique_version: str
    symbol: str
    timeframe: str
    signal: Literal["long", "short", "neutral"]
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float = Field(ge=0.0, le=1.0)
    analysis_timestamp: datetime = Field(default_factory=now_utc)
    outcome: TradeOutcome = TradeOutcome.PENDING
    exit_price: Decimal | None = None
    exit_timestamp: datetime | None = None
    pnl_percent: float | None = None
    # Trade execution details (added for NFR-007)
    quantity: Decimal | None = None
    leverage: int = 1
    fees: Decimal = Field(default=Decimal("0"))
    actual_entry_price: Decimal | None = None
    actual_exit_price: Decimal | None = None
    mode: Literal["backtest", "paper", "live"] = "backtest"
    trade_id: str | None = None
    sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID
    market_regime: Literal["bull", "bear", "sideways", "unknown"] = "unknown"
    # Profile dimension for FR-005 technique+profile combinations
    profile_name: str | None = None
    # Reconciliation markers (Q2 follow-up — CON-003 promotion gating).
    # ``synthetic=True`` records are written by
    # ``src.tools.close_unrecoverable_paper_trades`` to preserve the
    # audit trail of an unrecoverable open trade that the operator force-
    # closed; they MUST NOT count toward win-rate / Sharpe / expectancy /
    # profit-factor aggregations because they encode no real signal
    # outcome. ``reconciliation_close=True`` is the narrower flag —
    # currently always paired with ``synthetic=True``, but kept separate
    # so future reconciliation paths (e.g. half-closed sweep — see
    # DEBT-064) can mark real-but-tooling-touched rows. Both default to
    # ``False`` so every pre-existing on-disk record loads as non-synthetic.
    synthetic: bool = False
    reconciliation_close: bool = False

    model_config = {"use_enum_values": True}

    def calculate_pnl(self) -> float | None:
        """Calculate P&L percentage based on outcome.

        Returns:
            P&L as percentage of entry price, or None if pending.
        """
        if self.outcome == TradeOutcome.PENDING or self.exit_price is None:
            return None

        if self.signal == "neutral":
            return 0.0

        entry = float(self.entry_price)
        exit_p = float(self.exit_price)

        if self.signal == "long":
            return ((exit_p - entry) / entry) * 100
        else:  # short
            return ((entry - exit_p) / entry) * 100


class RegimePerformance(BaseModel):
    """Per-regime closed-trade expectancy snapshot."""

    trades: int = 0
    expectancy: float = 0.0
    total_pnl_percent: float = 0.0


class TechniquePerformance(BaseModel):
    """Aggregated performance metrics for a technique.

    Calculates and stores summary statistics across all trades
    for a specific technique.

    Attributes:
        technique_name: Name of the analysis technique.
        technique_version: Version of the technique.
        total_trades: Total number of trades recorded.
        wins: Number of winning trades.
        losses: Number of losing trades.
        breakevens: Number of breakeven trades.
        pending: Number of pending trades.
        win_rate: Win rate as decimal (wins / closed trades).
        avg_pnl_percent: Average P&L percentage per trade.
        total_pnl_percent: Cumulative P&L percentage.
        best_trade_pnl: Best single trade P&L percentage.
        worst_trade_pnl: Worst single trade P&L percentage.
        gross_win_pct: Sum of positive closed-trade P&L percentages.
        gross_loss_pct: Absolute sum of negative closed-trade P&L percentages.
        max_drawdown_pct: Max closed-trade drawdown over cumulative P&L.
        last_updated: Timestamp of last update.
    """

    sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID
    technique_name: str
    technique_version: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    pending: int = 0
    win_rate: float = 0.0
    avg_pnl_percent: float = 0.0
    total_pnl_percent: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    gross_win_pct: float = 0.0
    gross_loss_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    # DEBT-073: fee-inclusive ("net") counterparts of the percent aggregates
    # above. ``pnl_percent`` is intentionally a leverage-neutral *price-move*
    # percent, gross of fees (DEBT-024 / Phase 20.1-20.2), so the gross fields
    # above stay correct for display/charts. These ``net_*`` fields subtract
    # realized fee drag (round-trip fees as a percent of notional) per closed
    # real trade and are what edge/decision consumers (profit factor,
    # expectancy, closed-PnL) should read so a marginal ``keep`` is not granted
    # on fees-omitted optimism. Default ``0.0`` so pre-DEBT-073 on-disk
    # summaries load unchanged; the gating path always recomputes via
    # ``from_records`` so these are populated whenever the recommender reads
    # them. A trade that is a gross winner but a net loser after fees correctly
    # lands in ``net_loss_pct`` because the split is computed on the net value.
    net_total_pnl_percent: float = 0.0
    net_avg_pnl_percent: float = 0.0
    net_win_pct: float = 0.0
    net_loss_pct: float = 0.0
    last_updated: datetime = Field(default_factory=now_utc)
    # Q2 follow-up: number of ``synthetic=True`` records excluded from
    # the money-relevant aggregations above. Reported separately so
    # analytics can still surface "this many rows were reconciliation-
    # closed" without polluting win-rate / Sharpe / expectancy.
    synthetic_count: int = 0
    regime_performance: dict[str, "RegimePerformance"] = Field(default_factory=dict)

    @property
    def real_trade_count(self) -> int:
        """Closed-trade count excluding synthetic reconciliation rows.

        DEBT-065: ``total_trades`` intentionally includes synthetic
        reconciliation-close rows so operator-facing record counts stay
        honest (see the comment in :meth:`from_records` and the
        ``synthetic``/``reconciliation_close`` markers at
        ``PerformanceRecord``). Promotion-gating consumers
        (``ProposalEngine._cold_start_blocks_live`` and ``_score``'s
        ``sample_size``) must read *this* property instead, so
        synthetic markers cannot inflate a strategy past the live
        cold-start threshold.
        """
        return self.total_trades - self.synthetic_count

    @classmethod
    def from_records(
        cls,
        technique_name: str,
        technique_version: str,
        records: list[PerformanceRecord],
    ) -> "TechniquePerformance":
        """Calculate performance metrics from a list of records.

        Args:
            technique_name: Name of the technique.
            technique_version: Version of the technique.
            records: List of performance records.

        Returns:
            TechniquePerformance with calculated metrics.
        """
        if not records:
            return cls(
                technique_name=technique_name,
                technique_version=technique_version,
            )

        # Q2 follow-up: exclude synthetic rows from every money-relevant
        # aggregation (win-rate / Sharpe / expectancy / profit-factor).
        # Synthetic rows are reconciliation artefacts (close-tool wrote
        # them so we don't lose the audit trail of a force-closed
        # unrecoverable trade) — they encode no real signal outcome and
        # must not feed CON-003 promotion gating. ``total_trades`` still
        # reflects all records so operator-facing "how many records do
        # we have" counts stay honest; ``synthetic_count`` surfaces the
        # excluded count separately.
        # If a future performance derivation includes proposal-only
        # ``shadow=True`` rows, filter them out the same way before
        # they reach these money-relevant aggregates.
        synthetic_count = sum(1 for r in records if r.synthetic)
        real_records = [r for r in records if not r.synthetic]

        wins = sum(1 for r in real_records if r.outcome == TradeOutcome.WIN)
        losses = sum(1 for r in real_records if r.outcome == TradeOutcome.LOSS)
        breakevens = sum(1 for r in real_records if r.outcome == TradeOutcome.BREAKEVEN)
        pending = sum(1 for r in real_records if r.outcome == TradeOutcome.PENDING)

        closed_trades = wins + losses + breakevens
        win_rate = wins / closed_trades if closed_trades > 0 else 0.0

        # Calculate P&L stats from closed real trades only.
        closed_real_records = [
            r for r in real_records if r.outcome != TradeOutcome.PENDING
        ]
        pnl_values = [
            r.pnl_percent for r in closed_real_records if r.pnl_percent is not None
        ]
        total_pnl = sum(pnl_values) if pnl_values else 0.0
        avg_pnl = total_pnl / len(pnl_values) if pnl_values else 0.0
        best_pnl = max(pnl_values) if pnl_values else 0.0
        worst_pnl = min(pnl_values) if pnl_values else 0.0
        gross_win_pct = sum(pnl for pnl in pnl_values if pnl > 0.0)
        gross_loss_pct = abs(sum(pnl for pnl in pnl_values if pnl < 0.0))
        max_drawdown_pct = _max_drawdown_pct(pnl_values)

        # DEBT-073: fee-inclusive aggregates over the same closed real records.
        # Split winners/losers on the *net* value so a gross winner that turns
        # into a net loser after fees lands in the loss bucket for net PF.
        net_values = [
            net
            for net in (_net_pnl_pct_for_record(r) for r in closed_real_records)
            if net is not None
        ]
        net_total_pnl = sum(net_values) if net_values else 0.0
        net_avg_pnl = net_total_pnl / len(net_values) if net_values else 0.0
        net_win_pct = sum(net for net in net_values if net > 0.0)
        net_loss_pct = abs(sum(net for net in net_values if net < 0.0))
        regime_performance = _regime_performance_from_records(closed_real_records)

        return cls(
            sub_account_id=records[-1].sub_account_id,
            technique_name=technique_name,
            technique_version=technique_version,
            total_trades=len(records),
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            pending=pending,
            win_rate=win_rate,
            avg_pnl_percent=avg_pnl,
            total_pnl_percent=total_pnl,
            best_trade_pnl=best_pnl,
            worst_trade_pnl=worst_pnl,
            gross_win_pct=gross_win_pct,
            gross_loss_pct=gross_loss_pct,
            max_drawdown_pct=max_drawdown_pct,
            net_total_pnl_percent=net_total_pnl,
            net_avg_pnl_percent=net_avg_pnl,
            net_win_pct=net_win_pct,
            net_loss_pct=net_loss_pct,
            last_updated=now_utc(),
            synthetic_count=synthetic_count,
            regime_performance=regime_performance,
        )


def _max_drawdown_pct(pnl_values: list[float]) -> float:
    peak = 0.0
    cumulative = 0.0
    max_drawdown = 0.0
    for pnl in pnl_values:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    return max_drawdown


def _net_pnl_pct_for_record(record: PerformanceRecord) -> float | None:
    """Fee-netted price-move percent for a closed record (DEBT-073).

    ``record.pnl_percent`` is the gross, leverage-neutral price-move percent
    (DEBT-024). This subtracts realized round-trip fee drag expressed in the
    same unit — fees as a percent of notional (``entry_price * quantity``).

    Returns ``None`` when the record has no gross percent. Falls back to the
    gross percent when the notional cannot be derived (``quantity`` missing or
    ``notional <= 0``) — fees cannot be expressed as a percent without a
    notional (backtest rows often omit ``quantity``), and over-counting is
    worse than under-counting an unknown fee.
    """
    if record.pnl_percent is None:
        return None

    gross = record.pnl_percent
    if record.quantity is None or record.fees == 0:
        return gross

    notional = record.entry_price * record.quantity
    if notional <= 0:
        return gross

    fee_pct = float(record.fees / notional) * 100
    return gross - fee_pct


def _regime_performance_from_records(
    records: list[PerformanceRecord],
) -> dict[str, RegimePerformance]:
    """Aggregate fee-aware expectancy by entry-time market regime."""
    grouped: dict[str, list[float]] = {}
    for record in records:
        regime = record.market_regime or "unknown"
        if regime not in {"bull", "bear", "sideways", "unknown"}:
            regime = "unknown"
        net = _net_pnl_pct_for_record(record)
        if net is None:
            continue
        grouped.setdefault(regime, []).append(net)

    return {
        regime: RegimePerformance(
            trades=len(values),
            expectancy=sum(values) / len(values),
            total_pnl_percent=sum(values),
        )
        for regime, values in sorted(grouped.items())
        if values
    }


class PerformanceTracker:
    """Tracks and manages performance records for analysis techniques.

    Provides methods to record analysis results, update outcomes,
    and query aggregated performance metrics.

    Related Requirements:
    - FR-005: Analysis Technique Performance Tracking

    Attributes:
        data_dir: Directory for storing performance data.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID,
    ) -> None:
        """Initialize PerformanceTracker.

        Args:
            data_dir: Directory for storing performance data.
                     Defaults to data/performance/.
        """
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "performance"
        else:
            self.data_dir = data_dir
        self.sub_account_id = sub_account_id

    def _get_technique_dir(self, technique_name: str) -> Path:
        """Get the directory for a technique's performance data.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the technique's performance directory.
        """
        return self.data_dir / self.sub_account_id / technique_name

    def _get_records_path(self, technique_name: str) -> Path:
        """Get the path to the records file for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the records JSON file.
        """
        return self._get_technique_dir(technique_name) / "records.json"

    def _get_summary_path(self, technique_name: str) -> Path:
        """Get the path to the summary file for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the summary JSON file.
        """
        return self._get_technique_dir(technique_name) / "summary.json"

    def record_analysis(
        self,
        technique: TechniqueInfo,
        result: AnalysisResult,
        symbol: str,
        timeframe: str,
        profile_name: str | None = None,
    ) -> PerformanceRecord:
        """Record a new analysis result.

        Creates a PerformanceRecord from the analysis and saves it.

        Args:
            technique: The technique that produced the analysis.
            result: The analysis result.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            profile_name: Optional trading profile the analysis was
                combined with (FR-005 technique+profile tracking).

        Returns:
            The created PerformanceRecord.
        """
        record = PerformanceRecord(
            technique_name=technique.name,
            technique_version=technique.version,
            symbol=symbol,
            timeframe=timeframe,
            signal=result.signal,
            entry_price=result.entry_price,
            stop_loss=result.stop_loss,
            take_profit=result.take_profit,
            confidence=result.confidence,
            analysis_timestamp=result.timestamp,
            profile_name=profile_name,
            sub_account_id=self.sub_account_id,
        )

        self.save_record(record)
        logger.info(
            f"Recorded analysis: {technique.name} v{technique.version} "
            f"on {symbol} ({timeframe}) - signal: {result.signal}"
            + (f", profile={profile_name}" if profile_name else "")
        )
        return record

    def update_outcome(
        self,
        record_id: str,
        outcome: TradeOutcome,
        exit_price: Decimal,
        technique_name: str,
    ) -> PerformanceRecord | None:
        """Update the outcome of a pending trade.

        Args:
            record_id: ID of the record to update.
            outcome: The trade outcome.
            exit_price: The exit price.
            technique_name: Name of the technique (for loading records).

        Returns:
            Updated PerformanceRecord, or None if not found.
        """
        records = self.load_records(technique_name)
        updated_record = None

        for i, record in enumerate(records):
            if record.id == record_id:
                record.outcome = outcome
                record.exit_price = exit_price
                record.exit_timestamp = now_utc()
                record.pnl_percent = record.calculate_pnl()
                records[i] = record
                updated_record = record
                break

        if updated_record:
            self._save_records(technique_name, records)
            self._update_summary(technique_name, records)
            logger.info(
                f"Updated outcome for record {record_id}: "
                f"{outcome.value}, P&L: {updated_record.pnl_percent:.2f}%"
            )

        return updated_record

    def save_record(self, record: PerformanceRecord) -> None:
        """Save a performance record to storage.

        Appends the record to the technique's records file.

        Args:
            record: The record to save.
        """
        records = self.load_records(record.technique_name)
        records.append(record)
        self._save_records(record.technique_name, records)
        self._update_summary(record.technique_name, records)

    def _save_records(
        self, technique_name: str, records: list[PerformanceRecord]
    ) -> None:
        """Save all records for a technique.

        Args:
            technique_name: Name of the technique.
            records: List of records to save.
        """
        technique_dir = self._get_technique_dir(technique_name)
        technique_dir.mkdir(parents=True, exist_ok=True)

        records_path = self._get_records_path(technique_name)
        data = [self._record_to_dict(r) for r in records]

        # DEBT-028 (Phase 22.1): atomic write so a crash mid-save
        # leaves the previous records file intact rather than a
        # truncated one. Phase 19's sub-account fan-out will multiply
        # concurrent writers against this file.
        atomic_write_text(
            records_path,
            json.dumps(data, indent=2, default=str),
        )

    def _record_to_dict(self, record: PerformanceRecord) -> dict:
        """Convert a PerformanceRecord to a JSON-serializable dict.

        Args:
            record: The record to convert.

        Returns:
            Dictionary representation of the record.
        """
        data = record.model_dump()
        # Convert Decimals to strings for JSON
        decimal_fields = [
            "entry_price",
            "stop_loss",
            "take_profit",
            "exit_price",
            "quantity",
            "fees",
            "actual_entry_price",
            "actual_exit_price",
        ]
        for key in decimal_fields:
            if data[key] is not None:
                data[key] = str(data[key])
        # Convert datetime to ISO format
        for key in ["analysis_timestamp", "exit_timestamp"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    def _update_summary(
        self, technique_name: str, records: list[PerformanceRecord]
    ) -> None:
        """Update the summary file for a technique.

        Args:
            technique_name: Name of the technique.
            records: All records for the technique.
        """
        if not records:
            return

        # Get version from latest record
        version = records[-1].technique_version
        performance = TechniquePerformance.from_records(
            technique_name, version, records
        )

        summary_path = self._get_summary_path(technique_name)
        data = performance.model_dump()
        data["last_updated"] = data["last_updated"].isoformat()

        # DEBT-028 (Phase 22.1): atomic write — same load-all/save-all
        # shape as ``_save_records``.
        atomic_write_text(
            summary_path,
            json.dumps(data, indent=2),
        )

    def load_records(
        self,
        technique_name: str,
        version: str | None = None,
    ) -> list[PerformanceRecord]:
        """Load performance records for a technique.

        Args:
            technique_name: Name of the technique.
            version: Optional version filter.

        Returns:
            List of PerformanceRecords.
        """
        records_path = self._get_records_path(technique_name)

        if not records_path.exists():
            return []

        try:
            # CAH-14: route the read through ``utils/io`` so all FS access
            # in this module goes through one seam (writes already use
            # ``atomic_write_text``). Same error semantics as the prior
            # raw ``open(...)`` — ``OSError`` and a bad-JSON parse both
            # fall through to the handler below and yield an empty list.
            data = json.loads(read_text(records_path))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load records from {records_path}: {e}")
            return []

        records = [PerformanceRecord(**item) for item in data]

        if version:
            records = [r for r in records if r.technique_version == version]

        return records

    def get_performance(
        self,
        technique_name: str,
        version: str | None = None,
    ) -> TechniquePerformance:
        """Get aggregated performance metrics for a technique.

        Args:
            technique_name: Name of the technique.
            version: Optional version filter.

        Returns:
            TechniquePerformance with aggregated metrics.
        """
        records = self.load_records(technique_name, version)
        technique_version = version or (
            records[-1].technique_version if records else ""
        )
        return TechniquePerformance.from_records(
            technique_name, technique_version, records
        )

    def recalculate_performance(self, technique_name: str) -> TechniquePerformance:
        """Recalculate and update performance metrics.

        Forces a recalculation of all metrics from records.

        Args:
            technique_name: Name of the technique.

        Returns:
            Updated TechniquePerformance.
        """
        records = self.load_records(technique_name)
        if records:
            self._update_summary(technique_name, records)
        return self.get_performance(technique_name)

    def get_records_by_symbol(
        self,
        technique_name: str,
        symbol: str,
    ) -> list[PerformanceRecord]:
        """Get records filtered by symbol.

        Args:
            technique_name: Name of the technique.
            symbol: Trading pair symbol to filter by.

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if r.symbol == symbol]

    def get_records_by_timeframe(
        self,
        technique_name: str,
        timeframe: str,
    ) -> list[PerformanceRecord]:
        """Get records filtered by timeframe.

        Args:
            technique_name: Name of the technique.
            timeframe: Timeframe to filter by.

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if r.timeframe == timeframe]

    def get_records_by_profile(
        self,
        technique_name: str,
        profile_name: str | None,
    ) -> list[PerformanceRecord]:
        """Get records filtered by trading profile.

        Args:
            technique_name: Name of the technique.
            profile_name: Profile name to filter by, or None to match
                records that have no profile attached.

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if r.profile_name == profile_name]

    def get_performance_by_combination(
        self,
        technique_name: str,
        profile_name: str | None,
        version: str | None = None,
    ) -> TechniquePerformance:
        """Get aggregated performance for a technique+profile combination.

        Args:
            technique_name: Name of the technique.
            profile_name: Profile name to aggregate over.
            version: Optional version filter.

        Returns:
            TechniquePerformance computed only from records matching
            both the technique and the profile.
        """
        records = self.load_records(technique_name, version=version)
        filtered = [r for r in records if r.profile_name == profile_name]
        technique_version = version or (
            filtered[-1].technique_version if filtered else ""
        )
        return TechniquePerformance.from_records(
            technique_name, technique_version, filtered
        )

    def list_profiles_for_technique(
        self,
        technique_name: str,
    ) -> list[str]:
        """List distinct profile names seen for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            Sorted list of profile names (excluding None entries).
        """
        records = self.load_records(technique_name)
        profiles = {r.profile_name for r in records if r.profile_name}
        return sorted(profiles)

    def get_records_by_date_range(
        self,
        technique_name: str,
        start: datetime,
        end: datetime,
    ) -> list[PerformanceRecord]:
        """Get records within a date range.

        Args:
            technique_name: Name of the technique.
            start: Start of date range (inclusive).
            end: End of date range (inclusive).

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        # DEBT-025 (Phase 21.2): records on disk are now UTC-aware;
        # tolerate naive ``start`` / ``end`` from callers by coercing
        # to UTC so aware-vs-naive comparison doesn't raise.
        if start.tzinfo is None:
            start = ensure_utc(start)
        if end.tzinfo is None:
            end = ensure_utc(end)
        return [r for r in records if start <= r.analysis_timestamp <= end]

    def list_techniques(self) -> list[str]:
        """List all techniques with performance data.

        Returns:
            List of technique names.
        """
        sub_account_dir = self.data_dir / self.sub_account_id
        if not sub_account_dir.exists():
            return []

        return [
            d.name
            for d in sub_account_dir.iterdir()
            if d.is_dir() and (d / "records.json").exists()
        ]

    def delete_records(self, technique_name: str) -> bool:
        """Delete all records for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            True if deleted, False if not found.
        """
        technique_dir = self._get_technique_dir(technique_name)

        if not technique_dir.exists():
            return False

        import shutil

        shutil.rmtree(technique_dir)
        logger.info(f"Deleted performance data for technique: {technique_name}")
        return True


# CAH-08 / STRAT-F1: ``TradeHistory`` / ``TradeHistoryTracker`` and the
# ``data/trades`` aggregate were split into ``src.strategy.trade_history``.
# Re-exported here so every existing
# ``from src.strategy.performance import TradeHistory...`` import path keeps
# resolving (behaviour-preserving move — no importer changes required). The
# import is placed at the end of the module to avoid a circular import, since
# ``trade_history`` imports ``DEFAULT_SUB_ACCOUNT_ID`` from this module.
from src.strategy.trade_history import (  # noqa: E402
    DEFAULT_TRADES_DIR,
    TradeHistory,
    TradeHistoryTracker,
)

__all__ = [
    "DEFAULT_PERFORMANCE_DIR",
    "DEFAULT_SUB_ACCOUNT_ID",
    "DEFAULT_TRADES_DIR",
    "TradeOutcome",
    "PerformanceRecord",
    "RegimePerformance",
    "TechniquePerformance",
    "PerformanceTracker",
    "TradeHistory",
    "TradeHistoryTracker",
]
