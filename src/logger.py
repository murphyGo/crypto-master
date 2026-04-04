"""Logging module for Crypto Master.

Provides centralized logging with file and console output.
Configuration is loaded from the settings module.

Related Requirements:
- NFR-001: Python 3.10+
"""

import logging
import sys
from pathlib import Path
from typing import Literal

from src.config import get_settings

# Module-level cache for initialized loggers
_initialized_loggers: set[str] = set()

# Default format for log messages
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "crypto_master",
    log_file: Path | None = None,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
    console_output: bool = True,
    file_output: bool = True,
) -> logging.Logger:
    """Create and configure a logger with file and console handlers.

    Args:
        name: Logger name. Defaults to "crypto_master".
        log_file: Path to log file. If None, uses settings.log_file.
        log_level: Log level. If None, uses settings.log_level.
        console_output: Whether to output to console. Defaults to True.
        file_output: Whether to output to file. Defaults to True.

    Returns:
        logging.Logger: Configured logger instance.
    """
    settings = get_settings()

    # Use provided values or fall back to settings
    if log_file is None:
        log_file = settings.log_file
    if log_level is None:
        log_level = settings.log_level

    # Get or create logger
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already initialized
    if name in _initialized_loggers:
        return logger

    # Set log level
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

    # Add console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler
    if file_output:
        # Create log directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Mark as initialized
    _initialized_loggers.add(name)

    return logger


def get_logger(name: str = "crypto_master") -> logging.Logger:
    """Get or create a logger instance.

    If the logger hasn't been initialized yet, it will be set up with
    default settings from the configuration.

    Args:
        name: Logger name. Defaults to "crypto_master".

    Returns:
        logging.Logger: Logger instance.
    """
    if name not in _initialized_loggers:
        return setup_logger(name)
    return logging.getLogger(name)


def reset_loggers() -> None:
    """Reset all initialized loggers.

    Removes all handlers and clears the initialization cache.
    Useful for testing or reconfiguration.
    """
    global _initialized_loggers

    for name in list(_initialized_loggers):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    _initialized_loggers.clear()
