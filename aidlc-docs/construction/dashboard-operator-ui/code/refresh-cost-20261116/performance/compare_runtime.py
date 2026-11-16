"""Generate an isolated alternating comparison without changing deployed source."""
import ast
import hashlib
import json
import shlex
from pathlib import Path

root = Path.cwd()
scratch = root / '.tmp/dashboard-refresh-20261116'

def function(path, name, cls=None):
    tree = ast.parse(path.read_text())
    nodes = tree.body
    if cls:
        nodes = next(n.body for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls)
    return ast.unparse(next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name))

replacements = {
    'baseline': {
        'size': function(scratch / 'projections_baseline.py', 'size', 'StateBudget'),
        'encode_state': function(scratch / 'checkpoint_store_baseline.py', 'encode_state'),
    },
    'candidate': {
        'size': function(root / 'src/dashboard/projections.py', 'size', 'StateBudget'),
        'encode_state': function(root / 'src/dashboard/checkpoint_store.py', 'encode_state'),
    },
}
expected = {f'src/dashboard/{name}.py': hashlib.sha256((scratch / f'{name}_baseline.py').read_bytes()).hexdigest() for name in ('projections', 'checkpoint_store')}
code = r'''
import hashlib,json,resource,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
import src.dashboard.projections as projection
import src.dashboard.checkpoint_store as checkpoint
import src.dashboard.segment_checkpoints as segment
from src.dashboard.read_models import Limits,Query
from src.utils.bounded_read import ReadFailure
replacements=REPLACEMENTS
expected=EXPECTED
assert all(hashlib.sha256(Path('/app',name).read_bytes()).hexdigest()==digest for name,digest in expected.items())
functions={}
for version,sources in replacements.items():
 functions[version]={}
 for name,source in sources.items():
  namespace=dict(vars(projection if name=='size' else checkpoint))
  exec(compile(source,'<probe-'+version+'-'+name+'>','exec'),namespace)
  functions[version][name]=namespace[name]
root=Path('/data');at=datetime.now(timezone.utc)
accounts=tuple(sorted(p.name for p in (root/'portfolio/paper').iterdir() if p.is_dir()))
report={'captured_at':at.isoformat(),'method':'alternating implementation functions only in this standalone process; fresh isolated /tmp checkpoint per trial; no /data writes; warm imports/OS; fixed evaluation time','baseline_file_sha256':expected,'trials':[]}
for kind in ('activity','snapshots'):
 query=Query(root,kind,accounts=accounts if kind=='snapshots' else ('default',),at=at).normalized()
 for version in ('baseline','candidate','candidate','baseline','baseline','candidate'):
  projection.StateBudget.size=functions[version]['size']
  checkpoint.encode_state=segment.encode_state=functions[version]['encode_state']
  with tempfile.TemporaryDirectory(prefix='cm-refresh-compare-') as scratch:
   store=checkpoint.CheckpointStore(Path(scratch));result=None
   trial={'kind':kind,'version':version};started=time.perf_counter();cpu=time.process_time()
   try:
    for part in projection.build_projection(query,Limits(),checkpoint_store=store):
     if part is not None:result=part
    assert result is not None
    trial.update(status='complete',source_digest=result['_source_digest'],source_coverage=result['source_coverage'])
   except ReadFailure as exc:trial.update(status='unavailable',reason=str(exc))
   trial.update(wall_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,checkpoint_hits=store.hits)
   if result is not None:
    payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    trial.update(payload_bytes=len(payload),payload_sha256=hashlib.sha256(payload).hexdigest())
   report['trials'].append(trial)
report['process_highwater_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
report['temporary_stores_removed']=True
print(json.dumps(report))
'''.replace('REPLACEMENTS',repr(replacements)).replace('EXPECTED',repr(expected))
print(shlex.join(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)]))
