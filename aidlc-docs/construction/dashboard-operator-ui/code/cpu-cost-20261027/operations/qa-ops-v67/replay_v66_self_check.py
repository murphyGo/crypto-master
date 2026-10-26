"""Replay immutable v66 bytes through phase/path-only v67 adapters, offline."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import sys

OUT = Path(__file__).resolve().parent
PRIOR = Path('/private/tmp/crypto-master-cpu-cost-20261027/aidlc-docs/construction/dashboard-operator-ui/code/page-progress-20261027/operations/qa-v66-audit')
REPLAY = OUT/'self-check-v66'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(*args):
    result = subprocess.run([sys.executable,*map(str,args)],cwd=REPLAY,text=True,capture_output=True)
    assert result.returncode == 0, result.stderr
    return result.stdout

def normalized(value):
    value=json.loads(json.dumps(value))
    value.pop('audit_completed_at',None)
    value.pop('auditor_completed_at',None)
    if 'freeze' in value:
        value['freeze'].pop('manifest',None)
    return value

assert not REPLAY.exists(), 'Self-check capture already exists; retain it and use a separate task directory.'
old_hashes={str(p.relative_to(PRIOR)):sha(p) for p in PRIOR.rglob('*') if p.is_file()}
REPLAY.mkdir()
drivers=['audit_v67.py','base_auditor.py','supplement_audit.py','cpu_window_proof.py']
for name in drivers:
    shutil.copyfile(OUT/name,REPLAY/name)
manifest={'captured_at':datetime.now(timezone.utc).isoformat(),'mode':'self-check copies; original v66 byte content unchanged; v67 filename adapter only','files':[],'auditor_sha256':{name:sha(REPLAY/name) for name in drivers[:2]}}
for source in sorted((PRIOR/'frozen').rglob('*')):
    if not source.is_file():continue
    rel=str(source.relative_to(PRIOR)).replace('v66-','v67-')
    target=REPLAY/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    assert sha(source)==sha(target)
    manifest['files'].append({'source':str(source),'copy':str(target),'relative_copy':rel,'bytes':source.stat().st_size,'sha256':sha(source),'source_mtime_ns':source.stat().st_mtime_ns})
manifest['file_count']=len(manifest['files'])
manifest['total_bytes']=sum(r['bytes'] for r in manifest['files'])
(REPLAY/'freeze-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(REPLAY/'replay-stdout.json').write_text(run(REPLAY/'audit_v67.py','--audit-frozen'))
actual=json.loads((REPLAY/'audit-results.json').read_text())
expected=json.loads((PRIOR/'audit-results.json').read_text())
assert normalized(actual)==normalized(expected), 'Main audit output differs beyond timestamps/path.'
summary=json.loads((REPLAY/'audit-summary.json').read_text())
assert summary==json.loads((PRIOR/'audit-summary.json').read_text())
assert summary['verdict']=='FAIL_SAMPLE'
assert summary['requests']['starts']==summary['requests']['outcomes']==356
assert summary['requests']['status_counts']=={'complete':352,'aborted_after_guard_stop':4}
assert len(actual['health']['failures'])==1
assert not summary['full_cycles']
assert actual['enhanced_protocol_audit']['warmup']['observations'][0]['seconds']>10
cpu_input=REPLAY/'replay-inputs'/'v67-cpu-final.json'
cpu_input.parent.mkdir()
shutil.copy2(PRIOR/'supplements/cpu/v66-cpu-final.json',cpu_input)
(REPLAY/'cpu-replay-stdout.json').write_text(run(REPLAY/'supplement_audit.py','--cpu',cpu_input,'--name','cpu-supplement'))
(REPLAY/'cpu-window-stdout.json').write_text(run(REPLAY/'cpu_window_proof.py'))
cpu=json.loads((REPLAY/'cpu-window-proof.json').read_text())
assert cpu['sampled_original_window_coverage'] is True
assert cpu['sampled_throttle_observed'] is True
assert cpu['sampled_zero_balance_observed'] is False
assert cpu['depleted_cpu_qualified'] is False
assert cpu['series']==json.loads((PRIOR/'cpu-window-proof.json').read_text())['series']
assert 'buffered CPU evidence' not in cpu['qualification_limits']
assert old_hashes=={str(p.relative_to(PRIOR)):sha(p) for p in PRIOR.rglob('*') if p.is_file()}
report={'result':'PASS_ADAPTER_EQUIVALENCE','prior_package':str(PRIOR),'prior_file_count':len(old_hashes),'prior_package_unchanged':True,'content_copy_hashes_equal':True,'entire_main_audit_equal_except_dynamic_timestamps_and_manifest_path':True,'entire_summary_equal':True,'preserved_verdict':summary['verdict'],'requests':summary['requests'],'health_failures':len(actual['health']['failures']),'full_cycles':summary['full_cycles'],'strict_shape_and_classification_logic_unchanged':True,'cpu_series_exactly_equal':True,'cpu_original_window_coverage':True,'sampled_positive_throttle_retained':True,'zero_balance_not_sampled':True,'depleted_qualified':False,'cpu_interpretation':cpu['qualification_limits'],'self_check_script_sha256':sha(Path(__file__)),'prior_and_adapter_drivers':{name:sha(OUT/name) for name in drivers},'production_load_added':False,'scope':'Only immutable prior evidence replayed. No future observation was started or frozen; v67 is provisional until parent verifies actual deployment.'}
(OUT/'adapter-self-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
