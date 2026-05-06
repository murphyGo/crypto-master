"""Correlation-aware exposure inputs for runtime governance.

This module starts the Strategy Correlation Governor with a shared input
contract. Backtest trades and runtime trade history are normalized into the
same exposure records so advisory warnings and future rejection gates can reason
over sub-account, strategy, symbol, side, and notional consistently.

Related Requirements:
- FR-036: Multi-strategy portfolio governance
- FR-038: Strategy-combination A/B backtesting
- FR-044: Correlation-aware exposure controls
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from src.strategy.performance import TradeHistory
from src.utils.time import ensure_utc

if TYPE_CHECKING:
    from src.backtest.engine import BacktestResult, BacktestTrade


class CorrelationExposureSource(str, Enum):
    """Where a normalized exposure came from."""

    BACKTEST = "backtest"
    RUNTIME = "runtime"


class CorrelationWarningType(str, Enum):
    """Duplicate-exposure warning category."""

    DUPLICATE_SYMBOL_SIDE = "duplicate_symbol_side"
    DUPLICATE_STRATEGY_SYMBOL_SIDE = "duplicate_strategy_symbol_side"


class CorrelationExposure(BaseModel):
    """A strategy/symbol exposure sample used by correlation governance."""

    source: CorrelationExposureSource
    exposure_id: str
    sub_account_id: str
    strategy_id: str
    symbol: str
    side: Literal["long", "short"]
    opened_at: datetime
    closed_at: datetime | None = None
    entry_price: Decimal
    quantity: Decimal
    notional: Decimal = Field(ge=Decimal("0"))
    pnl: Decimal | None = None

    @classmethod
    def from_backtest_trade(
        cls,
        trade: BacktestTrade,
        *,
        result: BacktestResult,
    ) -> CorrelationExposure:
        """Normalize one backtest trade into a correlation exposure."""
        return cls(
            source=CorrelationExposureSource.BACKTEST,
            exposure_id=trade.trade_id,
            sub_account_id=trade.sub_account_id,
            strategy_id=trade.technique_name or result.technique_name,
            symbol=trade.symbol or result.symbol,
            side=trade.side,
            opened_at=ensure_utc(trade.entry_time),
            closed_at=ensure_utc(trade.exit_time),
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            notional=abs(trade.entry_price * trade.quantity),
            pnl=trade.pnl,
        )

    @classmethod
    def from_trade_history(
        cls,
        trade: TradeHistory,
        *,
        strategy_lookup: dict[str, str] | None = None,
    ) -> CorrelationExposure:
        """Normalize one runtime trade history record into an exposure."""
        strategy_id = "unknown"
        if trade.performance_record_id is not None and strategy_lookup is not None:
            strategy_id = strategy_lookup.get(trade.performance_record_id, "unknown")
        return cls(
            source=CorrelationExposureSource.RUNTIME,
            exposure_id=trade.id,
            sub_account_id=trade.sub_account_id,
            strategy_id=strategy_id,
            symbol=trade.symbol,
            side=trade.side,
            opened_at=ensure_utc(trade.entry_time),
            closed_at=ensure_utc(trade.exit_time) if trade.exit_time else None,
            entry_price=trade.entry_price,
            quantity=trade.entry_quantity,
            notional=abs(trade.entry_price * trade.entry_quantity),
            pnl=trade.pnl,
        )


class CorrelationInputSet(BaseModel):
    """Normalized exposure set consumed by the correlation governor."""

    exposures: list[CorrelationExposure] = Field(default_factory=list)

    @classmethod
    def from_backtest_results(
        cls,
        results: list[BacktestResult],
    ) -> CorrelationInputSet:
        """Build inputs from backtest result trade ledgers."""
        exposures = [
            CorrelationExposure.from_backtest_trade(trade, result=result)
            for result in results
            for trade in result.trades
        ]
        return cls(exposures=exposures)

    @classmethod
    def from_trade_history(
        cls,
        trades: list[TradeHistory],
        *,
        strategy_lookup: dict[str, str] | None = None,
    ) -> CorrelationInputSet:
        """Build inputs from runtime paper/live trade history."""
        exposures = [
            CorrelationExposure.from_trade_history(
                trade,
                strategy_lookup=strategy_lookup,
            )
            for trade in trades
        ]
        return cls(exposures=exposures)

    def for_sub_account(self, sub_account_id: str) -> list[CorrelationExposure]:
        """Return exposures for one sub-account."""
        return [
            exposure
            for exposure in self.exposures
            if exposure.sub_account_id == sub_account_id
        ]

    def for_symbol(self, symbol: str) -> list[CorrelationExposure]:
        """Return exposures for one trading symbol."""
        return [exposure for exposure in self.exposures if exposure.symbol == symbol]

    def open_only(self) -> CorrelationInputSet:
        """Return inputs containing only currently open exposures."""
        return self.model_copy(
            update={
                "exposures": [
                    exposure
                    for exposure in self.exposures
                    if exposure.closed_at is None
                ]
            }
        )


class CorrelationWarningPolicy(BaseModel):
    """Thresholds for duplicate-exposure advisory warnings."""

    max_sub_accounts_per_symbol_side: int = Field(default=1, ge=1)
    max_sub_accounts_per_strategy_symbol_side: int = Field(default=1, ge=1)


class CorrelationWarning(BaseModel):
    """Advisory duplicate-exposure warning across sub-accounts."""

    warning_type: CorrelationWarningType
    symbol: str
    side: Literal["long", "short"]
    strategy_id: str | None = None
    sub_account_ids: list[str]
    exposure_ids: list[str]
    total_notional: Decimal
    message: str


class CorrelationGateConfig(BaseModel):
    """Optional runtime rejection gate configuration."""

    enabled: bool = False
    warning_policy: CorrelationWarningPolicy = Field(
        default_factory=CorrelationWarningPolicy
    )


class CorrelationGateDecision(BaseModel):
    """Runtime gate decision for one candidate exposure."""

    allowed: bool
    reason: str
    warnings: list[CorrelationWarning] = Field(default_factory=list)


def compute_duplicate_exposure_warnings(
    inputs: CorrelationInputSet,
    *,
    policy: CorrelationWarningPolicy | None = None,
) -> list[CorrelationWarning]:
    """Compute advisory duplicate-exposure warnings across sub-accounts."""
    policy = policy or CorrelationWarningPolicy()
    warnings: list[CorrelationWarning] = []
    warnings.extend(_symbol_side_warnings(inputs.exposures, policy))
    warnings.extend(_strategy_symbol_side_warnings(inputs.exposures, policy))
    return warnings


def evaluate_correlation_gate(
    existing: CorrelationInputSet,
    candidate: CorrelationExposure,
    *,
    config: CorrelationGateConfig | None = None,
) -> CorrelationGateDecision:
    """Evaluate the optional runtime rejection gate for a candidate exposure."""
    config = config or CorrelationGateConfig()
    combined = CorrelationInputSet(exposures=[*existing.exposures, candidate])
    warnings = compute_duplicate_exposure_warnings(
        combined,
        policy=config.warning_policy,
    )
    candidate_warnings = [
        warning for warning in warnings if candidate.exposure_id in warning.exposure_ids
    ]
    if not candidate_warnings:
        return CorrelationGateDecision(
            allowed=True,
            reason="no correlated duplicate exposure detected",
            warnings=[],
        )
    if not config.enabled:
        return CorrelationGateDecision(
            allowed=True,
            reason="correlation gate disabled; advisory warnings only",
            warnings=candidate_warnings,
        )
    return CorrelationGateDecision(
        allowed=False,
        reason="correlation gate rejected excessive duplicate exposure",
        warnings=candidate_warnings,
    )


def _symbol_side_warnings(
    exposures: list[CorrelationExposure],
    policy: CorrelationWarningPolicy,
) -> list[CorrelationWarning]:
    grouped: dict[tuple[str, Literal["long", "short"]], list[CorrelationExposure]] = {}
    for exposure in exposures:
        grouped.setdefault((exposure.symbol, exposure.side), []).append(exposure)

    warnings: list[CorrelationWarning] = []
    for (symbol, side), group in sorted(grouped.items()):
        sub_accounts = _distinct_sub_accounts(group)
        if len(sub_accounts) <= policy.max_sub_accounts_per_symbol_side:
            continue
        warnings.append(
            CorrelationWarning(
                warning_type=CorrelationWarningType.DUPLICATE_SYMBOL_SIDE,
                symbol=symbol,
                side=side,
                sub_account_ids=sub_accounts,
                exposure_ids=_exposure_ids(group),
                total_notional=_total_notional(group),
                message=(
                    f"{symbol} {side} exposure spans "
                    f"{len(sub_accounts)} sub-accounts"
                ),
            )
        )
    return warnings


def _strategy_symbol_side_warnings(
    exposures: list[CorrelationExposure],
    policy: CorrelationWarningPolicy,
) -> list[CorrelationWarning]:
    grouped: dict[
        tuple[str, str, Literal["long", "short"]],
        list[CorrelationExposure],
    ] = {}
    for exposure in exposures:
        grouped.setdefault(
            (exposure.strategy_id, exposure.symbol, exposure.side),
            [],
        ).append(exposure)

    warnings: list[CorrelationWarning] = []
    for (strategy_id, symbol, side), group in sorted(grouped.items()):
        sub_accounts = _distinct_sub_accounts(group)
        if len(sub_accounts) <= policy.max_sub_accounts_per_strategy_symbol_side:
            continue
        warnings.append(
            CorrelationWarning(
                warning_type=CorrelationWarningType.DUPLICATE_STRATEGY_SYMBOL_SIDE,
                strategy_id=strategy_id,
                symbol=symbol,
                side=side,
                sub_account_ids=sub_accounts,
                exposure_ids=_exposure_ids(group),
                total_notional=_total_notional(group),
                message=(
                    f"{strategy_id} repeats {symbol} {side} across "
                    f"{len(sub_accounts)} sub-accounts"
                ),
            )
        )
    return warnings


def _distinct_sub_accounts(exposures: list[CorrelationExposure]) -> list[str]:
    return sorted({exposure.sub_account_id for exposure in exposures})


def _exposure_ids(exposures: list[CorrelationExposure]) -> list[str]:
    return sorted(exposure.exposure_id for exposure in exposures)


def _total_notional(exposures: list[CorrelationExposure]) -> Decimal:
    return sum((exposure.notional for exposure in exposures), Decimal("0"))


__all__ = [
    "CorrelationExposure",
    "CorrelationExposureSource",
    "CorrelationInputSet",
    "CorrelationGateConfig",
    "CorrelationGateDecision",
    "CorrelationWarning",
    "CorrelationWarningPolicy",
    "CorrelationWarningType",
    "compute_duplicate_exposure_warnings",
    "evaluate_correlation_gate",
]
