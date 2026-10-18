"""Explicit CPU/float32 Metal campaign adapters; preserve upstream rejection criteria."""
import hashlib,json,os,pathlib,subprocess
import fold_engine as fe
import mpnn

def execution_config(original,folder):
 """Choose an explicit single-model arm while retaining modality-specific checks."""
 validation='model_2_multimer_v3' if original.get('validation_model')=='multimer' else 'model_1_ptm'
 config={**original,'project_folder':str(folder/'output'),'design_models':['model_1_multimer_v3'],'validation_model':'multimer' if validation.endswith('multimer_v3') else 'monomer','validation_models':[validation],'design_workers':1,'auto_multi_gpu':False,'attention_backend':'stock','use_cueq':False,'resume':False}
 config['targets']=[{**target,'target_path':str(folder/target['target_path'])} for target in original['targets']]
 if original.get('binder_scaffold'):config['binder_scaffold']=str(folder/original['binder_scaffold'])
 return config,validation

def start(engine,p):
 if set(p)-{'id','projectId','profile'}:raise ValueError('Unsupported campaign launch fields.')
 profiles={'experimental-cpu-single-model':('cpu','upstream',False),'experimental-cpu-float32-single-model':('cpu','float32',False),'experimental-cpu-float32-scaffold':('cpu','float32',False),'experimental-cpu-float32-multitarget':('cpu','float32',False),'experimental-metal-float32-single-model':('metal','float32',False),'experimental-cpu-float32-ensemble':('cpu','float32',True),'experimental-metal-float32-ensemble':('metal','float32',True)}
 if p.get('profile') not in profiles:raise ValueError('Native binder-design execution is blocked without an explicit experimental execution profile.')
 backend,precision,ensemble=profiles[p['profile']]
 s=engine.s;job=engine.campaign(p)
 if job['state']!='prepared':raise ValueError('Only a prepared, unexecuted campaign can start.')
 if s.active():raise ValueError('Another local compute job is active.')
 prep=job['data']['preparation']
 state_count=len(prep['config']['targets']);multitarget=p['profile']=='experimental-cpu-float32-multitarget'
 if state_count>1 and not multitarget:raise ValueError('Multiple targets require the explicit multi-target CPU profile; other profiles remain limited to one state.')
 if multitarget and (not 2<=state_count<=3 or prep['modality'] not in ('binder','peptide')):raise ValueError('The multi-target CPU profile currently supports two or three observed target states with binder or linear-peptide designs.')
 limit=320 if p['profile']=='experimental-cpu-float32-scaffold' else 256
 if limit==320 and not prep.get('scaffold'):raise ValueError('The larger CPU profile requires an original scaffold campaign.')
 count=sum(1 for r in prep['residueMap']);length=max(prep['config']['binder_lengths'])
 if not prep.get('scaffold') and count+length>256:raise ValueError('Initial experimental campaigns are limited to 256 total residues for memory validation.')
 python=os.path.abspath(os.path.expanduser(mpnn.runtime(s)))
 runtime_info={}
 if backend=='metal':
  import metal_runtime
  runtime_info=metal_runtime.probe(s)
  if runtime_info['state']!='experimental':raise ValueError(runtime_info['error'])
  runtime_info['launchEnvironment']=metal_runtime.environment('ensemble' if ensemble else 'single')
  python=runtime_info['runtime']
 if not pathlib.Path(python).is_file():raise ValueError('Scientific Python runtime unavailable.')
 bundled=fe.BASE/'models/alphafold'
 parameters=pathlib.Path(os.environ.get('FOLD_AF2_PARAMETERS') or s.setting('af2Parameters') or (bundled if bundled.is_dir() else s.root/'engine/models/alphafold')).expanduser().absolute()
 fe.verify_source()
 pins=json.loads(pathlib.Path(__file__).with_name('af2-parameters.json').read_text())['models']
 folder=s.root/'jobs'/job['id'];original=json.loads((folder/'settings.json').read_text())
 # Peptide presets judge a bound peptide with a held-out multimer, not an
 # unbound monomer. Retain this upstream scientific distinction.
 if fe.checksum(fe.canonical(original).encode())!=prep['settingsSha256']:raise ValueError('Prepared settings changed.')
 from campaign_inputs import verify
 verify(folder,prep)
 config,validation=execution_config(original,folder)
 selection={'designModels':config['design_models'],'validationModels':[validation]}
 if ensemble:
  from campaign_profile import ensemble_models
  query={**original,'targets':config['targets']}
  if config.get('binder_scaffold'):query['binder_scaffold']=config['binder_scaffold']
  selection=ensemble_models(python,query,fe.UPSTREAM)
  config['design_models']=selection['designModels'];config['validation_models']=selection['validationModels'];config['validation_model']='multimer' if all(model.endswith('multimer_v3') for model in selection['validationModels']) else 'monomer'
 weights={}
 for model in (*selection['designModels'],*selection['validationModels']):
  if model not in pins:raise ValueError('AlphaFold model has no reviewed checkpoint pin: '+model)
  path=parameters/('params_'+model+'.npz')
  if not path.is_file() or path.stat().st_size<100*1024**2:raise ValueError('Missing genuine AlphaFold checkpoint: '+model)
  weights[model]=hashlib.sha256(path.read_bytes()).hexdigest()
  if weights[model]!=pins[model]:raise ValueError('AlphaFold checkpoint does not match the pinned official acquisition: '+model)
 from campaign_profile import resource_estimate
 estimate=resource_estimate(python,config,fe.UPSTREAM)
 if multitarget:
  estimate['aggregatePaddedResidues']=estimate['paddedResidues']*state_count
  if estimate['aggregatePaddedResidues']>192:raise ValueError('The experimental multi-target CPU profile is limited to 192 aggregate padded residues across all states; inputs remain prepared.')
 if estimate['paddedResidues']>limit:raise ValueError('Campaign requires up to '+str(estimate['paddedResidues'])+' padded residues; this experimental profile limit is '+str(limit)+'. Prepare an explicitly smaller target or scaffold.')
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Another local compute job is active.')
 current=s.job(job['id'])
 if current['state']!='prepared':s.db.rollback();raise ValueError('Campaign state changed.')
 data={**current['data'],'runtime':python,'parameters':str(parameters),'checkpointSha256':weights,'profile':p['profile'],'execution':backend,'precision':precision,'modelEnsemble':ensemble,'modelSelection':selection,'resourceEstimate':estimate,'paddedResidueLimit':limit,'runtimeInfo':runtime_info,'executionSettingsSha256':fe.checksum(fe.canonical(config).encode()),'outputs':[]}
 s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('queued',json.dumps(data),fe.mi.now(),job['id']));s.db.commit()
 try:
  (folder/'execution-settings.json').write_text(json.dumps(config,indent=2));return s.spawn(s.job(job['id']),'--bindcraft-cpu-job')
 except Exception as error:s.job_update(job['id'],'failed',{'error':str(error)});raise

def run(s,id):
 job=s.job(id);data=job['data'];folder=s.root/'jobs'/id
 if job['engine']!='bindcraft2' or job['state'] not in ('queued','running'):raise ValueError('Campaign cannot execute in this state.')
 try:
  s.job_update(id,'running',{'started':fe.mi.now(),'stage':'upstream_campaign'})
  backend=data.get('execution','cpu');env={**os.environ,'JAX_PLATFORMS':backend,'PYTHONUNBUFFERED':'1','XLA_PYTHON_CLIENT_PREALLOCATE':'false','PYTHONDONTWRITEBYTECODE':'1'}
  if backend=='metal':
   import metal_runtime
   env.update(metal_runtime.environment('ensemble' if data.get('modelEnsemble') else 'single'))
  settings=folder/'execution-settings.json'
  if data.get('executionSettingsSha256') and fe.checksum(fe.canonical(json.loads(settings.read_text())).encode())!=data['executionSettingsSha256']:raise ValueError('Execution settings changed after queueing.')
  from campaign_inputs import verify
  verify(folder,data['preparation'])
  proc=subprocess.run([data['runtime'],'-B',str(pathlib.Path(__file__).with_name('bindcraft_runner.py')),str(settings),data['parameters'],backend,data.get('precision','float32' if backend=='metal' else 'upstream'),'ensemble' if data.get('modelEnsemble') else 'single'],env=env,timeout=12*3600)
  if proc.returncode:raise RuntimeError('Upstream campaign failed with exit code '+str(proc.returncode)+'. Review execution.log.')
  if s.job(id)['state']=='cancelled':return
  ranked=folder/'output/3_Ranked';files=list(ranked.glob('*.cif')) if ranked.exists() else []
  imported=[]
  if files:
   result=fe.Engine(s).bindcraft_import({'projectId':job['project_id'],'id':id,'directory':str(folder/'output')});imported=result['records']
  s.job_update(id,'completed',{'outputs':imported,'stage':'completed','finished':fe.mi.now(),'acceptedStructureFiles':len(files),'outcome':'accepted_predictions' if files else 'no_accepted_designs','limitations':['Experimental '+backend+' campaign; default scientific rejection criteria retained.','Predicted designs are not validated binding or inhibition.','Full modality and ensemble scientific parity not established.']})
 except Exception as error:
  if s.job(id)['state']!='cancelled':s.job_update(id,'failed',{'error':str(error),'finished':fe.mi.now()})
  print('BindCraft CPU error:',error,flush=True)

def progress_from_log(log):
 """Report only explicitly emitted upstream events. Never invent percent/iteration progress."""
 import re
 trajectories=list(re.finditer(r'=== trajectory (\d+) \| ([^\n|]+) \| accepted (\d+)/(\d+) ===',log))
 out={'source':'upstream execution log','percent':None}
 if trajectories:
  match=trajectories[-1];out.update(trajectory=int(match[1]),trajectoryName=match[2].strip(),acceptedAtTrajectoryStart=int(match[3]),requested=int(match[4]))
  log=log[match.end():]
 events=list(re.finditer(r'(passed|rejected at) (screen|refine|anneal|harden|mutate|final) design stage([^\n]*)',log))
 if events:
  event=events[-1];out.update(lastReportedStage=event[2],stageOutcome='passed' if event[1]=='passed' else 'rejected',stageDetails=event[3].strip())
 for line in log.splitlines():
  if not line.startswith('FOLD_PROGRESS '):continue
  try:
   observed=json.loads(line[len('FOLD_PROGRESS '):])
   if not isinstance(observed,dict):continue
   if observed.get('stage') in ('screen','refine','anneal','harden','mutate') and type(observed.get('sequenceUpdates')) is int and observed['sequenceUpdates']>0:out['lastObservedUpdate']=observed
  except (ValueError,TypeError):pass
 return out
