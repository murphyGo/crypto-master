"""Tests for CAH-10: the LLMClient port + AI/feedback DIP seams.

Covers:
- AI-F1 / LAYER-F1: ``StrategyImprover`` and ``PromptStrategy`` accept
  an injected fake ``LLMClient`` (not just the concrete ``ClaudeCLI``),
  and the loader no longer news up a concrete client when one is
  injected.
- LAYER-F2: ``ClaudeTimeoutError`` is still an instance of the same
  ``StrategyError`` the proposal engine catches, even though
  ``ai/exceptions.py`` no longer imports ``strategy.base``.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from src.ai.ports import LLMClient
from src.models import OHLCV, AnalysisResult
from src.strategy.base import TechniqueInfo
from src.strategy.loader import PromptStrategy


class FakeLLM:
    """A structural ``LLMClient`` fake — NOT a ``ClaudeCLI`` subclass.

    Proves the DIP seam: consumers depend on the ``LLMClient`` Protocol,
    so any object with ``analyze``/``complete`` coroutines works without
    importing the concrete edge adapter.
    """

    def __init__(
        self,
        analyze_result: dict[str, Any] | None = None,
        complete_result: str = "",
    ) -> None:
        self.analyze_result = analyze_result or {}
        self.complete_result = complete_result
        self.analyze_calls: list[str] = []
        self.complete_calls: list[str] = []

    async def analyze(self, prompt: str) -> dict[str, Any]:
        self.analyze_calls.append(prompt)
        return self.analyze_result

    async def complete(self, prompt: str) -> str:
        self.complete_calls.append(prompt)
        return self.complete_result


def _ohlcv(n: int = 25) -> list[OHLCV]:
    return [
        OHLCV(
            timestamp=datetime(2026, 1, 1),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("102"),
            volume=Decimal("1000"),
        )
        for _ in range(n)
    ]


def test_fake_llm_satisfies_protocol_structurally() -> None:
    """A non-ClaudeCLI fake is a structural ``LLMClient``."""
    fake = FakeLLM()
    assert isinstance(fake, LLMClient)


async def test_prompt_strategy_uses_injected_llm_client() -> None:
    """LAYER-F1: an injected fake is used instead of constructing ClaudeCLI.

    No ``patch("src.ai.ClaudeCLI", ...)`` here — that is the whole
    point. The injected client is called directly, proving the domain
    strategy no longer news up the edge adapter when a client is
    supplied.
    """
    fake = FakeLLM(
        analyze_result={
            "signal": "long",
            "confidence": 0.8,
            "entry_price": 102,
            "stop_loss": 95,
            "take_profit": 110,
            "reasoning": "fake",
        }
    )
    info = TechniqueInfo(
        name="injected_tech",
        version="1.0.0",
        description="Test",
        technique_type="prompt",
    )
    strategy = PromptStrategy(
        info=info,
        prompt_content="Analyze {symbol} on {timeframe}: {ohlcv_data}",
        llm_client=fake,
    )

    result = await strategy.analyze(_ohlcv(), "BTC/USDT")

    assert isinstance(result, AnalysisResult)
    assert result.signal == "long"
    # The injected client received the formatted prompt — no ClaudeCLI
    # was constructed.
    assert len(fake.analyze_calls) == 1
    assert "BTC/USDT" in fake.analyze_calls[0]


async def test_strategy_improver_accepts_injected_llm_client(tmp_path: Any) -> None:
    """AI-F1: StrategyImprover drives an injected fake LLMClient."""
    from src.ai.improver import StrategyImprover

    response = (
        "```markdown\n"
        "---\n"
        "name: injected\n"
        "version: 0.1.0\n"
        "description: test\n"
        "technique_type: prompt\n"
        "hypothesis: An injected fake drives the improver end to end.\n"
        "---\n"
        "body\n\n"
        "## Output Contract\n"
        "Return JSON keys: signal, entry_price, stop_loss, take_profit.\n"
        "```"
    )
    fake = FakeLLM(complete_result=response)
    improver = StrategyImprover(
        claude=fake,
        experimental_dir=tmp_path / "experimental",
        catalog_path=tmp_path / "no_catalog.md",
    )

    generated = await improver.generate_idea(context="momentum", save=False)

    assert generated.name == "injected"
    assert len(fake.complete_calls) == 1


def test_claude_timeout_error_still_caught_as_strategy_error() -> None:
    """LAYER-F2 invariant: ClaudeTimeoutError IS-A StrategyError.

    ``ai/exceptions.py`` no longer imports ``strategy.base``, but
    ``ClaudeTimeoutError`` must still be caught by the proposal engine's
    ``except StrategyError`` clauses. Assert it against the SAME class
    object the proposal engine imports (``src.strategy.base``).
    """
    from src.ai.exceptions import ClaudeError, ClaudeTimeoutError
    from src.exceptions import StrategyError as NeutralStrategyError
    from src.strategy.base import StrategyError as DomainStrategyError

    # The re-exported domain symbol and the neutral source symbol are the
    # exact same class object (re-export, not a copy).
    assert DomainStrategyError is NeutralStrategyError

    err = ClaudeTimeoutError("timed out", timeout_seconds=120.0, attempt_number=1)
    assert isinstance(err, DomainStrategyError)
    assert isinstance(err, ClaudeError)

    # Confirm the actual catch behaviour the proposal engine relies on.
    caught_as_strategy_error = False
    try:
        raise err
    except DomainStrategyError:
        caught_as_strategy_error = True
    assert caught_as_strategy_error


def test_ai_exceptions_does_not_import_strategy_domain() -> None:
    """LAYER-F2: the ai adapter no longer imports the strategy domain."""
    import ast
    import pathlib

    source = pathlib.Path("src/ai/exceptions.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)

    assert not any(m.startswith("src.strategy") for m in imported_modules), (
        f"ai/exceptions.py must not import the strategy domain; "
        f"found {imported_modules}"
    )


@pytest.mark.parametrize("method", ["analyze", "complete"])
def test_claude_cli_satisfies_llm_client_protocol(method: str) -> None:
    """ClaudeCLI structurally satisfies LLMClient with no adapter change."""
    from src.ai.claude import ClaudeCLI

    client = ClaudeCLI(timeout=1.0, max_retries=0, model="")
    assert isinstance(client, LLMClient)
    assert hasattr(client, method)
