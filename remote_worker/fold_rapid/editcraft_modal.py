"""Independent CPU-only EditCraft service; never mutates protein campaigns."""
import hashlib,json,pathlib,uuid
from .editcraft_core import validate_plan,run_plan,utc,sha
APP='fold-editcraft-engine'
def source_identity():
 return hashlib.sha256(pathlib.Path(__file__).read_bytes()+pathlib.Path(__file__).with_name('editcraft_core.py').read_bytes()+pathlib.Path(__file__).with_name('editcraft_execute.py').read_bytes()).hexdigest()


def build_app():
 import modal
 source=pathlib.Path(__file__).resolve().parents[1]
 image=(modal.Image.debian_slim(python_version='3.12').pip_install('numpy==2.2.6','biopython==1.85','ViennaRNA==2.7.2')
        .add_local_dir(source,'/opt/editcraft',copy=True,ignore=['**/__pycache__/**','**/dist/**','**/*.pyc'])
        .env({'PYTHONPATH':'/opt/editcraft','FOLD_ENGINE_ROLE':'editcraft_cloud'}))
 app=modal.App(APP);volume=modal.Volume.from_name('fold-editcraft-research',create_if_missing=True);state=modal.Dict.from_name('fold-editcraft-state',create_if_missing=True)
 def atomic(path,value):
  path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(value,allow_nan=False));tmp.replace(path)
 @app.function(image=image,serialized=True,name='analyze',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def analyze(plan,key):
  import os
  validate_plan(plan)
  token={'inputSha256':sha(plan),'state':'running','started':utc()}
  if not state.put('claimed:'+key,token,skip_if_exists=True):raise ValueError('Request already claimed; reconnect without resubmission.')
  lease={'kind':'editcraft','request':key}
  if state.get('writer-lease')!=lease and not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('Another EditCraft calculation owns the data volume; no duplicate execution.')
  folder=pathlib.Path('/research')/key;volume.reload();atomic(folder/'plan.json',plan)
  row={**token,'id':key,'events':[],'cloudOnly':True,'gpuStarted':False};atomic(folder/'status.json',row);volume.commit();state['job:'+key]=row
  def progress(event):
   row['events'].append({**event,'time':utc()});row['updated']=utc();state['job:'+key]=row
   # Logs contain operation names and states, never genomic inputs/results.
   print(json.dumps({'jobId':key,'stageId':event['stageId'],'operation':event['operation'],'state':event['state']}),flush=True)
   atomic(folder/'status.json',row);volume.commit()
  import subprocess,sys,time,signal
  child=None;offset=0;deadline=time.monotonic()+plan['seconds']
  try:
   child=subprocess.Popen([sys.executable,'-B','-m','fold_rapid.editcraft_execute',str(folder)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
   while True:
    events=folder/'events.jsonl'
    if events.is_file():
     lines=events.read_text().splitlines()
     for line in lines[offset:]:progress(json.loads(line))
     offset=len(lines)
    if state.get('cancel:'+key,False):raise InterruptedError('Cancelled')
    if time.monotonic()>=deadline:raise TimeoutError('Scientific deadline reached')
    if child.poll() is not None:break
    time.sleep(1)
   if child.returncode:raise RuntimeError('Scientific subprocess failed')
   result=json.loads((folder/'result.json').read_text());row.update(state='completed',resultSha256=sha(result))
  except BaseException as exc:
   if child and child.poll() is None:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   row.update(state='cancelled' if isinstance(exc,InterruptedError) else 'deadline_exceeded' if isinstance(exc,TimeoutError) else 'failed',errorType=type(exc).__name__,error='Scientific operation stopped; inspect its input requirements or deadline. No automatic retry.')
  row['finished']=utc();atomic(folder/'status.json',row);volume.commit();state['job:'+key]=row
  if state.get('writer-lease')==lease:state.pop('writer-lease')
  return row
 @app.function(image=image,serialized=True,name='control',cpu=(1,1),memory=(512,512),volumes={'/research':volume},timeout=60,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
 def control(operation,payload):
  if operation=='health':
   import Bio,RNA
   return {'state':'available','engine':'EditCraft','cpuOnly':True,'gpuStarted':False,'biopython':Bio.__version__,'viennarna':RNA.__version__,'scientificBenchmarkComplete':False,'sourceSha256':source_identity()}
  key=payload.get('id','')
  if not isinstance(key,str) or len(key)!=32 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid EditCraft identity.')
  if operation=='submit':
   plan=validate_plan(payload['plan']);expected=sha(plan)
   if payload.get('approved') is not True:raise ValueError('Explicit input-transfer and cost approval required.')
   old=state.get('request:'+key)
   if old:
    if old['inputSha256']!=expected:raise ValueError('Idempotency identity conflicts with original input.')
    return old
   record={'id':key,'state':'submission_uncertain','inputSha256':expected}
   if not state.put('request:'+key,record,skip_if_exists=True):raise ValueError('A submission is already being reconciled; never retry automatically.')
   lease={'kind':'editcraft','request':key}
   if not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('Another EditCraft experiment is queued or running; reconnect instead of submitting.')
   call=analyze.spawn(plan,key);record.update(state='submitted',callId=call.object_id);state['request:'+key]=record;return record
  if operation=='cancel':
   state['cancel:'+key]=True
   original=state.get('request:'+key)
   if original and original.get('callId'):
    modal.FunctionCall.from_id(original['callId']).cancel(terminate_containers=True)
    lease=state.get('writer-lease')
    if lease and lease.get('request')==key:state.pop('writer-lease')
   row=state.get('job:'+key) or {'id':key}
   row={**row,'state':'cancelled','cancellationRequested':utc(),'billingStopped':False}
   state['job:'+key]=row
   return row
  if operation not in ('status','result'):raise ValueError('Unsupported EditCraft control operation.')
  row=state.get('job:'+key)
  if row is None:
   volume.reload();file=pathlib.Path('/research')/key/'status.json'
   row=json.loads(file.read_text()) if file.is_file() else state.get('request:'+key) or {'id':key,'state':'not_observed','retry':False}
  if operation=='result':
   if row.get('state')!='completed':raise ValueError('No completed result available.')
   volume.reload();data=json.loads((pathlib.Path('/research')/key/'result.json').read_text())
   if sha(data)!=row['resultSha256']:raise ValueError('Result checksum mismatch.')
   return {'status':row,'result':data}
  return row
 app._fold_resources=[state,volume]
 return app

def deploy():
 from .modal_provider import deploy_app
 app=build_app();deploy_app(app)
 import modal
 return {'appId':app.app_id,'health':modal.Function.from_name(APP,'control').remote('health',{})}
