"""Offline audit of retained starts, outcomes, health, memory and CPU samples."""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

root = Path.cwd()
base = root / '.tmp/dashboard-v68-resume-20261028'
raw = base / 'observation'

def read(name):
    return json.loads((raw / ('v68-resumed-' + name + '.json')).read_text())

def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()

def percentile(values, q):
    return sorted(values)[math.ceil(q * len(values)) - 1] if values else None

summary = read('concurrency-summary')
assert summary['final'], 'No final sample to audit'
start, end = stamp(summary['started_at']), stamp(summary['ended_at'])
starts = lines(raw / 'v68-resumed-page-starts.jsonl')
outcomes = lines(raw / 'v68-resumed-page-observations.jsonl')
keys = lambda rows: Counter((r['started_at'], r['client'], r['page']) for r in rows)
expected, actual = keys(starts), keys(outcomes)
labels = {
    'Home': {'Runtime safety', 'Last cycle', 'Open positions', 'Snapshot', 'Mode', 'Scope', 'Sub-accounts', 'Actionable events', 'Candidates', 'Awaiting approval', 'Promoted', 'Errored'},
    'Trading': {'Current Equity', 'Open Positions', 'Closed Trades', 'Win Rate', 'Realized P&L', 'Proposals rejected (threshold)'},
}
counts = {'Home': (12, 4, 0, 0, 0), 'Trading': (6, 3, 0, 1, 0)}
pages = {}
failures = []
shape_failures = []
for page in labels:
    rows = [r for r in outcomes if r['page'] == page]
    complete = [r for r in rows if r['status'] == 'complete']
    durations = [r['seconds'] for r in complete]
    pages[page] = {'requests': len(rows), 'complete': len(complete), 'status_counts': dict(Counter(r['status'] for r in rows)), 'complete_p50_seconds': percentile(durations, .5), 'complete_p95_seconds': percentile(durations, .95), 'complete_max_seconds': max(durations, default=None), 'at_least_20_complete': len(complete) >= 20}
    for row in complete:
        checks = (
            set(r.get('label') for r in row['metrics']) == labels[page],
            len(row['metrics']) == len(labels[page]),
            all(r.get('placeholder') is False for r in row['metrics']),
            tuple(row['elements'][k] for k in ('metric','dataframe','table','vega_lite_chart','exception')) == counts[page],
            row['incomplete_alerts'] == 0,
        )
        if not all(checks):
            shape_failures.append({'started_at':row['started_at'],'page':page,'client':row['client'],'checks':checks})
    failures += [{k:r.get(k) for k in ('started_at','client','page','status','seconds','alerts','alert_history','maximum_background_watchers')} for r in rows if r['status'] != 'complete']
health = read('health-samples')
memory = lines(raw / 'v68-resumed-memory-samples.jsonl')
window_memory = [r for r in memory if start <= stamp(r['captured_at']) <= end]
cycles = {}
for row in memory:
    for event in row.get('cycles', []):
        cycles.setdefault(event['cycle_id'], {})[event['event_type']] = event['timestamp']
full = {cid:e for cid,e in cycles.items() if 'cycle_started' in e and 'cycle_completed' in e and start <= stamp(e['cycle_started']) <= stamp(e['cycle_completed']) <= end}
cycle_errors = {cid:e for cid,e in cycles.items() if 'cycle_errored' in e and start <= stamp(e['cycle_errored']) <= end}
before = json.loads((base/'before-runtime.json').read_text())
after = json.loads((base/'after-runtime.json').read_text())
same_processes = all(before['processes'][k]['pid'] == after['processes'][k]['pid'] and before['processes'][k]['start_ticks'] == after['processes'][k]['start_ticks'] for k in ('engine','dashboard'))
diagnostics = lines(base/'diagnostics.jsonl')
window_diag = [r for r in diagnostics if r.get('fly_timestamp') and start <= stamp(r['fly_timestamp']) <= end]
cpu = {}
cpu_path = base/'cpu-window-supplement.json'
if not cpu_path.exists():
    cpu_path = base/'cpu-history.json'
if cpu_path.exists():
    for row in json.loads(cpu_path.read_text())['data']['result']:
        name = row['metric']['__name__']
        points = [(float(t),float(v)) for t,v in row.get('values', [])]
        inside = [(t,v) for t,v in points if start <= t <= end]
        earlier = [t for t,v in points if t < start]
        later = [t for t,v in points if t > end]
        deltas = [(a,b,y-x) for (a,x),(b,y) in zip(points,points[1:]) if start <= a < b <= end]
        cpu[name] = {'window_points':len(inside),'min':min((v for _,v in inside),default=None),'max':max((v for _,v in inside),default=None),'first':inside[0] if inside else None,'last':inside[-1] if inside else None,'preceding_point':max(earlier,default=None),'following_point':min(later,default=None),'max_sample_gap_seconds':max((b-a for (a,_),(b,_) in zip(points,points[1:])),default=None)}
        if name.endswith('throttle'):
            cpu[name].update(positive_increment_centiseconds=sum(max(d,0) for _,_,d in deltas),positive_intervals=[r for r in deltas if r[2]>0],reset_intervals=[r for r in deltas if r[2]<0])
warmup = [{k:r.get(k) for k in ('page','status','seconds','first_incomplete_shell_seconds')} for r in read('warmup-protocol')]
guest_peak = max((r['memory_kib']['MemTotal']-r['memory_kib']['MemAvailable'])/1024 for r in window_memory)
rss_peak = max(int(r['processes']['dashboard']['VmRSS'].split()[0]) for r in window_memory)
growth = (rss_peak-summary['warmed_dashboard_baseline_rss_kib'])/1024
reconciled = expected == actual and all(n==1 for n in expected.values())
health_pass = bool(health) and all(r['ok'] and r['seconds']<5 for r in health)
all_pages = len(outcomes)>0 and not failures and not shape_failures
protocol_pass = all_pages and reconciled and health_pass and end-start>=600 and bool(full) and not cycle_errors and same_processes and not summary['stop_reasons'] and guest_peak<=768 and growth<=256 and all(p['at_least_20_complete'] and p['complete_p95_seconds']<=2 for p in pages.values())
audit = {
    'verdict':'PASS_BOUNDED_PROTOCOL_SAMPLE' if protocol_pass else 'FAIL_SAMPLE',
    'window':{'start':summary['started_at'],'end':summary['ended_at'],'seconds':end-start},
    'requests':{'starts':len(starts),'outcomes':len(outcomes),'bijective':reconciled,'status_counts':dict(Counter(r['status'] for r in outcomes)),'shape_failures':shape_failures},
    'pages':pages,'failures':failures,'warmup':warmup,
    'health':{'samples':len(health),'all_under_5s_ok':health_pass,'max_seconds':max(r['seconds'] for r in health)},
    'full_cycles':full,'cycle_errors':cycle_errors,
    'memory':{'window_samples':len(window_memory),'raw_samples':len(memory),'guest_peak_mib':guest_peak,'dashboard_rss_growth_mib':growth,'configured_mib':2048,'original_1024_mib_qualified':False},
    'runtime':{'before_checks':before['checks'],'after_checks':after['checks'],'same_processes':same_processes},
    'diagnostics':{'raw_rows':len(diagnostics),'window_rows':len(window_diag),'window_classes':[{'kind':k[0],'reason':k[1],'stage':k[2],'count':v} for k,v in Counter((r['diagnostic']['kind'],r['diagnostic']['reason'],r['diagnostic']['stage']) for r in window_diag).items()]},
    'cpu':cpu,'cpu_source':cpu_path.name,
    'limits':['Protocol shape/metric coverage, not native viewport or table-cell oracle.','Observer starts/outcomes are bijective records, not server request IDs; queued responses after timeouts can contaminate reused-socket page/timing attribution. Separate fresh connections corroborate persistence.','Warmup is one pair, not cold percentile acceptance.','Original 1 GiB and depleted CPU acceptance remain separate.','Async diagnostic overlap and local/Fly timestamp differences cannot attribute a failure to a request or writer.','All earlier failed and user-stopped samples remain retained.'],
    'source_changes':False,
}
(base/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
manifest = {str(p.relative_to(base)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(base.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
(base/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:audit[k] for k in ('verdict','window','requests','pages','health','full_cycles','memory')},indent=2))
