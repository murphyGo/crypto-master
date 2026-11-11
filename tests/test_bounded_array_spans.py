"""Boundary/coverage invariants for bulk JSON object-array scanning."""

import json
import math
import random

import pytest

from src.utils import bounded_read as io


@pytest.mark.parametrize("block", [1, 2, 7, 31, 65536])
@pytest.mark.parametrize("ascii_only", [False, True])
def test_array_preserves_exact_rows_and_block_checkpoints(
    tmp_path, monkeypatch, block, ascii_only
):
    rng = random.Random(83)
    alphabet = ["plain", "한글🙂", '\\"{}[],', "\n\r\t", "\\" * 17, '"' * 11]
    rows = [
        {
            "n": n,
            "nested": [{"text": rng.choice(alphabet), "values": [None, True, n / 10]}],
            "empty": {},
            "padding": "x" * rng.randrange(1, 180),
        }
        for n in range(20)
    ]
    encoded = [
        json.dumps(row, ensure_ascii=ascii_only, indent=1).encode() for row in rows
    ]
    content = b" \n[\t" + b",\r\n ".join(encoded) + b" ] \r\n"
    path = tmp_path / "rows.json"
    path.write_bytes(content)
    monkeypatch.setattr(io, "BLOCK_BYTES", block)
    output = list(io.json_array_bytes(path, io.Generation.capture(path)))
    assert [row for row in output if row is not None] == encoded
    assert output.count(None) == math.ceil(len(content) / block)
    assert json.loads(content) == rows


@pytest.mark.parametrize("padding", [0, 1, 15, 31, 63])
@pytest.mark.parametrize("text", ["a" * 90, "\\" * 41, '"\\\n🙂' * 25])
def test_record_limit_spans_fast_and_escaped_strings(
    tmp_path, monkeypatch, padding, text
):
    row = json.dumps({"text": text, "nested": {"n": 1}}, ensure_ascii=False).encode()
    path = tmp_path / "rows.json"
    path.write_bytes(b" " * padding + b"[" + row + b"]")
    monkeypatch.setattr(io, "BLOCK_BYTES", 32)
    generation = io.Generation.capture(path)
    assert [
        part
        for part in io.json_array_bytes(path, generation, record_bytes=len(row))
        if part is not None
    ] == [row]
    with pytest.raises(io.ReadFailure, match="record_too_large"):
        list(io.json_array_bytes(path, generation, record_bytes=len(row) - 1))


@pytest.mark.parametrize(
    "damaged",
    [
        b'{"text":"bad\x01control"}',
        b'{"text":"bad\\q"}',
        b'{"text":"\xff"}',
        b'{"nested":[1,2}}',
    ],
)
def test_fast_string_scan_still_requires_full_json_validation(tmp_path, damaged):
    path = tmp_path / "rows.json"
    path.write_bytes(b"[" + damaged + b',{"ok":true}]')
    with pytest.raises(io.ReadFailure, match="malformed_json"):
        list(io.json_array_records(path, io.Generation.capture(path)))


@pytest.mark.parametrize("mutation", ["append", "truncate", "replace"])
def test_source_change_after_completed_rows_is_not_complete(
    tmp_path, monkeypatch, mutation
):
    path = tmp_path / "rows.json"
    content = b'[{"n":1},{"padding":"' + b"x" * 200 + b'"}]'
    path.write_bytes(content)
    monkeypatch.setattr(io, "BLOCK_BYTES", 32)
    reader = io.json_array_bytes(path, io.Generation.capture(path))
    assert next(reader) == b'{"n":1}'
    assert next(reader) is None
    if mutation == "append":
        with path.open("ab") as handle:
            handle.write(b" ")
    elif mutation == "truncate":
        path.write_bytes(b"[]")
    else:
        replacement = tmp_path / "new.json"
        replacement.write_bytes(content)
        replacement.replace(path)
    with pytest.raises(io.ReadFailure, match="source_changed"):
        list(reader)


@pytest.mark.parametrize("text", ["x" * (512 * 1024), "\\" * (256 * 1024)])
def test_large_record_keeps_exact_limit_across_many_default_blocks(tmp_path, text):
    row = json.dumps({"text": text, "tail": {"n": 1}}).encode()
    path = tmp_path / "rows.json"
    path.write_bytes(b"[" + row + b', {"last":true}]')
    generation = io.Generation.capture(path)
    assert [
        part
        for part in io.json_array_bytes(path, generation, record_bytes=len(row))
        if part is not None
    ] == [row, b'{"last":true}']
    with pytest.raises(io.ReadFailure, match="record_too_large"):
        list(io.json_array_bytes(path, generation, record_bytes=len(row) - 1))
