"""Ports (Protocols) for the AI layer.

Defines the narrow :class:`LLMClient` Protocol — the seam between the
domain/feedback consumers (``strategy/loader.py``, ``ai/improver.py``,
``feedback/loop.py``) and the concrete LLM transport.

Why a Protocol (structural typing): consumers depend on *what* the
client does (``analyze``/``complete``), not on the concrete
:class:`src.ai.claude.ClaudeCLI` adapter. ``ClaudeCLI`` satisfies this
Protocol structurally with NO changes, so the domain no longer has to
name the edge adapter to type its collaborator.

Related Requirements:
- NFR-002: Claude CLI Integration. ``ClaudeCLI`` remains the ONLY
  production adapter — this Protocol exists for dependency inversion
  and testability (fakes), NOT to introduce an Anthropic-API client.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Narrow port for the LLM transport used by AI/feedback consumers.

    Captures ONLY the two public coroutines consumers call:

    - :meth:`analyze` — send a prompt, get back a parsed JSON object
      (used by ``PromptStrategy.analyze`` for per-bar trade decisions).
    - :meth:`complete` — send a prompt, get back raw text (used by
      ``StrategyImprover`` for generated markdown / Python files).

    :class:`src.ai.claude.ClaudeCLI` structurally satisfies this
    Protocol. Tests can substitute any object with the same two
    coroutines (e.g. ``AsyncMock``) without importing the concrete
    adapter.
    """

    async def analyze(self, prompt: str) -> dict[str, Any]:
        """Send ``prompt`` and return the parsed JSON response object."""
        ...

    async def complete(self, prompt: str) -> str:
        """Send ``prompt`` and return the raw text response."""
        ...
