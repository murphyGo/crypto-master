"""Single-thread CPU attribution; no canonical input mutations or production IO."""
import cProfile, hashlib, io, json, pstats, time
from datetime import datetime, timezone
from pathlib import Path

from src.dashboard import app  # Warm the same imports as a running dashboard.
from src.dashboard.projections import build_projection
from src.dashboard.read_models import Limits, Query

OUT=Path('/private/tmp/crypto-master-cpu-cost-delivery-20261027/developer')
ROOT=Path('/private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z')
SOURCE=Path('/private/tmp/crypto-master-cpu-cost-20261027')
AT=datetime(2026,10,25,10,50,2,tzinfo=timezone.utc)
ACCOUNTS=tuple(sorted(p.name for p in (ROOT/'portfolio/paper').iterdir() if p.is_dir()))
FILES=sorted(p for directory in ['runtime','proposals','trades','portfolio','feedback/state'] for p in (ROOT/directory).rglob('*') if p.is_file())

def manifest():
 return {str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in FILES}

def fingerprint(data):
 b=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
 return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def consume(query,previous=None,store=None):
 result=None
 for part in build_projection(query,Limits(),previous=previous,checkpoint_store=store):
  if part is not None:result=part
 assert result is not None
 return result

def stats(profile):
 out=[]
 for (file,line,name),(cc,nc,tt,ct,callers) in pstats.Stats(profile).stats.items():
  out.append({'file':file,'line':line,'name':name,'calls':nc,'self':tt,'cumulative':ct})
 return sorted(out,key=lambda r:r['cumulative'],reverse=True)[:35]

def profile(label,fn,repeats=1):
 profiler=cProfile.Profile(); cpu=[];wall=[];result=None
 for _ in range(repeats):
  start=time.perf_counter();cp=time.process_time()
  result=profiler.runcall(fn)
  cpu.append(time.process_time()-cp);wall.append(time.perf_counter()-start)
 profiler.dump_stats(str(OUT/(label+'.prof')))
 for order in ['cumulative','tottime']:
  text=io.StringIO();pstats.Stats(profiler,stream=text).strip_dirs().sort_stats(order).print_stats(40)
  (OUT/(label+'-'+order+'.txt')).write_text(text.getvalue())
 return result,{'label':label,'repeats':repeats,'cpu_seconds':cpu,'wall_seconds':wall,'payload':fingerprint(result),'top':stats(profiler)}

before=manifest()
(OUT/'input-manifest.json').write_text(json.dumps(before,indent=2)+'\n')
report={'baseline':'2eae9cf74d33e52b5058e2a5597f2e3a76e86cdd','method':'Exact production build_projection, main-thread cProfile, warmed application imports and OS cache. Fixed-time full-payload equality. Repeated unchanged refresh deliberately revalidates every generation, modelling a service result expired by a20s poll; no fresh-cache bypass. CPU diagnosis, not browser/guest qualification.','fixture_root':str(ROOT),'fixed_now':AT.isoformat(),'accounts':ACCOUNTS,'variants':[],'source_hashes':{str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((SOURCE/'src/dashboard').rglob('*.py'))}}
for kind in ['activity','ledger','snapshots','candidates','proposals']:
 q=Query(ROOT,kind,accounts=ACCOUNTS if kind in ['ledger','snapshots'] else ('default',),window='24h' if kind=='proposals' else 'lifetime',at=AT).normalized()
 data,cold=profile(kind+'-cold',lambda:consume(q))
 previous=json.dumps(data,separators=(',',':')).encode()
 _,warm=profile(kind+'-revalidate',lambda:consume(q,previous),repeats=5)
 assert warm['payload']==cold['payload']
 report['variants'].extend([cold,warm])
 (OUT/'baseline-profile.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'kind':kind,'cold_cpu':cold['cpu_seconds'],'refresh_cpu':warm['cpu_seconds'],'refresh_top':[(x['name'],round(x['cumulative'],4)) for x in warm['top'][:7]]}),flush=True)
assert manifest()==before
report['input_hashes_unchanged']=True
(OUT/'baseline-profile.json').write_text(json.dumps(report,indent=2)+'\n')
print('BASELINE_DIRECT_DONE',flush=True)
