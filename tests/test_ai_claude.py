"""Tests for Claude CLI wrapper.

Tests the ClaudeCLI class and its async subprocess execution.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai import DEFAULT_TIMEOUT_SECONDS
from src.ai.claude import ClaudeCLI
from src.ai.exceptions import (
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeParseError,
    ClaudeTimeoutError,
)


class TestClaudeCLIInit:
    """Tests for ClaudeCLI initialization."""

    def test_default_timeout(self) -> None:
        """Test default timeout is set."""
        client = ClaudeCLI()
        assert client.timeout == DEFAULT_TIMEOUT_SECONDS

    def test_custom_timeout(self) -> None:
        """Test custom timeout is applied."""
        client = ClaudeCLI(timeout=60.0)
        assert client.timeout == 60.0

    def test_default_claude_path(self) -> None:
        """Test default claude path is 'claude'."""
        client = ClaudeCLI()
        assert client.claude_path == "claude"

    def test_custom_claude_path(self) -> None:
        """Test custom claude path is applied."""
        client = ClaudeCLI(claude_path="/usr/local/bin/claude")
        assert client.claude_path == "/usr/local/bin/claude"


class TestClaudeCLIIsAvailable:
    """Tests for is_available method."""

    def test_available_when_in_path(self) -> None:
        """Test returns True when claude is in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            client = ClaudeCLI()
            assert client.is_available() is True

    def test_not_available_when_not_in_path(self) -> None:
        """Test returns False when claude is not in PATH."""
        with patch("shutil.which", return_value=None):
            client = ClaudeCLI()
            assert client.is_available() is False


class TestClaudeCLIAnalyze:
    """Tests for analyze method."""

    @pytest.fixture
    def mock_process(self) -> AsyncMock:
        """Create a mock subprocess."""
        process = AsyncMock()
        process.returncode = 0
        return process

    @pytest.mark.asyncio
    async def test_successful_json_response(self, mock_process: AsyncMock) -> None:
        """Test successful analysis with direct JSON response."""
        response = {
            "signal": "long",
            "confidence": 0.85,
            "entry_price": 50000,
            "stop_loss": 49000,
            "take_profit": 52000,
            "reasoning": "Strong uptrend",
        }
        mock_process.communicate.return_value = (
            json.dumps(response).encode(),
            b"",
        )

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result == response

    @pytest.mark.asyncio
    async def test_json_in_markdown_code_block(
        self, mock_process: AsyncMock
    ) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        response = {"signal": "short", "confidence": 0.7}
        output = f"Here is the analysis:\n```json\n{json.dumps(response)}\n```"
        mock_process.communicate.return_value = (output.encode(), b"")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result["signal"] == "short"
        assert result["confidence"] == 0.7

    @pytest.mark.asyncio
    async def test_json_in_plain_code_block(
        self, mock_process: AsyncMock
    ) -> None:
        """Test parsing JSON in code block without language specifier."""
        response = {"signal": "neutral", "confidence": 0.5}
        output = f"```\n{json.dumps(response)}\n```"
        mock_process.communicate.return_value = (output.encode(), b"")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result["signal"] == "neutral"

    @pytest.mark.asyncio
    async def test_claude_not_found(self) -> None:
        """Test ClaudeNotFoundError when CLI not in PATH."""
        with patch("shutil.which", return_value=None):
            client = ClaudeCLI()

            with pytest.raises(ClaudeNotFoundError) as exc_info:
                await client.analyze("test prompt")

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_claude_execution_failure(
        self, mock_process: AsyncMock
    ) -> None:
        """Test ClaudeExecutionError on non-zero exit code."""
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error: API limit")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()

                with pytest.raises(ClaudeExecutionError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.exit_code == 1
                assert "API limit" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test ClaudeTimeoutError when process times out."""

        async def slow_communicate() -> tuple[bytes, bytes]:
            await asyncio.sleep(10)
            return (b"", b"")

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.communicate = slow_communicate
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI(timeout=0.1)

                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.timeout_seconds == 0.1
                mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_process: AsyncMock) -> None:
        """Test ClaudeParseError on empty response."""
        mock_process.communicate.return_value = (b"", b"")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_response(
        self, mock_process: AsyncMock
    ) -> None:
        """Test ClaudeParseError on whitespace-only response."""
        mock_process.communicate.return_value = (b"   \n\t\n  ", b"")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_json(self, mock_process: AsyncMock) -> None:
        """Test ClaudeParseError on malformed JSON."""
        mock_process.communicate.return_value = (b"{invalid json", b"")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.raw_output == "{invalid json"

    @pytest.mark.asyncio
    async def test_non_dict_json(self, mock_process: AsyncMock) -> None:
        """Test ClaudeParseError when JSON is not an object."""
        mock_process.communicate.return_value = (
            b'["array", "not", "dict"]',
            b"",
        )

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "Expected JSON object" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unicode_handling(self, mock_process: AsyncMock) -> None:
        """Test proper handling of unicode characters."""
        response = {
            "signal": "long",
            "confidence": 0.8,
            "reasoning": "Strong trend 📈",
        }
        mock_process.communicate.return_value = (
            json.dumps(response).encode("utf-8"),
            b"",
        )

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result["reasoning"] == "Strong trend 📈"


class TestJSONExtraction:
    """Tests for JSON extraction from markdown."""

    def test_extract_from_json_block(self) -> None:
        """Test extraction from ```json block."""
        client = ClaudeCLI()
        text = '```json\n{"key": "value"}\n```'
        result = client._extract_json_from_markdown(text)
        assert result == '{"key": "value"}'

    def test_extract_from_plain_block(self) -> None:
        """Test extraction from ``` block."""
        client = ClaudeCLI()
        text = '```\n{"key": "value"}\n```'
        result = client._extract_json_from_markdown(text)
        assert result == '{"key": "value"}'

    def test_no_code_block(self) -> None:
        """Test returns None when no code block present."""
        client = ClaudeCLI()
        text = '{"key": "value"}'
        result = client._extract_json_from_markdown(text)
        assert result is None

    def test_first_block_used(self) -> None:
        """Test uses first code block when multiple present."""
        client = ClaudeCLI()
        text = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = client._extract_json_from_markdown(text)
        assert '"first"' in result

    def test_block_with_surrounding_text(self) -> None:
        """Test extraction with surrounding text."""
        client = ClaudeCLI()
        text = """
Here is my analysis:

```json
{"signal": "long", "confidence": 0.9}
```

This is based on strong momentum.
"""
        result = client._extract_json_from_markdown(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["signal"] == "long"

    def test_block_with_json_uppercase(self) -> None:
        """Test extraction with JSON uppercase."""
        client = ClaudeCLI()
        text = '```JSON\n{"key": "value"}\n```'
        result = client._extract_json_from_markdown(text)
        assert result == '{"key": "value"}'

    def test_multiline_json_in_block(self) -> None:
        """Test extraction of multiline JSON."""
        client = ClaudeCLI()
        text = """```json
{
  "signal": "long",
  "confidence": 0.85,
  "reasoning": "Multiple indicators align"
}
```"""
        result = client._extract_json_from_markdown(text)
        parsed = json.loads(result)
        assert parsed["signal"] == "long"
        assert parsed["confidence"] == 0.85
