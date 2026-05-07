"""Operations diagnostics dashboard page.

Checks local runtime data freshness and an optional deployed health URL.

Related Requirements:
- FR-032 / NFR-003: Streamlit dashboard
- NFR-007: Trading history storage
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.runtime.activity_log import ActivityLog
from src.utils.time import ensure_utc, now_utc

DEFAULT_STALE_AFTER_MINUTES = 15
DEFAULT_HEALTH_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class OpsDiagnosticRow:
    """One operations diagnostic row."""

    check: str
    status: str
    detail: str
    next_step: str


def build_ops_diagnostic_rows(
    *,
    data_dir: Path,
    activity_path: Path,
    health_url: str = "",
    now: datetime | None = None,
    stale_after_minutes: int = DEFAULT_STALE_AFTER_MINUTES,
    health_checker: Callable[[str], tuple[bool, str]] | None = None,
) -> list[OpsDiagnosticRow]:
    """Build operations diagnostics from local paths and optional health URL."""
    current = ensure_utc(now or now_utc())
    rows = [
        _path_row("Data directory", data_dir, "Check mounted data volume"),
        _activity_row(activity_path, current, stale_after_minutes),
    ]
    if health_url.strip():
        checker = health_checker or check_health_url
        ok, detail = checker(health_url.strip())
        rows.append(
            OpsDiagnosticRow(
                check="Health endpoint",
                status="pass" if ok else "stop",
                detail=detail,
                next_step=(
                    "Monitor deployed health" if ok else "Check deployed runtime health"
                ),
            )
        )
    else:
        rows.append(
            OpsDiagnosticRow(
                check="Health endpoint",
                status="watch",
                detail="not configured",
                next_step="Provide health URL",
            )
        )
    return rows


def build_ops_diagnostic_dataframe(rows: list[OpsDiagnosticRow]) -> pd.DataFrame:
    """Build the operations diagnostics table."""
    columns = ["Check", "Status", "Detail", "Next Step"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Check": row.check,
                "Status": row.status,
                "Detail": row.detail,
                "Next Step": row.next_step,
            }
            for row in rows
        ],
        columns=columns,
    )


def check_health_url(
    health_url: str,
    *,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
) -> tuple[bool, str]:
    """Probe a deployed health URL using the standard library."""
    try:
        with urlopen(health_url, timeout=timeout_seconds) as response:  # noqa: S310
            status = getattr(response, "status", None) or response.getcode()
    except (OSError, URLError) as exc:
        return False, f"request failed: {exc}"
    return 200 <= int(status) < 400, f"HTTP {status}"


def render() -> None:
    """Render the Ops Diagnostics page."""
    st.title("Ops Diagnostics")
    st.caption("Runtime data freshness and optional deployed health checks.")

    settings = get_settings()
    activity_log = ActivityLog(data_dir=settings.data_dir)
    health_url = st.text_input(
        "Health URL",
        value=_query_param_first("health_url") or "",
        placeholder="https://crypto-master.fly.dev/_stcore/health",
    )
    rows = build_ops_diagnostic_rows(
        data_dir=settings.data_dir,
        activity_path=activity_log.path,
        health_url=health_url,
    )
    st.dataframe(
        build_ops_diagnostic_dataframe(rows),
        hide_index=True,
        use_container_width=True,
    )


def _path_row(check: str, path: Path, next_step: str) -> OpsDiagnosticRow:
    return OpsDiagnosticRow(
        check=check,
        status="pass" if path.exists() else "stop",
        detail=str(path),
        next_step="Monitor path" if path.exists() else next_step,
    )


def _activity_row(
    activity_path: Path,
    now: datetime,
    stale_after_minutes: int,
) -> OpsDiagnosticRow:
    latest = _latest_activity_file(activity_path)
    if latest is None:
        return OpsDiagnosticRow(
            check="Activity log",
            status="watch",
            detail=f"missing near {activity_path}",
            next_step="Check engine activity writer",
        )
    modified_at = datetime.fromtimestamp(latest.stat().st_mtime, tz=now.tzinfo)
    age = now - ensure_utc(modified_at)
    status = "watch" if age > timedelta(minutes=stale_after_minutes) else "pass"
    return OpsDiagnosticRow(
        check="Activity log",
        status=status,
        detail=f"{latest} updated {int(age.total_seconds())}s ago",
        next_step="Monitor activity log" if status == "pass" else "Check engine loop",
    )


def _latest_activity_file(activity_path: Path) -> Path | None:
    candidates = [activity_path] if activity_path.exists() else []
    candidates.extend(activity_path.parent.glob("activity*.jsonl"))
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _query_param_first(name: str) -> str | None:
    raw = st.query_params.get(name)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


__all__ = [
    "OpsDiagnosticRow",
    "build_ops_diagnostic_dataframe",
    "build_ops_diagnostic_rows",
    "check_health_url",
    "render",
]
