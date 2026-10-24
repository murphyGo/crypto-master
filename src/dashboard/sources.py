"""Read-only bounded discovery using the existing on-disk layout."""

from __future__ import annotations

import hashlib
import os
import re
import struct
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from src.dashboard.read_models import Limits, Query
from src.utils.bounded_read import Generation, ReadFailure


@dataclass(frozen=True, slots=True)
class Source:
    directory: Path
    name: str
    generation: Generation
    format: str
    account: str = ""

    @property
    def path(self) -> Path:
        return self.directory / self.name


class Manifest:
    def __init__(self, limits: Limits, base: Path) -> None:
        self.limits = limits
        self.base = base
        self.bytes = 0
        self._files: list[bytes] = []
        self.directories: dict[Path, Generation] = {}

    @property
    def files(self) -> Iterator[Source]:
        yield from self._sources(self._files)

    @property
    def reverse_files(self) -> Iterator[Source]:
        yield from self._sources(reversed(self._files))

    @property
    def file_count(self) -> int:
        return len(self._files)

    def _sources(self, entries: Iterable[bytes]) -> Iterator[Source]:
        formats = {b"l": "jsonl", b"o": "object", b"a": "array"}
        for packed in entries:
            relative, account, metadata = packed.split(b"\0", 2)
            path = self.base / relative.decode()
            generation = Generation(*struct.unpack("!QQQQ", metadata[:32]))
            yield Source(
                path.parent,
                path.name,
                generation,
                formats[metadata[32:]],
                account.decode(),
            )

    def sort(self) -> None:
        # Paths precede NUL and fixed-size generation metadata, so byte order
        # preserves legacy relative-path order without a second key list.
        self._files.sort()

    def digest(self) -> str:
        digest = hashlib.sha256()
        for packed in self._files:
            digest.update(len(packed).to_bytes(4, "big"))
            digest.update(packed)
        # Discovery captures the exact selected membership every time. An
        # unrelated sibling or atomic-write temporary file can change a
        # directory's metadata without changing these inputs. Directories
        # still participate in verify() to reject changes during this read.
        return digest.hexdigest()

    def charge(self, path: Path) -> None:
        # Source keeps a shared parent and basename; account conservatively
        # for its slots, generation integers, name and sorting references.
        self.bytes += 512 + 2 * len(path.name.encode())
        if self.bytes > self.limits.manifest_bytes:
            raise ReadFailure("manifest_budget_exhausted")

    def add(self, path: Path, format: str, account: str = "") -> None:
        if not path.is_file():
            return
        generation = Generation.capture(path)
        packed = (
            str(path.relative_to(self.base)).encode()
            + b"\0"
            + account.encode()
            + b"\0"
            + struct.pack(
                "!QQQQ",
                generation.device,
                generation.inode,
                generation.size,
                generation.mtime_ns,
            )
            + {"jsonl": b"l", "object": b"o", "array": b"a"}[format]
        )
        self.bytes += sys.getsizeof(packed) + 32  # list over-allocation/sort scratch
        if self.bytes > self.limits.manifest_bytes:
            raise ReadFailure("manifest_budget_exhausted")
        self._files.append(packed)

    def entries(self, directory: Path) -> Iterator[Path]:
        for entry in self.scan(directory):
            yield directory / entry.name

    def scan(self, directory: Path) -> Iterator[os.DirEntry[str]]:
        if not directory.is_dir():
            ancestor = directory.parent
            while not ancestor.is_dir() and ancestor != ancestor.parent:
                ancestor = ancestor.parent
            if ancestor.is_dir() and ancestor not in self.directories:
                self.charge(ancestor)
                self.directories[ancestor] = Generation.capture(ancestor)
            return
        if directory not in self.directories:
            self.charge(directory)
            self.directories[directory] = Generation.capture(directory)
        # At most the parent and one child iterator are open during proposal
        # discovery; names are not accumulated in another unbounded list.
        with os.scandir(directory) as entries:
            yield from entries

    def add_entry(self, entry: os.DirEntry[str], *, prefix: bytes = b"") -> None:
        """Capture proposal metadata once without per-member Path objects."""
        if not entry.is_file():
            return
        try:
            stat = entry.stat()
        except FileNotFoundError as exc:
            raise ReadFailure("source_changed") from exc
        packed = (
            prefix
            + entry.name.encode()
            + b"\0\0"
            + struct.pack(
                "!QQQQ", stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
            )
            + b"o"
        )
        self.bytes += sys.getsizeof(packed) + 32
        if self.bytes > self.limits.manifest_bytes:
            raise ReadFailure("manifest_budget_exhausted")
        self._files.append(packed)

    def verify(self) -> None:
        descriptor = None
        try:
            if self._files and os.stat in os.supports_dir_fd:
                descriptor = os.open(
                    self.base, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                )
                for packed in self._files:
                    relative, _account, metadata = packed.split(b"\0", 2)
                    stat = os.stat(relative, dir_fd=descriptor)
                    current = struct.pack(
                        "!QQQQ",
                        stat.st_dev,
                        stat.st_ino,
                        stat.st_size,
                        stat.st_mtime_ns,
                    )
                    if current != metadata[:32]:
                        raise ReadFailure("source_changed")
            else:
                for source in self.files:
                    if Generation.capture(source.path) != source.generation:
                        raise ReadFailure("source_changed")
            # Membership plus per-file checks, never directory mtime alone.
            for path, generation in self.directories.items():
                if Generation.capture(path) != generation:
                    raise ReadFailure("source_changed")
        except FileNotFoundError as exc:
            raise ReadFailure("source_changed") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)


def discover(query: Query, limits: Limits, retention: int) -> Manifest:
    source = query.source
    if query.kind == "audit":
        source = source or query.root / "audit" / "feedback.jsonl"
    if query.kind == "promotion":
        source = source or query.root / "feedback" / "promotion_lab"
    base_directory = (
        (source or query.root / "runtime" / "activity.jsonl").parent
        if query.kind in {"activity", "audit"}
        else (
            source or query.root / "proposals"
            if query.kind == "proposals"
            else (
                source or query.root / "feedback" / "state"
                if query.kind in {"candidates", "promotion"}
                else query.root
            )
        )
    )
    manifest = Manifest(limits, base_directory)
    if len(query.accounts) > limits.accounts:
        raise ReadFailure("account_budget_exhausted")
    if query.kind in {"activity", "audit"}:
        base = source or query.root / "runtime" / "activity.jsonl"
        base = base.with_suffix("") if base.suffix == ".jsonl" else base
        pattern = re.compile(re.escape(base.name) + r"\.\d{4}-\d{2}\.jsonl$")
        rotated: list[Path] = []
        for path in manifest.entries(base.parent):
            if pattern.fullmatch(path.name):
                rotated.append(path)
                rotated.sort()
                rotated = rotated[-retention:]
        legacy = base.with_name(base.name + ".jsonl")
        manifest.add(legacy, "jsonl")
        for path in rotated[-retention:]:
            manifest.add(path, "jsonl")
    elif query.kind == "proposals":
        base = query.source or query.root / "proposals"
        for entry in manifest.scan(base):
            if entry.name.endswith(".json") and entry.name != ".json":
                manifest.add_entry(entry)
            elif entry.is_dir() and entry.name != "archive":
                prefix = entry.name.encode() + b"/"
                for child in manifest.scan(base / entry.name):
                    if child.name.endswith(".json") and child.name != ".json":
                        manifest.add_entry(child, prefix=prefix)
        manifest.sort()
    elif query.kind in {"ledger", "snapshots"}:
        store = "trades" if query.kind == "ledger" else "portfolio"
        name = "trades.json" if query.kind == "ledger" else "snapshots.json"
        for account in query.accounts:
            directory = query.root / store / query.mode / account
            # Drain discovery for directory generation capture, without
            # retaining unrelated names.
            for _path in manifest.entries(directory):
                pass
            manifest.add(directory / name, "array", account)
    elif query.kind in {"candidates", "promotion"}:
        directory = source or query.root / "feedback" / "state"
        for path in manifest.entries(directory):
            if path.suffix == ".json":
                manifest.add(path, "object")
    else:
        raise ReadFailure("unknown_query")
    return manifest
