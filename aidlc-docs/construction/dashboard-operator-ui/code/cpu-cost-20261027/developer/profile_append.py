import ast,cProfile,hashlib,io,json,pstats,shutil,time
from datetime import datetime,timezone
from pathlib import Path
from src.dashboard import app,projections
from src.dashboard.read_models import Query,Limits
from src.runtime.activity_events import ActivityEvent
OUT=Path('/private/tmp/crypto-master-cpu-cost-delivery-20261027/developer')
ROOT=Path('/private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z')
FIXTURE=OUT/'append-fixture'
assert not FIXTURE.exists()
FIXTURE.mkdir()
shutil.copytree(ROOT/'runtime',FIXTURE/'runtime',copy_function=shutil.copy2)
AT=datetime(2026,10,25,10,50,2,tzinfo=timezone.utc)
query=Query(FIXTURE,'activity',at=AT).normalized()
tree=ast.parse((OUT/'baseline-projections.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_projection')
unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[]);ast.fix_missing_locations(unit)
namespace={};exec(compile(unit,str(OUT/'baseline-projections.py'),'exec'),projections.__dict__,namespace)
functions={'baseline':namespace['build_projection'],'candidate':projections.build_projection}
def consume(fn,previous=None):
 result=None
 for part in fn(query,Limits(),previous=previous):
  if part is not None:result=part
 assert result is not None
 return result
initial=consume(functions['baseline'])
previous=json.dumps(initial,separators=(',',':')).encode()
row=ActivityEvent(timestamp=AT,event_type='monitor_pass',cycle_id='offline-append',message='isolated fixture append',details={'sub_account_id':'default','open_positions':0}).model_dump_json()+'\n'
with (FIXTURE/'runtime/activity.2026-10.jsonl').open('a') as handle:handle.write(row)
report={'method':'Canonical direct reader cProfile after one valid engine-shaped append to a private COPY of existing frozen activity data. No checkpoint store; both variants receive identical old encoded projection and changed sources. This characterizes a remaining mutable-source path, not production attribution or latency qualification.','original_total':initial['total'],'appended_bytes':len(row.encode()),'variants':[]}
for name,fn in functions.items():
 profile=cProfile.Profile();start=time.perf_counter();cpu=time.process_time()
 result=profile.runcall(consume,fn,previous)
 cpu=time.process_time()-cpu;wall=time.perf_counter()-start
 encoded=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
 assert result['total']==initial['total']+1
 assert result['_source_digest']!=initial['_source_digest']
 profile.dump_stats(str(OUT/('append-'+name+'.prof')))
 text=io.StringIO();pstats.Stats(profile,stream=text).strip_dirs().sort_stats('cumulative').print_stats(30)
 (OUT/('append-'+name+'-cumulative.txt')).write_text(text.getvalue())
 report['variants'].append({'name':name,'cpu_seconds':cpu,'wall_seconds':wall,'full_payload_sha256':hashlib.sha256(encoded).hexdigest(),'total':result['total'],'coverage':result['source_coverage']})
assert len({row['full_payload_sha256'] for row in report['variants']})==1
manifest=json.loads((OUT/'input-manifest.json').read_text())
for rel,meta in manifest.items():
 if rel.startswith('runtime/'):
  assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==meta['sha256']
report['original_inputs_unchanged']=True
(OUT/'append-profile.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
