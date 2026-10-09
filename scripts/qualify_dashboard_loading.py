"""Offline query qualification; never writes into the supplied runtime root.

This reports query completion and process RSS, not browser/guest/engine
acceptance. Generated fixtures require a separate --fixture-root path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.dashboard import app as dashboard_app
from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Query


def generate(root: Path) -> None:
    if root.exists():
        raise ValueError("Fixture destination must be new")
    directory = root / "runtime"
    directory.mkdir(parents=True)
    types = ["monitor_pass"] * 10 + [
        "proposal_generated",
        "proposal_accepted",
        "proposal_rejected",
        "position_opened",
        "position_closed",
        "sleeping",
        "scan_errored",
        "notification_failed",
        "correlation_warning",
        "risk_cap_advisory",
    ]
    origin = datetime.now(timezone.utc) - timedelta(seconds=999_999 * 24)
    for month in range(1, 11):
        with (directory / f"activity.2026-{month:02d}.jsonl").open("w") as handle:
            for index in range(100_000):
                serial = (month - 1) * 100_000 + index
                cycle = serial // 100
                typ = (
                    "cycle_started"
                    if index % 100 == 0
                    else (
                        "cycle_completed"
                        if index % 100 == 99
                        else types[index % len(types)]
                    )
                )
                # Many independent cycles/accounts, variable payload sizes,
                # stale-quote and advisory shapes, real lifetime counters.
                details = {
                    "sub_account_id": f"account-{cycle % 4}",
                    "symbol": ["BTC/USDT", "ETH/USDT", "SOL/USDT"][serial % 3],
                    "proposal_id": f"proposal-{serial}",
                    "advisory": typ == "risk_cap_advisory",
                    "reason": (
                        "stale_quote_no_live_data"
                        if typ == "proposal_rejected" and serial % 11 == 0
                        else "test_observation"
                    ),
                    "context": "x" * [80, 200, 800][serial % 3],
                }
                at = origin + timedelta(seconds=serial * 24)
                event = {
                    "timestamp": at.isoformat(),
                    "event_type": typ,
                    "cycle_id": f"cycle-{cycle}",
                    "message": typ,
                    "details": details,
                }
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def rss_peak() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024 if platform.system() == "Darwin" else 1024)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--accounts", nargs="+", default=["default"])
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument(
        "--kinds",
        nargs="+",
        default=["activity", "proposals", "ledger", "snapshots", "candidates"],
    )
    args = parser.parse_args()
    if args.fixture_root:
        from src.config import get_settings

        if args.fixture_root.resolve().is_relative_to(
            get_settings().data_dir.resolve()
        ):
            raise ValueError("Fixture generation cannot use runtime data directories")
        generate(args.fixture_root)
    baseline_rss = (
        float(
            subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(os.getpid())]
            ).strip()
        )
        / 1024
    )
    output: dict[str, Any] = {
        "method": "offline shared-service query completion; warmed imports; no browser or guest claim",
        "python": platform.python_version(),
        "streamlit": dashboard_app.st.__version__,
        "platform": platform.platform(),
        "baseline_rss_mib": baseline_rss,
        "series": [],
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                *Path("src/dashboard").rglob("*.py"),
                Path("src/utils/bounded_read.py"),
                Path(__file__),
            ]
        },
    }
    for kind in args.kinds:
        cold, warm, revalidate = [], [], []
        statuses = []
        coverage: dict[str, Any] = {}
        for sample in range(args.samples):
            service = DashboardDataService()
            query = Query(args.root, kind, accounts=tuple(args.accounts))
            try:
                start = time.monotonic()
                result = service.request(query)
                while result.status == "pending" and time.monotonic() - start < 120:
                    result = service.request(query, wait=0.05)
                cold.append(time.monotonic() - start)
                statuses.append(
                    result.status + (":" + result.reason if result.reason else "")
                )
                if result.complete:
                    data = result.data()
                    coverage = {
                        **data.get("source_coverage", {}),
                        "activity_events": data.get("total"),
                    }
                start = time.monotonic()
                service.request(query)
                warm.append(time.monotonic() - start)
                # Expire only the result epoch; exercise verified source
                # generation reuse without sleeping 2s per sample.
                with service._condition:
                    for entry in service._cache.values():
                        entry.evaluated -= 3
                start = time.monotonic()
                rebuilt = service.request(query)
                revalidate.append(time.monotonic() - start)
                if not rebuilt.complete:
                    statuses.append(
                        "revalidate:" + rebuilt.status + ":" + rebuilt.reason
                    )
            finally:
                service.close()
            print(
                json.dumps(
                    {
                        "kind": kind,
                        "sample": sample + 1,
                        "cold_seconds": cold[-1],
                        "status": statuses[-1],
                    }
                ),
                flush=True,
            )

        def p95(values: list[float]) -> float:
            return sorted(values)[max(0, int(len(values) * 0.95 + 0.999999) - 1)]

        output["series"].append(
            {
                "kind": kind,
                "samples": args.samples,
                "statuses": statuses,
                "cold_seconds": cold,
                "warm_seconds": warm,
                "revalidate_seconds": revalidate,
                "cold_p95": p95(cold),
                "warm_p95": p95(warm),
                "revalidate_p95": p95(revalidate),
                "cold_median": statistics.median(cold),
                "process_peak_rss_mib": rss_peak(),
                "coverage": coverage,
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
