"""Explicit provider selection; no automatic fallback between credentials."""

from src.ai.ports import LLMClient
from src.config import get_settings


def create_llm_client(*, timeout: float | None = None) -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "codex":
        from src.ai.codex import CodexCLI

        return CodexCLI(timeout=timeout)
    # Keep the existing public constructor seam for legacy injected tests/callers.
    from src.ai import ClaudeCLI

    return ClaudeCLI() if timeout is None else ClaudeCLI(timeout=timeout)
