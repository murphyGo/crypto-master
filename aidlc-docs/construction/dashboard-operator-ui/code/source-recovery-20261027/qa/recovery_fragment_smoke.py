"""Temporary actual Streamlit fragment test; no network or canonical-data reads."""
import sys
sys.dont_write_bytecode=True
import hashlib,json,threading,time,traceback
from datetime import datetime,timezone
from pathlib import Path

REPO=Path('/private/tmp/crypto-master-source-recovery-20261027')
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(REPO))
import streamlit
from streamlit.testing.v1 import AppTest
from src.dashboard.data_service import DashboardDataService
from src.dashboard.read_models import Query
from src.utils.bounded_read import ReadFailure
FILES=['src/dashboard/data_service.py','src/dashboard/read_diagnostics.py','src/dashboard/availability.py','src/dashboard/read_models.py']
def hashes():return {p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in FILES}
def snap(test):
 s=test.session_state
 return {'renders':s['renders'],'status':s['read_status'],'dispatches':s['fragment_dispatches'],'dispatches_returned':s['dispatches_that_returned'],'fragment_count':s['fragment_count'],'buttons':[b.label for b in test.button],'metrics':[{'label':m.label,'value':m.value} for m in test.metric],'exceptions':[str(e.message) for e in test.exception]}
def make(service,query):
 test=AppTest.from_file(OUT/'recovery-fragment-dispatch-app.py',default_timeout=8)
 for key,value in {'service':service,'query':query,'renders':0,'fragment_dispatches':0,'dispatches_that_returned':0}.items():test.session_state[key]=value
 return test

gates=[threading.Event() for _ in range(3)];entered=[threading.Event() for _ in range(3)];calls=[]
def build(query,limits):
 attempt=len(calls);calls.append(query.kind);entered[attempt].set()
 assert gates[attempt].wait(15),'Fixture release timed out'
 if attempt<2:raise ReadFailure('source_changed')
 yield {'value':7}

before=hashes();service=DashboardDataService(builder=build)
result={'scope':'Real local Streamlit AppTest fragment closure and st.rerun, explicitly dispatched. No timer/native viewport/production qualification.','streamlit':streamlit.__version__,'source_before':before,'production_load_added':False,'sessions':[]}
try:
 query=Query(OUT/'fixture-root','activity');normalized=query.normalized()
 first=service.request(query,wait=0);assert first.status=='pending'
 assert entered[0].wait(2)
 with service._condition:future=service._jobs[normalized];signal=service._job_progress[normalized]
 tests=[]
 for _ in range(2):
  test=make(service,query);test.run();initial=snap(test)
  assert initial['status']=='pending' and initial['fragment_count']==1 and not initial['buttons'] and not initial['exceptions']
  tests.append(test);result['sessions'].append({'initial':initial,'between_attempts':[]})
 for index in range(2):
  gates[index].set();assert entered[index+1].wait(3)
  with service._condition:
   assert service._jobs[normalized] is future and service._job_progress[normalized] is signal
  assert not signal.is_set() and not future.done()
  assert service.stats()['admitted']==service.stats()['workers']==1
  for j,test in enumerate(tests):
   old_returns=test.session_state['dispatches_that_returned']
   test.session_state['fragment_only']=True;test.session_state['dispatch_saved']=True;test.run();pending=snap(test)
   assert pending['status']=='pending' and pending['fragment_count']==1 and not pending['buttons'] and not pending['exceptions']
   assert pending['dispatches_returned']==old_returns+1
   result['sessions'][j]['between_attempts'].append(pending)
 gates[2].set();assert future.result(timeout=3).complete and signal.is_set()
 for j,test in enumerate(tests):
  old_returns=test.session_state['dispatches_that_returned']
  test.session_state['fragment_only']=True;test.session_state['dispatch_saved']=True;test.run();ready=snap(test)
  assert ready['status']=='complete' and not ready['exceptions'] and ready['metrics']==[{'label':'Ready','value':'7'}]
  assert ready['dispatches_returned']==old_returns
  test.session_state['fragment_only']=True;test.session_state['dispatch_saved']=True;test.run();again=snap(test)
  assert again['status']=='complete' and again['dispatches_returned']==old_returns+1 and not again['exceptions']
  result['sessions'][j].update({'ready':ready,'repeated_old_fragment':again})
 assert calls==['activity']*3
 result.update({'verdict':'PASS','attempts':len(calls),'same_future_and_progress_across_attempts':True,'single_loading_watcher_each_render':True,'no_terminal_button_during_recovery':True,'each_session_settled_fragment_reruns_once':True,'service_stats':service.stats()})
except BaseException:
 result.update({'verdict':'FAIL','error':traceback.format_exc()});raise
finally:
 for gate in gates:gate.set()
 service.close()
 result['source_after']=hashes();result['source_unchanged']=before==result['source_after']
 result['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 result['fixture_sha256']=hashlib.sha256((OUT/'recovery-fragment-dispatch-app.py').read_bytes()).hexdigest()
 result['completed_at']=datetime.now(timezone.utc).isoformat()
 with (OUT/'recovery-fragment-smoke-result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result),flush=True)
