"""Fixed-input differential/latency evidence. Separate processes for memory peaks."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,resource,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path.cwd()
OUT=ROOT/'.tmp/dashboard-initial-read-20261111'
sys.path.insert(0,str(ROOT))

def prepare():
    root=OUT/'fixture'
    accounts=tuple(f'account-{i:02}' for i in range(13))
    start=datetime(2026,5,1,tzinfo=timezone.utc)
    files={}
    for account in accounts:
        p=root/'portfolio/paper'/account/'snapshots.json'
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('wb') as h:
            h.write(b'[\n')
            for n in range(7600):
                row={'timestamp':(start+timedelta(minutes=30*n)).isoformat(),'mode':'paper','sub_account_id':account,'quote_currency':'USDT','balances':{'USDT':str(10000+n%83),'BTC':str((n%7)/10)},'realized_pnl':str(n%101-50),'unrealized_pnl':str(n%21-10),'current_prices':{'BTC/USDT':str(50000+n%100),'ETH/USDT':str(2500+n%7)}}
                h.write((b',\n' if n else b'')+json.dumps(row,indent=2).encode())
            h.write(b'\n]\n')
        files[str(p.relative_to(root))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (OUT/'fixture-manifest.json').write_text(json.dumps({'accounts':accounts,'rows':98800,'files':files},indent=2)+'\n')
    print(json.dumps({'rows':98800,'bytes':sum(f['bytes'] for f in files.values())}))

def baseline():
    from src.utils import bounded_read as current
    spec=importlib.util.spec_from_file_location('frozen_bounded_read',OUT/'bounded_read_baseline.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    module.Generation=current.Generation
    module.ReadFailure=current.ReadFailure
    return module

def run(reader):
    from src.dashboard import projections
    from src.dashboard.read_models import Query,Limits
    from src.utils import bounded_read as current
    chosen=baseline() if reader=='baseline' else current
    projections.json_array_bytes=chosen.json_array_bytes
    manifest=json.loads((OUT/'fixture-manifest.json').read_text())
    q=Query(OUT/'fixture','snapshots',accounts=tuple(manifest['accounts']),at=datetime(2026,11,11,tzinfo=timezone.utc)).normalized()
    before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    trials=[]
    for i in range(3):
        start=time.perf_counter();cpu=time.process_time();result=None
        for part in projections.build_projection(q,Limits()):
            if part is not None:result=part
        elapsed=time.perf_counter()-start;used=time.process_time()-cpu
        payload=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
        trials.append({'wall_seconds':elapsed,'cpu_seconds':used,'sha256':hashlib.sha256(payload).hexdigest(),'payload_bytes':len(payload),'coverage':result['source_coverage']})
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report={'reader':reader,'method':'initial projection; warm imports/OS; no checkpoints or previous result; same immutable fixture; isolated process ru_maxrss in macOS bytes, includes imports; not an idle-RSS delta','trials':trials,'pre_read_high_water_bytes':before,'process_high_water_bytes':peak,'high_water_growth_bytes':peak-before}
    (OUT/f'benchmark-{reader}.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','baseline','candidate']);args=parser.parse_args()
    prepare() if args.mode=='prepare' else run(args.mode)
