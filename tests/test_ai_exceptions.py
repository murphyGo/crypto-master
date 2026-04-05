"""Tests for Claude AI exceptions.

Tests the exception hierarchy and attributes.
"""

import pytest

from src.ai.exceptions import (
    ClaudeError,
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeParseError,
    ClaudeTimeoutError,
)


class TestClaudeErrorHierarchy:
    """Tests for exception hierarchy."""

    def test_claude_not_found_is_claude_error(self) -> None:
        """Test ClaudeNotFoundError inherits from ClaudeError."""
        assert issubclass(ClaudeNotFoundError, ClaudeError)

    def test_claude_execution_error_is_claude_error(self) -> None:
        """Test ClaudeExecutionError inherits from ClaudeError."""
        assert issubclass(ClaudeExecutionError, ClaudeError)

    def test_claude_timeout_error_is_claude_error(self) -> None:
        """Test ClaudeTimeoutError inherits from ClaudeError."""
        assert issubclass(ClaudeTimeoutError, ClaudeError)

    def test_claude_parse_error_is_claude_error(self) -> None:
        """Test ClaudeParseError inherits from ClaudeError."""
        assert issubclass(ClaudeParseError, ClaudeError)

    def test_catch_all_claude_errors(self) -> None:
        """Test that catching ClaudeError catches all subtypes."""
        errors = [
            ClaudeNotFoundError("not found"),
            ClaudeExecutionError("failed", exit_code=1),
            ClaudeTimeoutError("timeout", timeout_seconds=30.0),
            ClaudeParseError("parse error"),
        ]

        for error in errors:
            with pytest.raises(ClaudeError):
                raise error


class TestClaudeNotFoundError:
    """Tests for ClaudeNotFoundError."""

    def test_message(self) -> None:
        """Test error message is preserved."""
        error = ClaudeNotFoundError("Claude CLI not found")
        assert str(error) == "Claude CLI not found"


class TestClaudeExecutionError:
    """Tests for ClaudeExecutionError."""

    def test_exit_code_attribute(self) -> None:
        """Test exit_code attribute is set."""
        error = ClaudeExecutionError(
            "CLI failed",
            exit_code=1,
            stderr="Error output",
        )
        assert error.exit_code == 1

    def test_stderr_attribute(self) -> None:
        """Test stderr attribute is set."""
        error = ClaudeExecutionError(
            "CLI failed",
            exit_code=1,
            stderr="Error output",
        )
        assert error.stderr == "Error output"

    def test_optional_attributes(self) -> None:
        """Test attributes are optional."""
        error = ClaudeExecutionError("CLI failed")
        assert error.exit_code is None
        assert error.stderr is None

    def test_message(self) -> None:
        """Test error message is preserved."""
        error = ClaudeExecutionError("Custom message", exit_code=2)
        assert str(error) == "Custom message"


class TestClaudeTimeoutError:
    """Tests for ClaudeTimeoutError."""

    def test_timeout_seconds_attribute(self) -> None:
        """Test timeout_seconds attribute is set."""
        error = ClaudeTimeoutError("Timeout exceeded", timeout_seconds=120.0)
        assert error.timeout_seconds == 120.0

    def test_message(self) -> None:
        """Test error message is preserved."""
        error = ClaudeTimeoutError("Took too long", timeout_seconds=60.0)
        assert str(error) == "Took too long"


class TestClaudeParseError:
    """Tests for ClaudeParseError."""

    def test_raw_output_attribute(self) -> None:
        """Test raw_output attribute is set."""
        error = ClaudeParseError("Invalid JSON", raw_output="{invalid}")
        assert error.raw_output == "{invalid}"

    def test_optional_raw_output(self) -> None:
        """Test raw_output is optional."""
        error = ClaudeParseError("Parse failed")
        assert error.raw_output is None

    def test_message(self) -> None:
        """Test error message is preserved."""
        error = ClaudeParseError("Could not parse", raw_output="bad data")
        assert str(error) == "Could not parse"
