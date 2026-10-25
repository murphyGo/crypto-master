"""Disposable private COW packs; every store failure is an acceleration miss.

No pickle, canonical writer locks or runtime risk decisions. Files on disk are
bounded and the resident packed index reserves space in the data-service cache.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import stat
import struct
import sys
import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import asdict, fields
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from src.dashboard.read_models import Query
from src.dashboard.sources import Source
from src.utils.bounded_read import Generation, ReadFailure

_MIB = 1024 * 1024
_ENTRY = struct.Struct("!32s16sII")
_MAGIC = b"CMCKPT01"
_SUFFIXES = {".cachepack", ".idx", ".owner", ".lock", ".tmp"}
_ALLOWED_NAMES = {"index.idx", "producer.owner", "store.lock"}


class CacheMiss(Exception):
    pass


def eligible_model(model: BaseModel) -> bool:
    """Missing time/UUID factories cannot be frozen across process restart."""
    pending: list[Any] = [model]
    while pending:
        value = pending.pop()
        if isinstance(value, BaseModel):
            for name, field in type(value).model_fields.items():
                if (
                    field.default_factory is not None
                    and name not in value.model_fields_set
                ):
                    if field.default_factory not in (dict, list, tuple, set):
                        return False
                pending.append(getattr(value, name))
        elif isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend(value)
    return True


def _wire(value: Any) -> Any:
    from src.dashboard.projections import CycleState

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return ["i", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CacheMiss("nonfinite")
        return ["f", repr(value)]
    if isinstance(value, datetime):
        return ["t", value.isoformat()]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CacheMiss("nonfinite")
        return ["d", str(value)]
    if isinstance(value, bytes):
        return ["b", base64.b64encode(value).decode("ascii")]
    if isinstance(value, CycleState):
        return ["c", [_wire(getattr(value, f.name)) for f in fields(value)]]
    if isinstance(value, dict):
        return ["m", [[_wire(k), _wire(v)] for k, v in value.items()]]
    if isinstance(value, (list, tuple, set)):
        return [
            {list: "l", tuple: "q", set: "s"}[type(value)],
            [_wire(v) for v in value],
        ]
    raise CacheMiss("unsupported")


def _unwire(value: Any, depth: int = 0) -> Any:
    from src.dashboard.projections import CycleState

    if depth > 64:
        raise CacheMiss("depth")
    if value is None or isinstance(value, (str, bool)):
        return value
    if not isinstance(value, list) or len(value) != 2:
        raise CacheMiss("codec")
    tag, raw = value
    if tag == "i":
        return int(raw)
    if tag == "f":
        v = float(raw)
        if not math.isfinite(v):
            raise CacheMiss("nonfinite")
        return v
    if tag == "t":
        return datetime.fromisoformat(raw)
    if tag == "d":
        decimal_value = Decimal(raw)
        if not decimal_value.is_finite():
            raise CacheMiss("nonfinite")
        return decimal_value
    if tag == "b":
        return base64.b64decode(raw, validate=True)
    if not isinstance(raw, list):
        raise CacheMiss("codec")
    if tag == "m":
        return {_unwire(k, depth + 1): _unwire(v, depth + 1) for k, v in raw}
    values = [_unwire(v, depth + 1) for v in raw]
    if tag == "c" and len(values) == len(fields(CycleState)):
        return CycleState(*values)
    if tag == "l":
        return values
    if tag == "q":
        return tuple(values)
    if tag == "s":
        return set(values)
    raise CacheMiss("codec")


def encode_state(state: dict[str, Any], cap: int = _MIB - 40) -> bytes:
    """Framed lossless JSONL: large containers split into bounded leaf rows."""
    from src.dashboard.projections import StateBudget
    from src.dashboard.read_models import Limits

    sizing = StateBudget(Limits())
    if state.get("kind") == "proposals" and isinstance(state.get("state"), dict):
        compact = dict(state)
        compact["at"] = state["at"].isoformat()
        compact["state"] = dict(state["state"])
        compact["state"]["timestamp"] = state["state"]["timestamp"].isoformat()
        output_raw = (
            b'["codec",3]\n'
            + json.dumps(compact, separators=(",", ":"), allow_nan=False).encode()
            + b"\n"
        )
        if len(output_raw) > cap:
            raise CacheMiss("logical_limit")
        return output_raw
    output = bytearray(b'["codec",2]\n')

    def emit(row: Any) -> None:
        raw = json.dumps(row, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        if len(raw) > _MIB or len(output) + len(raw) > cap:
            raise CacheMiss("logical_limit")
        output.extend(raw)

    def node(path: list[Any], value: Any, depth: int = 0) -> None:
        if depth > 64:
            raise CacheMiss("depth")
        if (
            isinstance(value, (dict, list, tuple, set))
            and sizing.size(value) > 32 * 1024
        ):
            kind = {dict: "m", list: "l", tuple: "q", set: "s"}[type(value)]
            emit(["open", path, kind])
            items = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in items:
                node([*path, _wire(key)], child, depth + 1)
            emit(["close", path])
        else:
            emit(["value", path, _wire(value)])

    node([], state)
    return bytes(output)


def decode_state(raw: bytes, *, max_bytes: int = 12 * _MIB) -> dict[str, Any]:
    from src.dashboard.projections import StateBudget
    from src.dashboard.read_models import Limits

    if raw.startswith(b'["codec",3]\n'):
        if len(raw) > min(_MIB, max_bytes // 24) or not raw.endswith(b"\n"):
            raise CacheMiss("decode_budget")
        compact = json.loads(raw[len(b'["codec",3]\n') :])
        if (
            not isinstance(compact, dict)
            or set(compact) != {"schema", "key", "kind", "at", "state"}
            or compact["kind"] != "proposals"
            or set(compact["state"])
            != {"timestamp", "threshold", "field", "account", "strategy"}
        ):
            raise CacheMiss("schema")
        compact["at"] = datetime.fromisoformat(compact["at"])
        compact["state"]["timestamp"] = datetime.fromisoformat(
            compact["state"]["timestamp"]
        )
        return compact
    if (
        len(raw) > _MIB
        or not raw.startswith(b'["codec",2]\n')
        or not raw.endswith(b"\n")
    ):
        raise CacheMiss("codec")
    sizing = StateBudget(Limits())
    frames: list[tuple[list[Any], str, Any]] = []
    result: Any = None
    charged = 0
    position = len(b'["codec",2]\n')

    def attach(path: list[Any], value: Any, *, leaf: bool) -> None:
        nonlocal result, charged
        if leaf:
            charge = sizing.size(value) + 128
            if charged + charge > max_bytes:
                raise CacheMiss("decode_budget")
            charged += charge
        if not frames:
            if path or result is not None:
                raise CacheMiss("path")
            result = value
            return
        parent_path, kind, parent = frames[-1]
        if path[:-1] != parent_path or len(path) != len(parent_path) + 1:
            raise CacheMiss("path")
        key = _unwire(path[-1])
        if kind == "m":
            if key in parent:
                raise CacheMiss("duplicate")
            parent[key] = value
        else:
            if key != len(parent):
                raise CacheMiss("path")
            parent.append(value)

    while position < len(raw):
        end = raw.find(b"\n", position)
        if (
            end < 0
            or end - position > _MIB
            or charged + (end - position) * 24 > max_bytes
        ):
            raise CacheMiss("decode_budget")
        row = json.loads(raw[position:end])
        position = end + 1
        if (
            not isinstance(row, list)
            or len(row) not in (2, 3)
            or not isinstance(row[1], list)
        ):
            raise CacheMiss("codec")
        op, path = row[:2]
        if len(path) > 64:
            raise CacheMiss("depth")
        if op == "open" and len(row) == 3 and row[2] in ("m", "l", "q", "s"):
            charged += 512
            if charged > max_bytes:
                raise CacheMiss("decode_budget")
            frames.append((path, row[2], {} if row[2] == "m" else []))
        elif op == "close" and len(row) == 2 and frames:
            expected, kind, value = frames.pop()
            if path != expected:
                raise CacheMiss("path")
            if kind == "q":
                value = tuple(value)
            elif kind == "s":
                value = set(value)
            attach(path, value, leaf=False)
        elif op == "value" and len(row) == 3:
            attach(path, _unwire(row[2]), leaf=True)
        else:
            raise CacheMiss("codec")
    if frames or not isinstance(result, dict):
        raise CacheMiss("codec")
    return result


def compatibility_digest() -> bytes:
    import numpy
    import pandas
    import pydantic
    import pydantic_core

    base = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    digest.update(
        repr(
            (
                sys.version,
                pydantic.__version__,
                pydantic_core.__version__,
                pandas.__version__,
                numpy.__version__,
            )
        ).encode()
    )
    # Bounded allowlist of deployment inputs; never .git or environment/secrets.
    count = total = 0
    paths = sorted((base / "src").rglob("*.py"))
    # Only the committed deployment configuration is allowlisted. In particular
    # runtime_flags/credentials/arbitrary custom YAML are never read here.
    config = base / "config" / "sub_accounts.yaml"
    if config.exists():
        paths.append(config)
    for path in paths:
        count += 1
        if count > 512:
            raise CacheMiss("compatibility_limit")
        digest.update(str(path.relative_to(base)).encode())
        with path.open("rb") as handle:
            while block := handle.read(65536):
                total += len(block)
                if total > 16 * _MIB:
                    raise CacheMiss("compatibility_limit")
                digest.update(block)
    return digest.digest()


class CheckpointStore:
    """One global store; 64 MiB all files, max64 physical and50k logical."""

    def __init__(
        self,
        data_root: Path,
        *,
        disk_bytes: int = 64 * _MIB,
        reserve_bytes: int = 128 * _MIB,
    ):
        self.data_root = data_root.resolve()
        self.base = self.data_root / ".dashboard-read-cache" / "v1"
        self.disk_bytes = disk_bytes
        self.reserve_bytes = reserve_bytes
        self.index_reservation = 4 * _MIB
        self._compatibility: bytes | None = None
        self.hits = 0
        self.misses = 0

    def _private(self, path: Path, *, directory: bool = False) -> None:
        info = path.lstat()
        if (
            info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or (not directory and info.st_nlink != 1)
        ):
            raise CacheMiss("owner")
        if not (
            stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        ):
            raise CacheMiss("shape")

    def prepare(self, query: Query) -> bool:
        try:
            if not self.data_root.is_dir():
                return False
            if (
                shutil.disk_usage(self.data_root).free
                < self.disk_bytes + self.reserve_bytes
            ):
                return False
            if query.source is not None and (
                query.source == self.base
                or self.base in query.source.parents
                or query.source in self.base.parents
                and query.kind == "proposals"
            ):
                return False
            # Happens before source-manifest capture (including missing inputs).
            for path in (self.base.parent, self.base):
                try:
                    path.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                self._private(path, directory=True)
            return True
        except (OSError, CacheMiss):
            return False

    @contextmanager
    def locked(self, exclusive: bool) -> Iterator[None]:
        descriptor = None
        try:
            import fcntl

            descriptor = os.open(
                self.base / "store.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            self._private(self.base / "store.lock")
            fcntl.flock(
                descriptor,
                (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB,
            )
            yield
        except (OSError, ImportError) as error:
            raise CacheMiss("lock") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _read(self, path: Path, cap: int) -> Generator[None | bytes, None, None]:
        self._private(path)
        if path.stat().st_size > cap:
            raise CacheMiss("file_limit")
        output = bytearray()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            while raw := handle.read(min(65536, cap + 1 - len(output))):
                output.extend(raw)
                if len(output) > cap:
                    raise CacheMiss("file_limit")
                yield None
        yield bytes(output)

    def _index(self) -> Generator[None, None, bytes]:
        path = self.base / "index.idx"
        if not path.exists():
            return b""
        data = yield from _last(self._read(path, self.index_reservation))
        if (
            len(data) < 40
            or data[:8] != _MAGIC
            or hashlib.sha256(data[:-32]).digest() != data[-32:]
            or (len(data) - 40) % _ENTRY.size
        ):
            raise CacheMiss("index")
        rows = data[8:-32]
        if len(rows) // _ENTRY.size > 50_000:
            raise CacheMiss("index_count")
        previous = b""
        for offset in range(0, len(rows), _ENTRY.size):
            key, _, _, _ = _ENTRY.unpack_from(rows, offset)
            if key <= previous:
                raise CacheMiss("index_order")
            previous = key
            if offset % (_ENTRY.size * 256) == 0:
                yield None
        return rows

    def _usage(self) -> tuple[int, int]:
        total = count = 0
        with os.scandir(self.base) as entries:
            for entry in entries:
                count += 1
                if count > 64:
                    raise CacheMiss("file_count")
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise CacheMiss("unknown_shape")
                total += max(info.st_size, info.st_blocks * 512) + 4096
                if total > self.disk_bytes:
                    raise CacheMiss("disk_limit")
        return total + 8192, count

    def _publish(self, path: Path, data: bytes) -> None:
        temporary = self.base / (uuid.uuid4().hex + ".tmp")
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            descriptor = os.open(self.base, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if temporary.exists():
                temporary.unlink()

    def session(self, query: Query) -> StoreSession:
        if self._compatibility is None:
            self._compatibility = compatibility_digest()
        return StoreSession(self, query)


class StoreSession:
    def __init__(self, store: CheckpointStore, query: Query):
        self.store = store
        self.query = query
        self.index = b""
        self.pack = b""
        self.pack_id = b""
        self.verified: set[bytes] = set()
        self.pending = bytearray()
        self.entries: list[tuple[bytes, int, int]] = []
        self.disabled = False
        self._read_lock: Any = None
        contract = asdict(query)
        contract["root"] = str(query.root)
        contract["source"] = str(query.source)
        contract["at"] = query.at.isoformat() if query.at else None
        self.prefix = hashlib.sha256(
            cast(bytes, store._compatibility)
            + json.dumps(contract, sort_keys=True, default=str).encode()
        ).digest()

    def key(self, source: Source, info: Any = None) -> bytes:
        info = info or source.path.stat()
        current = Generation(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if current != source.generation:
            raise ReadFailure("source_changed")
        metadata = struct.pack(
            "!QQQQQQ",
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_mode,
        )
        return hashlib.sha256(
            self.prefix
            + str(source.path).encode()
            + b"\0"
            + source.format.encode()
            + b"\0"
            + source.account.encode()
            + metadata
        ).digest()

    def close(self) -> None:
        if self._read_lock is not None:
            self._read_lock.__exit__(None, None, None)
            self._read_lock = None

    def _acquire_read(self) -> None:
        if self._read_lock is None:
            read_lock = self.store.locked(False)
            read_lock.__enter__()
            self._read_lock = read_lock

    def load(self) -> Generator[None, None, None]:
        try:
            self._acquire_read()
            self.index = yield from self.store._index()
            marker = self.store.base / "producer.owner"
            if self.index or marker.exists():
                raw = yield from _last(self.store._read(marker, 4096))
                owner = json.loads(raw)
                root_id = hashlib.sha256(str(self.query.root).encode()).hexdigest()
                if (
                    owner.get("producer") != "crypto-master-dashboard-v1"
                    or not isinstance(owner.get("roots"), list)
                    or len(owner["roots"]) > 2
                    or (root_id not in owner["roots"] and len(owner["roots"]) >= 2)
                ):
                    raise CacheMiss("owner")
        except (OSError, ValueError, CacheMiss):
            self.disabled = True
            self.close()

    def lookup(self, key: bytes, source: Source) -> Generator[None | bytes, None, None]:
        if self.disabled:
            self.store.misses += 1
            return
        try:
            self._acquire_read()
            # Index locators refer only to immutable pack names; EX cleanup
            # cannot delete/read-replace while this read holds SH.
            low = 0
            high = len(self.index) // _ENTRY.size
            while low < high:
                middle = (low + high) // 2
                found, token, offset, length = _ENTRY.unpack_from(
                    self.index, middle * _ENTRY.size
                )
                if found < key:
                    low = middle + 1
                else:
                    high = middle
            if low >= len(self.index) // _ENTRY.size:
                return
            found, token, offset, length = _ENTRY.unpack_from(
                self.index, low * _ENTRY.size
            )
            if found != key:
                return
            if length > _MIB or offset + length > _MIB:
                raise CacheMiss("locator")
            path = self.store.base / (token.hex() + ".cachepack")
            if token != self.pack_id:
                self.pack = yield from _last(self.store._read(path, _MIB))
                if (
                    len(self.pack) < 40
                    or self.pack[:8] != _MAGIC
                    or (
                        token not in self.verified
                        and hashlib.sha256(self.pack[:-32]).digest() != self.pack[-32:]
                    )
                ):
                    raise CacheMiss("pack")
                self.pack_id = token
                self.verified.add(token)
            if offset < 8 or offset + length > len(self.pack) - 32:
                raise CacheMiss("locator")
            with source.path.open("rb") as handle:
                info = os.fstat(handle.fileno())
                if (
                    Generation(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    != source.generation
                ):
                    raise CacheMiss("source_changed")
            self.store.hits += 1
            yield self.pack[offset : offset + length]
        except (OSError, ValueError, CacheMiss):
            self.pack = b""
            self.pack_id = b""
            self.store.misses += 1

    def put(self, key: bytes, raw: bytes) -> Generator[None, None, None]:
        if self.disabled:
            return
        if len(raw) > _MIB - 40:
            return
        if len(self.pending) + len(raw) > _MIB - 40 or len(self.entries) >= 4096:
            yield from self.flush()
        if self.disabled:
            return
        self.entries.append((key, len(self.pending) + 8, len(raw)))
        self.pending.extend(raw)

    def flush(self) -> Generator[None, None, None]:
        if not self.entries or self.disabled:
            return
        try:
            self.pack = b""
            self.pack_id = b""
            self.close()
            with self.store.locked(True):
                self.index = yield from self.store._index()
                usage, count = self.store._usage()
                referenced = {
                    _ENTRY.unpack_from(self.index, offset)[1].hex()
                    for offset in range(0, len(self.index), _ENTRY.size)
                }
                if (self.store.base / "producer.owner").exists():
                    with os.scandir(self.store.base) as entries:
                        for entry in entries:
                            path = self.store.base / entry.name
                            stem = path.stem
                            if len(stem) != 32 or any(
                                c not in "0123456789abcdef" for c in stem
                            ):
                                continue
                            if path.suffix == ".tmp":
                                self.store._private(path)
                                path.unlink()
                            elif path.suffix == ".cachepack" and stem not in referenced:
                                candidate = yield from _last(
                                    self.store._read(path, _MIB)
                                )
                                if (
                                    candidate[:8] == _MAGIC
                                    and len(candidate) >= 40
                                    and hashlib.sha256(candidate[:-32]).digest()
                                    == candidate[-32:]
                                ):
                                    path.unlink()
                    usage, count = self.store._usage()
                root_id = hashlib.sha256(str(self.query.root).encode()).hexdigest()
                owner = self.store.base / "producer.owner"
                roots = []
                if owner.exists():
                    raw = yield from _last(self.store._read(owner, 4096))
                    marker = json.loads(raw)
                    if marker.get("producer") != "crypto-master-dashboard-v1":
                        raise CacheMiss("owner")
                    roots = marker["roots"]
                if root_id not in roots:
                    if len(roots) >= 2:
                        raise CacheMiss("roots")
                    roots.append(root_id)
                token = uuid.uuid4().bytes
                incoming = sorted(
                    _ENTRY.pack(k, token, o, n) for k, o, n in self.entries
                )
                # At most4096 bounded incoming rows; existing index stays packed.
                combined = bytearray()
                position = 0
                old_count = len(self.index) // _ENTRY.size
                for row in incoming:
                    while position < old_count:
                        old = self.index[
                            position * _ENTRY.size : (position + 1) * _ENTRY.size
                        ]
                        if old[:32] >= row[:32]:
                            break
                        combined.extend(old)
                        position += 1
                    if (
                        position < old_count
                        and self.index[
                            position * _ENTRY.size : position * _ENTRY.size + 32
                        ]
                        == row[:32]
                    ):
                        position += 1
                    combined.extend(row)
                combined.extend(self.index[position * _ENTRY.size :])
                if (
                    len(combined) // _ENTRY.size > 50_000
                    or len(combined) + 40 > self.store.index_reservation
                ):
                    raise CacheMiss("index_count")
                pack = _MAGIC + bytes(self.pending)
                pack += hashlib.sha256(pack).digest()
                index = _MAGIC + bytes(combined)
                index += hashlib.sha256(index).digest()
                admitted = len(pack) + len(index) + 16384
                free = shutil.disk_usage(self.store.base).free
                if (
                    free < self.store.disk_bytes + self.store.reserve_bytes
                    or free < self.store.reserve_bytes + admitted
                ):
                    raise CacheMiss("free_floor")
                # No eviction touches canonical/unknown files. Evict only packs
                # already owned by the valid index, publishing omission first.
                if usage + admitted > self.store.disk_bytes or count + 4 > 64:
                    victims = {
                        _ENTRY.unpack_from(self.index, o)[1]
                        for o in range(0, len(self.index), _ENTRY.size)
                    }
                    empty = _MAGIC
                    empty += hashlib.sha256(empty).digest()
                    if count >= 64 or usage + len(empty) + 8192 > self.store.disk_bytes:
                        raise CacheMiss("disk_limit")
                    self.store._publish(self.store.base / "index.idx", empty)
                    for victim in victims:
                        path = self.store.base / (victim.hex() + ".cachepack")
                        if path.exists():
                            self.store._private(path)
                            path.unlink()
                    self.index = b""
                    combined = bytearray().join(incoming)
                    index = _MAGIC + bytes(combined)
                    index += hashlib.sha256(index).digest()
                    usage, count = self.store._usage()
                    if (
                        usage + len(pack) + len(index) + 16384 > self.store.disk_bytes
                        or count + 4 > 64
                    ):
                        raise CacheMiss("disk_limit")
                self.store._publish(
                    owner,
                    json.dumps(
                        {"producer": "crypto-master-dashboard-v1", "roots": roots}
                    ).encode(),
                )
                self.store._publish(
                    self.store.base / (token.hex() + ".cachepack"), pack
                )
                self.store._publish(self.store.base / "index.idx", index)
                self.index = bytes(combined)
            self._acquire_read()
            yield None
        except (OSError, ValueError, CacheMiss, TypeError):
            self.disabled = True
        finally:
            self.pending.clear()
            self.entries.clear()


def _last(
    iterator: Generator[None | bytes, None, None],
) -> Generator[None, None, bytes]:
    data = None
    try:
        for item in iterator:
            if item is None:
                yield None
            else:
                data = item
    finally:
        iterator.close()
    if data is None:
        raise CacheMiss("missing")
    return data
