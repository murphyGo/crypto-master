"""Read-only production query profile; emits timings/hashes, never source rows."""
import json
import shlex
import subprocess
from pathlib import Path

out = Path('.tmp/dashboard-rearm-20261030')
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
report={'captured_at':at.isoformat(),'method':'Separate read-only process, direct sequential cold projections then verified unchanged-result reuse; no checkpoints, no browser timing. Warm Python imports/OS caches; cProfile adds overhead only to the separate activity attribution trial.','series':[]}
for kind in ('activity','ledger','snapshots','candidates','proposals'):
 q=Query(root,kind,accounts=accounts if kind in ('ledger','snapshots') else ('default',),window='24h' if kind=='proposals' else 'lifetime',at=at).normalized()
 previous=None
 for trial in ('cold','revalidate'):
  start=time.perf_counter();cpu=time.process_time();result=None
  row={'kind':kind,'trial':trial}
  try:
   for part in build_projection(q,Limits(),previous=previous):
    if part is not None:result=part
   assert result is not None
   payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
   row.update(status='complete',payload_bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),source_coverage=result.get('source_coverage',{}),events=result.get('total'))
   previous=payload
  except ReadFailure as e:row.update(status='unavailable',reason=str(e))
  row.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
  report['series'].append(row)
q=Query(root,'activity',at=at).normalized();p=cProfile.Profile()
try:
 p.enable()
 for part in build_projection(q,Limits()):pass
 report['profile_status']='complete'
except ReadFailure as e:report['profile_status']=str(e)
finally:p.disable()
stats=[{'file':f,'line':line,'function':name,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct} for (f,line,name),(cc,nc,tt,ct,callers) in pstats.Stats(p).stats.items()]
report['activity_profile_top']=sorted(stats,key=lambda r:r['cumulative_seconds'],reverse=True)[:25]
print(json.dumps(report))
'''
result = subprocess.run(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)], capture_output=True,text=True,timeout=180)
if result.returncode:
    print(result.stderr[-2000:])
    raise SystemExit(result.returncode)
report=json.loads(result.stdout)
(out/'initial-profile.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'series':report['series'],'top':report['activity_profile_top'][:8]},indent=2))
