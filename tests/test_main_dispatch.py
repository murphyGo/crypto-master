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
from src.main import (
    _engine_auto_confirmation,
    _purge_old_proposals,
    build_exchange,
    build_trader,
)
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


# =============================================================================
# Phase 10.2: env override propagates through build_engine -> EngineConfig
# =============================================================================


class TestBuildEngineEnvOverride:
    """``build_engine`` must read its tunables from ``Settings`` so env
    vars propagate through to the resolved ``EngineConfig`` (Phase 10.2)."""

    def test_settings_overrides_propagate_to_engine_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting ``ENGINE_*`` env vars must surface on the engine's
        ``EngineConfig`` after ``build_engine``."""
        from src.config import Settings
        from src.main import build_engine

        monkeypatch.setenv("ENGINE_AUTO_APPROVE_THRESHOLD", "2.5")
        monkeypatch.setenv("ENGINE_CYCLE_INTERVAL", "120")
        monkeypatch.setenv("ENGINE_SYMBOLS", "BTC/USDT,ETH/USDT")
        monkeypatch.setenv("ENGINE_BALANCE", "7500")

        # Build Settings from env (no .env file shenanigans here — the
        # test process inherits env we just set via monkeypatch).
        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )
        settings = Settings(trading_mode="paper", binance=bn)
        exchange = build_exchange(settings)

        with patch(
            "src.main.load_all_strategies", return_value={}
        ), patch("src.main.PerformanceTracker"), patch(
            "src.main.ProposalHistory"
        ), patch("src.main.ActivityLog"):
            engine = build_engine(settings, exchange)

        assert engine.config.auto_approve_threshold == 2.5
        assert engine.config.cycle_interval_seconds == 120
        assert engine.config.altcoin_symbols == ["BTC/USDT", "ETH/USDT"]
        assert engine.config.balance == Decimal("7500")

    def test_slack_notifier_created_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``SLACK_WEBHOOK_URL`` set → dispatcher gains a SlackNotifier (Phase 11.3)."""
        from src.config import Settings
        from src.main import build_engine
        from src.proposal.notification import SlackNotifier

        monkeypatch.setenv(
            "SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/services/T0/B0/XXX",
        )

        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )
        settings = Settings(trading_mode="paper", binance=bn)
        exchange = build_exchange(settings)

        with patch(
            "src.main.load_all_strategies", return_value={}
        ), patch("src.main.PerformanceTracker"), patch(
            "src.main.ProposalHistory"
        ), patch("src.main.ActivityLog"):
            engine = build_engine(settings, exchange)

        notifiers = engine.notification_dispatcher._notifiers
        assert any(isinstance(n, SlackNotifier) for n in notifiers)

    def test_slack_notifier_silent_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unset ``SLACK_WEBHOOK_URL`` → no SlackNotifier in dispatcher."""
        from src.config import Settings
        from src.main import build_engine
        from src.proposal.notification import SlackNotifier

        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )
        # Explicit ``slack_webhook_url=None`` defends against a stale
        # value lingering in the test process's environment.
        settings = Settings(
            trading_mode="paper",
            binance=bn,
            slack_webhook_url=None,
        )
        exchange = build_exchange(settings)

        with patch(
            "src.main.load_all_strategies", return_value={}
        ), patch("src.main.PerformanceTracker"), patch(
            "src.main.ProposalHistory"
        ), patch("src.main.ActivityLog"):
            engine = build_engine(settings, exchange)

        notifiers = engine.notification_dispatcher._notifiers
        assert not any(isinstance(n, SlackNotifier) for n in notifiers)

    def test_telegram_notifier_created_when_both_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` set →
        dispatcher gains a TelegramNotifier (Phase 12.4)."""
        from src.config import Settings
        from src.main import build_engine
        from src.proposal.notification import TelegramNotifier

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAH-test-XYZ")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")

        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )
        settings = Settings(trading_mode="paper", binance=bn)
        exchange = build_exchange(settings)

        with patch(
            "src.main.load_all_strategies", return_value={}
        ), patch("src.main.PerformanceTracker"), patch(
            "src.main.ProposalHistory"
        ), patch("src.main.ActivityLog"):
            engine = build_engine(settings, exchange)

        notifiers = engine.notification_dispatcher._notifiers
        assert any(isinstance(n, TelegramNotifier) for n in notifiers)

    def test_telegram_notifier_silent_when_either_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If either Telegram env var is unset the notifier must NOT be
        added — partial config silently disables the backend."""
        from src.config import Settings
        from src.main import build_engine
        from src.proposal.notification import TelegramNotifier

        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )

        # Defend against env leakage between the three sub-cases by
        # passing the field explicitly on each Settings construction.
        scenarios: list[tuple[str | None, str | None]] = [
            ("123456789:AAH-test-XYZ", None),  # token only
            (None, "-1001234567890"),  # chat id only
            (None, None),  # neither
        ]

        for token, chat_id in scenarios:
            monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
            monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

            settings = Settings(
                trading_mode="paper",
                binance=bn,
                telegram_bot_token=token,
                telegram_chat_id=chat_id,
            )
            exchange = build_exchange(settings)

            with patch(
                "src.main.load_all_strategies", return_value={}
            ), patch("src.main.PerformanceTracker"), patch(
                "src.main.ProposalHistory"
            ), patch("src.main.ActivityLog"):
                engine = build_engine(settings, exchange)

            notifiers = engine.notification_dispatcher._notifiers
            assert not any(
                isinstance(n, TelegramNotifier) for n in notifiers
            ), f"TelegramNotifier should be silent for token={token!r}, chat_id={chat_id!r}"

    def test_explicit_config_argument_still_wins(self) -> None:
        """``build_engine`` allows callers (tests / one-shots) to pass
        their own ``EngineConfig``; that path must override Settings."""
        from src.config import Settings
        from src.main import build_engine

        bn = BinanceConfig(
            api_key="",
            api_secret="",
            testnet_api_key="testnet-bn-key",
            testnet_api_secret="testnet-bn-secret",
            testnet=False,
        )
        settings = Settings(
            trading_mode="paper",
            binance=bn,
            engine_auto_approve_threshold=0.5,
        )
        exchange = build_exchange(settings)
        explicit = EngineConfig(auto_approve_threshold=3.0)

        with patch(
            "src.main.load_all_strategies", return_value={}
        ), patch("src.main.PerformanceTracker"), patch(
            "src.main.ProposalHistory"
        ), patch("src.main.ActivityLog"):
            engine = build_engine(settings, exchange, config=explicit)

        assert engine.config.auto_approve_threshold == 3.0


# =============================================================================
# Phase 11.4: ProposalHistory.purge_old startup hook
# =============================================================================


class TestPurgeOldProposalsHook:
    """The startup hook archives stale proposals once per process boot
    and stays quiet when there's nothing to do."""

    def test_calls_purge_old_with_retention_from_settings(self) -> None:
        """The helper forwards ``retention_months`` from ``Settings``
        to ``ProposalHistory.purge_old`` verbatim."""
        from unittest.mock import MagicMock

        history = MagicMock()
        history.purge_old.return_value = []

        purged = _purge_old_proposals(history, retention_months=12)

        history.purge_old.assert_called_once_with(retention_months=12)
        assert purged == 0

    def test_returns_count_of_archived_records(self) -> None:
        """The helper returns ``len(archived)`` so callers can log it."""
        from pathlib import Path
        from unittest.mock import MagicMock

        history = MagicMock()
        history.purge_old.return_value = [
            Path("a.json"),
            Path("b.json"),
            Path("c.json"),
        ]

        purged = _purge_old_proposals(history, retention_months=6)

        assert purged == 3

    def test_logs_info_only_when_records_were_purged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No log line on the empty path — long-running deploys would
        otherwise emit a noisy "0 records" line every startup.

        ``get_logger`` disables propagation so the default ``caplog``
        handler (attached to root) misses these records — wire
        ``caplog.handler`` onto the named logger for the duration of
        the assertion (same pattern as ``test_ai_claude.py``).
        """
        import logging
        from pathlib import Path
        from unittest.mock import MagicMock

        history = MagicMock()
        target_logger = logging.getLogger("crypto_master.main")
        target_logger.addHandler(caplog.handler)
        target_logger.setLevel(logging.INFO)
        try:
            history.purge_old.return_value = []
            _purge_old_proposals(history, retention_months=12)
            assert not any(
                "Purged" in record.getMessage()
                and "proposal" in record.getMessage()
                for record in caplog.records
            )

            history.purge_old.return_value = [Path("old.json")]
            caplog.clear()
            _purge_old_proposals(history, retention_months=12)
            assert any(
                "Purged 1 proposal record" in record.getMessage()
                for record in caplog.records
            )
        finally:
            target_logger.removeHandler(caplog.handler)

    def test_build_engine_followed_by_purge_does_not_crash(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Smoke: ``build_engine`` then ``_purge_old_proposals`` runs
        cleanly against a real (empty) ``ProposalHistory`` rooted at a
        ``tmp_path``."""
        from src.main import build_engine
        from src.proposal.interaction import ProposalHistory

        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from src.config import reload_settings

        reload_settings()
        try:
            settings = Settings(
                trading_mode="paper",
                binance=BinanceConfig(
                    api_key="",
                    api_secret="",
                    testnet_api_key="testnet-bn-key",
                    testnet_api_secret="testnet-bn-secret",
                    testnet=False,
                ),
                data_dir=tmp_path,
            )
            exchange = build_exchange(settings)

            with patch(
                "src.main.load_all_strategies", return_value={}
            ), patch("src.main.PerformanceTracker"), patch(
                "src.main.ActivityLog"
            ):
                build_engine(settings, exchange)

            # Hook runs cleanly when the proposals dir does not yet exist.
            history = ProposalHistory(data_dir=tmp_path / "proposals")
            count = _purge_old_proposals(
                history, retention_months=settings.log_retention_months
            )
            assert count == 0
        finally:
            monkeypatch.delenv("DATA_DIR", raising=False)
            reload_settings()
