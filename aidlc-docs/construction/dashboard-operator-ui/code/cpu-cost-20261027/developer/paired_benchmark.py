"""Alternating exact-function CPU pairs; immutable fixtures, real source proof."""
import ast,hashlib,json,statistics,time
from datetime import datetime,timezone
from pathlib import Path
from src.dashboard import app,projections
from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.data_service import DashboardDataService,CacheEntry
from src.dashboard.read_models import Query,ReadResult,Limits

OUT=Path('/private/tmp/crypto-master-cpu-cost-delivery-20261027/developer')
ROOT=Path('/private/tmp/crypto-master-strategy-snapshots/fly-data-20261025T105002Z')
AT=datetime(2026,10,25,10,50,2,tzinfo=timezone.utc)
ACCOUNTS=tuple(sorted(p.name for p in (ROOT/'portfolio/paper').iterdir() if p.is_dir()))
text=(OUT/'baseline-projections.py').read_text()
tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_projection')
unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
ast.fix_missing_locations(unit)
namespace={}
exec(compile(unit,str(OUT/'baseline-projections.py'),'exec'),projections.__dict__,namespace)
FUNCTIONS={'baseline':namespace['build_projection'],'candidate':projections.build_projection}
source_hash=hashlib.sha256(Path(projections.__file__).read_bytes()).hexdigest()
store_root=OUT/'paired-enabled-store';store_root.mkdir(exist_ok=True)
store=CheckpointStore(store_root)
q=Query(ROOT,'proposals',window='24h',at=AT).normalized()
assert store.prepare(q) is True

def consume(fn,query,previous=None,current_store=None):
 result=None
 for value in fn(query,Limits(),previous=previous,checkpoint_store=current_store):
  if value is not None:result=value
 assert result is not None
 return result

def fingerprint(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

queries={kind:Query(ROOT,kind,accounts=ACCOUNTS if kind in {'ledger','snapshots'} else ('default',),window='24h' if kind=='proposals' else 'lifetime',at=AT).normalized() for kind in ['activity','ledger','snapshots','candidates','proposals']}
prior={kind:consume(FUNCTIONS['baseline'],query) for kind,query in queries.items()}
threshold=Query(ROOT,'proposals',window='threshold',at=AT).normalized()
prior_threshold=consume(FUNCTIONS['baseline'],threshold)
encoded={kind:json.dumps(value,separators=(',',':')).encode() for kind,value in prior.items()}
threshold_encoded=json.dumps(prior_threshold,separators=(',',':')).encode()
expected={kind:fingerprint(value) for kind,value in prior.items()}
expected_threshold=fingerprint(prior_threshold)
report={'baseline_source_sha256':hashlib.sha256(text.encode()).hexdigest(),'candidate_source_sha256':source_hash,'fixture_manifest_sha256':hashlib.sha256((OUT/'input-manifest.json').read_bytes()).hexdigest(),'method':'Twenty alternating unprofiled pairs per scenario, exact frozen baseline build_projection function compiled in memory versus candidate, identical helpers/inputs/fixed UTC. Enabled store root exists and prepare=True. Direct prior payloads fully validated before trials. Service trials prime only previously verified encoded cache entries at original age20s, so every request takes real generation revalidation; a fresh one-worker service is closed before switching variant. Process CPU is reported separately; concurrent full-suite host load makes wall values diagnostic only. No production/native/guest acceptance.','store_prepare_verified':True,'fixed_utc':AT.isoformat(),'series':[]}

for scenario in ['direct_disabled_store','direct_enabled_store','service_home_enabled','service_trading_enabled']:
 row={'scenario':scenario,'baseline':[],'candidate':[],'full_output_parity':True}
 for index in range(20):
  for variant in (['baseline','candidate'] if index%2==0 else ['candidate','baseline']):
   fn=FUNCTIONS[variant]
   service=None;holder={}
   if scenario.startswith('service'):
    selected=queries if scenario=='service_home_enabled' else {kind:queries[kind] for kind in ['activity','ledger','snapshots']}|{'proposals':threshold}
    def builder(query,limits):
     service=holder['service']
     with service._condition: previous=service._cache[query].result.payload
     yield from fn(query,limits,previous=previous,checkpoint_store=store)
    service=DashboardDataService(builder=builder,checkpoint_store=store)
    holder['service']=service
    epoch=time.monotonic()-20
    with service._condition:
     for kind,query in selected.items():
      payload=threshold_encoded if query==threshold else encoded[kind]
      value=ReadResult('complete',payload,AT,verified_monotonic=epoch)
      charge=len(payload)+4096+len(repr(query).encode())
      service._cache[query]=CacheEntry(value,epoch,charge)
      service._cache_bytes+=charge
   start=time.perf_counter();cpu=time.process_time()
   if service is None:
    value=consume(fn,q,encoded['proposals'],store if scenario=='direct_enabled_store' else None)
   else:
    results=service.request_many(list(selected.values()))
   measurement={'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-start}
   if service is None:
    assert fingerprint(value)==expected['proposals']
    measurement['payload_sha256']=fingerprint(value)
   else:
    assert all(value.complete for value in results.values()),{k:(v.status,v.reason) for k,v in results.items()}
    actual={kind:fingerprint(value.data()) for kind,value in results.items()}
    expected_row={kind:expected_threshold if query==threshold else expected[kind] for kind,query in selected.items()}
    assert actual==expected_row
    measurement['payload_sha256']=actual
    measurement['service_stats']=service.stats()
    service.close();holder.clear()
   row[variant].append(measurement)
 for variant in ['baseline','candidate']:
  row[variant+'_median_cpu']=statistics.median(r['cpu_seconds'] for r in row[variant])
 row['median_cpu_reduction_fraction']=1-row['candidate_median_cpu']/row['baseline_median_cpu']
 report['series'].append(row)
 (OUT/'paired-cpu-results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(scenario,row['baseline_median_cpu'],row['candidate_median_cpu'],row['median_cpu_reduction_fraction'],flush=True)
manifest=json.loads((OUT/'input-manifest.json').read_text())
for relative,meta in manifest.items():
 path=ROOT/relative
 assert path.stat().st_size==meta['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
assert hashlib.sha256(Path(projections.__file__).read_bytes()).hexdigest()==source_hash
report['all_fixture_hashes_unchanged']=True;report['source_unchanged_during_measurement']=True
(OUT/'paired-cpu-results.json').write_text(json.dumps(report,indent=2)+'\n')
print('PAIRED_CPU_COMPLETE',flush=True)
