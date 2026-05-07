"""Tests for the ops diagnostics dashboard page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.dashboard.pages.ops import (
    build_ops_diagnostic_dataframe,
    build_ops_diagnostic_rows,
)

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


def test_build_ops_diagnostic_rows_reports_data_and_activity(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime"
    runtime_dir.mkdir(parents=True)
    activity = runtime_dir / "activity.jsonl"
    activity.write_text("{}\n", encoding="utf-8")
    now = datetime.fromtimestamp(activity.stat().st_mtime, tz=timezone.utc)

    rows = build_ops_diagnostic_rows(
        data_dir=data_dir,
        activity_path=activity,
        health_url="",
        now=now,
    )

    assert [row.check for row in rows] == [
        "Data directory",
        "Activity log",
        "Health endpoint",
    ]
    assert rows[0].status == "pass"
    assert rows[1].status == "pass"
    assert rows[2].status == "watch"


def test_build_ops_diagnostic_rows_uses_health_checker(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    rows = build_ops_diagnostic_rows(
        data_dir=data_dir,
        activity_path=data_dir / "runtime" / "activity.jsonl",
        health_url="https://example.test/_stcore/health",
        health_checker=lambda _url: (True, "HTTP 200"),
    )

    assert rows[-1].check == "Health endpoint"
    assert rows[-1].status == "pass"
    assert rows[-1].detail == "HTTP 200"


def test_build_ops_diagnostic_dataframe_empty_has_columns() -> None:
    df = build_ops_diagnostic_dataframe([])

    assert df.empty
    assert list(df.columns) == ["Check", "Status", "Detail", "Next Step"]


def test_app_runs_with_ops_page_registered() -> None:
    at = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
