"""Verify exact rollback source, health, startup cycle and fresh UI sessions."""
import asyncio
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

root = Path.cwd()
out = root / '.tmp/dashboard-v68-resume-20261028'
sys.path.insert(0, str(root))
from scripts import observe_dashboard_protocol as observer
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

subprocess.run([sys.executable,str(out/'capture_runtime.py'),'rollback'],check=True)
runtime=json.loads((out/'rollback-runtime.json').read_text())
status=json.loads((out/'rollback-fly-status.json').read_text())
machine=status['Machines'][0]
events=machine.get('events',[])
machine_start=max(e['timestamp']/1000 for e in events if e['type']=='start')
groups={}
for event in runtime['cycles']:
    if datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()>=machine_start:
        groups.setdefault(event['cycle_id'],{})[event['event_type']]=event
full={k:v for k,v in groups.items() if 'cycle_started' in v and 'cycle_completed' in v}
result={'release':status['Version'],'image':machine['image_ref']['digest'],'checks':runtime['checks'],'startup_full_cycles':full,'startup_cycle_counts':{k:runtime['cycle_event_counts'][k] for k in full}}
start=time.monotonic()
with urllib.request.urlopen('https://crypto-master.fly.dev/_stcore/health',timeout=5) as response:
    result['public_health']={'status':response.status,'ok':response.read(256).strip()==b'ok','seconds':time.monotonic()-start}
fds=descriptor_pb2.FileDescriptorSet.FromString((out/'rollback-streamlit.pb').read_bytes())
pool=descriptor_pool.DescriptorPool()
for fd in fds.file:pool.AddSerializedFile(fd.SerializeToString())
observer.Back=message_factory.GetMessageClass(pool.FindMessageTypeByName('BackMsg'))
observer.Forward=message_factory.GetMessageClass(pool.FindMessageTypeByName('ForwardMsg'))
observer.args=SimpleNamespace(phase='rollback')
observer.OUT=out/'rollback-pages';observer.OUT.mkdir(exist_ok=False)
async def check():
    rows=[]
    async with observer.Client('rollback-fresh') as client:
        for page in ('Home','Trading'):
            rows.append(await client.view(page,timeout=60))
    return rows
result['pages']=asyncio.run(check())
(out/'rollback-verification.json').write_text(json.dumps(result,indent=2)+'\n')
# Capture only the original observation interval plus two 30 s brackets.
summary=json.loads((out/'observation/v68-resumed-concurrency-summary.json').read_text())
window_start=datetime.fromisoformat(summary['started_at'])-timedelta(seconds=30)
window_end=datetime.fromisoformat(summary['ended_at'])+timedelta(seconds=30)
credentials=json.loads(subprocess.run(['flyctl','auth','token','--json'],capture_output=True,text=True,check=True).stdout)
credential=credentials.get('token') or credentials.get('access_token')
assert isinstance(credential,str)
authorization=credential if credential.startswith(('FlyV1 ','Bearer ')) else ('FlyV1 '+credential if credential.startswith('fm2_') else 'Bearer '+credential)
query='{__name__=~"fly_instance_cpu_(baseline|balance|throttle)",app="crypto-master",instance="6835752b711958"}'
params=urllib.parse.urlencode({'query':query,'start':window_start.isoformat(),'end':window_end.isoformat(),'step':'15'})
request=urllib.request.Request('https://api.fly.io/prometheus/personal/api/v1/query_range?'+params,headers={'Authorization':authorization})
with urllib.request.urlopen(request,timeout=30) as response:cpu=json.load(response)
assert cpu['status']=='success'
(out/'cpu-window-supplement.json').write_text(json.dumps(cpu,indent=2)+'\n')
print(json.dumps({'release':result['release'],'image':result['image'],'public_health':result['public_health'],'startup_cycles':list(full),'startup_cycle_counts':result['startup_cycle_counts'],'pages':[{k:r.get(k) for k in ('page','status','seconds','first_incomplete_shell_seconds')} for r in result['pages']]},indent=2))
if not full or any('cycle_errored' in e for e in groups.values()) or not all(r['status']=='complete' for r in result['pages']):raise SystemExit(1)
