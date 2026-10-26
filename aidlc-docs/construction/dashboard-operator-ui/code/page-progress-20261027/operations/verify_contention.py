"""Offline calculation from retained observation; no application or network calls."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.raw / name for name in (
        "v66-memory-samples.jsonl", "v66-page-observations.jsonl"
    )]
    memory, pages = [
        [json.loads(line) for line in path.read_text().splitlines()] for path in paths
    ]

    def nearest(value):
        target = at(value)
        return min(memory, key=lambda row: abs((at(row["captured_at"]) - target).total_seconds()))

    def interval(start, end):
        first, last = nearest(start), nearest(end)
        seconds = (at(last["captured_at"]) - at(first["captured_at"])).total_seconds()
        assert first["pids"] == last["pids"]
        deltas = {name: round(last["processes"][name]["cpu_seconds"] -
                             first["processes"][name]["cpu_seconds"], 6)
                  for name in ("engine", "dashboard")}
        return {"first": first["captured_at"], "last": last["captured_at"],
                "wall_seconds": seconds, "cpu_seconds_delta": deltas,
                "single_core_fraction": {name: value / seconds for name, value in deltas.items()}}

    failed = [row for row in pages if row["status"] != "complete"]
    complete = [row for row in pages if row["status"] == "complete"]
    result = {
        "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "status_counts": dict(Counter(row["status"] for row in pages)),
        "complete_requests_all_zero_watchers": all(
            row["maximum_background_watchers"] == row["auto_rerun_registrations"] == 0
            and row["script_finished_values"] == [0] for row in complete),
        "failed_request_watchers": [
            {key: row[key] for key in ("started_at", "client", "page", "status",
             "script_finished_values", "maximum_background_watchers", "auto_rerun_registrations")}
            for row in failed
        ],
        "pre_cycle": interval("2026-10-26T16:39:24.107028Z", "2026-10-26T17:08:29.846Z"),
        "cycle_start_to_pre_guard": interval("2026-10-26T17:08:34.849Z", "2026-10-26T17:09:02.271Z"),
        "throttle_interval": interval("2026-10-26T17:09:00.191Z", "2026-10-26T17:09:14.831Z"),
        "interpretation": (
            "No rerender storm is observed. Per-process counters show simultaneous "
            "engine and dashboard CPU demand on the shared guest. They do not profile "
            "functions, include child/observer CPU, identify the exact failed request's "
            "cause, or establish causality for the deployed change. Baseline here means "
            "pre-cycle during the four-session observation, not zero-load idle cost."
        ),
        "follow_up": "Bounded CPU profiling and offline replay before any additional code or capacity change.",
        "rollback": "Not indicated by present evidence: no persistent process failure or observed bounds loss.",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
