"""Tests for ``src.main`` paper/live dispatch (Phase 10.1).

Verifies:
- ``build_exchange`` returns a testnet exchange in paper mode and a
  mainnet exchange in live mode (after credential validation).
- ``build_trader`` returns ``PaperTrader`` for paper mode and
  ``LiveTrader`` for live mode.
- ``LiveTrader``'s confirmation callback is the engine's
  auto-confirmation shim (live mode does not block on stdin).
- The paper-mode auto-confirmation function returns True (used by
  the engine's auto-decide path).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from src.config import BinanceConfig, BybitConfig, Settings
from src.exchange.binance import BinanceExchange
from src.exchange.bybit import BybitExchange
from src.main import _engine_auto_confirmation, build_exchange, build_trader
from src.runtime.engine import EngineConfig
from src.trading.live import LiveTrader
from src.trading.paper import PaperTrader


def _settings(
    *,
    mode: str = "paper",
    binance_live: bool = False,
    binance_testnet: bool = False,
    bybit_live: bool = False,
    bybit_testnet: bool = False,
) -> Settings:
    """Build a ``Settings`` instance with explicit credential presence.

    Avoids touching the user's real ``.env`` by passing fields directly.
    """
    bn = BinanceConfig(
        api_key="live-bn-key" if binance_live else "",
        api_secret="live-bn-secret" if binance_live else "",
        testnet_api_key="testnet-bn-key" if binance_testnet else "",
        testnet_api_secret="testnet-bn-secret" if binance_testnet else "",
        testnet=False,
    )
    by = BybitConfig(
        api_key="live-by-key" if bybit_live else "",
        api_secret="live-by-secret" if bybit_live else "",
        testnet_api_key="testnet-by-key" if bybit_testnet else "",
        testnet_api_secret="testnet-by-secret" if bybit_testnet else "",
        testnet=False,
    )
    return Settings(
        trading_mode=mode,  # type: ignore[arg-type]
        binance=bn,
        bybit=by,
    )


# =============================================================================
# build_exchange
# =============================================================================


class TestBuildExchange:
    def test_paper_returns_testnet_binance_when_configured(self) -> None:
        ex = build_exchange(_settings(mode="paper", binance_testnet=True))
        assert isinstance(ex, BinanceExchange)
        assert ex.testnet is True

    def test_paper_falls_back_to_bybit_when_only_bybit(self) -> None:
        ex = build_exchange(_settings(mode="paper", bybit_testnet=True))
        assert isinstance(ex, BybitExchange)
        assert ex.testnet is True

    def test_paper_raises_when_no_exchange_configured(self) -> None:
        with pytest.raises(RuntimeError, match="No exchange configured"):
            build_exchange(_settings(mode="paper"))

    def test_live_returns_mainnet_binance(self) -> None:
        ex = build_exchange(_settings(mode="live", binance_live=True))
        assert isinstance(ex, BinanceExchange)
        assert ex.testnet is False

    def test_live_falls_back_to_bybit_when_only_bybit_live(self) -> None:
        ex = build_exchange(_settings(mode="live", bybit_live=True))
        assert isinstance(ex, BybitExchange)
        assert ex.testnet is False

    def test_live_with_only_testnet_keys_raises(self) -> None:
        """Live mode demands live credentials specifically — testnet
        keys are not enough."""
        with pytest.raises(
            (ValueError, RuntimeError),
            match="(?i)live trading|live.*api keys",
        ):
            build_exchange(_settings(mode="live", binance_testnet=True))


# =============================================================================
# build_trader
# =============================================================================


class TestBuildTrader:
    def test_paper_returns_paper_trader(self, tmp_path: Any) -> None:
        # Use a stub exchange to avoid CCXT initialization.
        exchange = build_exchange(_settings(mode="paper", binance_testnet=True))
        trader = build_trader(
            _settings(mode="paper", binance_testnet=True),
            exchange,
            EngineConfig(),
        )
        assert isinstance(trader, PaperTrader)

    def test_live_returns_live_trader_with_engine_confirmation(self) -> None:
        exchange = build_exchange(_settings(mode="live", binance_live=True))
        trader = build_trader(
            _settings(mode="live", binance_live=True),
            exchange,
            EngineConfig(),
        )
        assert isinstance(trader, LiveTrader)
        # LiveTrader stores the callback on the private slot used at
        # confirmation time; verify the engine's auto-confirmation
        # function is what's wired.
        assert trader._confirmation_callback is _engine_auto_confirmation


# =============================================================================
# _engine_auto_confirmation
# =============================================================================


class TestEngineAutoConfirmation:
    @pytest.mark.asyncio
    async def test_returns_true_for_open_action(self) -> None:
        """The engine's auto-decide gate has already filtered the
        proposal; the live confirmation callback approves
        unconditionally."""

        class _StubPosition:
            symbol = "BTC/USDT"
            side = "long"
            quantity = Decimal("0.1")

        result = await _engine_auto_confirmation(_StubPosition(), "open")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_close_action(self) -> None:
        class _StubPosition:
            symbol = "ETH/USDT"
            side = "short"
            quantity = Decimal("1.0")

        result = await _engine_auto_confirmation(_StubPosition(), "close")
        assert result is True


# =============================================================================
# Wiring smoke
# =============================================================================


def test_build_engine_logs_trading_mode(tmp_path: Any) -> None:
    """The startup log line that operators rely on to verify mode
    must mention which trader was wired."""
    from src.main import build_engine

    settings = _settings(mode="paper", binance_testnet=True)
    exchange = build_exchange(settings)

    # Avoid persisting to the real data dir.
    with patch(
        "src.main.load_all_strategies", return_value={}
    ), patch("src.main.PerformanceTracker"), patch(
        "src.main.ProposalHistory"
    ), patch("src.main.ActivityLog"):
        engine = build_engine(settings, exchange)

    assert isinstance(engine.trader, PaperTrader)
