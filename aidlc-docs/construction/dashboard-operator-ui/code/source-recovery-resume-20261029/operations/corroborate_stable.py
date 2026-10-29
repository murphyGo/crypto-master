"""Separate post-observation read-only source stability and fresh-session check."""
import asyncio
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
out = root / '.tmp/dashboard-v68-resume-20261028'
sys.path.insert(0, str(root))
from scripts import observe_dashboard_protocol as observer
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from types import SimpleNamespace

code = r'''
import hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from src.config import get_settings
from src.dashboard.sources import discover
from src.dashboard.read_models import Query,Limits
query=Query(Path('/data'),'activity').normalized()
def capture():
 start=datetime.now(timezone.utc).isoformat();m=discover(query,Limits(),get_settings().log_retention_months);hashes=[];size=0
 for src in m.files:
  digest=hashlib.sha256()
  with src.path.open('rb') as h:
   while b:=h.read(65536):digest.update(b);size+=len(b)
  hashes.append(digest.hexdigest())
 m.verify()
 return {'started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'manifest_digest':m.digest(),'file_count':m.file_count,'bytes':size,'content_hashes':hashes,'full_generation_verified':True}
a=capture();time.sleep(20);b=capture()
print(json.dumps({'samples':[a,b],'same_manifest':a['manifest_digest']==b['manifest_digest'],'same_content':a['content_hashes']==b['content_hashes'],'scope':'Activity selected membership, per-file generations and content; twenty-second endpoint comparison, not proof of every intervening instant.'}))
'''
command='env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)
result=subprocess.run(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command',command],capture_output=True,text=True,timeout=60)
if result.returncode:
 print(result.stderr[-1500:]);raise SystemExit(result.returncode)
stability=json.loads(result.stdout)
(out/'activity-stability.json').write_text(json.dumps(stability,indent=2)+'\n')
assert stability['same_manifest'] and stability['same_content']
fds=descriptor_pb2.FileDescriptorSet.FromString((out/'before-streamlit.pb').read_bytes())
pool=descriptor_pool.DescriptorPool()
for fd in fds.file:pool.AddSerializedFile(fd.SerializeToString())
observer.Back=message_factory.GetMessageClass(pool.FindMessageTypeByName('BackMsg'))
observer.Forward=message_factory.GetMessageClass(pool.FindMessageTypeByName('ForwardMsg'))
observer.args=SimpleNamespace(phase='v68-stable')
observer.OUT=out/'fresh-session';observer.OUT.mkdir(exist_ok=False)
async def check():
 rows=[]
 # Each fresh connection has no queued response from the timed-out four-session run.
 async with observer.Client('fresh-home-1') as client:rows.append(await client.view('Home',timeout=30))
 async with observer.Client('fresh-home-2') as client:rows.append(await client.view('Home',timeout=30))
 (out/'fresh-session-check.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps({'stability':stability,'fresh_home':[{'status':r['status'],'seconds':r['seconds'],'alerts':r['alerts'],'watchers':r['maximum_background_watchers']} for r in rows]},indent=2))
asyncio.run(check())
