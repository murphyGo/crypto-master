#!/usr/bin/env python3
"""Independent, offline v66 audit. Reads existing evidence; writes only OUT.

The optional wait only stats the final health artifact. It never opens a
network connection, invokes Fly, imports application code, or starts load.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
LABELS = {
    'Home': sorted(['Actionable events', 'Awaiting approval', 'Candidates',
                    'Errored', 'Last cycle', 'Mode', 'Open positions', 'Promoted',
                    'Runtime safety', 'Scope', 'Snapshot', 'Sub-accounts']),
    'Trading': sorted(['Closed Trades', 'Current Equity', 'Open Positions',
                       'Proposals rejected (threshold)', 'Realized P&L', 'Win Rate']),
}
ELEMENTS = {
    'Home': {'metric': 12, 'dataframe': 4, 'table': 0, 'vega_lite_chart': 0, 'exception': 0},
    'Trading': {'metric': 6, 'dataframe': 3, 'table': 0, 'vega_lite_chart': 1, 'exception': 0},
}


def at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def p95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


def key(row):
    return row.get('started_at'), row.get('client'), row.get('page')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_jsonl(path):
    rows, errors = [], []
    with path.open(encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('nonobject')
                rows.append(row)
            except (ValueError, UnicodeError) as error:
                errors.append({'line': number, 'type': type(error).__name__})
    return rows, errors


def audit():
    frozen = OUT / 'frozen/raw'
    summary = read_json(frozen / 'v66-concurrency-summary.json')
    health = read_json(frozen / 'v66-health-samples.json')
    start, end = at(summary['started_at']), at(summary['ended_at'])
    starts, start_errors = read_jsonl(frozen / 'v66-page-starts.jsonl')
    outcomes, outcome_errors = read_jsonl(frozen / 'v66-page-observations.jsonl')
    memory, memory_errors = read_jsonl(frozen / 'v66-memory-samples.jsonl')
    sc, oc = Counter(map(key, starts)), Counter(map(key, outcomes))
    unmatched_starts = list((sc - oc).elements())
    unmatched_outcomes = list((oc - sc).elements())
    semantics = []
    clients = defaultdict(list)
    for row in outcomes:
        problems = []
        page = row.get('page')
        metrics = row.get('metrics', [])
        if row.get('status') != 'complete':
            problems.append('outcome_not_complete')
        if page not in LABELS or sorted(m.get('label', '') for m in metrics) != LABELS.get(page):
            problems.append('exact_metric_labels_differ')
        if any(m.get('placeholder') is not False for m in metrics):
            problems.append('placeholder_or_unproven_metric')
        if row.get('elements') != ELEMENTS.get(page):
            problems.append('exact_element_counts_differ')
        if row.get('incomplete_alerts') != 0:
            problems.append('incomplete_alert_present_or_unknown')
        if 0 not in row.get('script_finished_values', []):
            problems.append('successful_script_finish_missing')
        began = at(row['started_at'])
        finished = began + timedelta(seconds=row.get('seconds', 0))
        if began < start or finished > end + timedelta(milliseconds=10):
            problems.append('request_outside_observation_window')
        if problems:
            semantics.append({'key': key(row), 'problems': problems})
        clients[row.get('client')].append(row)
    pages = {}
    for page in LABELS:
        rows = [r for r in outcomes if r.get('page') == page]
        complete = [r for r in rows if r.get('status') == 'complete']
        durations = [r['seconds'] for r in complete]
        pages[page] = {'observations': len(rows), 'complete': len(complete),
                       'incomplete': len(rows) - len(complete),
                       'complete_seconds_p95': p95(durations),
                       'complete_seconds_max': max(durations, default=None),
                       'all_complete': bool(rows) and len(complete) == len(rows),
                       'completion_ratio': len(complete) / len(rows) if rows else 0,
                       'status_counts': dict(Counter(r.get('status') for r in rows)),
                       'per_client': dict(Counter(r.get('client') for r in rows))}
    client_summary = {}
    for identifier, rows in clients.items():
        rows.sort(key=lambda r: r['started_at'])
        gaps = [(at(b['started_at']) - at(a['started_at'])).total_seconds()
                for a, b in zip(rows, rows[1:])]
        client_summary[str(identifier)] = {
            'requests': len(rows), 'first': rows[0]['started_at'],
            'last': rows[-1]['started_at'],
            'alternates_home_trading': all(a['page'] != b['page']
                                          for a, b in zip(rows, rows[1:])),
            'minimum_start_gap_seconds': min(gaps, default=None),
            'maximum_start_gap_seconds': max(gaps, default=None),
        }
    process_summary = {}
    missing_processes = []
    for kind in ('engine', 'dashboard'):
        rows = []
        for sample in memory:
            process = sample.get('processes', {}).get(kind, {})
            if not all(k in process for k in ('VmRSS', 'VmHWM', 'Threads', 'cpu_seconds')):
                missing_processes.append({'at': sample.get('captured_at'), 'kind': kind})
            else:
                rows.append(process)
        number = lambda r, name: int(r[name].split()[0])
        process_summary[kind] = {
            'rss_first_kib': number(rows[0], 'VmRSS'), 'rss_last_kib': number(rows[-1], 'VmRSS'),
            'rss_peak_kib': max(number(r, 'VmRSS') for r in rows),
            'hwm_peak_kib': max(number(r, 'VmHWM') for r in rows),
            'threads_first': int(rows[0]['Threads']), 'threads_last': int(rows[-1]['Threads']),
            'threads_min': min(int(r['Threads']) for r in rows),
            'threads_max': max(int(r['Threads']) for r in rows),
            'cpu_delta_seconds': rows[-1]['cpu_seconds'] - rows[0]['cpu_seconds'],
        }
    mtimes = [at(r['captured_at']) for r in memory]
    sample_gaps = [(b-a).total_seconds() for a,b in zip(mtimes, mtimes[1:])]
    guest_peak = max((r['memory_kib']['MemTotal'] - r['memory_kib']['MemAvailable']) / 1024
                     for r in memory)
    baseline = process_summary['dashboard']['rss_first_kib']
    growth = (process_summary['dashboard']['rss_peak_kib'] - baseline) / 1024
    hwm_growth = (process_summary['dashboard']['hwm_peak_kib'] - baseline) / 1024
    cycles = defaultdict(dict)
    for sample in memory:
        for event in sample.get('cycles', []):
            cycles[event['cycle_id']][event['event_type']] = event['timestamp']
    full_cycles = []
    for cid, events in cycles.items():
        began, finished = events.get('cycle_started'), events.get('cycle_completed')
        if began and finished and start <= at(began) <= at(finished) <= end:
            full_cycles.append({'cycle_id': cid, 'started_at': began, 'completed_at': finished,
                                'seconds': (at(finished)-at(began)).total_seconds(),
                                'cycle_errored_seen': 'cycle_errored' in events})
    health_failures = [r for r in health if not r.get('ok') or r.get('seconds', math.inf) >= 5]
    htimes = [at(r['captured_at']) for r in health]
    cpu = {}
    for path in sorted(frozen.glob('v66-cpu-*.json')):
        value = read_json(path)
        for series in value.get('data', {}).get('result', []):
            name = series['metric']['__name__']
            points = cpu.setdefault(name, {})
            for timestamp, number in series.get('values', []):
                points[float(timestamp)] = float(number)
    cpu_summary = {}
    for name, points in cpu.items():
        times = sorted(points)
        window = [value for timestamp, value in points.items()
                  if start.timestamp() <= timestamp <= end.timestamp()]
        cpu_summary[name] = {
            'points': len(times), 'first_at': datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
            'last_at': datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
            'minimum': min(points.values()), 'maximum': max(points.values()),
            'observation_window_points': len(window),
            'covers_entire_window': times[0] <= start.timestamp() and times[-1] >= end.timestamp(),
            'window_minimum': min(window, default=None), 'window_maximum': max(window, default=None),
        }
    balance = cpu_summary.get('fly_instance_cpu_balance', {})
    throttle = cpu_summary.get('fly_instance_cpu_throttle', {})
    depletion = balance.get('window_minimum') is not None and balance['window_minimum'] <= 0
    declared_matches, differences = {}, []
    calculated = {
        'seconds': (end-start).total_seconds(), 'health_samples': len(health),
        'health_all_ok_under_5s': bool(health) and not health_failures,
        'health_max_seconds': max((r['seconds'] for r in health), default=None),
        'memory_samples': len(memory), 'warmed_dashboard_baseline_rss_kib': baseline,
        'dashboard_peak_rss_kib': process_summary['dashboard']['rss_peak_kib'],
        'dashboard_process_hwm_kib': process_summary['dashboard']['hwm_peak_kib'],
        'observed_dashboard_rss_increase_mib': growth,
        'conservative_hwm_minus_warmed_rss_mib': hwm_growth,
        'guest_use_peak_mib': guest_peak, 'guest_memtotal_kib': memory[0]['memory_kib']['MemTotal'],
        'request_starts_recorded': len(starts),
        'every_start_has_outcome': not unmatched_starts and not unmatched_outcomes and len(starts)==len(outcomes),
        'observed_guest_768_mib_ceiling_pass': guest_peak <= 768,
        'dashboard_growth_256_mib_pass': growth <= 256,
        'warm_page_p95_2s_pass': all(p['all_complete'] and p['complete_seconds_p95'] <= 2 for p in pages.values()),
        'minimum_duration_and_cycle_observed': (end-start).total_seconds() >= 600 and bool(full_cycles),
    }
    def compare(name, expected, actual):
        match = (math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-8)
                 if isinstance(expected, float) and isinstance(actual, (float, int)) else expected == actual)
        declared_matches[name] = match
        if not match:
            differences.append({'field': name, 'calculated': expected, 'declared': actual})
    for name, value in calculated.items():
        compare(name, value, summary.get(name))
    for page, values in pages.items():
        for name in ('observations','complete','incomplete','complete_seconds_p95','all_complete'):
            compare('pages.' + page + '.' + name, values[name], summary.get('pages',{}).get(page,{}).get(name))
    for kind, values in process_summary.items():
        compare('process_cpu_seconds_during_observation.' + kind, values['cpu_delta_seconds'],
                summary.get('process_cpu_seconds_during_observation',{}).get(kind))
    compare('engine_full_cycle', full_cycles[0]['cycle_id'] if full_cycles else None,
            summary.get('engine_full_cycle'))
    parse_errors = {'starts':start_errors, 'outcomes':outcome_errors, 'memory':memory_errors}
    pid_sets = {kind: sorted({r.get('pids',{}).get(kind) for r in memory}, key=str)
                for kind in ('engine','dashboard')}
    protocol_pass = (not any(parse_errors.values()) and not semantics and not differences
                     and not unmatched_starts and not unmatched_outcomes
                     and all(v == 1 for v in sc.values()) and all(v == 1 for v in oc.values())
                     and set(clients) == {0,1,2,3} and not health_failures and bool(health)
                     and not missing_processes and all(len(v)==1 for v in pid_sets.values())
                     and not summary.get('stop_reasons')
                     and calculated['minimum_duration_and_cycle_observed']
                     and all(not c['cycle_errored_seen'] for c in full_cycles)
                     and calculated['warm_page_p95_2s_pass'] and growth <= 256 and guest_peak <= 768)
    result = {
        'audit_completed_at': stamp(), 'mode': 'existing frozen evidence only; no new load',
        'window': {'start':start.isoformat(), 'end':end.isoformat(), 'seconds':(end-start).total_seconds()},
        'existing_warm_protocol_sample_pass': protocol_pass,
        'original_debt083_acceptance': False,
        'original_acceptance_unqualified': ['declared 1 GiB guest', 'native viewport',
            'per-page process-cold and cache-cold >=20 samples', 'depleted CPU qualification'],
        'request_reconciliation': {'starts':len(starts),'outcomes':len(outcomes),
            'unmatched_starts':unmatched_starts, 'unmatched_outcomes':unmatched_outcomes,
            'duplicate_starts':sum(v-1 for v in sc.values()),
            'duplicate_outcomes':sum(v-1 for v in oc.values()),
            'status_counts':dict(Counter(r.get('status') for r in outcomes)),
            'completion_ratio':sum(r.get('status')=='complete' for r in outcomes)/len(starts) if starts else 0},
        'parse_errors':parse_errors, 'semantic_shape_failures':semantics, 'pages':pages,
        'clients':client_summary,
        'health': {'samples':len(health),'failures':health_failures,
            'maximum_seconds':max((r['seconds'] for r in health), default=None),
            'first_at':health[0]['captured_at'] if health else None,
            'last_at':health[-1]['captured_at'] if health else None,
            'max_sample_gap_seconds':max(((b-a).total_seconds() for a,b in zip(htimes,htimes[1:])),default=None)},
        'memory': {'samples':len(memory), 'first_at':memory[0]['captured_at'],
            'last_at':memory[-1]['captured_at'],'max_sample_gap_seconds':max(sample_gaps,default=None),
            'guest_peak_mib':guest_peak, 'guest_memtotal_kib':memory[0]['memory_kib']['MemTotal'],
            'dashboard_growth_mib':growth,'dashboard_hwm_growth_mib':hwm_growth,
            'pid_sets':pid_sets,'missing_processes':missing_processes,'processes':process_summary},
        'full_cycles_inside_entire_window':full_cycles,
        'cpu': {'series':cpu_summary,'depletion_observed':depletion,
            'throttle_observed':(throttle.get('window_maximum') or 0)>0,
            'full_window_coverage':bool(cpu_summary) and all(v['covers_entire_window'] for v in cpu_summary.values())},
        'declared_summary_comparisons':declared_matches,'declared_summary_differences':differences,
        'limitations': ['Semantic audit covers exact labels/placeholders/element presence, not table-cell oracle or native rendering.',
            'Guest memory sampled about once per second; process HWM retained separately, no sum of process RSS.',
            'CPU snapshots cover only their recorded timestamps; missing final coverage is not zero throttle.',
            'Existing warmup and intermediate/canonical latency failures remain in frozen context.'],
    }
    (OUT / 'audit-results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

