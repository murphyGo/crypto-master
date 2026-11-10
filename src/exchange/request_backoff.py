"""Bounded, process-local venue cooldowns; no sleeps, retries or credentials.

DEBT-090 / CON-002: share a response's backoff across accounts using the same
endpoint family. This is reactive containment, not distributed IP accounting.
"""

import math
import re
import time
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from threading import Lock

from ccxt.base.errors import DDoSProtection, RateLimitExceeded

Scope = tuple[str, str, bool]
MAX_SCOPES = 64
_deadlines: dict[Scope, float] = {}
_lock = Lock()
_BAN_UNTIL = re.compile(r"banned until\s+(\d{13})(?!\d)", re.IGNORECASE)


class RequestBackoff(RateLimitExceeded):
    """Sanitized CCXT-compatible signal for the existing adapter error ladders."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("venue request cooldown active")
        self.retry_after_seconds = retry_after_seconds


def _prune(now: float) -> None:
    for scope in [key for key, deadline in _deadlines.items() if deadline <= now]:
        del _deadlines[scope]


def check_backoff(scope: Scope) -> None:
    """Reject before constructing a request coroutine while the scope is banned."""
    with _lock:
        now = time.monotonic()
        _prune(now)
        remaining = _deadlines.get(scope, now) - now
        if remaining > 0:
            raise RequestBackoff(remaining)
        if scope not in _deadlines and len(_deadlines) >= MAX_SCOPES:
            raise RequestBackoff(60.0)


def record_backoff(scope: Scope, error: Exception, headers: object) -> RequestBackoff:
    """Extend a monotonic deadline using only allowlisted response metadata."""
    delay = _retry_delay(error, headers)
    with _lock:
        now = time.monotonic()
        _prune(now)
        if scope in _deadlines or len(_deadlines) < MAX_SCOPES:
            _deadlines[scope] = max(_deadlines.get(scope, now), now + delay)
            delay = _deadlines[scope] - now
        # A full registry rejects unknown scopes in check_backoff as well.
    return RequestBackoff(delay)


def _retry_delay(error: Exception, headers: object) -> float:
    wall_now = time.time()
    hints: list[float] = []
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if isinstance(key, str) and key.lower() == "retry-after":
                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    text = str(value)[:128]
                    try:
                        hints.append(float(text))
                    except ValueError:
                        try:
                            parsed = parsedate_to_datetime(text)
                            if parsed.tzinfo is not None:
                                hints.append(parsed.timestamp() - wall_now)
                        except (ValueError, TypeError, OverflowError):
                            pass
                break
    match = _BAN_UNTIL.search(str(error)[:16384])
    if match:
        hints.append(int(match.group(1)) / 1000 - wall_now)
    usable = [hint for hint in hints if math.isfinite(hint) and hint > 0]
    if usable:
        return max(usable)
    return 120.0 if isinstance(error, DDoSProtection) else 60.0
