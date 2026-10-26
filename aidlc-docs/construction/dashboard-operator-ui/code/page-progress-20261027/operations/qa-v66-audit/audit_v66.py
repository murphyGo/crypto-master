#!/usr/bin/env python3
"""Independent final-evidence audit. No network, Fly, application, or load calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / 'v66-observation'
HARNESS = Path('/private/tmp/crypto-master-page-progress-20261027/scripts/observe_dashboard_protocol.py')
spec = importlib.util.spec_from_file_location('independent_base_auditor', OUT/'base_auditor.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT
SECTIONS = {'activity','ledger','snapshots','candidates','proposals','unknown'}
CATEGORIES = {'pending','stale','unavailable','other'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def freeze():
    """Publish one immutable local capture, retaining source generation and hash."""
    manifest_path = OUT/'freeze-manifest.json'
    if manifest_path.exists():
        raise RuntimeError('initial_freeze_already_exists_use_audit_frozen')
    paths = sorted(p for p in SOURCE.glob('v66-*') if p.is_file())
    paths += [HARNESS] if HARNESS.is_file() else []
    captured = []
    version = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    for path in paths:
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if version(before) != version(after):
            raise RuntimeError('source_changed_during_offline_capture')
        captured.append((path,data,after))
    for path,data,stat in captured:
        if version(path.stat()) != version(stat):
            raise RuntimeError('source_changed_during_offline_capture')
    manifest = {'captured_at':now(),'mode':'existing final evidence copied offline',
                'files':[], 'diagnostic_sidecar_status':'separate immutable supplement after collector finishes'}
    for path,data,stat in captured:
        category = 'raw' if path.parent == SOURCE else 'context'
        target = OUT/'frozen'/category/path.name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)
        manifest['files'].append({'source':str(path),'copy':str(target),
            'relative_copy':str(target.relative_to(OUT)),'source_mtime_ns':stat.st_mtime_ns,
            'bytes':len(data),'sha256':sha(data)})
    manifest['auditor_sha256']={name:sha((OUT/name).read_bytes()) for name in ('audit_v66.py','base_auditor.py')}
    manifest['file_count']=len(manifest['files'])
    manifest['total_bytes']=sum(row['bytes'] for row in manifest['files'])
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    manifest_path.chmod(0o444)


def frozen_integrity():
    manifest=base.read_json(OUT/'freeze-manifest.json')
    for row in manifest['files']:
        data=(OUT/row['relative_copy']).read_bytes()
        assert len(data)==row['bytes'] and sha(data)==row['sha256']
    for name,expected in manifest['auditor_sha256'].items():
        assert sha((OUT/name).read_bytes())==expected
    return manifest


def finite_offset(value,duration):
    return type(value) in (int,float) and math.isfinite(value) and 0 <= value <= duration+.01


def classifications(rows):
    failures=[]
    by_page={}
    for page in base.LABELS:
        selected=[row for row in rows if row.get('page')==page]
        shells=[row['first_incomplete_shell_seconds'] for row in selected
                if row.get('first_incomplete_shell_seconds') is not None]
        by_page[page]={'requests':len(selected),'first_shell_observed':len(shells),
            'first_shell_seconds_p95':base.p95(shells),'first_shell_seconds_max':max(shells,default=None),
            'first_shell_over_5s':sum(value>5 for value in shells),
            'incomplete_shell_classifications':dict(Counter(
                item.get('category') for row in selected for item in row.get('alert_history',[])
                if item.get('incomplete')))}
    for row in rows:
        problems=[]
        history=row.get('alert_history')
        alerts=row.get('alerts')
        if not isinstance(history,list) or not isinstance(alerts,list):
            failures.append({'key':base.key(row),'problems':['classification_fields_missing']})
            continue
        for field,items in [('alerts',alerts),('alert_history',history)]:
            expected={'section','category','incomplete'} | ({'first_seen_seconds'} if field=='alert_history' else set())
            for item in items:
                if set(item)!=expected or item.get('section') not in SECTIONS or item.get('category') not in CATEGORIES:
                    problems.append('unexpected_alert_schema_or_label')
                if item.get('incomplete') is not (item.get('category')!='other'):
                    problems.append('inconsistent_alert_incomplete_flag')
                if field=='alert_history' and not finite_offset(item.get('first_seen_seconds'),row['seconds']):
                    problems.append('invalid_alert_time')
        if len({(item.get('section'),item.get('category')) for item in history})!=len(history):
            problems.append('duplicate_alert_history_key')
        if row.get('incomplete_alerts')!=sum(item.get('incomplete') is True for item in alerts):
            problems.append('incomplete_alert_count_differs')
        first=row.get('first_incomplete_shell_seconds')
        stamps=[item['first_seen_seconds'] for item in history if item.get('incomplete')]
        if stamps:
            if not finite_offset(first,row['seconds']) or not math.isclose(first,min(stamps),abs_tol=1e-8):
                problems.append('first_shell_time_differs_from_alert_history')
        elif first is not None:
            problems.append('first_shell_without_incomplete_alert')
        finished=row.get('first_incomplete_script_finished_seconds')
        if finished is not None and not finite_offset(finished,row['seconds']):
            problems.append('invalid_first_incomplete_script_finish')
        if problems:failures.append({'key':base.key(row),'problems':sorted(set(problems))})
    return {'failures':failures,'pages':by_page}


def main_audit():
    manifest=frozen_integrity()
    raw=OUT/'frozen/raw'
    result=base.audit()
    summary=base.read_json(raw/'v66-concurrency-summary.json')
    config=base.read_json(raw/'v66-observer-config.json')
    starts,start_errors=base.read_jsonl(raw/'v66-page-starts.jsonl')
    rows,row_errors=base.read_jsonl(raw/'v66-page-observations.jsonl')
    memory,_=base.read_jsonl(raw/'v66-memory-samples.jsonl')
    warm_starts,warm_start_errors=base.read_jsonl(raw/'v66-warmup-page-starts.jsonl')
    warm_rows,warm_errors=base.read_jsonl(raw/'v66-warmup-page-observations.jsonl')
    warm_aggregate=base.read_json(raw/'v66-warmup-protocol.json')
    begin,end=base.at(summary['started_at']),base.at(summary['ended_at'])
    classified=classifications(rows)
    warm_classified=classifications(warm_rows)
    ws,wo=Counter(map(base.key,warm_starts)),Counter(map(base.key,warm_rows))
    warmup={'starts':len(warm_starts),'outcomes':len(warm_rows),
        'bijective':ws==wo and all(v==1 for v in ws.values()),
        'status_counts':dict(Counter(row['status'] for row in warm_rows)),
        'aggregate_matches_jsonl':warm_rows==warm_aggregate,
        'parse_errors':warm_start_errors+warm_errors,
        'classification_audit':warm_classified,
        'observations':[{'key':base.key(row),'status':row['status'],'seconds':row['seconds'],
                         'first_incomplete_shell_seconds':row.get('first_incomplete_shell_seconds')}
                        for row in warm_rows],
        'cold_p95_qualified':False}
    cycle_events={}
    for sample in memory:
        for event in sample.get('cycles',[]):
            cycle_events[(event['cycle_id'],event['event_type'])]=event
    errors=[{'cycle_id':event['cycle_id'],'timestamp':base.at(event['timestamp']).isoformat()}
            for event in cycle_events.values() if event['event_type']=='cycle_errored'
            and begin<=base.at(event['timestamp'])<=end]
    cycle_pass=bool(result['full_cycles_inside_entire_window']) and not errors and all(
        not row['cycle_errored_seen'] for row in result['full_cycles_inside_entire_window'])
    extra_differences=[]
    for name,value in [('final',True),('engine_cycle_errors',errors),('engine_continuity_pass',cycle_pass)]:
        if summary.get(name)!=value:extra_differences.append({'field':name,'calculated':value,'declared':summary.get(name)})
    baseline_shape=(config.get('metric_labels')==base.LABELS and config.get('expected_element_counts')==base.ELEMENTS)
    health=result['health'];mem=result['memory']
    health_coverage=(health['samples']>0 and abs((base.at(health['first_at'])-begin).total_seconds())<=10
                     and abs((end-base.at(health['last_at'])).total_seconds())<=10
                     and health['max_sample_gap_seconds']<=10)
    memory_coverage=(abs((base.at(mem['first_at'])-begin).total_seconds())<=2
                     and abs((end-base.at(mem['last_at'])).total_seconds())<=2
                     and mem['max_sample_gap_seconds']<=2.5)
    all_clients=(set(result['clients'])=={'0','1','2','3'}
                 and all(row['alternates_home_trading'] for row in result['clients'].values())
                 and all(set(map(str,p['per_client']))=={'0','1','2','3'} for p in result['pages'].values()))
    warmup_complete=(bool(warm_rows) and all(row['status']=='complete' for row in warm_rows)
                     and warmup['bijective'] and warmup['aggregate_matches_jsonl']
                     and not warmup['parse_errors'] and not warm_classified['failures'])
    result['existing_warm_protocol_sample_pass']=bool(result['existing_warm_protocol_sample_pass']
        and not classified['failures'] and not extra_differences and cycle_pass
        and all_clients and health_coverage and memory_coverage and warmup_complete
        and baseline_shape and result['window']['seconds']>=config['seconds'])
    result['enhanced_protocol_audit']={'classifications':classified,'warmup':warmup,
        'all_four_clients_alternate_both_pages':all_clients,'health_temporal_coverage':health_coverage,
        'memory_temporal_coverage':memory_coverage,'pinned_shape_matches_observer_configuration':baseline_shape,
        'all_observed_cycle_errors':errors,'cycle_continuity_pass':cycle_pass,
        'summary_extra_differences':extra_differences,
        'preserved_failure_rows':[row for row in rows if row.get('status')!='complete']}
    result['diagnostic_sidecar']={'status':'separate supplement required; not inferred from absence'}
    result['freeze']={'manifest':str(OUT/'freeze-manifest.json'),'file_count':manifest['file_count'],
                      'total_bytes':manifest['total_bytes'],'sha256_verified':True}
    result['auditor_completed_at']=now()
    (OUT/'audit-results.json').write_text(json.dumps(result,indent=2)+'\n')
    final={'verdict':'PASS_SAMPLE' if result['existing_warm_protocol_sample_pass'] else 'FAIL_SAMPLE',
        'original_debt083_acceptance':False,'window':result['window'],
        'requests':result['request_reconciliation'],'pages':result['pages'],
        'full_cycles':result['full_cycles_inside_entire_window'],'cycle_errors':errors,
        'health_max_seconds':health['maximum_seconds'],'guest_peak_mib':mem['guest_peak_mib'],
        'dashboard_growth_mib':mem['dashboard_growth_mib'],
        'classification_failures':len(classified['failures']),
        'summary_differences':result['declared_summary_differences']+extra_differences,
        'cpu_full_window_coverage':result['cpu']['full_window_coverage'],
        'cpu_note':'CPU final proof, if subsequently captured by lead, requires a separate immutable supplement.'}
    (OUT/'audit-summary.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps(final),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wait-seconds',type=int,default=900)
    parser.add_argument('--audit-frozen',action='store_true')
    args=parser.parse_args()
    if not args.audit_frozen:
        deadline=time.monotonic()+args.wait_seconds
        while not (SOURCE/'v66-health-samples.json').is_file():
            if time.monotonic()>=deadline:
                raise SystemExit('Final health evidence not present before bounded offline wait expired.')
            print(json.dumps({'at':now(),'state':'metadata-only wait for existing run final health'}),flush=True)
            time.sleep(min(30,max(0,deadline-time.monotonic())))
        freeze()
    main_audit()


if __name__=='__main__':
    main()
