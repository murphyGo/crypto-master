"""Claude AI exceptions for Crypto Master.

Related Requirements:
- NFR-002: Claude CLI Integration
"""

from src.strategy.base import StrategyError


class ClaudeError(Exception):
    """Base exception for Claude AI errors.

    All Claude-related exceptions inherit from this class,
    allowing callers to catch all Claude errors with a single except clause.
    """

    pass


class ClaudeNotFoundError(ClaudeError):
    """Claude CLI not found in PATH.

    Raised when the 'claude' command is not available.
    """

    pass


class ClaudeExecutionError(ClaudeError):
    """Claude CLI execution failed.

    Raised when Claude CLI returns a non-zero exit code.

    Attributes:
        exit_code: The exit code returned by the CLI.
        stderr: Error output from the CLI, if available.
    """

    def __init__(
        self,
        message: str,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        """Initialize ClaudeExecutionError.

        Args:
            message: Error description.
            exit_code: The exit code returned by the CLI.
            stderr: Error output from the CLI.
        """
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class ClaudeTimeoutError(ClaudeError, StrategyError):
    """Claude CLI execution timed out.

    Raised when Claude CLI does not respond within the timeout period.

    Inherits from both :class:`ClaudeError` (so existing
    ``except ClaudeError`` catches still work) and :class:`StrategyError`
    (Phase 12.3) so the proposal engine's existing
    ``except StrategyError`` clause in ``_build_proposal_for_strategy``
    treats a timeout as a clean per-strategy skip — neutral fallback,
    no cycle abort. Sites that need to distinguish a timeout from
    other strategy failures (e.g. the activity log's ``LLM_TIMEOUT``
    event) use ``isinstance(e, ClaudeTimeoutError)`` after the catch.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded
            (the *final* attempt's timeout when retry-on-timeout is
            in play).
        attempt_number: 1-indexed attempt number that raised — Phase
            14.1. ``1`` means the first attempt timed out and there
            was no retry (or retries were disabled);
            ``max_retries + 1`` means every attempt timed out.
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float,
        attempt_number: int = 1,
    ) -> None:
        """Initialize ClaudeTimeoutError.

        Args:
            message: Error description.
            timeout_seconds: The timeout duration that was exceeded.
            attempt_number: 1-indexed attempt that raised. Phase 14.1
                — surfaced in the ``LLM_TIMEOUT`` activity event so
                operators can verify the retry path is actually firing.
        """
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.attempt_number = attempt_number


class ClaudeParseError(ClaudeError):
    """Failed to parse Claude response.

    Raised when Claude returns output that cannot be parsed as expected JSON.

    Attributes:
        raw_output: The raw output that failed to parse.
    """

    def __init__(self, message: str, raw_output: str | None = None) -> None:
        """Initialize ClaudeParseError.

        Args:
            message: Error description.
            raw_output: The raw output that failed to parse.
        """
        super().__init__(message)
        self.raw_output = raw_output
