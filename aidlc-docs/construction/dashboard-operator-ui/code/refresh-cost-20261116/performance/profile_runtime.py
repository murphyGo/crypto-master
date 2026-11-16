"""Read-only production attribution; warm imports/OS, no cache writes or rows out."""
import json,shlex
from pathlib import Path
code = r'''
import cProfile,hashlib,json,pstats,time
from pathlib import Path
from datetime import datetime,timezone
from src.dashboard.projections import build_projection
from src.dashboard.read_models import Limits,Query
from src.utils.bounded_read import ReadFailure
root=Path('/data')
accounts=tuple(sorted(p.name for p in (root/'portfolio/paper').iterdir() if p.is_dir()))
at=datetime.now(timezone.utc)
report={'captured_at':at.isoformat(),'method':'direct initial projections; no previous result or checkpoint, warm imports/OS; profile overhead separate','trials':[]}
for kind in ('snapshots','activity'):
 q=Query(root,kind,accounts=accounts if kind=='snapshots' else ('default',),at=at).normalized()
 for profiled in (False,True):
  profiler=cProfile.Profile(); row={'kind':kind,'profiled':profiled}
  result=None;start=time.perf_counter();cpu=time.process_time()
  if profiled:profiler.enable()
  try:
   for part in build_projection(q,Limits()):
    if part is not None:result=part
   assert result is not None
   row.update(status='complete',source_coverage=result['source_coverage'])
  except ReadFailure as exc:row.update(status='unavailable',reason=str(exc))
  finally:
   if profiled:profiler.disable()
  row.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
  if result is not None:
   payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
   row.update(payload_bytes=len(payload),payload_sha256=hashlib.sha256(payload).hexdigest())
  if profiled:
   stats=[{'file':f,'line':line,'function':name,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct} for (f,line,name),(cc,nc,tt,ct,callers) in pstats.Stats(profiler).stats.items()]
   row['top']=sorted(stats,key=lambda x:x['cumulative_seconds'],reverse=True)[:35]
  report['trials'].append(row)
print(json.dumps(report))
'''
command=shlex.join(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)])
print(command)
