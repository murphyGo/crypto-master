"""Shared trade-analysis response parsing; preserves legacy exception contracts."""

import json
import logging
import re
from typing import Any

from src.ai.exceptions import ClaudeParseError

JSON_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE
)


class AnalysisResponseParser:
    _logger: logging.Logger

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
