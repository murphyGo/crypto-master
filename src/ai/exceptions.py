"""Claude AI exceptions for Crypto Master.

Related Requirements:
- NFR-002: Claude CLI Integration
"""


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


class ClaudeTimeoutError(ClaudeError):
    """Claude CLI execution timed out.

    Raised when Claude CLI does not respond within the timeout period.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded.
    """

    def __init__(self, message: str, timeout_seconds: float) -> None:
        """Initialize ClaudeTimeoutError.

        Args:
            message: Error description.
            timeout_seconds: The timeout duration that was exceeded.
        """
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


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
