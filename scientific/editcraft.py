"""Native EditCraft metadata/IPC. Scientific operations execute only on Modal."""
import hashlib,json,os,pathlib,subprocess,sys,uuid,datetime
ACTIONS={'editcraft_state','editcraft_save','editcraft_notebook','editcraft_prepare','editcraft_submit','editcraft_refresh','editcraft_cancel','editcraft_result','editcraft_deploy','editcraft_health','editcraft_import_text'}
NETWORK={'editcraft_submit','editcraft_refresh','editcraft_cancel','editcraft_result','editcraft_deploy','editcraft_health'}
KINDS={'gene','transcript','variant','sequence','construct','dataset','evidence','workflow','intervention','notebook','model_assessment','report'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def table(s):
 s.db.execute('CREATE TABLE IF NOT EXISTS editcraft_entities(id TEXT,project_id TEXT,version INTEGER,data TEXT,PRIMARY KEY(id,version))')
 s.db.execute('CREATE TABLE IF NOT EXISTS editcraft_jobs(id TEXT PRIMARY KEY,project_id TEXT,data TEXT)');s.db.commit()
def job(s,p):
 r=s.db.execute('SELECT data FROM editcraft_jobs WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone()
 if not r:raise ValueError('Choose an EditCraft experiment in this project.')
 return json.loads(r[0])
def save_job(s,row):
 with s.db:s.db.execute('INSERT OR REPLACE INTO editcraft_jobs VALUES(?,?,?)',(row['id'],row['projectId'],canonical(row)))
 return row

def save_entity(s,p):
 kind=p['kind'];name=str(p.get('name','')).strip()
 if kind not in KINDS or not name or len(name)>200:raise ValueError('Choose a supported entity type and a name.')
 data=p['data']
 if not isinstance(data,dict) or len(canonical(data))>4*1024**2:raise ValueError('Entity must be a bounded structured record.')
 id=p.get('id') or uuid.uuid4().hex
 with s.db:
  rows=s.rows('SELECT version,data FROM editcraft_entities WHERE id=? AND project_id=? ORDER BY version DESC',(id,p['projectId']))
  latest=rows[0] if rows else None
  if latest and p.get('parentVersion')!=latest['version']:raise ValueError('This entity has a newer version. Reload before saving another revision.')
  if not latest and p.get('id'):raise ValueError('Entity identity is absent from this project.')
  row={'id':id,'projectId':p['projectId'],'kind':kind,'name':name,'version':(latest['version'] if latest else 0)+1,'data':data,'parentVersion':latest['version'] if latest else None,'created':utc(),'sha256':digest(data)}
  s.db.execute('INSERT INTO editcraft_entities VALUES(?,?,?,?)',(id,p['projectId'],row['version'],canonical(row)))
 # Unified Library entry: append each immutable research version.
 library=s.record_save({'projectId':p['projectId'],'kind':'analysis','name':name+' · v'+str(row['version']),'data':{'domain':'editcraft','entityId':id,'version':row['version'],'entityKind':kind,'sha256':row['sha256'],'record':row}})
 row['libraryRecordId']=library['id'];return row

def provider(s,action,p,row=None):
 import biology_providers
 from cloud_accounts import environment
 python=biology_providers.interpreter(s)
 if not python:raise ValueError('The existing pinned provider runtime is unavailable.')
 account=row.get('accountId') if row else __import__('cloud_accounts').get(s).get('activeId')
 env={k:v for k,v in os.environ.items() if k not in ('PYTHONHOME','PYTHONPATH','MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE')}
 env.update(environment(s,account or 'legacy'));env.update(FOLD_EDITCRAFT_CHILD='1',PYTHONDONTWRITEBYTECODE='1')
 child=subprocess.run([str(python),'-B',str(pathlib.Path(__file__).with_name('worker.py')),'--root',str(s.root)],input=canonical({'action':action,'payload':p}),env=env,capture_output=True,text=True,timeout=300 if action=='editcraft_deploy' else 100)
 try:r=json.loads(child.stdout)
 except ValueError:raise ValueError('Provider response is unavailable. Reconnect to the saved identity; do not resubmit.') from None
 if r.get('error'):raise ValueError(r['error'])
 return r['result']

def dispatch(s,action,p):
 s.project(p['projectId']);table(s)
 import biology_pipeline
 biology_pipeline.common()
 from fold_rapid.editcraft_core import validate_plan,OPS
 if action=='editcraft_state':
  entities=[json.loads(r['data']) for r in s.rows('SELECT data FROM editcraft_entities WHERE project_id=? ORDER BY version DESC',(p['projectId'],))]
  latest={}
  for e in entities:latest.setdefault(e['id'],e)
  catalog=json.loads(pathlib.Path(__file__).with_name('editcraft-models.json').read_text())
  return {'entities':list(latest.values()),'versions':entities,'jobs':[json.loads(r['data']) for r in s.rows('SELECT data FROM editcraft_jobs WHERE project_id=?',(p['projectId'],))],'models':catalog,'operations':[{'id':k,'input':v[0],'output':v[1],'method':v[2]} for k,v in OPS.items()],'deployment':s.setting('editcraftDeployment'),'account':__import__('cloud_accounts').get(s).get('activeId'),'scientificScope':'CPU operation adapters implemented; cloud qualification tracked separately. Trained editor models are not yet connected.'}
 if action in ('editcraft_save','editcraft_notebook'):
  if action=='editcraft_notebook':p={**p,'kind':'notebook'}
  return save_entity(s,p)
 if action=='editcraft_import_text':
  file=pathlib.Path(p['path']).expanduser()
  if file.suffix.lower() not in ('.fa','.fasta','.fna','.gb','.gbk','.gff','.gtf','.bed','.vcf','.csv','.tsv','.fastq','.fq','.txt','.json'):raise ValueError('Unsupported biological research file.')
  if file.stat().st_size>4*1024**2:raise ValueError('This bounded import accepts files up to 4 MiB. Large dataset streaming is not yet connected.')
  return save_entity(s,{'projectId':p['projectId'],'kind':'dataset','name':file.name,'data':{'text':file.read_text(),'format':file.suffix.lower()[1:],'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'source':'user_import','analysisPerformed':False}})
 if action=='editcraft_prepare':
  if len(canonical(p['plan']))>4*1024**2:raise ValueError('Workflow exceeds the bounded input size.')
  plan=validate_plan(p['plan']);limit=p.get('allowanceUSD')
  if type(limit)not in(int,float) or not .01<=limit<=10:raise ValueError('Choose a CPU analysis allowance between $0.01 and $10.')
  # Explicit reviewed CPU/memory reserve; provider invoice remains separate.
  estimate=round((plan['seconds']+60)*(2*.0000131+4*.00000222)+.10,4)
  row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'state':'prepared','plan':plan,'inputSha256':digest(plan),'created':utc(),'allowanceUSD':limit,'estimatedUSD':estimate,'accountId':__import__('cloud_accounts').get(s).get('activeId'),'cloudOnly':True,'gpuStarted':False,'externalSources':[op for op in ('Ensembl' if any(x['operation']=='gene_context' for x in plan['stages']) else None,'NCBI PubMed' if any(x['operation']=='literature' for x in plan['stages']) else None) if op],'pricingBasis':'Review before launch: 2 CPU cores at $0.0000131/core/s, 4 GiB at $0.00000222/GiB/s, 60s startup and $0.10 reserve. Estimate, not provider balance or billing cap.'}
  return save_job(s,row)
 row=job(s,p) if p.get('id') else None
 if action in NETWORK and not os.environ.get('FOLD_EDITCRAFT_CHILD'):return provider(s,action,p,row)
 import modal
 from fold_rapid.editcraft_modal import APP
 if action=='editcraft_deploy':
  if p.get('approvedCPUDeployment')is not True or p.get('maxApprovedUSD')!=1:raise ValueError('Approve up to $1 CPU deployment and health checks; no GPU or trained models.')
  from fold_rapid.editcraft_modal import deploy
  import contextlib
  with contextlib.redirect_stdout(sys.stderr):result=deploy()
  receipt={'state':'deployed','checked':utc(),'appId':result['appId'],'health':result['health'],'accountId':__import__('cloud_accounts').get(s).get('activeId')}
  with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('editcraftDeployment',canonical(receipt)))
  return receipt
 control=modal.Function.from_name(APP,'control')
 if action=='editcraft_health':return control.remote('health',{})
 if row is None:raise ValueError('Select an EditCraft experiment.')
 if action=='editcraft_submit':
  from fold_rapid.editcraft_modal import source_identity
  deployment=s.setting('editcraftDeployment',{})
  if deployment.get('accountId')!=row.get('accountId') or deployment.get('health',{}).get('sourceSha256')!=source_identity():raise ValueError('Deploy this reviewed EditCraft worker for the campaign’s account before launching. No protein-engine update is required.')
  if p.get('approvedTransfer')is not True or p.get('approvedCost')is not True:raise ValueError('Approve this dataset transfer and CPU workload explicitly.')
  if row['estimatedUSD']>row['allowanceUSD']:raise ValueError('CPU estimate exceeds this experiment allowance.')
  with s.db:
   s.db.execute('BEGIN IMMEDIATE');current=job(s,p)
   if current['state']!='prepared':raise ValueError('Experiment already claimed; refresh its saved identity.')
   row['state']='submission_uncertain';s.db.execute('UPDATE editcraft_jobs SET data=? WHERE id=?',(canonical(row),row['id']))
  remote=control.remote('submit',{'id':row['id'],'plan':row['plan'],'approved':True});row.update(state=remote['state'],remote=remote);return save_job(s,row)
 if action=='editcraft_cancel':
  remote=control.remote('cancel',{'id':row['id']});row.update(state=remote['state'],remote=remote);return save_job(s,row)
 if action=='editcraft_refresh':
  remote=control.remote('status',{'id':row['id']});row.update(state=remote['state'],remote=remote);return save_job(s,row)
 if action=='editcraft_result':
  result=control.remote('result',{'id':row['id']});row.update(state='completed',result=result['result'],remote=result['status'])
  if not row.get('resultEntityId'):
   entity=save_entity(s,{'projectId':p['projectId'],'kind':'report','name':'EditCraft experiment '+row['id'][:8],'data':{'experimentId':row['id'],'inputSha256':row['inputSha256'],'result':row['result']}})
   note=save_entity(s,{'projectId':p['projectId'],'kind':'notebook','name':'Experiment receipt '+row['id'][:8],'data':{'experimentId':row['id'],'plan':row['plan'],'resultEntityId':entity['id'],'provenance':row['result']['provenance'],'estimatedUSD':row['estimatedUSD'],'providerReportedUSD':None}})
   row.update(resultEntityId=entity['id'],notebookId=note['id'])
  return save_job(s,row)
 raise ValueError('Unsupported EditCraft action.')
