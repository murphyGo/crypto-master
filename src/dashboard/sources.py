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
        for path, generation in sorted(self.directories.items()):
            digest.update(str(path).encode())
            digest.update(repr(generation).encode())
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
            for entry in entries:
                yield directory / entry.name

    def verify(self) -> None:
        try:
            for source in self.files:
                if Generation.capture(source.path) != source.generation:
                    raise ReadFailure("source_changed")
            # Membership plus per-file checks, never directory mtime alone.
            for path, generation in self.directories.items():
                if Generation.capture(path) != generation:
                    raise ReadFailure("source_changed")
        except FileNotFoundError as exc:
            raise ReadFailure("source_changed") from exc


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
        for path in manifest.entries(base):
            if path.suffix == ".json":
                manifest.add(path, "object")
            elif path.is_dir() and path.name != "archive":
                for child in manifest.entries(path):
                    if child.suffix == ".json":
                        manifest.add(child, "object")
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
