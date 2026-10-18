"""Experimental single-model CPU campaign adapter; preserves upstream rejection criteria."""
import hashlib,json,os,pathlib,subprocess
import fold_engine as fe
import mpnn

def start(engine,p):
 if set(p)-{'id','projectId','profile'}:raise ValueError('Unsupported campaign launch fields.')
 if p.get('profile')!='experimental-cpu-single-model':raise ValueError('Native binder-design execution is blocked without explicit experimental-cpu-single-model selection. Metal is not available.')
 s=engine.s;job=engine.campaign(p)
 if job['state']!='prepared':raise ValueError('Only a prepared, unexecuted campaign can start.')
 prep=job['data']['preparation'];count=sum(1 for r in prep['residueMap']);length=max(prep['config']['binder_lengths'])
 if count+length>256:raise ValueError('Initial experimental CPU campaigns are limited to 256 total residues for memory validation.')
 python=os.path.abspath(os.path.expanduser(mpnn.runtime(s)))
 if not pathlib.Path(python).is_file():raise ValueError('Scientific Python runtime unavailable.')
 bundled=fe.BASE/'models/alphafold'
 parameters=pathlib.Path(os.environ.get('FOLD_AF2_PARAMETERS') or s.setting('af2Parameters') or (bundled if bundled.is_dir() else s.root/'engine/models/alphafold')).expanduser().absolute()
 fe.verify_source()
 pins=json.loads(pathlib.Path(__file__).with_name('af2-parameters.json').read_text())['models']
 weights={}
 for model in ('model_1_multimer_v3','model_1_ptm'):
  path=parameters/('params_'+model+'.npz')
  if not path.is_file() or path.stat().st_size<100*1024**2:raise ValueError('Missing genuine AlphaFold checkpoint: '+model)
  weights[model]=hashlib.sha256(path.read_bytes()).hexdigest()
  if weights[model]!=pins[model]:raise ValueError('AlphaFold checkpoint does not match the pinned official acquisition: '+model)
 folder=s.root/'jobs'/job['id'];original=json.loads((folder/'settings.json').read_text())
 if fe.checksum(fe.canonical(original).encode())!=prep['settingsSha256']:raise ValueError('Prepared settings changed.')
 source=folder/original['targets'][0]['target_path']
 if fe.checksum(source.read_bytes())!=prep['source']['sha256']:raise ValueError('Prepared source changed.')
 config={**original,'project_folder':str(folder/'output'),'design_models':['model_1_multimer_v3'],'validation_model':'monomer','validation_models':['model_1_ptm'],'design_workers':1,'auto_multi_gpu':False,'attention_backend':'stock','use_cueq':False,'resume':False}
 config['targets']=[{**target,'target_path':str(folder/target['target_path'])} for target in original['targets']]
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Another local compute job is active.')
 current=s.job(job['id'])
 if current['state']!='prepared':s.db.rollback();raise ValueError('Campaign state changed.')
 data={**current['data'],'runtime':python,'parameters':str(parameters),'checkpointSha256':weights,'profile':p['profile'],'execution':'cpu','outputs':[]}
 s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('queued',json.dumps(data),fe.mi.now(),job['id']));s.db.commit()
 try:
  (folder/'execution-settings.json').write_text(json.dumps(config,indent=2));return s.spawn(s.job(job['id']),'--bindcraft-cpu-job')
 except Exception as error:s.job_update(job['id'],'failed',{'error':str(error)});raise

def run(s,id):
 job=s.job(id);data=job['data'];folder=s.root/'jobs'/id
 if job['engine']!='bindcraft2' or job['state'] not in ('queued','running'):raise ValueError('Campaign cannot execute in this state.')
 try:
  s.job_update(id,'running',{'started':fe.mi.now(),'stage':'upstream_campaign'})
  proc=subprocess.run([data['runtime'],'-B',str(pathlib.Path(__file__).with_name('bindcraft_runner.py')),str(folder/'execution-settings.json'),data['parameters']],env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONUNBUFFERED':'1','XLA_PYTHON_CLIENT_PREALLOCATE':'false'},timeout=12*3600)
  if proc.returncode:raise RuntimeError('Upstream campaign failed with exit code '+str(proc.returncode)+'. Review execution.log.')
  if s.job(id)['state']=='cancelled':return
  ranked=folder/'output/3_Ranked';files=list(ranked.glob('*.cif')) if ranked.exists() else []
  imported=[]
  if files:
   result=fe.Engine(s).bindcraft_import({'projectId':job['project_id'],'id':id,'directory':str(folder/'output')});imported=result['records']
  s.job_update(id,'completed',{'outputs':imported,'stage':'completed','finished':fe.mi.now(),'acceptedStructureFiles':len(files),'outcome':'accepted_predictions' if files else 'no_accepted_designs','limitations':['Experimental CPU single-model campaign; default scientific rejection criteria retained.','Predicted designs are not validated binding or inhibition.','No Metal acceleration. Full modality and ensemble parity not established.']})
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
 return out
