"""Tests for the operator runtime-flag loader (DEBT-068(d)).

Covers the fail-safe semantics of :func:`read_trading_freeze`: freeze is
an explicit opt-in, so missing / empty / malformed files all resolve to
"not frozen" without crashing, and a malformed file logs a loud warning.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

from src.runtime.runtime_flags import (
    DEFAULT_RUNTIME_FLAGS_PATH,
    RuntimeFlagsWriteError,
    read_trading_freeze,
    write_trading_freeze,
)

_LOGGER_NAME = "src.runtime.runtime_flags"


@contextmanager
def _capture_warnings(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """Wire caplog onto the module logger (``get_logger`` disables propagation).

    Same pattern as the engine warning-assertion tests in
    ``tests/test_runtime_engine.py`` — the named logger has
    ``propagate=False`` so caplog's root handler never sees the records.
    """
    target_logger = logging.getLogger(_LOGGER_NAME)
    target_logger.addHandler(caplog.handler)
    previous_level = target_logger.level
    target_logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        target_logger.removeHandler(caplog.handler)
        target_logger.setLevel(previous_level)


def test_missing_file_is_not_frozen(tmp_path: Path) -> None:
    """Absent flag file ⇒ not frozen, no warning (absence is normal)."""
    missing = tmp_path / "does_not_exist.yaml"
    assert read_trading_freeze(missing) is False


def test_default_path_constant() -> None:
    """The default path matches the documented config-dir convention."""
    assert DEFAULT_RUNTIME_FLAGS_PATH == Path("config/runtime_flags.yaml")


def test_trading_freeze_true(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("runtime_flags:\n  trading_freeze: true\n", encoding="utf-8")
    assert read_trading_freeze(flags) is True


def test_trading_freeze_false(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("runtime_flags:\n  trading_freeze: false\n", encoding="utf-8")
    assert read_trading_freeze(flags) is False


def test_empty_file_is_not_frozen(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("", encoding="utf-8")
    assert read_trading_freeze(flags) is False


def test_missing_runtime_flags_section_is_not_frozen(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("other: 1\n", encoding="utf-8")
    assert read_trading_freeze(flags) is False


def test_missing_trading_freeze_key_is_not_frozen(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("runtime_flags:\n  other_flag: true\n", encoding="utf-8")
    assert read_trading_freeze(flags) is False


def test_malformed_yaml_warns_and_is_not_frozen(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unparseable YAML ⇒ loud warning, treated as not frozen (no crash)."""
    flags = tmp_path / "runtime_flags.yaml"
    # Unbalanced bracket → yaml.YAMLError.
    flags.write_text("runtime_flags: [oops\n", encoding="utf-8")
    with _capture_warnings(caplog):
        assert read_trading_freeze(flags) is False
    assert any(
        "trading_freeze" in record.getMessage() and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_non_mapping_top_level_warns_and_is_not_frozen(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with _capture_warnings(caplog):
        assert read_trading_freeze(flags) is False
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_non_mapping_runtime_flags_warns_and_is_not_frozen(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("runtime_flags: not_a_mapping\n", encoding="utf-8")
    with _capture_warnings(caplog):
        assert read_trading_freeze(flags) is False
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_non_boolean_trading_freeze_warns_and_is_not_frozen(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-boolean value never silently freezes; warns and stays false."""
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("runtime_flags:\n  trading_freeze: yes_please\n", encoding="utf-8")
    with _capture_warnings(caplog):
        assert read_trading_freeze(flags) is False
    assert any(
        "trading_freeze" in record.getMessage() and record.levelno == logging.WARNING
        for record in caplog.records
    )


# --- DEBT-068(f-2): write_trading_freeze ---


def test_write_then_read_round_trip_true(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    write_trading_freeze(True, flags)
    assert read_trading_freeze(flags) is True


def test_write_then_read_round_trip_false(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    write_trading_freeze(False, flags)
    assert read_trading_freeze(flags) is False


def test_write_creates_missing_parent_dir(tmp_path: Path) -> None:
    flags = tmp_path / "config" / "runtime_flags.yaml"
    assert not flags.parent.exists()
    write_trading_freeze(True, flags)
    assert flags.exists()
    assert read_trading_freeze(flags) is True


def test_write_preserves_other_runtime_flags_keys(tmp_path: Path) -> None:
    """An unrelated key under runtime_flags survives the toggle."""
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text(
        "runtime_flags:\n  other_flag: true\n  trading_freeze: false\n",
        encoding="utf-8",
    )
    write_trading_freeze(True, flags)
    parsed = yaml.safe_load(flags.read_text(encoding="utf-8"))
    assert parsed["runtime_flags"]["other_flag"] is True
    assert parsed["runtime_flags"]["trading_freeze"] is True
    assert read_trading_freeze(flags) is True


def test_write_preserves_other_top_level_keys(tmp_path: Path) -> None:
    """Top-level keys outside runtime_flags are not clobbered."""
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text(
        "some_other_section:\n  nested: 42\nruntime_flags:\n  trading_freeze: false\n",
        encoding="utf-8",
    )
    write_trading_freeze(True, flags)
    parsed = yaml.safe_load(flags.read_text(encoding="utf-8"))
    assert parsed["some_other_section"]["nested"] == 42
    assert parsed["runtime_flags"]["trading_freeze"] is True


def test_write_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    """Atomic write cleans up — only the target file exists afterwards."""
    flags = tmp_path / "runtime_flags.yaml"
    write_trading_freeze(True, flags)
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["runtime_flags.yaml"]


def test_write_into_existing_empty_file(tmp_path: Path) -> None:
    """An empty existing file is the fresh-start case, not a refusal."""
    flags = tmp_path / "runtime_flags.yaml"
    flags.write_text("", encoding="utf-8")
    write_trading_freeze(True, flags)
    assert read_trading_freeze(flags) is True


def test_write_refuses_malformed_existing_file(tmp_path: Path) -> None:
    """Malformed YAML ⇒ refuse (raise), do NOT clobber the operator's file."""
    flags = tmp_path / "runtime_flags.yaml"
    original = "runtime_flags: [oops\n"
    flags.write_text(original, encoding="utf-8")
    with pytest.raises(RuntimeFlagsWriteError):
        write_trading_freeze(True, flags)
    # File left untouched.
    assert flags.read_text(encoding="utf-8") == original


def test_write_refuses_non_mapping_top_level(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    original = "- a\n- b\n"
    flags.write_text(original, encoding="utf-8")
    with pytest.raises(RuntimeFlagsWriteError):
        write_trading_freeze(True, flags)
    assert flags.read_text(encoding="utf-8") == original


def test_write_refuses_non_mapping_runtime_flags_section(tmp_path: Path) -> None:
    flags = tmp_path / "runtime_flags.yaml"
    original = "runtime_flags: not_a_mapping\n"
    flags.write_text(original, encoding="utf-8")
    with pytest.raises(RuntimeFlagsWriteError):
        write_trading_freeze(True, flags)
    assert flags.read_text(encoding="utf-8") == original
