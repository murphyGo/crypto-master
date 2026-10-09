"""Bounded persistence parsing and damaged/source-change coverage."""

import json
from pathlib import Path

import pytest

from src.utils import bounded_read as io


def records(reader, path: Path, **kwargs):
    return [
        value
        for value in reader(path, io.Generation.capture(path), **kwargs)
        if value is not None
    ]


@pytest.mark.parametrize("block", [1, 2, 3, 7, 64])
def test_array_utf8_nested_escaped_and_whitespace(tmp_path, monkeypatch, block):
    monkeypatch.setattr(io, "BLOCK_BYTES", block)
    values = [{"text": '한글🙂\\"[,{}]', "nested": [{"x": [1, None, True]}]}, {"n": 2}]
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    assert records(io.json_array_records, path) == values


@pytest.mark.parametrize(
    "raw",
    ["[{},]", "[{} {}]", "[] false", "{}", "[1]", "[{]}", "[{}", '[{"s":"unterminated'],
)
def test_array_damage_is_explicit(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    with pytest.raises(io.ReadFailure):
        records(io.json_array_records, path)


def test_array_total_exceeds_record_budget(tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_text(json.dumps([{"n": n} for n in range(1000)]))
    monkeypatch.setattr(io, "BLOCK_BYTES", 13)
    assert len(records(io.json_array_records, path, record_bytes=32)) == 1000


@pytest.mark.parametrize(
    "reader,raw",
    [
        (io.json_array_records, '[{"payload":"' + "a" * 1000 + '"}]'),
        (io.jsonl_records, '{"payload":"' + "a" * 1000 + '"}\n'),
        (io.json_object, '{"payload":"' + "a" * 1000 + '"}'),
    ],
)
def test_oversize_is_rejected_before_json_decode(tmp_path, monkeypatch, reader, raw):
    path = tmp_path / "large"
    path.write_text(raw)
    monkeypatch.setattr(io, "BLOCK_BYTES", 17)
    monkeypatch.setattr(io.json, "loads", lambda _: pytest.fail("oversize decoded"))
    with pytest.raises(io.ReadFailure, match="record_too_large"):
        records(reader, path, record_bytes=64)


def test_jsonl_partial_append_and_invalid_lines_do_not_certify_empty(tmp_path):
    path = tmp_path / "log"
    path.write_text('{"n":1}\n{"n":2}')
    with pytest.raises(io.ReadFailure, match="partial_record"):
        records(io.jsonl_records, path)
    path.write_text('bad\n{"n":2}\n')
    with pytest.raises(io.ReadFailure, match="malformed_json"):
        records(io.jsonl_records, path)


def test_replacement_during_captured_prefix_read_is_rejected(tmp_path):
    path = tmp_path / "log"
    path.write_text('{"n":1}\n')
    iterator = io.jsonl_records(path, io.Generation.capture(path))
    assert next(iterator) == {"n": 1}
    replacement = tmp_path / "replacement"
    replacement.write_text('{"n":2}\n')
    replacement.replace(path)
    with pytest.raises(io.ReadFailure, match="source_changed"):
        list(iterator)


def test_jsonl_large_multibyte_record_split_at_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "BLOCK_BYTES", 19)
    path = tmp_path / "log"
    values = [{"text": "한글" * 500}, {"n": 2}]
    path.write_text(
        "\n".join(json.dumps(value, ensure_ascii=False) for value in values) + "\n",
        encoding="utf-8",
    )
    assert records(io.jsonl_records, path) == values


@pytest.mark.parametrize("block", [1, 2, 7, 64])
def test_reverse_jsonl_has_exact_forward_order_and_offsets(
    tmp_path, monkeypatch, block
):
    monkeypatch.setattr(io, "BLOCK_BYTES", block)
    path = tmp_path / "log"
    values = [{"text": "한글" * 200}, {"n": 2}, {"n": 3}]
    path.write_text(
        "\n\n".join(json.dumps(value, ensure_ascii=False) for value in values) + "\n",
        encoding="utf-8",
    )
    reversed_rows = records(io.reverse_jsonl_records, path)
    offsets = [row.pop("_offset") for row in reversed_rows]
    assert reversed_rows == list(reversed(values))
    assert offsets == sorted(offsets, reverse=True)
