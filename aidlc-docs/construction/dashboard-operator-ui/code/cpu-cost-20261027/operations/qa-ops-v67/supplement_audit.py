#!/usr/bin/env python3
"""Offline supplemental checks; never imports application code or makes requests."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('base', OUT/'base_auditor.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capture(source, category):
    before = source.stat()
    data = source.read_bytes()
    after = source.stat()
    version = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if version(before) != version(after):
        raise RuntimeError('supplement_source_changed')
    target = OUT/'supplements'/category/source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as file:
        file.write(data)
    target.chmod(0o444)
    return target, {'source':str(source), 'copy':str(target), 'bytes':len(data),
                    'source_mtime_ns':after.st_mtime_ns, 'sha256':digest(data)}


def temporal(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def shapes(rows):
    failures = []
    for row in rows:
        problems = []
        metrics = row.get('metrics', [])
        if sorted(metric.get('label', '') for metric in metrics) != base.LABELS.get(row.get('page')):
            problems.append('exact_metric_labels')
        if row.get('elements') != base.ELEMENTS.get(row.get('page')):
            problems.append('exact_element_counts')
        if any(metric.get('placeholder') is not False for metric in metrics):
            problems.append('placeholder_or_unproven')
        if any(not isinstance(metric.get('value_sha256'), str) or len(metric['value_sha256']) != 64
               or set(metric['value_sha256']) - set('0123456789abcdef') for metric in metrics):
            problems.append('invalid_value_digest')
        if row.get('incomplete_alerts') != 0:
            problems.append('terminal_incomplete_alerts_present')
        if row.get('status') != 'complete' or 0 not in row.get('script_finished_values', []):
            problems.append('not_successfully_completed')
        if not temporal(row.get('seconds')):
            problems.append('invalid_duration')
        if problems:
            failures.append({'key':base.key(row), 'problems':problems})
    return failures


def diagnostics(path, begin, end):
    copied, proof = capture(path, 'diagnostics')
    rows, errors = base.read_jsonl(copied)
    allowed = {'event', 'kind', 'status', 'reason', 'stage', 'cache_age_seconds', 'admitted'}
    kinds = {'activity', 'ledger', 'snapshots', 'candidates', 'proposals', 'audit', 'promotion', 'unknown'}
    statuses = {'pending', 'stale', 'unavailable', 'unknown'}
    stages = {'admission', 'error_cache', 'foreground_wait', 'projection', 'encoding', 'cache_publication', 'unknown'}
    reasons = {'rebuild_pending', 'queue_full', 'service_closed', 'root_budget_exhausted',
               'cache_budget_exhausted', 'empty_projection', 'result_budget_exhausted',
               'account_budget_exhausted', 'evaluation_clock_reversed', 'identity_budget_exhausted',
               'invalid_record', 'missing_timestamp', 'source_changed', 'state_budget_exhausted',
               'strategy_budget_exhausted', 'window_evaluation_budget_exhausted',
               'manifest_budget_exhausted', 'unknown_query', 'malformed_json',
               'malformed_json_array', 'partial_record', 'record_too_large', 'read_failed', 'unknown'}
    schema_failures = []
    within = []
    for number, row in enumerate(rows, 1):
        event = row.get('diagnostic', {})
        age = event.get('cache_age_seconds')
        admitted = event.get('admitted')
        valid = (set(row) == {'received_at', 'fly_timestamp', 'diagnostic'}
                 and set(event) == allowed and event.get('event') == 'dashboard_read_incomplete'
                 and event.get('kind') in kinds and event.get('status') in statuses
                 and event.get('stage') in stages and event.get('reason') in reasons
                 and (age is None or temporal(age))
                 and (admitted is None or type(admitted) is int and 0 <= admitted <= 4))
        if not valid:
            schema_failures.append(number)
        try:
            stamped = base.at(row['fly_timestamp'])
            if begin <= stamped <= end:
                within.append(row)
        except (TypeError, ValueError, KeyError):
            schema_failures.append(number)
    counts = Counter((row['diagnostic'].get('kind'), row['diagnostic'].get('status'),
                      row['diagnostic'].get('reason'), row['diagnostic'].get('stage')) for row in within)
    return {'freeze':proof, 'rows':len(rows), 'parse_errors':errors,
            'schema_failure_rows':sorted(set(schema_failures)),
            'first_received_at':rows[0].get('received_at') if rows else None,
            'last_received_at':rows[-1].get('received_at') if rows else None,
            'in_page_window_by_fly_timestamp':len(within),
            'window_classifications':[{'kind':key[0], 'status':key[1], 'reason':key[2],
                                       'stage':key[3], 'count':value} for key,value in sorted(counts.items())],
            'interpretation':'Intermediate query diagnostics may occur during successful page requests. Fly timestamps reflect asynchronous sink delivery, not exact throw times. Projection combines several verification branches, and there is no query/request token. Temporal overlap only; do not count these events as page failures or assert exact causality.',
            'coverage':'Collection coverage requires collector metadata; emitted diagnostics are rate-limited and may be dropped. Absence is not proof of no errors.'}


def cpu(path, begin, end):
    copied, proof = capture(path, 'cpu')
    raw = base.read_json(copied)
    expected = {'fly_instance_cpu_baseline', 'fly_instance_cpu_balance', 'fly_instance_cpu_throttle'}
    series = {}
    duplicates = []
    for row in raw.get('data', {}).get('result', []):
        name = row.get('metric', {}).get('__name__')
        if name in series:
            duplicates.append(name)
        points = [(float(stamp), float(value)) for stamp, value in row.get('values', [])]
        stamps = [stamp for stamp, _ in points]
        valid = (bool(points) and all(math.isfinite(stamp) and math.isfinite(value) for stamp,value in points)
                 and stamps == sorted(set(stamps)))
        window = [value for stamp,value in points if begin.timestamp() <= stamp <= end.timestamp()]
        gaps = [b-a for a,b in zip(stamps,stamps[1:])]
        series[name] = {'points':len(points), 'valid_points':valid,
                        'first_at':datetime.fromtimestamp(min(stamps),timezone.utc).isoformat() if stamps else None,
                        'last_at':datetime.fromtimestamp(max(stamps),timezone.utc).isoformat() if stamps else None,
                        'maximum_gap_seconds':max(gaps,default=None),
                        'covers_entire_window':bool(stamps) and min(stamps)<=begin.timestamp() and max(stamps)>=end.timestamp(),
                        'window_points':len(window), 'window_min':min(window,default=None),
                        'window_max':max(window,default=None)}
    coverage = (raw.get('status') == 'success' and set(series)==expected and not duplicates
                and all(item['valid_points'] and item['covers_entire_window'] and item['maximum_gap_seconds']<=15.001
                        for item in series.values()))
    balance = series.get('fly_instance_cpu_balance', {}).get('window_min')
    throttle = series.get('fly_instance_cpu_throttle', {}).get('window_max')
    return {'freeze':proof, 'series':series, 'duplicate_series':duplicates,
            'full_window_coverage':coverage,
            'depletion_observed':balance is not None and balance<=0,
            'throttle_observed':throttle is not None and throttle>0,
            'depleted_cpu_qualified':False,
            'interpretation':'Sampled CPU evidence only. Positive balance does not establish depleted-load acceptance.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostics',type=Path)
    parser.add_argument('--cpu',type=Path)
    parser.add_argument('--functional',action='store_true')
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert args.name and set(args.name) <= set('abcdefghijklmnopqrstuvwxyz0123456789-_')
    manifest = base.read_json(OUT/'freeze-manifest.json')
    for item in manifest['files']:
        data = (OUT/item['relative_copy']).read_bytes()
        assert len(data)==item['bytes'] and digest(data)==item['sha256']
    result = base.read_json(OUT/'audit-results.json')
    begin, end = base.at(result['window']['start']), base.at(result['window']['end'])
    raw = OUT/'frozen/raw'
    rows, _ = base.read_jsonl(raw/'v67-page-observations.jsonl')
    warm, _ = base.read_jsonl(raw/'v67-warmup-page-observations.jsonl')
    findings = {'created_at':datetime.now(timezone.utc).isoformat(), 'window':result['window'],
                'auditor_sha256':digest(Path(__file__).read_bytes()),
                'initial_frozen_hashes_verified':True, 'main_shape_failures':shapes(rows),
                'warmup_shape_failures':shapes(warm),
                'first_shell_over_5s':[{'scope':scope, 'key':base.key(row),
                                        'first_shell_seconds':row['first_incomplete_shell_seconds'],
                                        'complete_seconds':row['seconds'], 'terminal_status':row['status']}
                                       for scope, group in [('warmup',warm), ('main',rows)] for row in group
                                       if (row.get('first_incomplete_shell_seconds') or 0)>5],
                'all_first_shell_timing_scope':'Protocol receipt offsets, not native browser visual rendering.',
                'production_load_added':False}
    findings['page_distributions'] = {}
    for page in base.LABELS:
        selected = [row for row in rows if row.get('page') == page]
        complete = [row for row in selected if row.get('status') == 'complete']
        failures = len(selected) - len(complete)
        findings['page_distributions'][page] = {
            'attempts':len(selected), 'complete':len(complete), 'failures':failures,
            'failure_ratio':failures/len(selected) if selected else None,
            'all_outcome_seconds_nearest_rank_p95':base.p95([row['seconds'] for row in selected]),
            'complete_seconds_nearest_rank_p95':base.p95([row['seconds'] for row in complete]),
        }
    findings['failed_request_timeline'] = []
    for row in rows:
        if row.get('status') == 'complete':
            continue
        started = base.at(row['started_at'])
        finished = started + timedelta(seconds=row['seconds'])
        relevant_cycles = []
        for cycle in result['full_cycles_inside_entire_window']:
            cycle_start = base.at(cycle['started_at'])
            cycle_end = base.at(cycle['completed_at'])
            overlap = max(0.0, (min(finished,cycle_end)-max(started,cycle_start)).total_seconds())
            relevant_cycles.append({'cycle_id':cycle['cycle_id'],
                                    'request_started_after_cycle_start_seconds':(started-cycle_start).total_seconds(),
                                    'request_finished_after_cycle_end_seconds':(finished-cycle_end).total_seconds(),
                                    'overlap_seconds':overlap})
        findings['failed_request_timeline'].append({
            'key':base.key(row), 'started_at':started.isoformat(), 'finished_at_derived':finished.isoformat(),
            'status':row['status'], 'seconds':row['seconds'],
            'first_incomplete_shell_seconds':row.get('first_incomplete_shell_seconds'),
            'first_incomplete_script_finished_seconds':row.get('first_incomplete_script_finished_seconds'),
            'alerts':row.get('alerts'), 'alert_history':row.get('alert_history'),
            'elements':row.get('elements'), 'cycles':relevant_cycles,
        })
    if args.diagnostics:
        findings['diagnostics'] = diagnostics(args.diagnostics,begin,end)
    if args.cpu:
        findings['cpu'] = cpu(args.cpu,begin,end)
    if args.functional:
        proofs = []
        for source in sorted(OUT.parent.glob('qa-fragment-smoke*')):
            if source.is_file():
                _, proof = capture(source, 'functional')
                proofs.append(proof)
        findings['functional_evidence'] = {
            'files':proofs,
            'scope':'Local two-session AppTest dispatches actual stored fragments to verify completion events and per-page latches. No production load, browser timer or native DOM claim.',
        }
    target = OUT/(args.name+'.json')
    with target.open('x') as file:
        json.dump(findings,file,indent=2)
        file.write('\n')
    target.chmod(0o444)
    print(json.dumps(findings),flush=True)


if __name__ == '__main__':
    main()
