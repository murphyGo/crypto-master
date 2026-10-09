"""Secret-safe managed-login validation; no OAuth refresh implementation."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

MAX_AUTH_BYTES = 48 * 1024


class CodexAuthError(ValueError):
    """Fixed diagnostic; never carries input, filesystem paths or API bodies."""

    def __init__(self) -> None:
        super().__init__("codex_auth_invalid")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CodexAuthError()
        result[key] = value
    return result


@dataclass(frozen=True, slots=True, repr=False)
class AuthDocument:
    raw: bytes = field(repr=False)
    secrets: tuple[str, ...] = field(repr=False)

    def __repr__(self) -> str:
        return "AuthDocument(<redacted>)"


def validate_auth(raw: bytes) -> AuthDocument:
    if not raw or len(raw) >= MAX_AUTH_BYTES:
        raise CodexAuthError()
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError):
        raise CodexAuthError() from None
    if not isinstance(payload, dict) or payload.get("auth_mode") != "chatgpt":
        raise CodexAuthError()
    if payload.get("OPENAI_API_KEY") not in (None, ""):
        raise CodexAuthError()
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexAuthError()
    leaves: list[str] = []
    for key in ("id_token", "access_token", "refresh_token"):
        value = tokens.get(key)
        if not isinstance(value, str) or not value.strip():
            raise CodexAuthError()
        leaves.append(value)
    account = tokens.get("account_id")
    if account is not None:
        if not isinstance(account, str) or not account.strip():
            raise CodexAuthError()
        leaves.append(account)
    return AuthDocument(raw, tuple(leaves))


def read_auth(path: Path) -> AuthDocument:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.getuid()
            ):
                raise CodexAuthError()
            return validate_auth(stream.read(MAX_AUTH_BYTES))
    except OSError:
        raise CodexAuthError() from None


def write_auth(path: Path, raw: bytes) -> AuthDocument:
    document = validate_auth(raw)
    temporary: str | None = None
    try:
        parent = path.parent
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            raise CodexAuthError()
        if path.is_symlink():
            raise CodexAuthError()
        fd, temporary = tempfile.mkstemp(prefix=".auth-", dir=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(document.raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise CodexAuthError() from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return document
