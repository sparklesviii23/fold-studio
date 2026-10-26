"""Independent CPU-only EditCraft service; never mutates protein campaigns."""
import hashlib,json,pathlib,uuid
from .editcraft_core import validate_plan,run_plan,utc,sha
APP='fold-editcraft-engine'
def source_identity():
 return hashlib.sha256(b''.join(pathlib.Path(__file__).with_name(name).read_bytes() for name in ('editcraft_modal.py','editcraft_core.py','editcraft_execute.py','editcraft_models.py','editcraft_assets.json','editcraft_toolchain.py','editcraft_toolchain.json','editcraft_offtargets.py','editcraft_variants.py','editcraft_singlecell.py','editcraft_cell_assets.json','editcraft_process.py'))).hexdigest()


def trained_image(base):
 # Core Python and scientific versions stay unchanged. Historical models get
 # separate Linux Python 3.10 environments; nothing is installed on the Mac.
 return (base.apt_install('libgomp1').pip_install('uv==0.8.22').run_commands(
  'uv python install 3.10.18',
  'uv venv --python 3.10.18 /opt/rs3-runtime',
  'uv pip install --python /opt/rs3-runtime/bin/python setuptools==69.5.1 numpy==1.23.5 pandas==1.5.3 scipy==1.10.1 scikit-learn==1.0.2 lightgbm==3.3.5 biopython==1.79 sglearn==1.2.5 seqfold==0.7.7 tqdm==4.65.0 joblib==1.3.1 ViennaRNA==2.7.2',
  'uv venv --python 3.10.18 /opt/bedict-runtime',
  'uv pip install --python /opt/bedict-runtime/bin/python torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu',
  'uv pip install --python /opt/bedict-runtime/bin/python numpy==1.23.5 pandas==1.5.3 scipy==1.10.1 scikit-learn==1.0.2 matplotlib==3.7.2 seaborn==0.12.2 prettytable==3.8.0 tqdm==4.65.0',
  'uv venv --python 3.10.18 /opt/pridict2-runtime',
  'uv pip install --python /opt/pridict2-runtime/bin/python torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu',
  'uv pip install --python /opt/pridict2-runtime/bin/python numpy==1.24.3 biopython==1.81 joblib==1.3.1 matplotlib==3.7.2 pandas==2.0.3 prettytable==3.8.0 primer3-py==2.3.0 scikit-learn==1.3.0 scipy==1.11.1 seaborn==0.12.2 tqdm==4.65.0',
 ).env({'UV_PYTHON_DOWNLOADS':'never'}))

def tool_image(base):
 source=pathlib.Path(__file__).parent
 return (base.apt_install('cmake','g++','ocl-icd-opencl-dev','pocl-opencl-icd','clinfo')
         .add_local_file(source/'editcraft_toolchain.py','/opt/tool-bootstrap/editcraft_toolchain.py',copy=True)
         .add_local_file(source/'editcraft_toolchain.json','/opt/tool-bootstrap/editcraft_toolchain.json',copy=True)
         .run_commands('python -B /opt/tool-bootstrap/editcraft_toolchain.py')
         .env({'POCL_MAX_PTHREAD_COUNT':'2','OMP_NUM_THREADS':'2'}))

def build_app(include_models=False,include_tools=False,include_singlecell=False):
 import modal
 source=pathlib.Path(__file__).resolve().parents[1]
 runtime=(modal.Image.debian_slim(python_version='3.12').pip_install('numpy==2.2.6','biopython==1.85','ViennaRNA==2.7.2').env({'FOLD_ENGINE_ROLE':'editcraft_cloud'}))
 def attach_code(base):return base.add_local_dir(source,'/opt/editcraft',copy=True,ignore=['**/__pycache__/**','**/dist/**','**/*.pyc']).env({'PYTHONPATH':'/opt/editcraft'})
 # Scientific dependency layers precede application source. Editing a parser or
 # form no longer reinstalls the historical model dependencies on every update.
 model_runtime=trained_image(runtime) if include_models else runtime
 image=attach_code(runtime);model_image=attach_code(model_runtime)
 scientific_tools_image=attach_code(tool_image(model_runtime)) if include_tools else model_image
 if include_singlecell:
  from .editcraft_singlecell import MANIFEST as cell_manifest
  cells_image=attach_code(runtime.pip_install(*[name+'=='+version for name,version in cell_manifest['runtime'].items()]).env({'NUMBA_NUM_THREADS':'2','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','HDF5_PLUGIN_PATH':''}))
 else:cells_image=image
 app=modal.App(APP);volume=modal.Volume.from_name('fold-editcraft-research',create_if_missing=True);state=modal.Dict.from_name('fold-editcraft-state',create_if_missing=True)
 def atomic(path,value):
  path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(value,allow_nan=False));tmp.replace(path)
 def analyze_impl(plan,key):
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
   if child:
    # Even an exited interpreter can leave a scientific grandchild in its group.
    # Terminate that owned group before releasing the writer lease.
    from .editcraft_process import terminate_owned_group
    terminate_owned_group(child)
   row.update(state='cancelled' if isinstance(exc,InterruptedError) else 'deadline_exceeded' if isinstance(exc,TimeoutError) else 'failed',errorType=type(exc).__name__,error='Scientific operation stopped; inspect its input requirements or deadline. No automatic retry.')
  row['finished']=utc();atomic(folder/'status.json',row);volume.commit();state['job:'+key]=row
  if state.get('writer-lease')==lease:state.pop('writer-lease')
  return row
 @app.function(image=image,serialized=True,name='analyze',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def analyze(plan,key):return analyze_impl(plan,key)
 @app.function(image=model_image,serialized=True,name='analyze_models',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def analyze_models(plan,key):
  if not include_models:raise ValueError('Deploy the reviewed isolated model runtimes first.')
  return analyze_impl(plan,key)
 @app.function(image=scientific_tools_image,serialized=True,name='analyze_tools',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def analyze_tools(plan,key):
  if not include_tools:raise ValueError('Deploy the reviewed Cas-OFFinder CPU runtime first.')
  return analyze_impl(plan,key)
 @app.function(image=cells_image,serialized=True,name='analyze_singlecell',cpu=(2,2),memory=(8192,8192),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def analyze_singlecell(plan,key):
  if not include_singlecell:raise ValueError('Deploy the reviewed isolated Scanpy CPU runtime first.')
  return analyze_impl(plan,key)
 @app.function(image=image,serialized=True,name='prepare_dataset',cpu=(2,2),memory=(1024,1024),volumes={'/research':volume},timeout=180,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def prepare_dataset(payload):
  from .editcraft_singlecell import prepare_dataset as install_dataset
  lease={'kind':'dataset_preparation','sha256':payload['expectedSha256']}
  if state.get('writer-lease')!=lease:raise ValueError('Dataset preparation does not own the approved scientific volume lease.')
  try:
   volume.reload();receipt=install_dataset(payload['source']);volume.commit();receipts=state.get('dataset-receipts',{});receipts[receipt['sha256']]=receipt;state['dataset-receipts']=receipts;state['dataset-preparation']={'state':'completed','sha256':receipt['sha256'],'finished':utc()};return receipt
  except BaseException as exc:
   state['dataset-preparation']={'state':'failed','sha256':payload['expectedSha256'],'errorType':type(exc).__name__,'finished':utc(),'retry':False};raise
  finally:
   if state.get('writer-lease')==lease:state.pop('writer-lease')
 @app.function(image=image,serialized=True,name='prepare_reference',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def prepare_reference(identity):
  from .editcraft_toolchain import prepare_reference as install_reference
  lease={'kind':'reference_preparation','reference':identity}
  if state.get('writer-lease')!=lease:raise ValueError('Reference preparation does not own the approved volume lease.')
  try:
   volume.reload();receipt=install_reference(identity);volume.commit();receipts=state.get('reference-receipts',{});receipts[identity]=receipt;state['reference-receipts']=receipts;state['reference-preparation']={'state':'completed','reference':identity,'finished':utc()};return receipt
  except BaseException as exc:
   state['reference-preparation']={'state':'failed','reference':identity,'errorType':type(exc).__name__,'finished':utc(),'retry':False};raise
  finally:
   if state.get('writer-lease')==lease:state.pop('writer-lease')
 @app.function(image=image,serialized=True,name='prepare_models',cpu=(2,2),memory=(4096,4096),volumes={'/research':volume},timeout=660,retries=0,min_containers=0,max_containers=1,scaledown_window=10)
 def prepare_models(models):
  from .editcraft_models import install_models
  lease={'kind':'model_preparation','models':models}
  if state.get('writer-lease')!=lease and not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('An EditCraft experiment is active; preserve its data volume.')
  try:
   volume.reload();receipts=install_models(models);volume.commit();all_receipts=state.get('model-receipts',{});all_receipts.update(receipts);state['model-receipts']=all_receipts;state['model-preparation']={'state':'completed','models':models,'finished':utc()};return receipts
  except BaseException as exc:
   state['model-preparation']={'state':'failed','models':models,'errorType':type(exc).__name__,'finished':utc(),'retry':False};raise
  finally:
   if state.get('writer-lease')==lease:state.pop('writer-lease')
 @app.function(image=image,serialized=True,name='control' ,cpu=(1,1),memory=(512,512),volumes={'/research':volume},timeout=60,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
 def control(operation,payload):
  if operation=='health':
   import Bio,RNA
   from .editcraft_toolchain import manifest_sha as tool_manifest_sha
   from .editcraft_singlecell import manifest_sha as cell_manifest_sha
   return {'state':'available','engine':'EditCraft','cpuOnly':True,'gpuStarted':False,'biopython':Bio.__version__,'viennarna':RNA.__version__,'scientificBenchmarkComplete':False,'sourceSha256':source_identity(),'modelRuntimesIncluded':include_models,'models':state.get('model-receipts',{}),'modelPreparation':state.get('model-preparation'),'toolRuntimesIncluded':include_tools,'toolManifestSha256':tool_manifest_sha(),'references':state.get('reference-receipts',{}),'referencePreparation':state.get('reference-preparation'),'singlecellRuntimesIncluded':include_singlecell,'cellManifestSha256':cell_manifest_sha(),'datasets':state.get('dataset-receipts',{}),'datasetPreparation':state.get('dataset-preparation'),'activeTask':state.get('writer-lease')}
  if operation=='prepare_dataset':
   from .editcraft_singlecell import MANIFEST as cells,manifest_sha as cell_manifest_sha
   source=payload.get('source',{});expected=payload.get('expectedSha256')
   if payload.get('approved') is not True or payload.get('manifestSha256')!=cell_manifest_sha():raise ValueError('Approve this exact dataset transfer and preparation cost.')
   if source.get('kind')=='public':
    if source.get('id') not in cells['datasets'] or cells['datasets'][source['id']]['sha256']!=expected:raise ValueError('Public dataset identity differs from the approved reference.')
   elif source.get('kind')=='upload':
    if source.get('sha256')!=expected:raise ValueError('Uploaded dataset differs from the approved checksum.')
   else:raise ValueError('Unsupported dataset source.')
   lease={'kind':'dataset_preparation','sha256':expected}
   if not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('A scientific task already owns the data volume. Reconnect instead of resubmitting.')
   row={'state':'submission_uncertain','sha256':expected,'started':utc(),'retry':False};state['dataset-preparation']=row
   call=prepare_dataset.spawn(payload);row.update(state='submitted',callId=call.object_id);state['dataset-preparation']=row;return row
  if operation=='prepare_reference':
   from .editcraft_toolchain import MANIFEST,manifest_sha as tool_manifest_sha
   identity=payload.get('referenceId')
   if payload.get('approved') is not True or identity not in MANIFEST['references'] or payload.get('manifestSha256')!=tool_manifest_sha():raise ValueError('Approve the exact reviewed assembly download and CPU preparation.')
   old=state.get('reference-preparation',{})
   if old.get('state') in ('submission_uncertain','submitted'):raise ValueError('Reference preparation is already claimed; check health without repeating it.')
   lease={'kind':'reference_preparation','reference':identity}
   if not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('An EditCraft task already owns the reference volume.')
   row={'state':'submission_uncertain','reference':identity,'started':utc(),'retry':False};state['reference-preparation']=row
   call=prepare_reference.spawn(identity);row.update(state='submitted',callId=call.object_id);state['reference-preparation']=row;return row
  if operation=='prepare_models':
   from .editcraft_models import MANIFEST,manifest_sha
   models=payload.get('models')
   if payload.get('approved') is not True or not isinstance(models,list) or not models or len(set(models))!=len(models) or set(models)-set(MANIFEST['models']):raise ValueError('Approve the exact supported checkpoint downloads.')
   if payload.get('manifestSha256')!=manifest_sha():raise ValueError('Model preparation source differs from the approved manifest.')
   old=state.get('model-preparation',{})
   if old.get('state') in ('submission_uncertain','submitted'):raise ValueError('Model preparation is already claimed; check health instead of repeating it.')
   lease={'kind':'model_preparation','models':models}
   if not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('An EditCraft task is already active.')
   row={'state':'submission_uncertain','models':models,'started':utc(),'retry':False};state['model-preparation']=row
   call=prepare_models.spawn(models);row.update(state='submitted',callId=call.object_id);state['model-preparation']=row;return row
  key=payload.get('id','')
  if not isinstance(key,str) or len(key)!=32 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid EditCraft identity.')
  if operation=='submit':
   plan=validate_plan(payload['plan']);expected=sha(plan)
   if payload.get('approved') is not True:raise ValueError('Explicit input-transfer and cost approval required.')
   needs_models=any(s['operation'] in ('rs3_activity','bedict_per_base','pridict2_design') for s in plan['stages'])
   needs_tools=any(s['operation']=='cas_offinder' for s in plan['stages'])
   needs_cells=any(s['operation']=='scanpy_analysis' for s in plan['stages'])
   if needs_cells:
    if not include_singlecell:raise ValueError('The isolated Scanpy CPU runtime is not deployed.')
    from .editcraft_singlecell import verify_dataset
    for stage in plan['stages']:
     if stage['operation']=='scanpy_analysis':volume.reload();verify_dataset(stage['parameters']['datasetSha256'])
   if needs_tools and not include_tools:raise ValueError('The pinned Cas-OFFinder CPU runtime is not deployed.')
   from .editcraft_toolchain import verify_reference
   for stage in plan['stages']:
    if stage['operation']=='reference_window' or stage['operation']=='cas_offinder' and stage['parameters']['reference']['kind']=='catalog':
     ref=stage['parameters']['reference'];volume.reload();verify_reference(ref['id'],ref['fastaSha256'])
   if needs_models:
    from .editcraft_models import OPERATIONS,manifest_sha
    if not include_models:raise ValueError('Trained model runtimes are not deployed.')
    receipts=state.get('model-receipts',{})
    for stage in plan['stages']:
     model=OPERATIONS.get(stage['operation'])
     if model and receipts.get(model,{}).get('manifestSha256')!=manifest_sha():raise ValueError('Required model is not prepared for this pinned release.')
   old=state.get('request:'+key)
   if old:
    if old['inputSha256']!=expected:raise ValueError('Idempotency identity conflicts with original input.')
    return old
   record={'id':key,'state':'submission_uncertain','inputSha256':expected}
   if not state.put('request:'+key,record,skip_if_exists=True):raise ValueError('A submission is already being reconciled; never retry automatically.')
   lease={'kind':'editcraft','request':key}
   if not state.put('writer-lease',lease,skip_if_exists=True):raise ValueError('Another EditCraft experiment is queued or running; reconnect instead of submitting.')
   call=(analyze_singlecell if needs_cells else analyze_tools if needs_tools else analyze_models if needs_models else analyze).spawn(plan,key);record.update(state='submitted',callId=call.object_id);state['request:'+key]=record;return record
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
  if operation not in ('status','result','artifact_info','diagnostics'):raise ValueError('Unsupported EditCraft control operation.')
  row=state.get('job:'+key)
  if row is None:
   volume.reload();file=pathlib.Path('/research')/key/'status.json'
   row=json.loads(file.read_text()) if file.is_file() else state.get('request:'+key) or {'id':key,'state':'not_observed','retry':False}
  if operation=='diagnostics':
   if row.get('state') not in ('failed','deadline_exceeded','cancelled'):raise ValueError('Failure details are available only for a stopped experiment.')
   volume.reload();file=pathlib.Path('/research')/key/'failure.private.json'
   if not file.is_file():return {'available':False,'message':'This earlier/interrupted worker did not retain a private traceback; no diagnostic was invented.','scientificCalculationStarted':False}
   if file.stat().st_size>1024**2:raise ValueError('Private diagnostic exceeds its bounded retrieval size.')
   return {'available':True,'diagnostic':json.loads(file.read_text()),'scientificCalculationStarted':False}
  if operation in ('result','artifact_info'):
   if row.get('state')!='completed':raise ValueError('No completed result available.')
   volume.reload();data=json.loads((pathlib.Path('/research')/key/'result.json').read_text())
   if sha(data)!=row['resultSha256']:raise ValueError('Result checksum mismatch.')
   if operation=='artifact_info':
    from .editcraft_singlecell import artifact_info
    artifacts=[value['result'].get('artifact') for value in data['results'].values() if value.get('operation')=='scanpy_analysis' and value['result'].get('artifact',{}).get('sha256')==payload.get('artifactSha256')]
    if len(artifacts)!=1:raise ValueError('Choose one exact processed artifact from this completed experiment.')
    return artifact_info(artifacts[0],key)
   return {'status':row,'result':data}
  return row
 app._fold_resources=[state,volume]
 return app

def deploy(include_models=False,include_tools=False,include_singlecell=False):
 from .modal_provider import deploy_app
 import modal
 # deploy_app already acquires the shared scientific writer lease atomically.
 # Taking it here as well would make the guarded deployment reject itself.
 app=build_app(include_models,include_tools,include_singlecell);deploy_app(app)
 return {'appId':app.app_id,'health':modal.Function.from_name(APP,'control').remote('health',{})}
