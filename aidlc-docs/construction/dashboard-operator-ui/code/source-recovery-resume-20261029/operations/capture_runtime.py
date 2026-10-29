"""Task-owned read-only v68 runtime/source/descriptor capture."""
import base64
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / '.tmp/dashboard-v68-resume-20261028'
BASE = ROOT / 'aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-20261027/operations'
phase = sys.argv[1]
rollback = phase.startswith('rollback')
baseline_path = (ROOT / 'aidlc-docs/construction/dashboard-operator-ui/code/cpu-cost-20261027/operations/postdeploy.json') if rollback else BASE / 'postdeploy.json'
baseline = json.loads(baseline_path.read_text())
code = r'''
import base64,hashlib,importlib.metadata,json,os,pathlib,sys,urllib.request
from datetime import datetime,timezone
from collections import Counter
paths=PATHS
out={'captured_at':datetime.now(timezone.utc).isoformat()}
out['runtime_sha256']={p:hashlib.sha256(pathlib.Path('/app',p).read_bytes()).hexdigest() for p in paths}
out['dependencies']={p:importlib.metadata.version(p) for p in ('streamlit','pandas','pydantic','pydantic-core','numpy')}
out['python']=sys.version.split()[0]
out['configuration']={p:os.environ.get(p) for p in ('TRADING_MODE','LLM_PROVIDER','CODEX_CLI_MODEL','CLAUDE_CLI_MODEL','ENGINE_CYCLE_INTERVAL')}
from src.config import get_settings
out['settings_mode']=get_settings().trading_mode
out['processes']={}
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  kind='engine' if cmd.startswith('python -m src.main') else ('dashboard' if 'streamlit run src/dashboard/app.py' in cmd and not cmd.startswith('python -c') else None)
  if kind:
   stat=(d/'stat').read_text().split(') ',1)[1].split()
   out['processes'][kind]={'pid':int(d.name),'start_ticks':int(stat[19]),'cpu_seconds':(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK')}
 except (FileNotFoundError,PermissionError):pass
out['memory_kib']={s.split(':')[0]:int(s.split()[1]) for s in pathlib.Path('/proc/meminfo').read_text().splitlines() if s.startswith(('MemTotal:','MemAvailable:'))}
with urllib.request.urlopen('http://127.0.0.1:8080/_stcore/health',timeout=5) as r:out['internal_health']={'status':r.status,'body':r.read(256).decode()}
files=sorted(pathlib.Path('/data/runtime').glob('activity.*.jsonl'));events=[];bad=0
if files:
 with files[-1].open('rb') as h:
  offset=max(0,files[-1].stat().st_size-524288);h.seek(offset);raw=h.read(524288)
 for line in raw.splitlines()[1 if offset else 0:]:
  try:row=json.loads(line)
  except ValueError:bad+=1;continue
  events.append(row)
out['activity_tail']={'bytes':len(raw) if files else 0,'parse_errors':bad,'event_counts':dict(Counter(r.get('event_type') for r in events))}
out['cycles']=[{k:r.get(k) for k in ('timestamp','event_type','cycle_id','details')} for r in events if r.get('event_type') in ('cycle_started','cycle_completed','cycle_errored')][-12:]
out['cycle_event_counts']={cid:dict(Counter(r.get('event_type') for r in events if r.get('cycle_id')==cid)) for cid in dict.fromkeys(r.get('cycle_id') for r in out['cycles'])}
from google.protobuf import descriptor_pb2
from streamlit.proto import BackMsg_pb2,ForwardMsg_pb2
fds=descriptor_pb2.FileDescriptorSet();seen=set()
def visit(fd):
 if fd.name in seen:return
 for dep in fd.dependencies:visit(dep)
 seen.add(fd.name);fd.CopyToProto(fds.file.add())
visit(BackMsg_pb2.DESCRIPTOR);visit(ForwardMsg_pb2.DESCRIPTOR)
out['descriptor_base64']=base64.b64encode(fds.SerializeToString()).decode()
print(json.dumps(out))
'''.replace('PATHS',repr(sorted(baseline['runtime_sha256'])))
remote='env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)
status=json.loads(subprocess.run(['fly','status','--app','crypto-master','--json'],capture_output=True,text=True,check=True,timeout=30).stdout)
(OUT/f'{phase}-fly-status.json').write_text(json.dumps(status,indent=2)+'\n')
result=subprocess.run(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command',remote],capture_output=True,text=True,timeout=60)
if result.returncode:
 print(result.stderr[-1500:]);raise SystemExit(result.returncode)
runtime=json.loads(result.stdout)
descriptor=base64.b64decode(runtime.pop('descriptor_base64'))
(OUT/f'{phase}-streamlit.pb').write_bytes(descriptor)
runtime['descriptor_sha256']=hashlib.sha256(descriptor).hexdigest()
machine=status['Machines'][0];previous=json.loads((BASE/('status-before-deploy.json' if rollback else 'status-after-deploy.json')).read_text())['Machines'][0]
checks={k:machine['config'].get(k)==previous['config'].get(k) for k in ('env','init','guest','mounts','services','restart')}
checks.update(runtime_source=runtime['runtime_sha256']==baseline['runtime_sha256'],dependencies=runtime['dependencies']==baseline['dependencies'],configuration=runtime['configuration']==baseline['configuration'],settings_mode=runtime['settings_mode']=='paper',image=machine['image_ref']['digest']==previous['image_ref']['digest'],instance=machine['instance_id']==previous['instance_id'],processes=set(runtime['processes'])=={'engine','dashboard'},internal_health=runtime['internal_health']=={'status':200,'body':'ok'})
if rollback:
 checks.pop('instance')
 checks['restarted_from_v68']=machine['instance_id']!=json.loads((BASE/'status-after-deploy.json').read_text())['Machines'][0]['instance_id']
runtime['expected_source']=baseline['expected_source']
runtime['checks']=checks
(OUT/f'{phase}-runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
print(json.dumps({'phase':phase,'checks':checks,'runtime_files':len(runtime['runtime_sha256']),'descriptor_sha256':runtime['descriptor_sha256'],'processes':runtime['processes'],'cycles':runtime['cycles'][-4:]},indent=2))
if not all(checks.values()):raise SystemExit(1)
