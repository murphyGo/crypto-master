"""Tests for Claude CLI wrapper.

Tests the ClaudeCLI class and its async subprocess execution.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.ai import DEFAULT_TIMEOUT_SECONDS
from src.ai.claude import ClaudeCLI
from src.ai.exceptions import (
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeParseError,
    ClaudeTimeoutError,
)


def _make_popen_success(
    stdout: str, stderr: str = "", returncode: int = 0
) -> MagicMock:
    """Build a Popen mock whose ``communicate`` returns ``(stdout, stderr)``.

    Phase 16.1: ``_execute_cli_once`` uses ``subprocess.Popen`` (run
    via ``asyncio.to_thread``) so tests need to mock ``Popen`` rather
    than the old ``asyncio.create_subprocess_exec`` surface.
    """
    proc = MagicMock(spec=subprocess.Popen)
    proc.communicate = MagicMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = MagicMock()
    proc.pid = 12345
    return proc


def _make_popen_timeout() -> MagicMock:
    """Build a Popen mock whose ``communicate`` raises ``TimeoutExpired``.

    The child reaps cleanly on ``proc.wait(timeout=5)``. Use
    :func:`_make_popen_unkillable` for the SIGKILL-fails-too case.
    """
    proc = MagicMock(spec=subprocess.Popen)
    proc.communicate = MagicMock(
        side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=0.1)
    )
    proc.returncode = None
    proc.kill = MagicMock()
    # wait succeeds (child reaped after SIGKILL)
    proc.wait = MagicMock(return_value=0)
    proc.pid = 12345
    return proc


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

    @pytest.mark.asyncio
    async def test_successful_json_response(self) -> None:
        """Test successful analysis with direct JSON response."""
        response = {
            "signal": "long",
            "confidence": 0.85,
            "entry_price": 50000,
            "stop_loss": 49000,
            "take_profit": 52000,
            "reasoning": "Strong uptrend",
        }
        proc = _make_popen_success(json.dumps(response))

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result == response

    @pytest.mark.asyncio
    async def test_json_in_markdown_code_block(self) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        response = {"signal": "short", "confidence": 0.7}
        output = f"Here is the analysis:\n```json\n{json.dumps(response)}\n```"
        proc = _make_popen_success(output)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result["signal"] == "short"
        assert result["confidence"] == 0.7

    @pytest.mark.asyncio
    async def test_json_in_plain_code_block(self) -> None:
        """Test parsing JSON in code block without language specifier."""
        response = {"signal": "neutral", "confidence": 0.5}
        output = f"```\n{json.dumps(response)}\n```"
        proc = _make_popen_success(output)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
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
    async def test_claude_execution_failure(self) -> None:
        """Test ClaudeExecutionError on non-zero exit code."""
        proc = _make_popen_success("", "Error: API limit", returncode=1)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()

                with pytest.raises(ClaudeExecutionError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.exit_code == 1
                assert "API limit" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test ClaudeTimeoutError when process times out (no retry).

        Phase 16.1: ``communicate`` raises ``TimeoutExpired``; the
        wrapper must call ``proc.kill()`` and surface a
        :class:`ClaudeTimeoutError`.
        """
        proc = _make_popen_timeout()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                # Phase 12.3: pin max_retries=0 so this single-attempt
                # test stays single-attempt (the default is 1).
                client = ClaudeCLI(timeout=0.1, max_retries=0)

                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.timeout_seconds == 0.1
                proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        """Test ClaudeParseError on empty response."""
        proc = _make_popen_success("")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_response(self) -> None:
        """Test ClaudeParseError on whitespace-only response."""
        proc = _make_popen_success("   \n\t\n  ")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_json(self) -> None:
        """Test ClaudeParseError on malformed JSON."""
        proc = _make_popen_success("{invalid json")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert exc_info.value.raw_output == "{invalid json"

    @pytest.mark.asyncio
    async def test_non_dict_json(self) -> None:
        """Test ClaudeParseError when JSON is not an object."""
        proc = _make_popen_success('["array", "not", "dict"]')

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()

                with pytest.raises(ClaudeParseError) as exc_info:
                    await client.analyze("test prompt")

                assert "Expected JSON object" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unicode_handling(self) -> None:
        """Test proper handling of unicode characters."""
        response = {
            "signal": "long",
            "confidence": 0.8,
            "reasoning": "Strong trend 📈",
        }
        proc = _make_popen_success(json.dumps(response))

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI()
                result = await client.analyze("test prompt")

        assert result["reasoning"] == "Strong trend 📈"


class TestClaudeCLIRetryOnTimeout:
    """Phase 12.3: retry-on-timeout with 1.5x backoff.

    Phase 16.1 rewired this onto :class:`subprocess.Popen`-shaped
    mocks (the implementation now uses blocking ``Popen`` via
    :func:`asyncio.to_thread`). Behaviour under test is unchanged —
    only the mock surface moved.
    """

    def _make_slow_process(self) -> MagicMock:
        """Popen mock whose ``communicate`` raises ``TimeoutExpired``."""
        return _make_popen_timeout()

    def _make_success_process(self, payload: dict[str, object]) -> MagicMock:
        """Popen mock whose ``communicate`` returns ``payload`` as JSON."""
        return _make_popen_success(json.dumps(payload))

    @pytest.mark.asyncio
    async def test_subprocess_retries_on_timeout(self) -> None:
        """Timeout twice, succeed on third attempt — return result, call count = 3."""
        slow1 = self._make_slow_process()
        slow2 = self._make_slow_process()
        success_payload = {"signal": "long", "confidence": 0.8}
        success = self._make_success_process(success_payload)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                side_effect=[slow1, slow2, success],
            ) as mock_popen:
                client = ClaudeCLI(timeout=0.05, max_retries=2)
                result = await client.analyze("test")

        assert result == success_payload
        assert mock_popen.call_count == 3

    @pytest.mark.asyncio
    async def test_subprocess_raises_after_max_retries(self) -> None:
        """Always-timeout: ClaudeTimeoutError after max_retries+1 calls."""
        processes = [self._make_slow_process() for _ in range(3)]

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                side_effect=processes,
            ) as mock_popen:
                client = ClaudeCLI(timeout=0.05, max_retries=2)

                with pytest.raises(ClaudeTimeoutError):
                    await client.analyze("test")

        assert mock_popen.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_escalates_each_retry(self) -> None:
        """The per-attempt timeout multiplies by 1.5x each retry.

        Phase 16.1: capture the ``timeout`` kwarg passed to
        ``proc.communicate``, since the wrapper now drives the
        timeout there (instead of via ``asyncio.wait_for``).
        """
        captured_timeouts: list[float] = []

        def make_capturing_proc() -> MagicMock:
            proc = MagicMock(spec=subprocess.Popen)

            def capture_communicate(timeout: float) -> tuple[str, str]:
                captured_timeouts.append(timeout)
                raise subprocess.TimeoutExpired(cmd=["claude"], timeout=timeout)

            proc.communicate = MagicMock(side_effect=capture_communicate)
            proc.returncode = None
            proc.kill = MagicMock()
            proc.wait = MagicMock(return_value=0)
            proc.pid = 12345
            return proc

        processes = [make_capturing_proc() for _ in range(3)]

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                side_effect=processes,
            ):
                client = ClaudeCLI(timeout=0.04, max_retries=2)
                with pytest.raises(ClaudeTimeoutError):
                    await client.analyze("test")

        assert len(captured_timeouts) == 3
        # 0.04 -> 0.06 -> 0.09 (1.5x backoff)
        assert captured_timeouts[0] == pytest.approx(0.04)
        assert captured_timeouts[1] == pytest.approx(0.06)
        assert captured_timeouts[2] == pytest.approx(0.09)

    @pytest.mark.asyncio
    async def test_max_retries_zero_means_no_retry(self) -> None:
        """max_retries=0 -> exactly one subprocess call, then ClaudeTimeoutError."""
        slow = self._make_slow_process()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                return_value=slow,
            ) as mock_popen:
                client = ClaudeCLI(timeout=0.05, max_retries=0)

                with pytest.raises(ClaudeTimeoutError):
                    await client.analyze("test")

        assert mock_popen.call_count == 1

    @pytest.mark.asyncio
    async def test_non_timeout_errors_do_not_trigger_retry(self) -> None:
        """ClaudeExecutionError must NOT be retried — bail immediately."""
        proc = _make_popen_success("", "server error", returncode=1)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                return_value=proc,
            ) as mock_popen:
                client = ClaudeCLI(timeout=0.05, max_retries=2)

                with pytest.raises(ClaudeExecutionError):
                    await client.analyze("test")

        # No retry — execution errors are not transient.
        assert mock_popen.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_error_carries_final_timeout(self) -> None:
        """The raised ClaudeTimeoutError reports the final escalated timeout."""
        processes = [self._make_slow_process() for _ in range(2)]

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                side_effect=processes,
            ):
                client = ClaudeCLI(timeout=0.04, max_retries=1)
                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test")

        # Final attempt used 0.04 * 1.5 = 0.06s.
        assert exc_info.value.timeout_seconds == pytest.approx(0.06)

    @pytest.mark.asyncio
    async def test_timeout_error_carries_final_attempt_number(self) -> None:
        """Phase 14.1: ``attempt_number`` reports the final 1-indexed attempt.

        With ``max_retries=2`` (3 total attempts) and every attempt
        timing out, the raised error must carry ``attempt_number=3``
        — the final attempt's index. This is what the proposal engine
        forwards into ``LLM_TIMEOUT.details.attempt_number`` so
        operators can see "every retry exhausted" vs "first attempt
        failed and no retry path".
        """
        processes = [self._make_slow_process() for _ in range(3)]

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                side_effect=processes,
            ):
                client = ClaudeCLI(timeout=0.04, max_retries=2)
                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test")

        assert exc_info.value.attempt_number == 3

    @pytest.mark.asyncio
    async def test_timeout_error_attempt_number_is_one_with_no_retry(self) -> None:
        """Phase 14.1: ``max_retries=0`` -> ``attempt_number=1`` on raise."""
        slow = self._make_slow_process()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "subprocess.Popen",
                return_value=slow,
            ):
                client = ClaudeCLI(timeout=0.04, max_retries=0)
                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test")

        assert exc_info.value.attempt_number == 1


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


class TestBalancedBraceExtraction:
    """Tests for the balanced-brace `{...}` fallback extractor.

    This is the path Claude Code's `claude -p` typically lands on:
    no code fence, JSON embedded in conversational prose.
    """

    def test_returns_none_when_no_brace(self) -> None:
        assert ClaudeCLI._extract_balanced_json_object("just words") is None

    def test_finds_simple_object(self) -> None:
        text = '{"signal": "long"}'
        assert ClaudeCLI._extract_balanced_json_object(text) == text

    def test_strips_leading_prose(self) -> None:
        text = (
            "Looking at this BTC chart, here is my analysis: "
            '{"signal": "long", "confidence": 0.9}'
        )
        extracted = ClaudeCLI._extract_balanced_json_object(text)
        assert extracted == '{"signal": "long", "confidence": 0.9}'

    def test_strips_trailing_prose(self) -> None:
        text = (
            '{"signal": "short", "confidence": 0.7} ' "I think this is a strong setup."
        )
        extracted = ClaudeCLI._extract_balanced_json_object(text)
        assert extracted == '{"signal": "short", "confidence": 0.7}'

    def test_handles_nested_objects(self) -> None:
        text = (
            "Here you go: "
            '{"signal": "long", "score": {"composite": 1.5, "confidence": 0.8}}'
        )
        extracted = ClaudeCLI._extract_balanced_json_object(text)
        assert extracted is not None
        parsed = json.loads(extracted)
        assert parsed["score"]["composite"] == 1.5

    def test_braces_inside_strings_dont_break_depth(self) -> None:
        """`{` inside a string literal must not be treated as a real open."""
        text = '{"reasoning": "{not a real brace}", "signal": "long"}'
        extracted = ClaudeCLI._extract_balanced_json_object(text)
        assert extracted == text

    def test_escaped_quotes_in_strings(self) -> None:
        """Escaped `\\"` inside a string must not flip the in-string flag."""
        text = '{"reasoning": "He said \\"hi\\"", "signal": "long"}'
        extracted = ClaudeCLI._extract_balanced_json_object(text)
        assert extracted is not None
        parsed = json.loads(extracted)
        assert parsed["reasoning"] == 'He said "hi"'


class TestParseResponseRobustness:
    """End-to-end tests of `_parse_response` across the response shapes
    Claude Code is known to produce."""

    def test_parses_prose_with_embedded_json(self) -> None:
        client = ClaudeCLI()
        raw = (
            "Looking at this BTC chart, here is my decision:\n\n"
            '{"signal": "long", "confidence": 0.85, "reasoning": "Strong trend"}\n\n'
            "I'm recommending an entry near current price."
        )
        result = client._parse_response(raw)
        assert result["signal"] == "long"
        assert result["confidence"] == 0.85

    def test_parses_fenced_block_when_both_present(self) -> None:
        """Code fence wins over the balanced-brace fallback."""
        client = ClaudeCLI()
        raw = (
            "Some prose with a tangent: {wrong: data}\n"
            "```json\n"
            '{"signal": "short", "confidence": 0.6}\n'
            "```\n"
        )
        result = client._parse_response(raw)
        assert result["signal"] == "short"

    def test_logs_raw_output_when_unparseable(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Parse failure should surface the raw response in the log.

        The project's ``get_logger`` sets ``propagate = False`` so the
        default caplog handler (attached to root) doesn't see these
        records — wire ``caplog.handler`` onto the named logger for
        the duration of the test.
        """
        import logging

        client = ClaudeCLI()
        raw = "I can't help with that. (no JSON anywhere.)"
        target_logger = logging.getLogger("crypto_master.ai.claude")
        target_logger.addHandler(caplog.handler)
        target_logger.setLevel(logging.WARNING)
        try:
            with pytest.raises(ClaudeParseError):
                client._parse_response(raw)
        finally:
            target_logger.removeHandler(caplog.handler)
        # ``record.message`` is pre-format; ``getMessage()`` resolves
        # the %s args we passed to ``logger.warning``.
        assert any(
            "I can't help with that" in record.getMessage() for record in caplog.records
        )


class TestParseResponseNestedTradeForm:
    """Phase 16.1: parser must accept the chasulang nested-``trade`` shape.

    The chasulang_ict_smc.md template returns a top-level dict whose
    actionable trade is nested under ``trade``, alongside structural
    analysis frames (``external_structure``, ``liquidity_map``, etc.).
    The parser promotes ``trade.*`` to top level so the downstream
    ``StrategyTechnique.analyze`` consumer in ``src/strategy/loader.py``
    sees a single canonical shape.
    """

    def test_parse_response_handles_nested_trade_form(self) -> None:
        """Chasulang shape: signal/entry/SL/TP nested under ``trade``."""
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "external_structure": {
                    "timeframe": "4h",
                    "bias": "bullish",
                    "reference_price": 95.0,
                },
                "liquidity_map": {"primary_target": 110.0},
                "order_blocks": [{"type": "bullish_ob", "timeframe": "1h"}],
                "trade": {
                    "signal": "long",
                    "entry_price": 100,
                    "stop_loss": 95,
                    "take_profit_1": 105,
                    "confidence": 0.8,
                    "reasoning": "structure + liquidity + MSS aligned",
                },
            }
        )

        result = client._parse_response(raw)

        # Promoted to top-level for downstream consumer.
        assert result["signal"] == "long"
        assert result["entry_price"] == 100
        assert result["stop_loss"] == 95
        assert result["take_profit"] == 105
        assert result["confidence"] == 0.8
        assert result["reasoning"] == "structure + liquidity + MSS aligned"
        # Original nested ``trade`` block remains intact for callers
        # that want the full view (e.g. ``take_profit_2``).
        assert result["trade"]["take_profit_1"] == 105

    def test_parse_response_handles_top_level_form(self) -> None:
        """Legacy flat shape (sample_prompt.md) parses unchanged."""
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "signal": "short",
                "entry_price": 50000,
                "stop_loss": 51000,
                "take_profit": 48000,
                "confidence": 0.65,
                "reasoning": "bearish breakdown",
            }
        )

        result = client._parse_response(raw)

        assert result["signal"] == "short"
        assert result["entry_price"] == 50000
        assert result["stop_loss"] == 51000
        assert result["take_profit"] == 48000
        assert result["confidence"] == 0.65
        assert result["reasoning"] == "bearish breakdown"

    def test_parse_response_picks_take_profit_1_when_tp2_present(self) -> None:
        """When nested form has TP1 + TP2, pick TP1 (closer, conservative)."""
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "trade": {
                    "signal": "long",
                    "entry_price": 100,
                    "stop_loss": 95,
                    "take_profit_1": 105,
                    "take_profit_2": 115,
                    "confidence": 0.7,
                    "reasoning": "two-step target",
                },
            }
        )

        result = client._parse_response(raw)

        # TP1 wins; TP2 is the stretch target and is dropped from the
        # canonical top-level view (callers can still read it from
        # ``result["trade"]["take_profit_2"]`` if needed).
        assert result["take_profit"] == 105

    def test_parse_response_explicit_take_profit_beats_tp1(self) -> None:
        """Explicit nested ``trade.take_profit`` wins over ``take_profit_1``.

        Defensive: if a future template carries both an explicit
        ``take_profit`` and a ``take_profit_1``, the explicit value
        is the source of truth.
        """
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "trade": {
                    "signal": "long",
                    "entry_price": 100,
                    "stop_loss": 95,
                    "take_profit": 110,
                    "take_profit_1": 105,
                    "confidence": 0.7,
                    "reasoning": "explicit tp wins",
                },
            }
        )

        result = client._parse_response(raw)

        assert result["take_profit"] == 110

    def test_parse_response_raises_clear_error_when_neither_has_signal(
        self,
    ) -> None:
        """Missing signal in both top-level and ``trade``: error names both paths."""
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "external_structure": {"bias": "ranging"},
                "trade": {
                    # No 'signal' key.
                    "confidence": 0.2,
                    "reasoning": "no setup",
                },
            }
        )

        with pytest.raises(ClaudeParseError) as exc_info:
            client._parse_response(raw)

        msg = str(exc_info.value)
        # Both candidate paths must be referenced so operators can
        # quickly identify which template needs a signal field.
        assert "'signal'" in msg
        assert "trade.signal" in msg

    def test_parse_response_top_level_signal_wins_when_trade_lacks_one(
        self,
    ) -> None:
        """If top-level has ``signal`` but ``trade`` doesn't, top-level wins.

        Back-compat insurance: a template could legitimately mix in
        a ``trade`` sub-dict (e.g. for trade-detail metadata) while
        the canonical signal stays at top level. We must not lose the
        top-level value.
        """
        client = ClaudeCLI()
        raw = json.dumps(
            {
                "signal": "neutral",
                "entry_price": 100,
                "stop_loss": 95,
                "take_profit": 105,
                "confidence": 0.4,
                "reasoning": "wait",
                "trade": {
                    # Trade block carries metadata, not the signal.
                    "notes": "see top-level signal",
                },
            }
        )

        result = client._parse_response(raw)

        assert result["signal"] == "neutral"
        assert result["take_profit"] == 105


class TestSubprocessKillOnTimeout:
    """Phase 16.1: explicit ``proc.kill()`` on timeout.

    The pre-Phase-16.1 wrapper used
    ``asyncio.create_subprocess_exec`` + ``asyncio.wait_for`` which
    was observed in prod (2026-04-28T15:02:15Z chasulang retry) to
    leave the child alive even after the wrapper raised, wedging the
    engine for 12+ hours. The new implementation uses blocking
    ``Popen`` via ``asyncio.to_thread`` so we get a real SIGKILL on
    timeout.
    """

    @pytest.mark.asyncio
    async def test_subprocess_kill_on_timeout(self) -> None:
        """``communicate`` raises TimeoutExpired -> ``proc.kill()`` is called.

        Verifies the wrapper:
        1. Calls ``proc.kill()`` exactly once on timeout.
        2. Calls ``proc.wait(timeout=5)`` to reap the child.
        3. Raises :class:`ClaudeTimeoutError` with the right
           ``timeout_seconds`` and ``attempt_number`` (Phase 14.1
           propagation must keep working).
        4. Returns within bounded wall-clock time — the assertion
           uses pytest's default test-timeout handling but the test
           itself never sleeps.
        """
        proc = MagicMock(spec=subprocess.Popen)
        proc.communicate = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=0.05)
        )
        proc.returncode = None
        proc.kill = MagicMock()
        # ``wait(timeout=5)`` succeeds — child reaped cleanly after
        # SIGKILL. The ``test_subprocess_kill_failed_on_timeout`` test
        # below covers the harder case where SIGKILL itself doesn't
        # work.
        proc.wait = MagicMock(return_value=0)
        proc.pid = 99999

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI(timeout=0.05, max_retries=0)
                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test")

        # 1. kill() called exactly once.
        proc.kill.assert_called_once()
        # 2. wait() called with the bounded 5s reap timeout.
        proc.wait.assert_called_once_with(timeout=5)
        # 3. Error carries the right metadata for the retry path.
        assert exc_info.value.timeout_seconds == 0.05
        assert exc_info.value.attempt_number == 1

    @pytest.mark.asyncio
    async def test_subprocess_kill_failed_on_timeout(self) -> None:
        """Even SIGKILL hanging surfaces a distinct ``ClaudeTimeoutError``.

        If ``proc.wait(timeout=5)`` itself raises ``TimeoutExpired``,
        the child didn't respond to SIGKILL — likely a zombie or
        stuck-in-kernel process. Surface it with a distinct message
        so operators can spot the difference in the activity log,
        but keep the same exception type so the proposal engine's
        ``except StrategyError`` path still treats it as a clean
        per-strategy skip.
        """
        proc = MagicMock(spec=subprocess.Popen)
        proc.communicate = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=0.05)
        )
        proc.returncode = None
        proc.kill = MagicMock()
        # SIGKILL fails to reap within 5s.
        proc.wait = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=5)
        )
        proc.pid = 99999

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.Popen", return_value=proc):
                client = ClaudeCLI(timeout=0.05, max_retries=0)
                with pytest.raises(ClaudeTimeoutError) as exc_info:
                    await client.analyze("test")

        proc.kill.assert_called_once()
        # The error message differentiates SIGKILL-failed from a
        # normal timeout.
        assert "SIGKILL" in str(exc_info.value)
        assert exc_info.value.timeout_seconds == 0.05
        assert exc_info.value.attempt_number == 1
