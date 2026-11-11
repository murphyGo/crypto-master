"""Prepare read-only candidate/base comparison in an isolated production process."""
import base64,hashlib,shlex
from pathlib import Path
source=Path('src/utils/bounded_read.py').read_bytes()
code=r'''
import base64,hashlib,json,resource,sys,time,types
from pathlib import Path
from datetime import datetime,timezone
from src.dashboard import projections
from src.dashboard.read_models import Limits,Query
from src.utils import bounded_read as baseline
assert hashlib.sha256(Path('/app/src/utils/bounded_read.py').read_bytes()).hexdigest()==BASELINE_SHA
candidate=types.ModuleType('candidate_bounded_read');sys.modules[candidate.__name__]=candidate
source=base64.b64decode(SOURCE)
assert hashlib.sha256(source).hexdigest()==CANDIDATE_SHA
exec(compile(source,'<candidate_bounded_read>','exec'),candidate.__dict__)
candidate.Generation=baseline.Generation;candidate.ReadFailure=baseline.ReadFailure
root=Path('/data');accounts=tuple(sorted(p.name for p in (root/'portfolio/paper').iterdir() if p.is_dir()));at=datetime.now(timezone.utc)
q=Query(root,'snapshots',accounts=accounts,at=at).normalized()
report={'captured_at':at.isoformat(),'baseline_sha256':BASELINE_SHA,'candidate_sha256':CANDIDATE_SHA,'method':'Read-only standalone process, candidate compiled only in memory; alternate initial projections on canonical files, warm imports/OS, no checkpoints or previous result. Same fixed evaluation time; no engine or dashboard mutation.','trials':[],'pre_read_high_water_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
for name in ('baseline','candidate','candidate','baseline','baseline','candidate'):
 projections.json_array_bytes=getattr(baseline if name=='baseline' else candidate,'json_array_bytes')
 result=None;row={'reader':name};start=time.perf_counter();cpu=time.process_time()
 try:
  for part in projections.build_projection(q,Limits()):
   if part is not None:result=part
  assert result is not None
  row.update(status='complete',source_coverage=result['source_coverage'],source_digest=result['_source_digest'])
 except baseline.ReadFailure as exc:row.update(status='unavailable',reason=str(exc))
 row.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
 if result is not None:
  payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
  row.update(payload_sha256=hashlib.sha256(payload).hexdigest(),payload_bytes=len(payload))
 report['trials'].append(row)
report['process_high_water_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps(report))
'''
code=code.replace('BASELINE_SHA',repr(hashlib.sha256(Path('.tmp/dashboard-initial-read-20261111/bounded_read_baseline.py').read_bytes()).hexdigest())).replace('CANDIDATE_SHA',repr(hashlib.sha256(source).hexdigest())).replace('SOURCE',repr(base64.b64encode(source).decode()))
print(shlex.join(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)]))
