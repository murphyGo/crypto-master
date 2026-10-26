"""Finalize existing frozen v67 evidence and verify local Git source hashes only."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import io
import json
import re
import subprocess
import tarfile

OUT=Path(__file__).resolve().parent
REPO=Path('/private/tmp/crypto-master-cpu-cost-20261027')
SOURCE=Path('/private/tmp/crypto-master-debt087-089-closeout/cpu-cost-final.json')
PRIOR=REPO/'aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/operations/qa-v66-audit/supplements/recovery/page-progress-final.json'

def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(path.read_text())
def write(name,value):
    path=OUT/name
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    path.chmod(0o444)
    return path

def capture(source,relative):
    before=source.stat();data=source.read_bytes();after=source.stat()
    shape=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    assert shape(before)==shape(after)
    target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(data)
    target.chmod(0o444)
    return {'source':str(source),'relative_copy':relative,'bytes':len(data),'sha256':sha(data),'source_mtime_ns':after.st_mtime_ns}

manifest=load(OUT/'freeze-manifest.json')
for row in manifest['files']:
    data=(OUT/row['relative_copy']).read_bytes()
    assert len(data)==row['bytes'] and sha(data)==row['sha256']
proof=capture(SOURCE,'supplements/runtime/cpu-cost-final.json')
runtime=load(OUT/proof['relative_copy']);prior=load(PRIOR)
expected='120b4408dc0d3eedb241edf26f8f161c062cf126'
assert runtime['expected_source']==expected
hashes=runtime['runtime_sha256'];assert len(hashes)==182
archive=subprocess.check_output(['git','archive','--format=tar',expected,*hashes],cwd=REPO)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    actual={p:sha(tar.extractfile(p).read()) for p in hashes}
assert actual==hashes
assert runtime['fly']['release']==67 and runtime['fly']['machine']=='6835752b711958'
assert runtime['fly']['instance']=='01M5WNEGCGSRY9CE34VRT7K6X3'
assert runtime['fly']['image']['digest']=='sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382'
assert runtime['internal_health']==runtime['public_health']=={'status':200,'body':'ok'}
comparisons={name:runtime[name]==prior[name] for name in ['dependencies','configuration']}
comparisons.update({name:runtime['fly'][name]==prior['fly'][name] for name in ['guest','mounts']})
assert all(comparisons.values())
audit=load(OUT/'audit-results.json');summary=load(OUT/'audit-summary.json');supp=load(OUT/'diagnostics-supplement.json');cpu=load(OUT/'cpu-window-proof.json');counter=load(OUT/'cpu-counter-interpretation.json')
observed={kind:values for kind,values in audit['memory']['pid_sets'].items()}
assert all(observed[p['kind']]==[p['pid']] for p in runtime['processes'])
cycle=summary['full_cycles'][0]
for event in runtime['cycles']:
    assert event['cycle_id']==cycle['cycle_id']
    field={'cycle_started':'started_at','cycle_completed':'completed_at'}[event['event_type']]
    assert event['timestamp']==cycle[field]
write('post-run-runtime-verification.json',{'freeze':proof,'captured_at':runtime['captured_at'],'expected_source':expected,'independent_git_blob_hash_matches':True,'runtime_files_checked':len(hashes),'release':runtime['fly']['release'],'machine':runtime['fly']['machine'],'instance':runtime['fly']['instance'],'image':runtime['fly']['image'],'configuration_unchanged_vs_v66':comparisons,'guest':runtime['fly']['guest'],'observed_process_ids_still_match':True,'health':{'public':runtime['public_health'],'internal':runtime['internal_health']},'cycle_matches_in_window_observation':True,'cycle':cycle,'event_counts':runtime['event_counts'],'errors':runtime['errors'],'interpretation':'Separate post-observation source/config/process/health proof. Does not erase eight incomplete page outcomes or warmup misses. Matching PID numbers across different releases alone are not proof of absence of deployment restart.'})
write('collector-termination-proof.json',{'authority':'Parent confirmed observer session73599 exited1, diagnosticcollector21879 exited0 and local process check found no observer/collector/flylogs process before freeze. Independent QA made no process or production query.','collector_report':{'diagnostic_events':566,'log_lines':154783,'json_records':4993,'client_exit':127,'stopped_by_collector':True,'seconds':1836.32026775},'interpretation':'Collector requested stop is retained explicitly; client exit127 is not silently recast as zero. Framed payload bytes are audited separately. Rate limiting/drops and delivery delay prevent absence-of-diagnostic claims.'})
rows=[json.loads(s) for s in (OUT/'frozen/raw/v67-page-observations.jsonl').read_text().splitlines()]
watchers={'complete_request_watcher_counts':dict(Counter(r.get('maximum_background_watchers') for r in rows if r['status']=='complete')),'failed_requests':[{'key':[r['started_at'],r['client'],r['page']],'status':r['status'],'seconds':r['seconds'],'maximum_background_watchers':r.get('maximum_background_watchers'),'script_finished_values':r.get('script_finished_values'),'auto_rerun_registrations':r.get('auto_rerun_registrations')} for r in rows if r['status']!='complete'],'interpretation':'The first four terminal incomplete responses had zero watchers; the latter four had max one watcher and bounded registered reruns. These protocol counts do not identify function-level CPU costs or a sole failure cause.'}
write('watcher-protocol-counts.json',watchers)
final={'verdict':'FAIL_SAMPLE','window':summary['window'],'requests':summary['requests'],'pages':supp['page_distributions'],'failure_kind':'8 terminal incomplete outcomes, neither30s deadline timeouts nor guard aborts; all retained.','failure_durations_seconds':[r['seconds'] for r in supp['failed_request_timeline']],'health_samples':audit['health']['samples'],'health_failures':len(audit['health']['failures']),'health_max_seconds':summary['health_max_seconds'],'full_cycles':summary['full_cycles'],'cycle_errors':summary['cycle_errors'],'memory':audit['memory'],'warmup':audit['enhanced_protocol_audit']['warmup']['observations'],'diagnostics_rows':supp['diagnostics']['rows'],'diagnostics_window_rows':supp['diagnostics']['in_page_window_by_fly_timestamp'],'diagnostic_source_changed_events_in_window':sum(r['count'] for r in supp['diagnostics']['window_classifications'] if r['reason']=='source_changed'),'cpu_sampled_original_window_coverage':cpu['sampled_original_window_coverage'],'cpu_balance_window_centiseconds':{'min':cpu['series']['fly_instance_cpu_balance']['window_minimum'],'max':cpu['series']['fly_instance_cpu_balance']['window_maximum']},'cpu_throttle_counter':counter['counter_analysis'],'runtime_verification':'post-run-runtime-verification.json','preserved_unqualified':['native viewport','cache-cold/process-cold >=20 samples per page','depleted CPU qualification','original1GiB configuration acceptance'],'interpretation':['Correctness tests/local CPU improvement and successful health/fullcycle do not qualify incomplete page outcomes.','This failed observation has no sampled throttle counter increase; do not attribute these failures to sampled CPU throttling.','Async source_changed diagnostics overlap requests but have no request/query identity, so causality is not established.','Memory sampler retained1.678257s after formal page observation end; reported raw maxima include that small drain tail.','All previous v66 failures and this run warmup misses remain preserved.'],'production_load_added_by_auditor':False}
write('final-audit-outcome.json',final)
patterns={'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','openai_key':rb'sk-(?:proj-)?[A-Za-z0-9_-]{20,}','github_token':rb'gh[pousr]_[A-Za-z0-9]{30,}','fly_token':rb'FlyV1 [A-Za-z0-9_-]{30,}'}
hits=[];inspected=[]
for folder in [OUT/'frozen',OUT/'supplements']:
    for path in folder.rglob('*'):
        if path.is_file():
            data=path.read_bytes();inspected.append(str(path.relative_to(OUT)))
            for name,pattern in patterns.items():
                if re.search(pattern,data):hits.append({'path':str(path.relative_to(OUT)),'pattern':name})
write('artifact-hygiene.json',{'scanned_files':inspected,'credential_pattern_hits':hits,'limits':'Known credential patterns only, not a proof against arbitrary secret formats; no values are reproduced.'})
assert not hits,hits
files={str(p.relative_to(OUT)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'self-check-v66' not in p.parts}
write('audit-package-manifest.json',{'files':files,'file_count':len(files),'total_bytes':sum(v['bytes'] for v in files.values()),'self_check_replay':'Retained separately under self-check-v66; its result and driver hashes are included here via adapter-self-check.json.','initial_freeze_file_count':manifest['file_count'],'initial_freeze_bytes':manifest['total_bytes'],'initial_freeze_manifest_sha256':sha((OUT/'freeze-manifest.json').read_bytes())})
print(json.dumps({'verdict':final['verdict'],'files':len(files),'bytes':sum(v['bytes'] for v in files.values()),'runtime_git182_match':True,'all_final_artifacts_ready':True,'source_copies':len(inspected),'hygiene_hits':len(hits)}))
