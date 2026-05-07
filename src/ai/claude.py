"""Claude CLI wrapper for Crypto Master.

Provides async interface to Claude via CLI.

Related Requirements:
- NFR-002: Claude CLI Integration
- FR-001: Bitcoin Chart Analysis
- FR-002: Altcoin Chart Analysis
"""

import asyncio
import json
import re
import shutil
import subprocess
from typing import Any

from src.ai.exceptions import (
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeParseError,
    ClaudeTimeoutError,
)
from src.logger import get_logger

# Default timeout for Claude CLI execution (2 minutes)
DEFAULT_TIMEOUT_SECONDS = 120.0

# Phase 12.3: Default number of retries on subprocess timeout. ``0``
# means no retry (single-shot timeout). Each retry multiplies the
# timeout by :data:`TIMEOUT_BACKOFF_MULTIPLIER`.
DEFAULT_MAX_RETRIES = 1

# Multiplier applied to the timeout on each retry attempt. With the
# default 120s base and 1 retry, the schedule is 120s → 180s. With 2
# retries it is 120s → 180s → 270s.
TIMEOUT_BACKOFF_MULTIPLIER = 1.5

# Pattern to extract JSON from markdown code blocks
JSON_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


class ClaudeCLI:
    """Async wrapper for Claude CLI.

    Executes Claude via `claude -p "..."` command and parses JSON responses.

    Related Requirements:
    - NFR-002: Claude CLI Integration

    Usage:
        client = ClaudeCLI()
        result = await client.analyze(prompt)
        print(result["signal"])

    Attributes:
        timeout: Timeout in seconds for CLI execution.
        claude_path: Path to claude executable (or 'claude' for PATH lookup).
    """

    def __init__(
        self,
        timeout: float | None = None,
        claude_path: str = "claude",
        max_retries: int | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize ClaudeCLI.

        Args:
            timeout: Base timeout in seconds for one CLI invocation.
                When ``None`` (default), reads from
                ``Settings.claude_cli_timeout_seconds`` so operators can
                tune via env without redeploy. Tests can pin a value
                explicitly to keep them fast.
            claude_path: Path to claude executable or command name.
            max_retries: Maximum number of retries on
                :class:`asyncio.TimeoutError`. ``0`` means no retry
                (single-shot timeout). Each retry multiplies the
                timeout by ``TIMEOUT_BACKOFF_MULTIPLIER`` (1.5x). When
                ``None`` (default), reads from
                ``Settings.claude_cli_max_retries``.
            model: Optional Claude model alias or full name to pass via
                ``--model``. ``None`` reads
                ``Settings.claude_cli_model``; empty string preserves
                Claude CLI's configured default.
        """
        # Resolve defaults from Settings lazily so import-time env
        # changes are honoured. Explicit args win for tests.
        if timeout is None or max_retries is None:
            from src.config import get_settings

            settings = get_settings()
            if timeout is None:
                timeout = float(settings.claude_cli_timeout_seconds)
            if max_retries is None:
                max_retries = settings.claude_cli_max_retries
            if model is None:
                model = settings.claude_cli_model

        self.timeout = timeout
        self.claude_path = claude_path
        self.max_retries = max_retries
        self.model = (model or "").strip()
        self._logger = get_logger("crypto_master.ai.claude")

    def is_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if claude command is found in PATH.
        """
        return shutil.which(self.claude_path) is not None

    async def analyze(self, prompt: str) -> dict[str, Any]:
        """Execute Claude CLI with prompt and parse JSON response.

        Args:
            prompt: The formatted prompt to send to Claude.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            ClaudeNotFoundError: If claude CLI is not found.
            ClaudeTimeoutError: If execution exceeds timeout.
            ClaudeExecutionError: If CLI returns non-zero exit code.
            ClaudeParseError: If response cannot be parsed as JSON.
        """
        # Validate Claude CLI availability
        if not self.is_available():
            raise ClaudeNotFoundError(
                f"Claude CLI not found: '{self.claude_path}'. "
                "Ensure Claude CLI is installed and in PATH."
            )

        self._logger.debug(f"Executing Claude CLI (timeout={self.timeout}s)")

        # Execute Claude CLI
        stdout, stderr = await self._execute_cli(prompt)

        # Parse and return JSON
        return self._parse_response(stdout)

    async def complete(self, prompt: str) -> str:
        """Execute Claude CLI with prompt and return raw stdout text.

        Use this when the caller expects free-form text (e.g. a
        generated markdown file) rather than a JSON payload. For
        JSON-shaped responses, prefer :meth:`analyze`.

        Args:
            prompt: The prompt to send to Claude.

        Returns:
            The raw stdout text from the CLI, stripped of leading and
            trailing whitespace.

        Raises:
            ClaudeNotFoundError: If claude CLI is not found.
            ClaudeTimeoutError: If execution exceeds timeout.
            ClaudeExecutionError: If CLI returns non-zero exit code.
            ClaudeParseError: If Claude returned no output.
        """
        if not self.is_available():
            raise ClaudeNotFoundError(
                f"Claude CLI not found: '{self.claude_path}'. "
                "Ensure Claude CLI is installed and in PATH."
            )

        self._logger.debug(
            f"Executing Claude CLI for completion (timeout={self.timeout}s)"
        )
        stdout, _ = await self._execute_cli(prompt)
        text = stdout.strip()
        if not text:
            raise ClaudeParseError(
                "Claude returned empty response",
                raw_output=stdout,
            )
        return text

    async def _execute_cli(self, prompt: str) -> tuple[str, str]:
        """Execute claude -p command with retry-on-timeout (Phase 12.3).

        On :class:`asyncio.TimeoutError` the wrapper retries up to
        ``self.max_retries`` times, multiplying the per-attempt
        timeout by :data:`TIMEOUT_BACKOFF_MULTIPLIER` (1.5x) each
        retry — e.g. with ``timeout=120`` and ``max_retries=2`` the
        schedule is 120s → 180s → 270s. Only timeouts trigger a
        retry; ``ClaudeExecutionError`` (non-zero exit) and
        ``ClaudeNotFoundError`` raise immediately so genuine failures
        surface fast.

        Args:
            prompt: The prompt text to pass to Claude.

        Returns:
            Tuple of (stdout, stderr) from the process.

        Raises:
            ClaudeNotFoundError: If claude executable not found.
            ClaudeTimeoutError: If every attempt times out.
            ClaudeExecutionError: If CLI returns non-zero exit code.
        """
        timeout = self.timeout
        total_attempts = self.max_retries + 1
        for attempt in range(total_attempts):
            try:
                return await self._execute_cli_once(
                    prompt, timeout=timeout, attempt_number=attempt + 1
                )
            except ClaudeTimeoutError:
                if attempt < self.max_retries:
                    next_timeout = timeout * TIMEOUT_BACKOFF_MULTIPLIER
                    self._logger.warning(
                        f"Claude CLI timeout (attempt {attempt + 1}/"
                        f"{total_attempts}, timeout={timeout}s); retrying "
                        f"with timeout={next_timeout}s"
                    )
                    timeout = next_timeout
                    continue
                # Final attempt: re-raise so the caller sees the
                # ClaudeTimeoutError. The exception already carries the
                # final attempt number from ``_execute_cli_once``.
                raise
        # Unreachable — the loop either returns or raises.
        raise RuntimeError("unreachable: retry loop exited without resolution")

    async def _execute_cli_once(
        self, prompt: str, *, timeout: float, attempt_number: int = 1
    ) -> tuple[str, str]:
        """Run one ``claude -p`` invocation with the supplied timeout.

        Split out from :meth:`_execute_cli` (Phase 12.3) so the retry
        loop can call it with an escalating timeout per attempt
        without re-implementing subprocess teardown for each.

        Phase 16.1: rebuilt on top of the blocking
        :class:`subprocess.Popen` API (run via :func:`asyncio.to_thread`
        so we don't block the event loop). The previous
        :func:`asyncio.create_subprocess_exec` + :func:`asyncio.wait_for`
        path was observed to wedge in prod — on
        ``2026-04-28T15:02:15Z`` a chasulang retry timed out at 360s
        and the engine sat silent for 12+ hours, suggesting the child
        wasn't actually killed when the wrapper raised. With explicit
        ``Popen`` + ``proc.kill()`` + ``proc.wait(timeout=5)`` we get
        a hard SIGKILL on timeout and a separate error if even SIGKILL
        fails to reap the child.

        Args:
            prompt: The prompt text to pass to Claude.
            timeout: Per-attempt timeout in seconds.
            attempt_number: 1-indexed attempt number — Phase 14.1.
                Stamped onto any raised :class:`ClaudeTimeoutError` so
                the proposal engine can surface it in the
                ``LLM_TIMEOUT`` activity event for retry-path
                verification.

        Returns:
            Tuple of (stdout, stderr) from the process.

        Raises:
            ClaudeNotFoundError: If claude executable not found.
            ClaudeTimeoutError: If this single attempt times out (or if
                even SIGKILL fails to reap the child within 5s).
            ClaudeExecutionError: If CLI returns non-zero exit code.
        """

        def _run_blocking() -> tuple[str, str, int]:
            """Spawn Claude, communicate with timeout, hard-kill on hang.

            Returns ``(stdout, stderr, returncode)``. Raises
            :class:`ClaudeTimeoutError` directly so the caller doesn't
            need to translate :class:`subprocess.TimeoutExpired`
            (which would lose the kill-failed vs kill-succeeded
            distinction). Re-raises :class:`FileNotFoundError`
            unchanged for the caller to convert.
            """
            cmd = [self.claude_path]
            if self.model:
                cmd.extend(["--model", self.model])
            cmd.extend(["-p", prompt])
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as timeout_exc:
                # Hard SIGKILL — Phase 16.1: prior soft-terminate path
                # was observed to leave the child alive and the engine
                # wedged. Force-kill, then bounded-wait for reap.
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired as kill_failed:
                    # Even SIGKILL didn't reap the child within 5s —
                    # this is a different failure mode than a normal
                    # timeout (likely zombie / kernel-stuck process).
                    # Surface as a ClaudeTimeoutError but with a
                    # distinct message so operators can tell them
                    # apart in logs.
                    raise ClaudeTimeoutError(
                        f"Claude CLI timed out after {timeout}s and "
                        f"did not respond to SIGKILL within 5s "
                        f"(pid={proc.pid})",
                        timeout_seconds=timeout,
                        attempt_number=attempt_number,
                    ) from kill_failed
                raise ClaudeTimeoutError(
                    f"Claude CLI timed out after {timeout} seconds",
                    timeout_seconds=timeout,
                    attempt_number=attempt_number,
                ) from timeout_exc
            return stdout, stderr, proc.returncode

        try:
            stdout, stderr, returncode = await asyncio.to_thread(_run_blocking)
        except FileNotFoundError as e:
            raise ClaudeNotFoundError(
                f"Claude CLI not found: '{self.claude_path}'"
            ) from e

        # Check exit code
        if returncode != 0:
            self._logger.error(
                f"Claude CLI failed with exit code {returncode}: {stderr}"
            )
            raise ClaudeExecutionError(
                f"Claude CLI failed with exit code {returncode}",
                exit_code=returncode,
                stderr=stderr,
            )

        self._logger.debug("Claude CLI completed successfully")
        return stdout, stderr

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        """Parse Claude response to extract JSON.

        Tries three strategies in order:
        1. JSON inside a ```json``` / ``` markdown fence.
        2. Balanced-brace `{...}` substring anywhere in the output —
           covers the common case where Claude prefixes the JSON with
           prose ("Looking at this chart, here's my decision: {...}")
           or appends commentary after it.
        3. The raw output as-is (back-compat for prompts that already
           guarantee a clean JSON-only reply).

        Phase 16.1: once the JSON is extracted, normalize the trade
        fields. Some prompts (chasulang_ict_smc.md) nest the trade
        decision under a ``trade`` sub-dict alongside structural
        analysis frames (``external_structure``, ``liquidity_map``,
        etc.). Other prompts (sample_prompt.md, simple_trend_analysis)
        use a flat top-level shape. We promote ``trade.*`` keys to
        the top level so downstream code (``StrategyTechnique`` /
        ``AnalysisResult`` construction in ``src/strategy/loader.py``)
        sees a single canonical shape regardless of template.

        On total failure, the raw response is logged at WARNING (truncated
        to 1000 chars) so operators can see *what* Claude actually said
        without re-running the cycle.

        Args:
            raw_output: Raw stdout from Claude CLI.

        Returns:
            Parsed JSON as dictionary, with ``trade.*`` flattened to
            top level when present.

        Raises:
            ClaudeParseError: If JSON cannot be extracted, parsed, or
                neither shape carries a ``signal`` key.
        """
        if not raw_output or not raw_output.strip():
            raise ClaudeParseError(
                "Claude returned empty response",
                raw_output=raw_output,
            )

        candidates: list[str] = []
        fenced = self._extract_json_from_markdown(raw_output)
        if fenced is not None:
            candidates.append(fenced)
        balanced = self._extract_balanced_json_object(raw_output)
        if balanced is not None and balanced not in candidates:
            candidates.append(balanced)
        candidates.append(raw_output.strip())

        last_error: json.JSONDecodeError | None = None
        for json_text in candidates:
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError as e:
                last_error = e
                continue
            if not isinstance(result, dict):
                # Wrong shape from this candidate; try the next one
                # before giving up — a balanced match might land on
                # an inner array while the fenced block has the dict.
                last_error = json.JSONDecodeError(
                    f"Expected JSON object, got {type(result).__name__}",
                    json_text,
                    0,
                )
                continue
            return self._normalize_trade_fields(result)

        # All candidates failed — log the raw output for diagnostics.
        preview = raw_output.strip()
        if len(preview) > 1000:
            preview = preview[:1000] + "...(truncated)"
        self._logger.warning(
            "Claude response did not contain parseable JSON. Raw output:\n%s",
            preview,
        )
        raise ClaudeParseError(
            f"Failed to parse JSON: {last_error}",
            raw_output=raw_output,
        )

    def _normalize_trade_fields(self, result: dict[str, Any]) -> dict[str, Any]:
        """Promote nested ``trade.*`` keys to top level (Phase 16.1).

        The chasulang_ict_smc.md template nests the actionable trade
        under ``response["trade"]`` alongside structural analysis
        frames; sample_prompt.md / simple_trend_analysis.md use a flat
        top-level shape. To keep the downstream
        ``StrategyTechnique.analyze`` consumer in
        ``src/strategy/loader.py`` single-shape, we promote the
        nested fields when present.

        Precedence:
        1. If a ``trade`` sub-dict exists and carries the canonical
           keys, those win — operationally the structural top-level
           keys (``external_structure``, ``liquidity_map``, ...) are
           never themselves the trade decision in the chasulang shape,
           and the ``trade`` block is the single source of truth.
        2. Otherwise the top-level value is preserved (back-compat
           for the simple flat shapes).

        Take-profit handling: when the nested ``trade`` carries
        both ``take_profit_1`` and ``take_profit_2`` (chasulang's
        primary + secondary targets), we pick ``take_profit_1`` —
        the closer, more conservative target. The secondary target
        is not preserved on the top-level view; downstream code only
        consumes a single ``take_profit``. If the strategy ever needs
        the secondary target it should read from
        ``trade.take_profit_2`` directly (the original ``trade``
        block is left intact in the result).

        Validation: after normalization, the result must carry a
        ``signal`` key; if neither the top level nor ``trade`` had
        one, raise ``ClaudeParseError`` with a message that names
        both candidate paths so operators can quickly spot which
        prompt template needs fixing.

        Args:
            result: Already-parsed JSON object (a dict).

        Returns:
            Normalized dict with ``trade.*`` flattened to the top
            level when applicable. The original ``trade`` sub-dict
            is left in place for callers that want the full nested
            view.
        """
        # Make a shallow copy so we don't mutate the caller's view of
        # the parsed JSON. Inner dicts are not mutated either way.
        normalized = dict(result)
        trade = result.get("trade")
        if isinstance(trade, dict):
            # Canonical fields the downstream loader expects. Keep
            # this list in sync with src/strategy/loader.py's
            # AnalysisResult construction.
            for key in (
                "signal",
                "entry_price",
                "stop_loss",
                "take_profit",
                "confidence",
                "reasoning",
            ):
                if key in trade:
                    normalized[key] = trade[key]
            # take_profit precedence: explicit `take_profit` >
            # `take_profit_1` (closest target, conservative) >
            # nothing. We deliberately pick TP1 over TP2 — TP2 is
            # the stretch target, far more likely to give back open
            # profit than be hit.
            if "take_profit" not in trade:
                if "take_profit_1" in trade:
                    normalized["take_profit"] = trade["take_profit_1"]

        if "signal" not in normalized:
            raise ClaudeParseError(
                "Claude response missing 'signal'. Checked top-level "
                "'signal' and nested 'trade.signal' — neither was "
                "present. Either the prompt template needs to declare "
                "one of these paths, or Claude returned an unexpected "
                "shape.",
                raw_output=json.dumps(result),
            )

        return normalized

    def _extract_json_from_markdown(self, text: str) -> str | None:
        """Extract JSON from markdown code block.

        Handles formats like:
        - ```json\\n{...}\\n```
        - ```\\n{...}\\n```

        Args:
            text: Text that may contain markdown code blocks.

        Returns:
            Extracted JSON text, or None if no code block found.
        """
        match = JSON_BLOCK_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _extract_balanced_json_object(text: str) -> str | None:
        """Find the first balanced ``{...}`` substring in ``text``.

        Handles the common Claude Code response shape where the JSON
        is embedded in prose without a code fence::

            Looking at this chart, here is my analysis: {"signal": ...}.
            The setup is strong because ...

        String literals are tracked so that braces inside ``"..."`` do
        not throw off the depth counter. Returns ``None`` if no
        balanced object is found.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None
