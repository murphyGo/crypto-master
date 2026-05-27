"""Paper trading engine for simulated trading.

Provides a virtual trading environment that simulates real trading
without using actual funds. Supports both local simulation and
exchange testnet integration.

Related Requirements:
- FR-010: Paper Trading Mode
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.logger import get_logger
from src.models import OrderRequest, Position
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.base import exit_condition_for_position
from src.trading.strategy import TradingError
from src.utils.io import atomic_write_text
from src.utils.trading_math import pnl_for_trade
from src.utils.trading_types import (
    OrderSide,
    closing_order_side,
    entry_order_side,
)

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange

logger = get_logger("crypto_master.trading.paper")


class FeeConfig(BaseModel):
    """Maker/taker fee configuration for paper trading simulation.

    Fee rates are expressed as decimal fractions of notional value
    (e.g., ``Decimal("0.0004")`` represents 0.04%).

    Attributes:
        maker_fee_rate: Fee rate applied to maker (passive) orders.
        taker_fee_rate: Fee rate applied to taker (aggressive) orders.
    """

    maker_fee_rate: Decimal = Field(default=Decimal("0"), ge=0)
    taker_fee_rate: Decimal = Field(default=Decimal("0"), ge=0)

    model_config = {"frozen": True}


# Default fee configurations per exchange (futures maker/taker defaults).
# Rates are based on the standard/base tier published by each exchange.
# NFR-008: Realistic fee simulation for accurate P&L tracking.
DEFAULT_FEE_CONFIGS: dict[str, FeeConfig] = {
    "binance": FeeConfig(
        maker_fee_rate=Decimal("0.0002"),
        taker_fee_rate=Decimal("0.0004"),
    ),
    "bybit": FeeConfig(
        maker_fee_rate=Decimal("0.0002"),
        taker_fee_rate=Decimal("0.00055"),
    ),
}

# Fallback for trading without an exchange reference — no simulated fees.
ZERO_FEE_CONFIG = FeeConfig()


class PaperTradingError(TradingError):
    """Base exception for paper trading errors."""

    pass


class InsufficientPaperBalanceError(PaperTradingError):
    """Raised when paper balance is insufficient for operation.

    Attributes:
        required: The required amount.
        available: The available amount.
        currency: The currency.
    """

    def __init__(
        self,
        message: str,
        required: Decimal,
        available: Decimal,
        currency: str,
    ) -> None:
        """Initialize InsufficientPaperBalanceError.

        Args:
            message: Error message.
            required: The required amount.
            available: The available amount.
            currency: The currency.
        """
        super().__init__(message)
        self.required = required
        self.available = available
        self.currency = currency


class PaperBalance(BaseModel):
    """Virtual balance for paper trading.

    Tracks free (available) and locked (in positions) amounts.

    Phase 22.2 / DEBT-027 relaxes the ``ge=0`` constraint on ``free``
    so :meth:`PaperTrader.close_position` can record true post-
    liquidation negative equity. The ``lock`` / ``deduct`` methods
    still reject operations that would overdraw, so the only path to
    a negative ``free`` is the deliberate liquidation branch in
    ``close_position``. ``locked`` keeps its non-negative invariant —
    no leverage scenario produces negative locked margin.

    Attributes:
        currency: Currency code (e.g., "USDT").
        free: Available balance. Normally non-negative, but may go
            negative after a paper-mode liquidation event when
            ``EngineConfig.paper_auto_deposit_on_liquidation`` is False
            (the default).
        locked: Balance locked in open positions.
    """

    currency: str
    free: Decimal = Field(default=Decimal("0"))
    locked: Decimal = Field(default=Decimal("0"), ge=0)

    model_config = {"validate_assignment": True}

    @property
    def total(self) -> Decimal:
        """Get total balance (free + locked)."""
        return self.free + self.locked

    def lock(self, amount: Decimal) -> None:
        """Lock an amount from free balance.

        Args:
            amount: Amount to lock.

        Raises:
            InsufficientPaperBalanceError: If insufficient free balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Lock amount must be positive: {amount}")

        if amount > self.free:
            raise InsufficientPaperBalanceError(
                f"Insufficient free balance: need {amount} {self.currency}, "
                f"have {self.free}",
                required=amount,
                available=self.free,
                currency=self.currency,
            )

        self.free -= amount
        self.locked += amount

    def unlock(self, amount: Decimal) -> None:
        """Unlock an amount back to free balance.

        Args:
            amount: Amount to unlock.

        Raises:
            PaperTradingError: If amount exceeds locked balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Unlock amount must be positive: {amount}")

        if amount > self.locked:
            raise PaperTradingError(
                f"Cannot unlock {amount} {self.currency}: only {self.locked} locked"
            )

        self.locked -= amount
        self.free += amount

    def add(self, amount: Decimal) -> None:
        """Add amount to free balance (e.g., profit or deposit).

        Args:
            amount: Amount to add.
        """
        if amount <= 0:
            raise PaperTradingError(f"Add amount must be positive: {amount}")

        self.free += amount

    def deduct(self, amount: Decimal) -> None:
        """Deduct amount from free balance (e.g., loss or withdrawal).

        Args:
            amount: Amount to deduct.

        Raises:
            InsufficientPaperBalanceError: If insufficient free balance.
        """
        if amount <= 0:
            raise PaperTradingError(f"Deduct amount must be positive: {amount}")

        if amount > self.free:
            raise InsufficientPaperBalanceError(
                f"Insufficient free balance to deduct: need {amount} {self.currency}, "
                f"have {self.free}",
                required=amount,
                available=self.free,
                currency=self.currency,
            )

        self.free -= amount


class OpenPosition(BaseModel):
    """Tracks an open position in paper trading.

    Links a Position to its TradeHistory and tracks margin and fees.

    Attributes:
        trade_id: ID of the associated TradeHistory.
        position: The original Position.
        margin: Margin locked for this position.
        quote_currency: The quote currency (for balance management).
        entry_fee: Fee already paid on entry (deducted from free balance).
    """

    trade_id: str
    position: Position
    margin: Decimal
    quote_currency: str
    entry_fee: Decimal = Decimal("0")


class PaperTrader:
    """Simulates trading with virtual funds.

    Provides a complete paper trading environment including:
    - Virtual balance management
    - Market order instant fill simulation
    - Stop-loss and take-profit monitoring
    - Trade history recording via TradeHistoryTracker
    - Optional exchange testnet integration for more realistic simulation

    Related Requirements:
    - FR-010: Paper Trading Mode
    - NFR-007: Trading History Storage
    - NFR-008: Asset/PnL History

    Usage (local simulation):
        trader = PaperTrader(initial_balance={"USDT": Decimal("10000")})

        # Open position from a Position object
        trade = trader.open_position(position)

        # Check exit conditions with current price
        should_exit, reason = trader.check_exit_conditions(trade.id, current_price)
        if should_exit:
            trader.close_position(trade.id, current_price, reason)

    Usage (testnet mode):
        exchange = BinanceExchange(config, testnet=True)
        await exchange.connect()
        trader = PaperTrader(exchange=exchange)

        # Sync balance from exchange testnet
        await trader.sync_balance_from_exchange()

        # Open position via exchange testnet
        trade = await trader.open_position_on_testnet(position)
    """

    def __init__(
        self,
        initial_balance: dict[str, Decimal] | None = None,
        data_dir: Path | None = None,
        exchange: "BaseExchange | None" = None,
        fee_config: FeeConfig | None = None,
        *,
        activity_log: ActivityLog | None = None,
        auto_deposit_on_liquidation: bool = False,
        sub_account_id: str = "default",
    ) -> None:
        """Initialize PaperTrader.

        Args:
            initial_balance: Initial virtual balances per currency.
                            Example: {"USDT": Decimal("10000")}
            data_dir: Directory for trade history storage.
                     Defaults to data/trades/.
            exchange: Optional exchange instance for testnet execution.
                     If provided and in testnet mode, orders can execute on testnet.
            fee_config: Maker/taker fee rates for simulation. If None, uses
                       the default config for the supplied ``exchange`` (keyed
                       by ``exchange.name``), or zero fees when no exchange
                       is configured.
            activity_log: Optional :class:`ActivityLog` used to surface
                paper-mode liquidation events (Phase 22.2 / DEBT-027).
                When ``None``, the under-water close still records true
                negative equity on the balance but no
                :attr:`ActivityEventType.LIQUIDATED` event is emitted —
                this matches the legacy in-memory test setup. Production
                wires in the engine's shared ``ActivityLog`` so the
                dashboard sees the event.
            auto_deposit_on_liquidation: Opt-out flag for the legacy
                balance-clamp behaviour (Phase 22.2 / DEBT-027). Default
                ``False`` means an under-water close lets ``free`` go
                negative so paper-mode forecasts include the liquidation
                cliff. ``True`` re-enables the legacy
                ``balance.free = Decimal("0")`` clamp — intended only
                for testing scenarios that need a continuing run after
                liquidation. Either way, when ``activity_log`` is wired,
                the ``LIQUIDATED`` event is still emitted so the
                shortfall is never silently swallowed.
            sub_account_id: Capital bucket whose trade history this
                trader owns. Defaults to ``"default"`` for legacy
                single-account deployments.
        """
        self._balances: dict[str, PaperBalance] = {}
        self._open_positions: dict[str, OpenPosition] = {}
        self._trade_tracker = TradeHistoryTracker(
            data_dir=data_dir,
            sub_account_id=sub_account_id,
        )
        self._exchange = exchange
        self._use_testnet = exchange is not None and exchange.testnet
        self._fee_config = self._resolve_fee_config(fee_config, exchange)
        self._activity_log = activity_log
        self._auto_deposit_on_liquidation = auto_deposit_on_liquidation
        self._loaded_balance_snapshot = False

        # Initialize balances. A persisted snapshot wins over the
        # configured seed so process restarts preserve realised PnL,
        # locked margin, and paid entry fees instead of re-crediting
        # the full starting balance.
        self._loaded_balance_snapshot = self._load_balances()
        if initial_balance and not self._loaded_balance_snapshot:
            for currency, amount in initial_balance.items():
                self._balances[currency] = PaperBalance(
                    currency=currency,
                    free=amount,
                )

        # DEBT-053: rebuild monitorable in-memory positions from the
        # persisted ledger so a process restart doesn't leave open
        # paper trades orphaned. Must run after ``_open_positions`` /
        # ``_balances`` / ``_trade_tracker`` are wired but before any
        # consumer of this instance can call ``check_exit_conditions``.
        self._rehydrate_open_positions()

        mode_str = "testnet" if self._use_testnet else "local simulation"
        logger.info(
            f"PaperTrader initialized in {mode_str} mode with balances: "
            f"{self.get_balance_summary()}, "
            f"fees: maker={self._fee_config.maker_fee_rate}, "
            f"taker={self._fee_config.taker_fee_rate}"
        )

    def _rehydrate_open_positions(self) -> None:
        """Rebuild monitorable paper positions from persisted open trades.

        DEBT-053: mirrors ``LiveTrader._rehydrate_open_positions`` so a
        Fly machine restart (or any other in-process restart) doesn't
        leave open paper trades stranded with no in-memory tracking.
        Without this, ``check_exit_conditions`` returns ``(False, None)``
        for every restored trade and the runtime engine's orphan guard
        fires ``MONITOR_ERRORED:orphan_open_trade`` forever.

        Legacy open trades that were persisted before SL/TP was wired
        through ``open_position`` will lack both bounds. Those are
        intentionally skipped (with a warning) so the orphan guard can
        still surface them for operator reconciliation — silently
        rehydrating a position with no exit bounds would mean the
        runtime can never auto-close it. Per-strategy backfill from the
        ``PerformanceRecord`` is intentionally out of scope for this
        commit (TECH-DEBT follow-up in the engine layer).

        DEBT-059: when a persisted balance snapshot exists, this method
        only restores the in-memory ``OpenPosition`` stash because
        ``PaperBalance`` was loaded with the original locked/free shape.
        On legacy ledgers with no snapshot, the runtime seed is the full
        configured initial balance, so rehydration reconciles margin and
        recorded entry fees once and then writes the first snapshot.
        """
        rehydrated: list[OpenPosition] = []
        for trade in self._trade_tracker.get_open_trades(mode="paper"):
            if trade.stop_loss is None and trade.take_profit is None:
                logger.warning(
                    "Open paper trade %s has no persisted SL/TP bounds; "
                    "operator reconciliation required before monitoring",
                    trade.id,
                )
                continue

            position = Position(
                symbol=trade.symbol,
                side=trade.side,
                entry_price=trade.entry_price,
                quantity=trade.entry_quantity,
                leverage=trade.leverage,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
            )
            margin = self._calculate_required_margin(position)
            quote_currency = self._get_quote_currency(trade.symbol)
            # ``trade.fees`` on an open trade only accumulates the
            # entry-side fee (``close_trade`` adds the exit fee at
            # close time). For trades opened on a build that didn't
            # record entry fees this is simply ``Decimal("0")``,
            # which is the safe default — we'd rather under-count
            # the paid entry fee than double-deduct it on close.
            entry_fee = trade.fees if trade.exit_price is None else Decimal("0")

            open_position = OpenPosition(
                trade_id=trade.id,
                position=position,
                margin=margin,
                quote_currency=quote_currency,
                entry_fee=entry_fee,
            )
            self._open_positions[trade.id] = open_position
            rehydrated.append(open_position)

            logger.info(
                "Rehydrated open paper position %s: %s %s @ %s qty=%s",
                trade.id,
                trade.side,
                trade.symbol,
                trade.entry_price,
                trade.entry_quantity,
            )

        if rehydrated and not self._loaded_balance_snapshot:
            self._reconcile_legacy_rehydrated_balances(rehydrated)

    def _get_balances_path(self) -> Path:
        """Return the per-sub-account paper balance snapshot path."""
        balances_dir = (
            self._trade_tracker.data_dir / "paper" / self._trade_tracker.sub_account_id
        )
        balances_dir.mkdir(parents=True, exist_ok=True)
        return balances_dir / "balances.json"

    def _load_balances(self) -> bool:
        """Load persisted paper balances, returning ``True`` when present."""
        balances_path = self._get_balances_path()
        if not balances_path.exists():
            return False

        try:
            with open(balances_path, encoding="utf-8") as f:
                rows = json.load(f)
            if not isinstance(rows, dict):
                raise ValueError("expected object keyed by currency")

            loaded: dict[str, PaperBalance] = {}
            for currency, row in rows.items():
                if not isinstance(row, dict):
                    raise ValueError(f"expected object for {currency}")
                loaded[currency] = PaperBalance(
                    currency=str(row.get("currency", currency)),
                    free=Decimal(str(row["free"])),
                    locked=Decimal(str(row["locked"])),
                )
        except Exception as exc:
            logger.error(
                "Failed to load paper balances from %s: %s", balances_path, exc
            )
            return False

        self._balances = loaded
        logger.info("Loaded paper balances from %s", balances_path)
        return True

    def _save_balances(self) -> None:
        """Persist paper balances atomically for restart-safe accounting."""
        balances_path = self._get_balances_path()
        payload = {
            currency: {
                "currency": balance.currency,
                "free": str(balance.free),
                "locked": str(balance.locked),
            }
            for currency, balance in sorted(self._balances.items())
        }
        atomic_write_text(
            balances_path,
            json.dumps(payload, indent=2, default=str),
        )

    def _reconcile_legacy_rehydrated_balances(
        self,
        open_positions: list[OpenPosition],
    ) -> None:
        """Apply one-time balance reconciliation for ledgers predating snapshots."""
        changed = False
        for open_pos in open_positions:
            balance = self.get_balance(open_pos.quote_currency)
            if balance is None:
                logger.warning(
                    "Cannot reconcile rehydrated paper position %s: "
                    "no %s balance configured",
                    open_pos.trade_id,
                    open_pos.quote_currency,
                )
                continue

            try:
                balance.lock(open_pos.margin)
                changed = True
            except InsufficientPaperBalanceError as exc:
                logger.warning(
                    "Cannot re-lock margin for rehydrated paper position %s: %s",
                    open_pos.trade_id,
                    exc,
                )
                continue

            if open_pos.entry_fee > 0:
                try:
                    balance.deduct(open_pos.entry_fee)
                    changed = True
                except InsufficientPaperBalanceError as exc:
                    logger.warning(
                        "Cannot re-apply entry fee for rehydrated paper position "
                        "%s: %s",
                        open_pos.trade_id,
                        exc,
                    )

        if changed:
            self._save_balances()

    @staticmethod
    def _resolve_fee_config(
        fee_config: FeeConfig | None,
        exchange: "BaseExchange | None",
    ) -> FeeConfig:
        """Determine the effective fee config for the trader.

        Precedence: explicit ``fee_config`` > exchange-specific default >
        zero-fee fallback.

        Args:
            fee_config: Explicitly supplied configuration, if any.
            exchange: Exchange instance used to look up a default.

        Returns:
            The effective FeeConfig.
        """
        if fee_config is not None:
            return fee_config
        if exchange is not None:
            return DEFAULT_FEE_CONFIGS.get(exchange.name.lower(), ZERO_FEE_CONFIG)
        return ZERO_FEE_CONFIG

    @property
    def fee_config(self) -> FeeConfig:
        """Get the active fee configuration.

        Returns:
            The FeeConfig in use for fee simulation.
        """
        return self._fee_config

    @property
    def is_testnet_mode(self) -> bool:
        """Check if using exchange testnet for execution.

        Returns:
            True if an exchange in testnet mode is configured.
        """
        return self._use_testnet

    @property
    def exchange(self) -> "BaseExchange | None":
        """Get the configured exchange instance.

        Returns:
            The exchange instance, or None if not configured.
        """
        return self._exchange

    def get_balance_summary(self) -> dict[str, dict[str, str]]:
        """Get a summary of all balances.

        Returns:
            Dictionary of currency -> {free, locked, total} as strings.
        """
        return {
            currency: {
                "free": str(balance.free),
                "locked": str(balance.locked),
                "total": str(balance.total),
            }
            for currency, balance in self._balances.items()
        }

    async def get_balances(self) -> dict[str, Decimal]:
        """Return per-currency total balances for the snapshot recorder.

        The paper ledger is in-memory so the ``async`` here is purely
        protocol conformance — there is no I/O.
        """
        return {currency: balance.total for currency, balance in self._balances.items()}

    def get_balance(self, currency: str) -> PaperBalance | None:
        """Get balance for a currency.

        Args:
            currency: Currency code.

        Returns:
            PaperBalance or None if currency not found.
        """
        return self._balances.get(currency)

    def get_all_balances(self) -> dict[str, PaperBalance]:
        """Get all balances.

        Returns:
            Dictionary of currency -> PaperBalance.
        """
        return self._balances.copy()

    def set_balance(self, currency: str, amount: Decimal) -> None:
        """Set the free balance for a currency.

        Creates the currency balance if it doesn't exist.

        Args:
            currency: Currency code.
            amount: Amount to set as free balance.
        """
        if currency in self._balances:
            # Reset to the new amount (keeping locked as is)
            balance = self._balances[currency]
            balance.free = amount
        else:
            self._balances[currency] = PaperBalance(
                currency=currency,
                free=amount,
            )
        self._save_balances()

    def _get_quote_currency(self, symbol: str) -> str:
        """Extract quote currency from symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT").

        Returns:
            Quote currency (e.g., "USDT").
        """
        if "/" in symbol:
            return symbol.split("/")[1]
        # Assume last 4 characters for USDT, 3 for USD, etc.
        if symbol.endswith("USDT"):
            return "USDT"
        if symbol.endswith("USD"):
            return "USD"
        if symbol.endswith("BTC"):
            return "BTC"
        # Default fallback
        return symbol[-4:] if len(symbol) > 4 else symbol

    def _calculate_required_margin(self, position: Position) -> Decimal:
        """Calculate margin required for a position.

        Args:
            position: The position.

        Returns:
            Required margin amount.
        """
        notional = position.notional_value
        return notional / Decimal(position.leverage)

    def _calculate_fee(
        self,
        notional: Decimal,
        is_maker: bool = False,
    ) -> Decimal:
        """Calculate trading fee for a notional value.

        Market orders are treated as taker fills; limit orders resting on
        the book are maker fills.

        Args:
            notional: The notional value (price * quantity) of the trade.
            is_maker: Whether to apply the maker rate instead of taker.

        Returns:
            Fee amount in the quote currency.
        """
        rate = (
            self._fee_config.maker_fee_rate
            if is_maker
            else self._fee_config.taker_fee_rate
        )
        return notional * rate

    def _generate_order_id(self) -> str:
        """Generate a simulated order ID.

        Returns:
            Unique order ID string.
        """
        return f"paper-{uuid.uuid4().hex[:12]}"

    async def open_position(
        self,
        position: Position,
        performance_record_id: str | None = None,
    ) -> TradeHistory:
        """Open a paper trading position.

        Locks the required margin and creates a trade record.

        Async to satisfy the :class:`~src.trading.base.Trader` protocol
        (``LiveTrader`` is naturally async). The body itself is purely
        in-memory and does not actually await anything; the runtime
        cost of the ``async``/``await`` is negligible.

        Args:
            position: The Position to open (from TradingStrategy.create_position).
            performance_record_id: Optional link to PerformanceRecord.

        Returns:
            TradeHistory record for the opened trade.

        Raises:
            InsufficientPaperBalanceError: If insufficient balance for margin.
            PaperTradingError: If position is invalid.
        """
        # Extract quote currency for balance management
        quote_currency = self._get_quote_currency(position.symbol)

        # Check balance exists
        balance = self.get_balance(quote_currency)
        if balance is None:
            raise PaperTradingError(
                f"No {quote_currency} balance configured for paper trading"
            )

        # Calculate and lock margin
        margin = self._calculate_required_margin(position)
        balance.lock(margin)

        # Calculate and deduct entry fee (market orders = taker).
        # On failure, unlock the margin to keep balance state consistent.
        entry_fee = self._calculate_fee(position.notional_value, is_maker=False)
        if entry_fee > 0:
            try:
                balance.deduct(entry_fee)
            except InsufficientPaperBalanceError:
                balance.unlock(margin)
                raise

        # Generate order ID for simulation
        order_id = self._generate_order_id()

        # Record trade via TradeHistoryTracker.
        # DEBT-053: persist SL/TP so ``_rehydrate_open_positions`` can
        # restore monitorable state across process restarts. The
        # testnet path below already passed these; the local-sim path
        # used to drop them, leaving rehydrated trades unmonitorable
        # and orphaned forever (see Fly paper run 2026-04-28~05-09).
        trade = self._trade_tracker.open_trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            entry_quantity=position.quantity,
            mode="paper",
            leverage=position.leverage,
            entry_order_id=order_id,
            performance_record_id=performance_record_id,
            fees=entry_fee,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
        )

        # Track open position
        self._open_positions[trade.id] = OpenPosition(
            trade_id=trade.id,
            position=position,
            margin=margin,
            quote_currency=quote_currency,
            entry_fee=entry_fee,
        )

        logger.info(
            f"Opened paper position: {position.side} {position.symbol} "
            f"@ {position.entry_price}, qty={position.quantity}, "
            f"margin={margin} {quote_currency}, entry_fee={entry_fee}"
        )
        self._save_balances()

        return trade

    async def close_position(
        self,
        trade_id: str,
        exit_price: Decimal,
        reason: str = "manual",
    ) -> TradeHistory | None:
        """Close a paper trading position.

        Calculates P&L, updates balance, and records the trade closure.

        Async to satisfy the :class:`~src.trading.base.Trader` protocol;
        the body is in-memory only and does not actually await anything.

        Args:
            trade_id: ID of the trade to close.
            exit_price: Price at which to close.
            reason: Reason for closing (manual, stop_loss, take_profit).

        Returns:
            Updated TradeHistory, or None if trade not found.

        Raises:
            PaperTradingError: If trade is not an open paper trade.
        """
        # Get open position
        open_pos = self._open_positions.get(trade_id)
        if open_pos is None:
            logger.warning(f"No open paper position found: {trade_id}")
            return None

        position = open_pos.position
        margin = open_pos.margin
        quote_currency = open_pos.quote_currency
        entry_fee = open_pos.entry_fee

        # Realised P&L via the single-source helper (DEBT-024 / Phase
        # 20.1). PaperTrader's convention has always matched the
        # helper (no double-leverage); routing through ``pnl_for_trade``
        # is for symmetry with the backtester and portfolio sites.
        pnl = pnl_for_trade(
            entry=position.entry_price,
            exit=exit_price,
            qty=position.quantity,
            side=position.side,
        )

        # Calculate exit fee (market orders = taker)
        exit_notional = exit_price * position.quantity
        exit_fee = self._calculate_fee(exit_notional, is_maker=False)
        total_fees = entry_fee + exit_fee

        # Update balance: unlock margin, apply P&L, deduct exit fee.
        # Entry fee was already deducted at open time.
        #
        # Phase 22.2 / DEBT-027: when ``pnl - exit_fee`` would push
        # ``free`` below zero the trade is under water — the legacy
        # behaviour silently clamped to zero, hiding the shortfall.
        # The new behaviour records true (negative) post-liquidation
        # equity AND emits a ``LIQUIDATED`` activity event so the
        # dashboard / operators see the cliff. The legacy clamp is
        # available behind ``self._auto_deposit_on_liquidation``
        # for testing scenarios that need the run to continue.
        balance = self.get_balance(quote_currency)
        liquidated = False
        balance_before = Decimal("0")
        balance_after = Decimal("0")
        if balance:
            balance.unlock(margin)
            balance_before = balance.free

            # Net delta to ``free`` from this close: pnl is negative on
            # losses (we add it directly so a loss subtracts) and
            # exit_fee always deducts.
            net_delta = pnl - exit_fee
            projected_free = balance.free + net_delta
            liquidated = projected_free < 0

            if liquidated and self._auto_deposit_on_liquidation:
                # Legacy clamp — available only behind the explicit
                # opt-in flag so paper forecasts continue past the
                # liquidation point. The shortfall is still visible
                # via the LIQUIDATED activity event below.
                balance.free = Decimal("0")
            else:
                # Default + non-liquidating happy path: write the
                # projected balance directly. The relaxed ``ge=0``
                # constraint on ``PaperBalance.free`` lets this go
                # negative when ``liquidated`` is True, reflecting the
                # true post-liquidation equity (negative when
                # leverage > 1).
                balance.free = projected_free

            balance_after = balance.free

        # Close trade via tracker (records total fees for P&L accuracy)
        closed_trade = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            close_reason=reason,
            fees=exit_fee,
        )

        # Remove from open positions
        del self._open_positions[trade_id]

        logger.info(
            f"Closed paper position {trade_id}: {reason}, "
            f"exit_price={exit_price}, P&L={pnl}, fees={total_fees}"
        )

        if liquidated and self._activity_log is not None:
            # Structured-fields contract pinned by
            # ``test_under_water_close_emits_liquidated_event``. The
            # dashboard reads these keys verbatim.
            self._activity_log.append(
                ActivityEventType.LIQUIDATED,
                (
                    f"Paper liquidation: {position.symbol} {position.side} "
                    f"realized_pnl={pnl} balance_after={balance_after}"
                ),
                details={
                    "symbol": position.symbol,
                    "side": position.side,
                    "entry": str(position.entry_price),
                    "exit": str(exit_price),
                    "qty": str(position.quantity),
                    "realized_pnl": str(pnl),
                    "balance_before": str(balance_before),
                    "balance_after": str(balance_after),
                },
            )

        if closed_trade is not None and balance is not None:
            self._save_balances()

        return closed_trade

    async def force_close_orphan(
        self,
        trade_id: str,
        exit_price: Decimal,
    ) -> TradeHistory | None:
        """Persistence-only force-close for an orphaned paper trade.

        DEBT-058 follow-up watchdog hook (see
        :class:`~src.trading.base.Trader`). Closes the persisted trade
        record without requiring ``self._open_positions[trade_id]`` —
        by definition the in-memory position state is gone, which is
        precisely what makes the trade an orphan.

        Returns ``None`` (no-op) when the trade is already closed or
        unknown; mirrors the missing-trade contract on
        :meth:`close_position` so the runtime watchdog doesn't crash
        on a transient race.

        Best-effort balance unlock: ``OpenPosition.margin`` is the
        only authoritative source for the originally-locked margin,
        and by the time a trade is orphaned that record is gone. The
        caller (the runtime watchdog) accepts that ``PaperBalance``
        may drift; an operator can run a rebalance script later.
        Fees on the persisted trade are left as their existing value
        — fee inputs are not available here (no order fill to read
        from), so under-counting is preferable to fabricating numbers.
        """
        existing = self._trade_tracker.get_trade(trade_id)
        if existing is None or existing.status != "open":
            logger.warning(
                "force_close_orphan: trade %s not found or not open "
                "(status=%s); no-op",
                trade_id,
                existing.status if existing is not None else "missing",
            )
            return None

        # Defensive race: if a late rehydration restored
        # ``_open_positions[trade_id]`` between the watchdog's
        # ``_missing_position_state`` check and now, drop it so the
        # in-memory map doesn't outlive the persisted "closed" row.
        # Best-effort margin unlock if we still have it.
        open_pos = self._open_positions.pop(trade_id, None)
        balance_changed = False
        if open_pos is not None:
            balance = self.get_balance(open_pos.quote_currency)
            if balance is not None:
                try:
                    balance.unlock(open_pos.margin)
                    balance_changed = True
                except PaperTradingError as e:
                    logger.warning(
                        "force_close_orphan: best-effort margin unlock "
                        "failed for %s (%s); operator rebalance may be needed",
                        trade_id,
                        e,
                    )

        closed = self._trade_tracker.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            close_reason="orphan_force_close",
        )

        if closed is not None:
            logger.warning(
                "force_close_orphan: closed orphaned paper trade %s at %s "
                "(side=%s entry=%s pnl=%s)",
                trade_id,
                exit_price,
                closed.side,
                closed.entry_price,
                closed.pnl,
            )

        if closed is not None and balance_changed:
            self._save_balances()

        return closed

    def check_exit_conditions(
        self,
        trade_id: str,
        current_price: Decimal,
    ) -> tuple[bool, str | None]:
        """Check if a position should be closed due to SL/TP.

        Args:
            trade_id: ID of the trade to check.
            current_price: Current market price.

        Returns:
            Tuple of (should_exit, reason). reason is None if should_exit is False.
        """
        open_pos = self._open_positions.get(trade_id)
        if open_pos is None:
            return False, None

        return exit_condition_for_position(open_pos.position, current_price)

    def get_open_trades(self) -> list[TradeHistory]:
        """Get all open paper trades.

        Returns:
            List of open TradeHistory records.
        """
        return self._trade_tracker.get_open_trades(mode="paper")

    def get_trade(self, trade_id: str) -> TradeHistory | None:
        """Get a trade by ID.

        Args:
            trade_id: The trade ID.

        Returns:
            TradeHistory or None if not found.
        """
        return self._trade_tracker.get_trade(trade_id)

    def get_open_position(self, trade_id: str) -> OpenPosition | None:
        """Get an open position's details.

        Args:
            trade_id: The trade ID.

        Returns:
            OpenPosition or None if not found.
        """
        return self._open_positions.get(trade_id)

    def update_unrealized_pnl(
        self,
        current_prices: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Update unrealized P&L for all open positions.

        Args:
            current_prices: Dictionary of symbol -> current price.

        Returns:
            Dictionary of trade_id -> unrealized P&L.
        """
        pnl_by_trade: dict[str, Decimal] = {}

        for trade_id, open_pos in self._open_positions.items():
            symbol = open_pos.position.symbol
            if symbol in current_prices:
                current_price = current_prices[symbol]
                pnl = open_pos.position.calculate_pnl(current_price)
                pnl_by_trade[trade_id] = pnl

        return pnl_by_trade

    def get_total_unrealized_pnl(
        self,
        current_prices: dict[str, Decimal],
    ) -> Decimal:
        """Get total unrealized P&L across all open positions.

        Args:
            current_prices: Dictionary of symbol -> current price.

        Returns:
            Total unrealized P&L.
        """
        pnl_by_trade = self.update_unrealized_pnl(current_prices)
        return sum(pnl_by_trade.values(), Decimal("0"))

    def get_total_equity(
        self,
        quote_currency: str,
        current_prices: dict[str, Decimal] | None = None,
    ) -> Decimal:
        """Get total equity (balance + unrealized P&L).

        Args:
            quote_currency: The quote currency to calculate equity for.
            current_prices: Current prices for unrealized P&L calculation.

        Returns:
            Total equity in quote currency.
        """
        balance = self.get_balance(quote_currency)
        if balance is None:
            return Decimal("0")

        equity = balance.total

        if current_prices:
            unrealized_pnl = self.get_total_unrealized_pnl(current_prices)
            equity += unrealized_pnl

        return equity

    # =========================================================================
    # Testnet Integration Methods
    # =========================================================================

    async def sync_balance_from_exchange(
        self,
        currency: str | None = None,
    ) -> None:
        """Sync balance from exchange testnet.

        Fetches real testnet balances and updates internal state.
        Requires exchange instance in testnet mode.

        Args:
            currency: Optional currency filter. If None, syncs all non-zero balances.

        Raises:
            PaperTradingError: If not in testnet mode or sync fails.
        """
        if not self._use_testnet or self._exchange is None:
            raise PaperTradingError(
                "sync_balance_from_exchange requires testnet mode with exchange"
            )

        try:
            balances = await self._exchange.get_balance(currency)

            for balance in balances:
                self._balances[balance.currency] = PaperBalance(
                    currency=balance.currency,
                    free=balance.free,
                    locked=balance.locked,
                )
            self._save_balances()

            logger.info(
                f"Synced {len(balances)} balance(s) from {self._exchange.name} testnet"
            )

        except Exception as e:
            raise PaperTradingError(f"Failed to sync balance from exchange: {e}") from e

    async def open_position_on_testnet(
        self,
        position: Position,
        performance_record_id: str | None = None,
    ) -> TradeHistory:
        """Open position via exchange testnet order.

        Creates a real order on the exchange testnet instead of simulating.
        Uses market orders for immediate execution.

        Args:
            position: The Position to open.
            performance_record_id: Optional link to PerformanceRecord.

        Returns:
            TradeHistory record with real order ID from exchange.

        Raises:
            PaperTradingError: If not in testnet mode or order fails.
        """
        if not self._use_testnet or self._exchange is None:
            raise PaperTradingError(
                "open_position_on_testnet requires testnet mode with exchange"
            )

        # Extract quote currency for balance tracking
        quote_currency = self._get_quote_currency(position.symbol)

        # Build order request
        order_request = OrderRequest(
            symbol=position.symbol,
            side=entry_order_side(position.side),
            type="market",
            quantity=position.quantity,
        )

        try:
            # Execute order on exchange testnet
            order = await self._exchange.create_order(order_request)

            logger.info(
                f"Testnet order executed: {order.id} {order.side} {order.symbol} "
                f"qty={order.filled_quantity}"
            )

            # Calculate margin for tracking
            margin = self._calculate_required_margin(position)

            entry_fill_price = order.average_price or position.entry_price
            filled_quantity = (
                order.filled_quantity
                if order.filled_quantity > 0
                else position.quantity
            )
            entry_fee = order.fee or Decimal("0")

            # Record trade via TradeHistoryTracker
            trade = self._trade_tracker.open_trade(
                symbol=position.symbol,
                side=position.side,
                entry_price=entry_fill_price,
                entry_quantity=filled_quantity,
                mode="paper",
                leverage=position.leverage,
                entry_order_id=order.id,  # Real order ID from exchange
                performance_record_id=performance_record_id,
                fees=entry_fee,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
            )

            # Track open position
            self._open_positions[trade.id] = OpenPosition(
                trade_id=trade.id,
                position=position.model_copy(
                    update={
                        "entry_price": entry_fill_price,
                        "quantity": filled_quantity,
                    }
                ),
                margin=margin,
                quote_currency=quote_currency,
                entry_fee=entry_fee,
            )

            logger.info(
                f"Opened testnet position: {position.side} {position.symbol} "
                f"@ {entry_fill_price}, qty={filled_quantity}, "
                f"entry_fee={entry_fee} {order.fee_currency or ''}, "
                f"order_id={order.id}"
            )
            self._save_balances()

            return trade

        except Exception as e:
            # Check for insufficient funds
            error_str = str(e).lower()
            if "insufficient" in error_str:
                raise InsufficientPaperBalanceError(
                    f"Insufficient testnet funds: {e}",
                    required=position.notional_value,
                    available=Decimal("0"),  # Unknown from error
                    currency=quote_currency,
                ) from e
            raise PaperTradingError(f"Failed to create testnet order: {e}") from e

    async def close_position_on_testnet(
        self,
        trade_id: str,
        exit_price: Decimal | None = None,
        reason: str = "manual",
    ) -> TradeHistory | None:
        """Close position via exchange testnet order.

        Creates a closing order on exchange testnet.
        Uses market orders for immediate execution.

        Args:
            trade_id: ID of the trade to close.
            exit_price: Expected exit price (for P&L calculation).
                       If None, will use the filled price from exchange.
            reason: Reason for closing (manual, stop_loss, take_profit).

        Returns:
            Updated TradeHistory, or None if trade not found.

        Raises:
            PaperTradingError: If not in testnet mode or order fails.
        """
        if not self._use_testnet or self._exchange is None:
            raise PaperTradingError(
                "close_position_on_testnet requires testnet mode with exchange"
            )

        # Get open position
        open_pos = self._open_positions.get(trade_id)
        if open_pos is None:
            logger.warning(f"No open testnet position found: {trade_id}")
            return None

        position = open_pos.position

        # Build closing order (opposite side)
        closing_side: OrderSide = closing_order_side(position.side)
        order_request = OrderRequest(
            symbol=position.symbol,
            side=closing_side,
            type="market",
            quantity=position.quantity,
        )

        try:
            # Execute closing order on exchange testnet
            order = await self._exchange.create_order(order_request)

            logger.info(
                f"Testnet closing order executed: {order.id} {order.side} "
                f"{order.symbol} qty={order.filled_quantity}"
            )

            # Prefer exchange fill economics when available. The
            # caller-provided exit_price is the expected trigger price,
            # while average_price is what the testnet order actually filled at.
            actual_exit_price = (
                order.average_price or exit_price or position.entry_price
            )
            exit_fee = order.fee or Decimal("0")

            # Calculate P&L
            pnl = position.calculate_pnl(actual_exit_price)

            # Close trade via tracker
            closed_trade = self._trade_tracker.close_trade(
                trade_id=trade_id,
                exit_price=actual_exit_price,
                exit_quantity=order.filled_quantity or position.quantity,
                close_reason=reason,
                exit_order_id=order.id,
                fees=exit_fee,
            )

            # Remove from open positions
            del self._open_positions[trade_id]

            logger.info(
                f"Closed testnet position {trade_id}: {reason}, "
                f"exit_price={actual_exit_price}, P&L={pnl}, order_id={order.id}, "
                f"exit_fee={exit_fee} {order.fee_currency or ''}"
            )

            return closed_trade

        except Exception as e:
            raise PaperTradingError(
                f"Failed to create testnet closing order: {e}"
            ) from e
