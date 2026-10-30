"""Post-observation read-only CPU, startup-cycle and sampler lifecycle audit."""
import base64,json,shlex,subprocess,sys,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
root=Path.cwd();out=root/'.tmp/dashboard-rearm-20261030/resumed'
sys.path.insert(0,str(root))
from scripts import observe_dashboard_protocol as observer
summary=json.loads((out/'observation/rearm-concurrency-summary.json').read_text())
window_start=datetime.fromisoformat(summary['started_at'])-timedelta(seconds=30)
window_end=datetime.fromisoformat(summary['ended_at'])+timedelta(seconds=30)
assert datetime.now(timezone.utc)>=window_end,'Following CPU bracket not yet available'
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
runtime=json.loads((out/'after-runtime.json').read_text())
status=json.loads((out/'postdeploy-fly-status.json').read_text())
machine=status['Machines'][0]
machine_start=max(e['timestamp']/1000 for e in machine['events'] if e['type']=='start')
groups={}
for event in runtime['cycles']:
 if datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()>=machine_start:
  groups.setdefault(event['cycle_id'],{})[event['event_type']]=event
full={k:v for k,v in groups.items() if 'cycle_started' in v and 'cycle_completed' in v}
result={'release':status['Version'],'image':machine['image_ref']['digest'],'source':runtime['expected_source'],'checks':runtime['checks'],'full_cycles_since_deploy':full,'cycle_counts':{k:runtime['cycle_event_counts'][k] for k in full}}
started=time.monotonic()
with urllib.request.urlopen('https://crypto-master.fly.dev/_stcore/health',timeout=5) as r:
 result['public_health']={'status':r.status,'ok':r.read(256).strip()==b'ok','seconds':time.monotonic()-started}
body=observer.REMOTE.replace('DURATION','2190')
expected='import base64;exec(base64.b64decode('+repr(base64.b64encode(body.encode()).decode())+'))'
remote="import json,pathlib; expected="+repr(expected)+"; found=[]\nfor p in pathlib.Path('/proc').iterdir():\n if not p.name.isdigit():continue\n try:\n  a=(p/'cmdline').read_bytes().split(bytes([0]))\n  if len(a)>2 and a[1]==b'-c' and a[2].decode()==expected:found.append(int(p.name))\n except (FileNotFoundError,PermissionError,UnicodeError):pass\nprint(json.dumps({'remaining_task_sampler_pids':found}))"
probe=subprocess.run(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command','env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(remote)],capture_output=True,text=True,check=True,timeout=30)
result['sampler_lifecycle']=json.loads(probe.stdout)
(out/'post-observation-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'release':result['release'],'full_cycles':list(full),'counts':result['cycle_counts'],'public_health':result['public_health'],'sampler':result['sampler_lifecycle']},indent=2))
assert full
# Preserve the observed engine failure as a failed gate, never hide it.
if any('cycle_errored' in v for v in groups.values()): print('ENGINE_CYCLE_GATE_FAILED')
assert all(result['checks'].values()) and result['public_health']['ok']
