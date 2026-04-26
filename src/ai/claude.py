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
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        claude_path: str = "claude",
    ) -> None:
        """Initialize ClaudeCLI.

        Args:
            timeout: Timeout in seconds for CLI execution.
            claude_path: Path to claude executable or command name.
        """
        self.timeout = timeout
        self.claude_path = claude_path
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
        """Execute claude -p command.

        Args:
            prompt: The prompt text to pass to Claude.

        Returns:
            Tuple of (stdout, stderr) from the process.

        Raises:
            ClaudeNotFoundError: If claude executable not found.
            ClaudeTimeoutError: If execution exceeds timeout.
            ClaudeExecutionError: If CLI returns non-zero exit code.
        """
        process = None
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                self.claude_path,
                "-p",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Check exit code
            if process.returncode != 0:
                self._logger.error(
                    f"Claude CLI failed with exit code {process.returncode}: {stderr}"
                )
                raise ClaudeExecutionError(
                    f"Claude CLI failed with exit code {process.returncode}",
                    exit_code=process.returncode,
                    stderr=stderr,
                )

            self._logger.debug("Claude CLI completed successfully")
            return stdout, stderr

        except asyncio.TimeoutError:
            # Kill the process if it's still running
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()

            raise ClaudeTimeoutError(
                f"Claude CLI timed out after {self.timeout} seconds",
                timeout_seconds=self.timeout,
            )

        except FileNotFoundError:
            raise ClaudeNotFoundError(f"Claude CLI not found: '{self.claude_path}'")

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

        On total failure, the raw response is logged at WARNING (truncated
        to 1000 chars) so operators can see *what* Claude actually said
        without re-running the cycle.

        Args:
            raw_output: Raw stdout from Claude CLI.

        Returns:
            Parsed JSON as dictionary.

        Raises:
            ClaudeParseError: If JSON cannot be extracted or parsed.
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
            return result

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
