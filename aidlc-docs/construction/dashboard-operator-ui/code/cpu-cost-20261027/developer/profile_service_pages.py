import ast,cProfile,hashlib,io,json,pstats,sys,time
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest
from src.dashboard import app, data_service, projections
from src.dashboard.data_service import DashboardDataService
from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.pages import home,trading
from src.config import Settings

OUT=Path('/private/tmp/crypto-master-cpu-cost-delivery-20261027/developer')
LABEL=sys.argv[1]
ROOT=Path('/private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z')
AT=datetime(2026,10,25,10,50,2,tzinfo=timezone.utc)
settings=Settings(data_dir=ROOT,log_file=OUT/'harness.log')
for name,module in list(sys.modules.items()):
 if name.startswith('src.') and hasattr(module,'get_settings'):module.get_settings=lambda:settings
accounts=sorted(p.name for p in (ROOT/'portfolio/paper').iterdir() if p.is_dir())
queries=home._home_queries('paper','Aggregate',accounts)
store_root=OUT/(LABEL+'-service-checkpoints');store_root.mkdir(exist_ok=True)
store=CheckpointStore(store_root)
assert store.prepare(queries[0])
if LABEL=='baseline-enabled':
 tree=ast.parse((OUT/'baseline-projections.py').read_text())
 node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_projection')
 unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[]);ast.fix_missing_locations(unit)
 namespace={}
 exec(compile(unit,str(OUT/'baseline-projections.py'),'exec'),projections.__dict__,namespace)
 projections.build_projection=namespace['build_projection']
worker=[]
service=None

def build(q,limits):
 with service._condition:
  entry=service._cache.get(q);previous=entry.result.payload if entry else None
 begin=time.thread_time();wall=time.perf_counter()
 try:
  yield from projections.build_projection(replace(q,at=AT),limits,previous=previous,checkpoint_store=store)
 finally:worker.append({'kind':q.kind,'window':q.window,'thread_cpu':time.thread_time()-begin,'wall':time.perf_counter()-wall})

service=DashboardDataService(builder=build)
data_service.get_data_service=lambda:service

def age():
 with service._condition:
  for entry in service._cache.values():entry.evaluated-=20

def fingerprint(results):
 return {kind:hashlib.sha256(json.dumps(result.data(),sort_keys=True,separators=(',',':')).encode()).hexdigest() for kind,result in results.items()}

def page_fingerprint(at):
 raw={'metrics':[(m.label,m.value) for m in at.metric],'frames':[frame.value.to_json(date_format='iso') for frame in at.dataframe],'warnings':[v.value for v in at.warning],'info':[v.value for v in at.info]}
 return hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()

report={'method':'Actual shared read service with task-owned enabled checkpoint store and fixed projectionUTC; expire complete-cache evaluation epochs by20s before each trial. AppTest executes real render functions. Unprofiled processCPU includes reader+render threads; worker threadCPU separately measured. Not guest/native qualification.','service':[],'pages':[]}
try:
 for q in queries:
  r=service.request(q)
  while r.status=='pending':r=service.request(q)
  assert r.complete,(q.kind,r.reason)
 for index in range(5):
  age();start=time.perf_counter();cpu=time.process_time();start_jobs=len(worker)
  results=service.request_many(queries)
  assert all(r.complete for r in results.values())
  report['service'].append({'cpu':time.process_time()-cpu,'wall':time.perf_counter()-start,'payloads':fingerprint(results),'workers':worker[start_jobs:]})
 print('SERVICE',[(round(v['cpu'],6),round(v['wall'],6)) for v in report['service']],flush=True)
 for page,entry in [('home','render_home'),('trading','render')]:
  script='from src.dashboard.pages.'+page+' import '+entry+'\n'+entry+'()'
  at=AppTest.from_string(script)
  for index in range(3):
   age();start=time.perf_counter();cpu=time.process_time();start_jobs=len(worker)
   at.run(timeout=60)
   assert not at.exception,[(e.message) for e in at.exception]
   report['pages'].append({'page':page,'iteration':index,'cpu':time.process_time()-cpu,'wall':time.perf_counter()-start,'fingerprint':page_fingerprint(at),'metrics':[(m.label,m.value) for m in at.metric],'workers':worker[start_jobs:]})
  print('PAGE',page,[(round(v['cpu'],6),round(v['wall'],6)) for v in report['pages'] if v['page']==page],flush=True)
  age()
  profile_path=OUT/(page+'-render-'+LABEL+'.prof')
  script='import cProfile,time\nfrom src.dashboard.pages.'+page+' import '+entry+'\np=cProfile.Profile(timer=time.thread_time)\np.runcall('+entry+')\np.dump_stats('+repr(str(profile_path))+')'
  profiled=AppTest.from_string(script).run(timeout=60)
  assert not profiled.exception
  for order in ['cumulative','tottime']:
   text=io.StringIO();pstats.Stats(str(profile_path),stream=text).strip_dirs().sort_stats(order).print_stats(45)
   (OUT/(page+'-render-'+LABEL+'-'+order+'.txt')).write_text(text.getvalue())
finally:service.close()
report['store_hits']=store.hits
report['variant']=LABEL
report['store_prepare_verified']=True
report['source_projection_sha256']=hashlib.sha256(Path(projections.__file__).read_bytes()).hexdigest()
(OUT/('service-page-'+LABEL+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print('SERVICE_PAGE_BASELINE_DONE',flush=True)
