"""Neutral, layer-agnostic base exceptions for Crypto Master.

Houses base exception classes that more than one layer needs to share
without creating a cross-layer import. In particular ``StrategyError``
lives here so the AI adapter (``src/ai/exceptions.py``) can root
``ClaudeTimeoutError`` off the same base the strategy domain uses —
without ``ai`` having to import ``strategy.base`` (a layering
violation, LAYER-F2).

``src.strategy.base`` re-exports ``StrategyError`` for backward
compatibility, so existing ``from src.strategy.base import
StrategyError`` imports — and every ``except StrategyError`` /
``isinstance(..., StrategyError)`` site — continue to reference this
exact same class object.
"""

from __future__ import annotations


class StrategyError(Exception):
    """Base exception for strategy errors.

    All strategy-related exceptions inherit from this class, allowing
    callers to catch all strategy errors with a single except clause.

    Defined here (a neutral module) rather than in ``strategy.base`` so
    the AI adapter can subclass it (``ClaudeTimeoutError``) without the
    AI layer importing the strategy domain. ``strategy.base`` re-exports
    it so the canonical import path is unchanged.
    """

    pass
