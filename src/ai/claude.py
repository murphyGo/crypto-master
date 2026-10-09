"""Claude CLI wrapper for Crypto Master.

Provides async interface to Claude via CLI.

Related Requirements:
- NFR-002: Claude CLI Integration
- FR-001: Bitcoin Chart Analysis
- FR-002: Altcoin Chart Analysis
"""

import asyncio
import os
import shutil
import subprocess
from typing import Any

from src.ai.exceptions import (
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeParseError,
    ClaudeTimeoutError,
)
from src.ai.response import AnalysisResponseParser
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

CLAUDE_SUBPROCESS_ENV_ALLOWLIST = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TERM",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
}


class ClaudeCLI(AnalysisResponseParser):
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
                env=self._subprocess_env(),
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

    @staticmethod
    def _subprocess_env() -> dict[str, str]:
        """Pass only process basics to Claude CLI, never ambient API keys."""
        return {
            key: value
            for key, value in os.environ.items()
            if key in CLAUDE_SUBPROCESS_ENV_ALLOWLIST
        }
