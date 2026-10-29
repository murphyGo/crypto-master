"""Read-only four-session dashboard protocol observer, not native acceptance.

Run only under the operator's production-observation authorization. Importing
this module performs no filesystem, network, subprocess or descriptor reads.
The default endpoint/machine and admission/drain guards match the v64 observer.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import re
import shlex
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ELEMENT_KINDS = ("metric", "dataframe", "table", "vega_lite_chart", "exception")
METRIC_LABELS = {
    "Home": frozenset(
        {
            "Runtime safety",
            "Last cycle",
            "Open positions",
            "Snapshot",
            "Mode",
            "Scope",
            "Sub-accounts",
            "Actionable events",
            "Candidates",
            "Awaiting approval",
            "Promoted",
            "Errored",
        }
    ),
    "Trading": frozenset(
        {
            "Current Equity",
            "Open Positions",
            "Closed Trades",
            "Win Rate",
            "Realized P&L",
            "Proposals rejected (threshold)",
        }
    ),
}
ELEMENT_COUNTS = {
    "Home": dict(zip(ELEMENT_KINDS, (12, 4, 0, 0, 0), strict=True)),
    "Trading": dict(zip(ELEMENT_KINDS, (6, 3, 0, 1, 0), strict=True)),
}
ALERT_SECTIONS = {
    "Runtime safety and activity": "activity",
    "Runtime reconciliation": "activity",
    "Trade ledger": "ledger",
    "Portfolio snapshots": "snapshots",
    "Candidate evidence": "candidates",
    "24h proposal funnel": "proposals",
    "Threshold rejections": "proposals",
}


def classify_alert(body: str) -> dict[str, str | bool]:
    """Return finite classifications only; never retain an arbitrary alert body."""
    lowered = body.lower()
    if "loading in the background" in lowered:
        category = "pending"
    elif "current data is unavailable" in lowered:
        category = "stale"
    elif "data could not be verified" in lowered:
        category = "unavailable"
    else:
        category = "other"
    return {
        "section": ALERT_SECTIONS.get(body.partition(":")[0].strip(), "unknown"),
        "category": category,
        "incomplete": category != "other",
    }


def element_counts(elements: dict) -> dict[str, int]:
    return {
        kind: sum(row["kind"] == kind for row in elements.values())
        for kind in ELEMENT_KINDS
    }


def complete_data(page: str, elements: dict) -> bool:
    """Pinned default aggregate page shape, not a table-cell or native oracle."""
    if page not in METRIC_LABELS:
        return False
    metrics = [row for row in elements.values() if row["kind"] == "metric"]
    return (
        element_counts(elements) == ELEMENT_COUNTS[page]
        and len(metrics) == len(METRIC_LABELS[page])
        and {row.get("label") for row in metrics} == METRIC_LABELS[page]
        and all(row.get("placeholder") is False for row in metrics)
        and not any(row.get("incomplete", False) for row in elements.values())
    )


def reconcile_requests(starts: list[dict], outcomes: list[dict]) -> dict:
    def keys(rows):
        return Counter((row["started_at"], row["client"], row["page"]) for row in rows)

    expected, actual = keys(starts), keys(outcomes)
    return {
        "starts": len(starts),
        "outcomes": len(outcomes),
        "unmatched_starts": sum((expected - actual).values()),
        "unmatched_outcomes": sum((actual - expected).values()),
        "duplicate_starts": sum(count - 1 for count in expected.values()),
        "duplicate_outcomes": sum(count - 1 for count in actual.values()),
        "status_counts": dict(Counter(row["status"] for row in outcomes)),
        "bijective": expected == actual
        and all(count == 1 for count in expected.values()),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New task-owned directory; an existing directory is refused.",
    )
    value.add_argument(
        "--descriptor",
        type=Path,
        default=Path("/private/tmp/crypto-master-ui-protocol-20261025.pb"),
    )
    value.add_argument("--seconds", type=int, default=600)
    value.add_argument("--max-seconds", type=int, default=2100)
    value.add_argument("--phase", default="after")
    value.add_argument("--cadence", type=float, default=5)
    return value


def prepare_output(options: argparse.Namespace) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", options.phase):
        raise ValueError(
            "phase must contain only letters, digits, hyphens or underscores"
        )
    if options.seconds <= 0 or options.max_seconds < options.seconds:
        raise ValueError("durations must be positive and max-seconds >= seconds")
    if not math.isfinite(options.cadence) or options.cadence <= 0:
        raise ValueError("cadence must be finite and positive")
    options.output_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    return options.output_dir


args: argparse.Namespace
OUT: Path
Back = Forward = None
pages: dict[str, str] = {}
stop = asyncio.Event()
admission_closed = asyncio.Event()
tracking = False
reason: list[str] = []
observations: list[dict] = []
warmup_observations: list[dict] = []
health: list[dict] = []
memory: list[dict] = []
cycles: dict = {}


def append_jsonl(suffix: str, row: dict) -> None:
    with (OUT / f"{args.phase}-{suffix}.jsonl").open("a") as handle:
        handle.write(json.dumps(row) + "\n")


class Client:
    def __init__(self, identifier):
        self.identifier = identifier
        self.ws = None
        self._record = {}
        self._started = 0.0
        self._reconnect_after_timeout = False

    async def __aenter__(self):
        await self._connect()
        return self

    async def _connect(self):
        import websockets

        self.ws = await websockets.connect(
            "wss://crypto-master.fly.dev/_stcore/stream",
            origin="https://crypto-master.fly.dev",
            subprotocols=["streamlit"],
            max_size=16 * 1024 * 1024,
            open_timeout=20,
        )

    async def __aexit__(self, *exc):
        await self.ws.close()

    async def send(self, page_hash="", fragment=""):
        message = Back()
        message.rerun_script.SetInParent()
        message.rerun_script.page_script_hash = page_hash
        if fragment:
            message.rerun_script.fragment_id = fragment
            message.rerun_script.is_auto_rerun = True
        await self.ws.send(message.SerializeToString())

    async def view(self, page, timeout=60):
        self._started = time.monotonic()
        observed = tracking
        row = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "client": self.identifier,
            "page": page,
            "status": "started",
        }
        self._record = row
        prefix = "" if observed else "warmup-"
        append_jsonl(prefix + "page-starts", row)
        try:
            row["reconnected_after_timeout"] = self._reconnect_after_timeout
            if self._reconnect_after_timeout:
                # A timed-out run can still have responses queued. Close it
                # before opening the replacement; never reuse that queue for
                # another page or have more than four connected clients.
                # Reconnect time is included in this request's elapsed time.
                await self.ws.close()
                await self._connect()
                self._reconnect_after_timeout = False
            await self._view(page, timeout)
            self._reconnect_after_timeout = row["status"] == "timeout"
            return row
        except asyncio.CancelledError:
            row.update(
                status=(
                    "cancelled_after_guard_stop"
                    if stop.is_set()
                    else "cancelled_at_observation_boundary"
                ),
                seconds=time.monotonic() - self._started,
            )
            raise
        except Exception as error:
            row.update(
                status="request_failed",
                reason=type(error).__name__,
                seconds=time.monotonic() - self._started,
            )
            raise
        finally:
            (observations if observed else warmup_observations).append(row)
            append_jsonl(prefix + "page-observations", row)

    async def _view(self, page, timeout=60):
        page_hash = pages.get(page, "")
        elements, fragments, alert_history = {}, {}, {}
        messages = max_watchers = auto_reruns = 0
        finished = []
        row = self._record
        row.update(
            status="timeout",
            first_incomplete_shell_seconds=None,
            first_incomplete_script_finished_seconds=None,
        )
        try:
            await self.send(page_hash)
            while time.monotonic() - self._started < timeout and not stop.is_set():
                try:
                    raw = await asyncio.wait_for(self.ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    for frag, due in list(fragments.items()):
                        if now >= due:
                            await self.send(page_hash, frag)
                            fragments[frag] = now + 0.5
                    continue
                if isinstance(raw, str):
                    continue
                message = Forward.FromString(raw)
                messages += 1
                kind = message.WhichOneof("type")
                if kind == "navigation":
                    for item in message.navigation.app_pages:
                        pages[item.page_name] = item.page_script_hash
                elif kind == "new_session":
                    for item in message.new_session.app_pages:
                        pages[item.page_name] = item.page_script_hash
                    if not message.new_session.fragment_ids_this_run:
                        elements.clear()
                        fragments.clear()
                elif kind == "auto_rerun":
                    fragments[message.auto_rerun.fragment_id] = (
                        time.monotonic() + message.auto_rerun.interval
                    )
                    auto_reruns += 1
                    max_watchers = max(max_watchers, len(fragments))
                elif kind == "stop_auto_rerun":
                    fragments.clear()
                elif (
                    kind == "delta"
                    and message.delta.WhichOneof("type") == "new_element"
                ):
                    element = message.delta.new_element
                    element_kind = element.WhichOneof("type")
                    element_kind = {
                        "arrow_data_frame": "dataframe",
                        "arrow_vega_lite_chart": "vega_lite_chart",
                    }.get(element_kind, element_kind)
                    value = {"kind": element_kind}
                    if element_kind == "metric":
                        label = element.metric.label
                        if (
                            label
                            not in METRIC_LABELS["Home"] | METRIC_LABELS["Trading"]
                        ):
                            label = "unknown"
                        value.update(
                            label=label,
                            value_sha256=hashlib.sha256(
                                element.metric.body.encode()
                            ).hexdigest(),
                            placeholder=element.metric.body.strip() in ("", "—", "-"),
                        )
                    if element_kind == "alert":
                        classification = classify_alert(element.alert.body)
                        value.update(classification)
                        offset = time.monotonic() - self._started
                        alert_history.setdefault(
                            (classification["section"], classification["category"]),
                            {**classification, "first_seen_seconds": offset},
                        )
                        if (
                            classification["incomplete"]
                            and row["first_incomplete_shell_seconds"] is None
                        ):
                            row["first_incomplete_shell_seconds"] = offset
                    elements[tuple(message.metadata.delta_path)] = value
                elif kind == "script_finished":
                    finished.append(int(message.script_finished))
                    if int(message.script_finished) != 0:
                        continue
                    if complete_data(page, elements):
                        row["status"] = "complete"
                        break
                    if row["first_incomplete_script_finished_seconds"] is None:
                        row["first_incomplete_script_finished_seconds"] = (
                            time.monotonic() - self._started
                        )
                    if not fragments:
                        row["status"] = "incomplete"
                        break
            if stop.is_set() and row["status"] == "timeout":
                row["status"] = "aborted_after_guard_stop"
        finally:
            row.update(
                seconds=time.monotonic() - self._started,
                messages=messages,
                elements=element_counts(elements),
                incomplete_alerts=sum(
                    value.get("incomplete", False) for value in elements.values()
                ),
                alerts=[
                    {key: value[key] for key in ("section", "category", "incomplete")}
                    for value in elements.values()
                    if value["kind"] == "alert"
                ],
                alert_history=list(alert_history.values()),
                metrics=[
                    value for value in elements.values() if value["kind"] == "metric"
                ],
                script_finished_values=finished,
                maximum_background_watchers=max_watchers,
                auto_rerun_registrations=auto_reruns,
            )


REMOTE = """
import json,pathlib,time,os
from datetime import datetime,timezone
pids={}
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  cmd=(d/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  if cmd.startswith('python -m src.main'):pids['engine']=int(d.name)
  elif 'streamlit run src/dashboard/app.py' in cmd:pids['dashboard']=int(d.name)
 except (FileNotFoundError,PermissionError):pass
for index in range(DURATION):
 out={'captured_at':datetime.now(timezone.utc).isoformat(),'pids':pids,'processes':{}}
 for kind,pid in pids.items():
  try:
   values={s.split(':')[0]:s.split(':')[1].strip() for s in pathlib.Path('/proc',str(pid),'status').read_text().splitlines() if s.startswith(('VmRSS:','VmHWM:','Threads:'))}
   stat=pathlib.Path('/proc',str(pid),'stat').read_text().split(') ',1)[1].split()
   values['cpu_seconds']=(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK')
   out['processes'][kind]=values
  except FileNotFoundError:out['processes'][kind]={'missing':True}
 out['memory_kib']={s.split(':')[0]:int(s.split()[1]) for s in pathlib.Path('/proc/meminfo').read_text().splitlines() if s.startswith(('MemTotal:','MemAvailable:'))}
 if index%15==0:
  paths=sorted(pathlib.Path('/data/runtime').glob('activity.*.jsonl'));events=[]
  if paths:
   with paths[-1].open('rb') as h:h.seek(max(0,paths[-1].stat().st_size-262144));raw=h.read()
   for line in raw.splitlines()[1:]:
    try:row=json.loads(line)
    except ValueError:continue
    if row.get('event_type') in ('cycle_started','cycle_completed','cycle_errored'):events.append({k:row.get(k) for k in ('timestamp','event_type','cycle_id')})
  out['cycles']=events[-8:]
 try:print(json.dumps(out),flush=True)
 except BrokenPipeError:break
 time.sleep(1)
"""


def number(value):
    return int(value.split()[0])


def full_cycle(start: datetime, end: datetime):
    for cid, row in cycles.items():
        if (
            "cycle_started" in row
            and "cycle_completed" in row
            and start <= row["cycle_started"] <= row["cycle_completed"] <= end
        ):
            return cid
    return None


def summarize(start, end, baseline, *, final=False):
    def p95(v):
        return sorted(v)[math.ceil(0.95 * len(v)) - 1] if v else None

    summary = {
        "surface": "four concurrent actual Streamlit WebSocket sessions; not native viewport/browser acceptance",
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "seconds": (end - start).total_seconds(),
        "clients": 4,
        "cadence_seconds": args.cadence,
        "stop_reasons": reason,
        "health_samples": len(health),
        "health_all_ok_under_5s": bool(health)
        and all(r["ok"] and r["seconds"] < 5 for r in health),
        "health_max_seconds": max((r["seconds"] for r in health), default=None),
        "memory_samples": len(memory),
        "warmed_dashboard_baseline_rss_kib": baseline,
        "engine_full_cycle": full_cycle(start, end),
        "pages": {},
    }
    # Preserve the first complete cycle as evidence even when it errored. Do
    # not wait for a later clean cycle and thereby hide an observed failure.
    summary["engine_cycle_errors"] = [
        {"cycle_id": cycle_id, "timestamp": events["cycle_errored"].isoformat()}
        for cycle_id, events in cycles.items()
        if "cycle_errored" in events and start <= events["cycle_errored"] <= end
    ]
    summary["engine_full_cycle_error_seen"] = bool(
        summary["engine_full_cycle"]
        and "cycle_errored" in cycles[summary["engine_full_cycle"]]
    )
    summary["engine_continuity_pass"] = bool(summary["engine_full_cycle"]) and not (
        summary["engine_full_cycle_error_seen"] or summary["engine_cycle_errors"]
    )
    for page in ("Home", "Trading"):
        rows = [r for r in observations if r["page"] == page]
        complete = [r for r in rows if r["status"] == "complete"]
        summary["pages"][page] = {
            "observations": len(rows),
            "complete": len(complete),
            "incomplete": len(rows) - len(complete),
            "complete_seconds_p95": p95([r["seconds"] for r in complete]),
            "all_complete": bool(rows) and len(complete) == len(rows),
        }
    if memory:
        dash = [
            number(r["processes"]["dashboard"]["VmRSS"])
            for r in memory
            if "VmRSS" in r["processes"].get("dashboard", {})
        ]
        hwm = [
            number(r["processes"]["dashboard"]["VmHWM"])
            for r in memory
            if "VmHWM" in r["processes"].get("dashboard", {})
        ]
        used = [
            r["memory_kib"]["MemTotal"] - r["memory_kib"]["MemAvailable"]
            for r in memory
        ]
        summary.update(
            dashboard_peak_rss_kib=max(dash, default=0),
            dashboard_process_hwm_kib=max(hwm, default=0),
            observed_dashboard_rss_increase_mib=(max(dash, default=0) - baseline)
            / 1024,
            conservative_hwm_minus_warmed_rss_mib=(max(hwm, default=0) - baseline)
            / 1024,
            guest_use_peak_mib=max(used) / 1024,
            guest_memtotal_kib=memory[0]["memory_kib"]["MemTotal"],
        )
    summary["minimum_duration_and_cycle_observed"] = summary[
        "seconds"
    ] >= args.seconds and bool(summary["engine_full_cycle"])
    summary["process_cpu_seconds_during_observation"] = (
        {
            kind: memory[-1]["processes"].get(kind, {}).get("cpu_seconds", 0)
            - memory[0]["processes"].get(kind, {}).get("cpu_seconds", 0)
            for kind in ("engine", "dashboard")
        }
        if memory
        else {}
    )
    starts_path = OUT / (args.phase + "-page-starts.jsonl")
    starts = (
        [json.loads(line) for line in starts_path.read_text().splitlines()]
        if starts_path.exists()
        else []
    )
    summary["request_reconciliation"] = reconcile_requests(starts, observations)
    summary["request_starts_recorded"] = len(starts)
    summary["every_start_has_outcome"] = summary["request_reconciliation"]["bijective"]
    summary["final"] = final
    summary["observed_guest_768_mib_ceiling_pass"] = (
        summary.get("guest_use_peak_mib", float("inf")) <= 768
    )
    summary["dashboard_growth_256_mib_pass"] = (
        summary.get("observed_dashboard_rss_increase_mib", float("inf")) <= 256
    )
    summary["warm_page_p95_2s_pass"] = all(
        v["all_complete"]
        and v["complete_seconds_p95"] is not None
        and v["complete_seconds_p95"] <= 2
        for v in summary["pages"].values()
    )
    summary["original_1024_mib_guest_qualification"] = False
    return summary


async def observe():
    import aiohttp

    global tracking
    try:
        async with Client("warmup") as client:
            warm = [
                await client.view(page, timeout=240) for page in ("Home", "Trading")
            ]
            if not all(r["status"] == "complete" for r in warm):
                raise RuntimeError("warmup_incomplete")
    finally:
        (OUT / (args.phase + "-warmup-protocol.json")).write_text(
            json.dumps(warmup_observations, indent=2) + "\n"
        )
    code = REMOTE.replace("DURATION", str(args.max_seconds + 90))
    remote = "python -c " + shlex.quote(
        "import base64;exec(base64.b64decode("
        + repr(base64.b64encode(code.encode()).decode())
        + "))"
    )
    proc = await asyncio.create_subprocess_exec(
        "flyctl",
        "ssh",
        "console",
        "--app",
        "crypto-master",
        "--machine",
        "6835752b711958",
        "--quiet",
        "--command",
        remote,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    ready = asyncio.Event()
    baseline = 0

    async def sampler():
        nonlocal baseline
        path = OUT / (args.phase + "-memory-samples.jsonl")
        with path.open("w") as file:
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                memory.append(row)
                file.write(json.dumps(row) + "\n")
                file.flush()
                if not ready.is_set():
                    if not all(
                        "VmRSS" in row["processes"].get(kind, {})
                        for kind in ("engine", "dashboard")
                    ):
                        reason.append("runtime_process_missing_at_baseline")
                        stop.set()
                        ready.set()
                        break
                    baseline = number(row["processes"]["dashboard"]["VmRSS"])
                    ready.set()
                for event in row.get("cycles", []):
                    at = datetime.fromisoformat(
                        event["timestamp"].replace("Z", "+00:00")
                    )
                    cycles.setdefault(event["cycle_id"], {})[event["event_type"]] = at
                if row["memory_kib"]["MemAvailable"] < 128 * 1024:
                    reason.append("guest_available_memory_below_128_mib")
                    stop.set()
                if any(p.get("missing") for p in row["processes"].values()):
                    reason.append("runtime_process_disappeared")
                    stop.set()
                if (
                    number(row["processes"].get("dashboard", {}).get("VmRSS", "0"))
                    > baseline + 256 * 1024
                ):
                    reason.append("dashboard_growth_exceeds_256_mib")
                    stop.set()
            if not stop.is_set():
                reason.append("memory_sampler_ended_unexpectedly")
                stop.set()

    sampler_task = asyncio.create_task(sampler())
    try:
        await asyncio.wait_for(ready.wait(), timeout=30)
    except asyncio.TimeoutError:
        proc.terminate()
        await proc.wait()
        raise RuntimeError("memory_sampler_did_not_start") from None
    (OUT / (args.phase + "-page-observations.jsonl")).touch(exist_ok=False)
    (OUT / (args.phase + "-page-starts.jsonl")).touch(exist_ok=False)
    tracking = True
    start = datetime.now(timezone.utc)
    start_mono = time.monotonic()

    async def health_loop():
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        ) as session:
            while not stop.is_set():
                at = time.monotonic()
                entry = {"captured_at": datetime.now(timezone.utc).isoformat()}
                try:
                    async with session.get(
                        "https://crypto-master.fly.dev/_stcore/health"
                    ) as r:
                        entry["ok"] = (
                            r.status == 200 and (await r.text()).strip() == "ok"
                        )
                except Exception as exc:
                    entry.update(ok=False, reason=type(exc).__name__)
                entry["seconds"] = time.monotonic() - at
                health.append(entry)
                if not entry["ok"] or entry["seconds"] >= 5:
                    reason.append("health_failed_or_deadline_exceeded")
                    stop.set()
                await asyncio.sleep(5)

    async def runner(identifier):
        await asyncio.sleep(identifier * 0.3)
        try:
            async with Client(identifier) as client:
                index = 0
                while not stop.is_set() and not admission_closed.is_set():
                    tick = time.monotonic()
                    await client.view(
                        ("Home", "Trading")[(index + identifier) % 2], timeout=30
                    )
                    index += 1
                    try:
                        await asyncio.wait_for(
                            admission_closed.wait(),
                            timeout=max(0, args.cadence - (time.monotonic() - tick)),
                        )
                    except asyncio.TimeoutError:
                        pass
        except Exception as exc:
            reason.append("session_" + str(identifier) + "_" + type(exc).__name__)
            stop.set()

    health_task = asyncio.create_task(health_loop())
    tasks = [asyncio.create_task(runner(i)) for i in range(4)]
    try:
        while not stop.is_set():
            elapsed = time.monotonic() - start_mono
            observed_at = datetime.now(timezone.utc)
            if elapsed >= args.seconds and full_cycle(start, observed_at):
                break
            if elapsed >= args.max_seconds:
                reason.append("maximum_observation_without_full_cycle")
                break
            summary = summarize(start, observed_at, baseline)
            (OUT / (args.phase + "-concurrency-summary.json")).write_text(
                json.dumps(summary, indent=2) + "\n"
            )
            print(
                json.dumps(
                    {
                        "elapsed_seconds": round(elapsed),
                        "page_observations": len(observations),
                        "memory_samples": len(memory),
                        "health_samples": len(health),
                        "full_engine_cycle": bool(full_cycle(start, observed_at)),
                    }
                ),
                flush=True,
            )
            await asyncio.sleep(30)
    finally:
        admission_closed.set()
        if not stop.is_set():
            done, pending = await asyncio.wait(tasks, timeout=35)
            if pending:
                reason.append("requests_did_not_drain_within_35s")
        stop.set()
        for t in tasks + [health_task]:
            t.cancel()
        await asyncio.gather(*tasks, health_task, return_exceptions=True)
        if proc.returncode is None:
            proc.terminate()
        await proc.wait()
        await sampler_task
    end = datetime.now(timezone.utc)
    summary = summarize(start, end, baseline, final=True)
    (OUT / (args.phase + "-concurrency-summary.json")).write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    (OUT / (args.phase + "-health-samples.json")).write_text(
        json.dumps(health, indent=2) + "\n"
    )
    print(json.dumps(summary), flush=True)
    if (
        reason
        or not summary["observed_guest_768_mib_ceiling_pass"]
        or not summary["dashboard_growth_256_mib_pass"]
        or not summary["warm_page_p95_2s_pass"]
        or not summary["every_start_has_outcome"]
        or not summary["minimum_duration_and_cycle_observed"]
        or not summary["engine_continuity_pass"]
        or not all(r["all_complete"] for r in summary["pages"].values())
    ):
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    global args, OUT, Back, Forward
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    try:
        descriptor = descriptor_pb2.FileDescriptorSet.FromString(
            args.descriptor.read_bytes()
        )
        pool = descriptor_pool.DescriptorPool()
        for file in descriptor.file:
            pool.AddSerializedFile(file.SerializeToString())
        Back = message_factory.GetMessageClass(pool.FindMessageTypeByName("BackMsg"))
        Forward = message_factory.GetMessageClass(
            pool.FindMessageTypeByName("ForwardMsg")
        )
        OUT = prepare_output(args)
    except (OSError, ValueError, KeyError) as error:
        argument_parser.error(str(error))
    (OUT / f"{args.phase}-observer-config.json").write_text(
        json.dumps(
            {
                "seconds": args.seconds,
                "max_seconds": args.max_seconds,
                "cadence_seconds": args.cadence,
                "phase": args.phase,
                "surface": "protocol only, not native browser acceptance",
                "timeout_policy": "retain failed outcome; close and reconnect before next request, including reconnect time",
                "metric_labels": {
                    page: sorted(labels) for page, labels in METRIC_LABELS.items()
                },
                "expected_element_counts": ELEMENT_COUNTS,
                "descriptor_sha256": hashlib.sha256(
                    args.descriptor.read_bytes()
                ).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    asyncio.run(observe())


if __name__ == "__main__":
    main()
