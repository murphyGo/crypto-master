"""Profile isolated checkpoint reconstruction; /data is read-only input."""
import shlex

code = r'''
import cProfile,hashlib,json,pstats,resource,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from src.dashboard.projections import build_projection
from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.read_models import Limits,Query
from src.utils.bounded_read import ReadFailure
root=Path('/data')
accounts=tuple(sorted(p.name for p in (root/'portfolio/paper').iterdir() if p.is_dir()))
at=datetime.now(timezone.utc)
report={'captured_at':at.isoformat(),'method':'isolated temporary checkpoint store under /tmp; /data read only; fixed evaluation time; warm imports/OS; profile overhead separate','trials':[]}
for kind in ('snapshots','activity'):
 q=Query(root,kind,accounts=accounts if kind=='snapshots' else ('default',),at=at).normalized()
 with tempfile.TemporaryDirectory(prefix='cm-refresh-profile-') as scratch:
  store=CheckpointStore(Path(scratch))
  for phase in ('direct','empty_store','warm_store','profile_empty_store'):
   if phase=='profile_empty_store':
    store=CheckpointStore(Path(scratch)/'profile');store.data_root.mkdir()
   profiler=cProfile.Profile();row={'kind':kind,'phase':phase};result=None
   start=time.perf_counter();cpu=time.process_time()
   if phase.startswith('profile'):profiler.enable()
   try:
    for part in build_projection(q,Limits(),checkpoint_store=None if phase=='direct' else store):
     if part is not None:result=part
    assert result is not None
    row.update(status='complete',source_coverage=result['source_coverage'],source_digest=result['_source_digest'])
   except ReadFailure as exc:row.update(status='unavailable',reason=str(exc))
   finally:
    if phase.startswith('profile'):profiler.disable()
   row.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,checkpoint_hits=store.hits,checkpoint_misses=store.misses)
   if result is not None:
    payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    row.update(payload_bytes=len(payload),payload_sha256=hashlib.sha256(payload).hexdigest())
   if phase.startswith('profile'):
    stats=[{'file':f,'line':line,'function':name,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct} for (f,line,name),(cc,nc,tt,ct,callers) in pstats.Stats(profiler).stats.items()]
    row['top']=sorted(stats,key=lambda x:x['cumulative_seconds'],reverse=True)[:30]
   report['trials'].append(row)
report['process_highwater_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
report['temporary_stores_removed']=True
print(json.dumps(report))
'''
print(shlex.join(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)]))
