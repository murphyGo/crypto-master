"""Read captured file prefixes without allocating an entire archive.

``None`` is a cooperative checkpoint at each read block. Callers may pause
iteration there; closing the iterator releases its file handle. Invalid or
unfinished input is an explicit coverage failure, never an empty result.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BLOCK_BYTES = 64 * 1024
RECORD_BYTES = 1024 * 1024


class ReadFailure(Exception):
    """Stable reason suitable for read-result metadata; no source payload."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Generation:
    device: int
    inode: int
    size: int
    mtime_ns: int

    @classmethod
    def capture(cls, path: Path) -> Generation:
        stat = path.stat()
        return cls(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _blocks(path: Path, generation: Generation) -> Iterator[bytes]:
    with path.open("rb") as handle:
        stat = os.fstat(handle.fileno())
        if (
            Generation(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            != generation
        ):
            raise ReadFailure("source_changed")
        remaining = generation.size
        while remaining:
            block = handle.read(min(BLOCK_BYTES, remaining))
            if not block:
                raise ReadFailure("source_changed")
            remaining -= len(block)
            yield block
    if Generation.capture(path) != generation:
        raise ReadFailure("source_changed")


def _object(raw: bytes | bytearray) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReadFailure("malformed_json") from exc
    if not isinstance(value, dict):
        raise ReadFailure("invalid_record")
    return value


def jsonl_records(
    path: Path, generation: Generation, *, record_bytes: int = RECORD_BYTES
) -> Generator[dict[str, Any] | None, None, None]:
    pending = bytearray()
    for block in _blocks(path, generation):
        start = 0
        while start < len(block):
            end = block.find(b"\n", start)
            stop = len(block) if end < 0 else end
            if len(pending) + stop - start > record_bytes:
                raise ReadFailure("record_too_large")
            pending.extend(block[start:stop])
            if end < 0:
                break
            if pending.strip():
                yield _object(pending)
            pending.clear()
            start = end + 1
        yield None
    # Writers terminate every record with a newline. A captured incomplete
    # append cannot certify the safety/reconciliation view as complete.
    if pending.strip():
        raise ReadFailure("partial_record")


def json_object(
    path: Path, generation: Generation, *, record_bytes: int = RECORD_BYTES
) -> Generator[dict[str, Any] | None, None, None]:
    if generation.size > record_bytes:
        raise ReadFailure("record_too_large")
    pending = bytearray()
    for block in _blocks(path, generation):
        pending.extend(block)
        yield None
    yield _object(pending)


def reverse_jsonl_records(
    path: Path, generation: Generation, *, record_bytes: int = RECORD_BYTES
) -> Generator[dict[str, Any] | None, None, None]:
    """Newest-first blocks; byte offsets preserve original timestamp ties."""
    carry = b""
    first = True
    with path.open("rb") as handle:
        stat = os.fstat(handle.fileno())
        if (
            Generation(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            != generation
        ):
            raise ReadFailure("source_changed")
        position = generation.size
        while position:
            length = min(BLOCK_BYTES, position)
            position -= length
            handle.seek(position)
            block = handle.read(length)
            if len(block) != length:
                raise ReadFailure("source_changed")
            boundary = block.rfind(b"\n")
            if len(carry) + length - boundary - 1 > record_bytes:
                raise ReadFailure("record_too_large")
            buffer = block + carry
            right = len(buffer)
            if first:
                first = False
                if buffer.endswith(b"\n"):
                    right -= 1
                elif buffer.strip():
                    raise ReadFailure("partial_record")
            while right:
                left = buffer.rfind(b"\n", 0, right)
                if left < 0:
                    break
                raw = buffer[left + 1 : right]
                if len(raw) > record_bytes:
                    raise ReadFailure("record_too_large")
                if raw.strip():
                    value = _object(raw)
                    value["_offset"] = position + left + 1
                    yield value
                right = left
            carry = buffer[:right]
            if len(carry) > record_bytes:
                raise ReadFailure("record_too_large")
            yield None
        if carry.strip():
            value = _object(carry)
            value["_offset"] = 0
            yield value
    if Generation.capture(path) != generation:
        raise ReadFailure("source_changed")


def json_array_records(
    path: Path, generation: Generation, *, record_bytes: int = RECORD_BYTES
) -> Generator[dict[str, Any] | None, None, None]:
    """Incremental object-array parser, including nested/escaped strings.

    Allocation is checked before adding bytes to the current object. JSON's
    own decoder validates nesting, numbers and UTF-8 within each object;
    this state machine validates array separators and trailing content.
    """
    state = "start"
    pending = bytearray()
    depth = 0
    quoted = False
    escaped = False
    for block in _blocks(path, generation):
        # Find structural ASCII bytes while in an object. Processing slices
        # rather than decoding the whole array also handles UTF-8 boundaries.
        for char in block:
            if state == "object":
                if len(pending) >= record_bytes:
                    raise ReadFailure("record_too_large")
                pending.append(char)
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == 92:
                        escaped = True
                    elif char == 34:
                        quoted = False
                elif char == 34:
                    quoted = True
                elif char in (123, 91):
                    depth += 1
                elif char in (125, 93):
                    depth -= 1
                    if depth == 0:
                        yield _object(pending)
                        pending.clear()
                        state = "separator"
                continue
            if char in (9, 10, 13, 32):
                continue
            if state == "start" and char == 91:
                state = "first"
            elif state in ("first", "next") and char == 123:
                pending.append(char)
                depth = 1
                state = "object"
            elif state in ("first", "separator") and char == 93:
                state = "done"
            elif state == "separator" and char == 44:
                state = "next"
            else:
                raise ReadFailure("malformed_json_array")
        yield None
    if state != "done":
        raise ReadFailure("partial_record")
