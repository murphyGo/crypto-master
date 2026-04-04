"""Tests for the logging module."""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.logger import get_logger, reset_loggers, setup_logger


@pytest.fixture(autouse=True)
def clean_loggers():
    """Reset loggers before and after each test."""
    reset_loggers()
    yield
    reset_loggers()


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_creates_logger_with_name(self) -> None:
        """Test that setup_logger creates a logger with the given name."""
        logger = setup_logger("test_logger")
        assert logger.name == "test_logger"

    def test_default_name_is_crypto_master(self) -> None:
        """Test that default logger name is crypto_master."""
        logger = setup_logger()
        assert logger.name == "crypto_master"

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Test that log directory is created if it doesn't exist."""
        log_file = tmp_path / "logs" / "subdir" / "test.log"
        assert not log_file.parent.exists()

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"
            setup_logger("test_dir_creation", log_file=log_file)

        assert log_file.parent.exists()

    def test_writes_to_file(self, tmp_path: Path) -> None:
        """Test that logger writes to log file."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"
            logger = setup_logger("test_file_write", log_file=log_file)

        logger.info("Test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_respects_log_level(self, tmp_path: Path) -> None:
        """Test that logger respects the configured log level."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "WARNING"
            logger = setup_logger(
                "test_log_level", log_file=log_file, log_level="WARNING"
            )

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")

        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" in content

    def test_console_output_can_be_disabled(self, tmp_path: Path) -> None:
        """Test that console output can be disabled."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"
            logger = setup_logger(
                "test_no_console", log_file=log_file, console_output=False
            )

        # Should only have file handler
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" not in handler_types
        assert "FileHandler" in handler_types

    def test_file_output_can_be_disabled(self, tmp_path: Path) -> None:
        """Test that file output can be disabled."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"
            logger = setup_logger(
                "test_no_file", log_file=log_file, file_output=False
            )

        # Should only have stream handler
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "FileHandler" not in handler_types

    def test_does_not_add_duplicate_handlers(self, tmp_path: Path) -> None:
        """Test that calling setup_logger twice doesn't add duplicate handlers."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            logger1 = setup_logger("test_duplicate", log_file=log_file)
            handler_count1 = len(logger1.handlers)

            logger2 = setup_logger("test_duplicate", log_file=log_file)
            handler_count2 = len(logger2.handlers)

        assert handler_count1 == handler_count2
        assert logger1 is logger2


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_same_logger_instance(self, tmp_path: Path) -> None:
        """Test that get_logger returns the same instance for the same name."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            logger1 = get_logger("test_same")
            logger2 = get_logger("test_same")

        assert logger1 is logger2

    def test_initializes_logger_if_not_exists(self, tmp_path: Path) -> None:
        """Test that get_logger initializes a new logger if it doesn't exist."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            logger = get_logger("new_logger")

        assert logger.name == "new_logger"
        assert len(logger.handlers) > 0

    def test_default_name_is_crypto_master(self, tmp_path: Path) -> None:
        """Test that default logger name is crypto_master."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            logger = get_logger()

        assert logger.name == "crypto_master"


class TestResetLoggers:
    """Tests for reset_loggers function."""

    def test_removes_all_handlers(self, tmp_path: Path) -> None:
        """Test that reset_loggers removes all handlers."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            logger = setup_logger("test_reset", log_file=log_file)
            assert len(logger.handlers) > 0

            reset_loggers()

        # After reset, the logger object still exists but has no handlers
        logger = logging.getLogger("test_reset")
        assert len(logger.handlers) == 0

    def test_allows_reinitialization(self, tmp_path: Path) -> None:
        """Test that loggers can be reinitialized after reset."""
        log_file = tmp_path / "test.log"

        with patch("src.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file = log_file
            mock_settings.return_value.log_level = "INFO"

            setup_logger("test_reinit", log_file=log_file)
            reset_loggers()
            logger = setup_logger("test_reinit", log_file=log_file)

        assert len(logger.handlers) > 0
