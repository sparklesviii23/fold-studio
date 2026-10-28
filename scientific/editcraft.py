"""Native EditCraft metadata/IPC. Scientific operations execute only on Modal."""
import hashlib,json,os,pathlib,subprocess,sys,uuid,datetime,re
ACTIONS={'editcraft_state','editcraft_save','editcraft_notebook','editcraft_prepare','editcraft_submit','editcraft_refresh','editcraft_cancel','editcraft_result','editcraft_deploy','editcraft_health','editcraft_import_text','editcraft_models_prepare','editcraft_reference_prepare','editcraft_dataset_import','editcraft_dataset_prepare','editcraft_artifact_export','editcraft_diagnostics'}
NETWORK={'editcraft_submit','editcraft_refresh','editcraft_cancel','editcraft_result','editcraft_deploy','editcraft_health','editcraft_models_prepare','editcraft_reference_prepare','editcraft_dataset_prepare','editcraft_artifact_export','editcraft_diagnostics'}
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
  # Serialize optimistic version checks and publish the mirrored Library record atomically.
  if not s.db.in_transaction:s.db.execute('BEGIN IMMEDIATE')
  s.project(p['projectId'])
  rows=s.rows('SELECT version,data FROM editcraft_entities WHERE id=? AND project_id=? ORDER BY version DESC',(id,p['projectId']))
  latest=rows[0] if rows else None
  if latest and p.get('parentVersion')!=latest['version']:raise ValueError('This entity has a newer version. Reload before saving another revision.')
  if not latest and p.get('id'):raise ValueError('Entity identity is absent from this project.')
  row={'id':id,'projectId':p['projectId'],'kind':kind,'name':name,'version':(latest['version'] if latest else 0)+1,'data':data,'parentVersion':latest['version'] if latest else None,'created':utc(),'sha256':digest(data)}
  s.db.execute('INSERT INTO editcraft_entities VALUES(?,?,?,?)',(id,p['projectId'],row['version'],canonical(row)))
  library_id=str(uuid.uuid4());date=utc()
  library_data={'domain':'editcraft','entityId':id,'version':row['version'],'entityKind':kind,'sha256':row['sha256'],'record':row}
  s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(library_id,p['projectId'],'analysis',name+' · v'+str(row['version']),json.dumps(library_data),date))
  s.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,p['projectId']))
 row['libraryRecordId']=library_id;return row

def provider(s,action,p,row=None):
 import biology_providers
 from cloud_accounts import environment
 python=biology_providers.interpreter(s)
 if not python:raise ValueError('The existing pinned provider runtime is unavailable.')
 account=row.get('accountId') if row else __import__('cloud_accounts').get(s).get('activeId')
 env={k:v for k,v in os.environ.items() if k not in ('PYTHONHOME','PYTHONPATH','MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE')}
 env.update(environment(s,account or 'legacy'));env.update(FOLD_EDITCRAFT_CHILD='1',PYTHONDONTWRITEBYTECODE='1')
 child=subprocess.run([str(python),'-B',str(pathlib.Path(__file__).with_name('worker.py')),'--root',str(s.root)],input=canonical({'action':action,'payload':p}),env=env,capture_output=True,text=True,timeout=900 if action=='editcraft_deploy' else 100)
 try:r=json.loads(child.stdout)
 except ValueError:raise ValueError('Provider response is unavailable. Reconnect to the saved identity; do not resubmit.') from None
 if r.get('error'):raise ValueError(r['error'])
 return r['result']

def dispatch(s,action,p):
 s.project(p['projectId']);table(s)
 import biology_pipeline
 biology_pipeline.common()
 from fold_rapid.editcraft_core import validate_plan,OPS,resources
 if action=='editcraft_state':
  entities=[json.loads(r['data']) for r in s.rows('SELECT data FROM editcraft_entities WHERE project_id=? ORDER BY version DESC',(p['projectId'],))]
  latest={}
  for e in entities:latest.setdefault(e['id'],e)
  catalog=json.loads(pathlib.Path(__file__).with_name('editcraft-models.json').read_text())
  # Qualification comes from verified saved remote results, not catalogue labels.
  from fold_rapid.editcraft_models import manifest_sha
  deployed=s.setting('editcraftDeployment',{});health=deployed.get('health',{});active=__import__('cloud_accounts').get(s).get('activeId')
  verified_models=health.get('models',{}) if deployed.get('accountId')==active else {}
  completed=[json.loads(r['data']) for r in s.rows('SELECT data FROM editcraft_jobs')]
  for model in catalog:
   key={'rule-set-3':'rs3','be-dict':'bedict','pridict2':'pridict2'}.get(model['id'])
   if not key:continue
   model['modelInstalled']=verified_models.get(key,{}).get('manifestSha256')==manifest_sha()
   runs=[row for row in completed if row.get('accountId')==active and row.get('state')=='completed' and any(stage.get('operation')==model['operation'] and stage.get('result',{}).get('provenance',{}).get('manifestSha256')==manifest_sha() for stage in row.get('result',{}).get('results',{}).values())]
   model['genuineInferenceTested']=bool(runs);model['cloudExecutionValidated']=bool(runs);model['executionEvidenceIds']=[row['id'] for row in runs]
   if runs:model.update(state='Executed on cloud · independent benchmark pending',blocker='Genuine pinned-model inference exists. Independent held-out accuracy/calibration and complete native workflow qualification remain unresolved.')
   elif model['modelInstalled']:model.update(state='Installed · inference qualification pending')
  from fold_rapid.editcraft_toolchain import MANIFEST,manifest_sha as tool_manifest_sha
  matching_health=health if deployed.get('accountId')==active else {}
  for model in catalog:
   if model['id']=='cas-offinder':
    runs=[row for row in completed if row.get('accountId')==active and row.get('state')=='completed' and any(stage.get('operation')=='cas_offinder' and stage.get('result',{}).get('provenance',{}).get('manifestSha256')==tool_manifest_sha() for stage in row.get('result',{}).get('results',{}).values())]
    installed=matching_health.get('toolRuntimesIncluded') is True and matching_health.get('toolManifestSha256')==tool_manifest_sha()
    model.update(adapterImplemented=True,operation='cas_offinder',modelInstalled=installed,genuineInferenceTested=bool(runs),cloudExecutionValidated=bool(runs),executionEvidenceIds=[r['id'] for r in runs],state='Executed on cloud · reference validation recorded separately' if runs else 'Runtime deployed · qualification pending' if installed else 'Adapter implemented · cloud qualification pending',blocker='Only verified reference coverage is searched. Human genome assemblies, bulges, genomic annotation and cleavage probability models remain separate requirements.')
  references=[{'id':key,**spec,'receipt':matching_health.get('references',{}).get(key)} for key,spec in MANIFEST['references'].items()]
  from fold_rapid.editcraft_singlecell import MANIFEST as cells,manifest_sha as cell_manifest_sha
  cell_datasets=[{'id':key,'kind':'public',**spec,'receipt':matching_health.get('datasets',{}).get(spec['sha256'])} for key,spec in cells['datasets'].items()]
  cell_datasets += [{'id':e['id'],'kind':'user_upload','name':e['name'],'sha256':e['data']['sha256'],'bytes':e['data']['bytes'],'receipt':matching_health.get('datasets',{}).get(e['data']['sha256'])} for e in latest.values() if e['kind']=='dataset' and e['data'].get('format')=='h5ad']
  for model in catalog:
   if model['id']=='scanpy':
    runs=[row for row in completed if row.get('accountId')==active and row.get('state')=='completed' and any(stage.get('operation')=='scanpy_analysis' and stage.get('result',{}).get('provenance',{}).get('manifestSha256')==cell_manifest_sha() for stage in row.get('result',{}).get('results',{}).values())]
    model.update(adapterImplemented=True,operation='scanpy_analysis',modelInstalled=matching_health.get('singlecellRuntimesIncluded') is True and matching_health.get('cellManifestSha256')==cell_manifest_sha(),genuineInferenceTested=bool(runs),cloudExecutionValidated=bool(runs),executionEvidenceIds=[r['id'] for r in runs],state='Executed on cloud · reference qualification tracked separately' if runs else 'Adapter implemented · genuine cloud qualification pending',blocker='Raw-count QC, normalization, PCA, UMAP, Leiden and exploratory markers only. scvi-tools, Pertpy, donor-aware contrasts, cell-type inference and batch correction remain separate requirements.')
  return {'entities':list(latest.values()),'versions':entities,'jobs':[json.loads(r['data']) for r in s.rows('SELECT data FROM editcraft_jobs WHERE project_id=?',(p['projectId'],))],'models':catalog,'references':references,'cellDatasets':cell_datasets,'operations':[{'id':k,'input':v[0],'output':v[1],'method':v[2]} for k,v in OPS.items()],'deployment':s.setting('editcraftDeployment'),'account':active,'scientificScope':'Cloud-only methods. Model installation, genuine execution and independent benchmarking are separate qualification stages.'}
 if action in ('editcraft_save','editcraft_notebook'):
  if action=='editcraft_notebook':p={**p,'kind':'notebook'}
  return save_entity(s,p)
 if action=='editcraft_import_text':
  file=pathlib.Path(p['path']).expanduser()
  if file.suffix.lower() not in ('.fa','.fasta','.fna','.gb','.gbk','.gff','.gtf','.bed','.vcf','.csv','.tsv','.gmt','.fastq','.fq','.txt','.json'):raise ValueError('Unsupported biological research file.')
  if file.stat().st_size>4*1024**2:raise ValueError('This bounded import accepts files up to 4 MiB. Large dataset streaming is not yet connected.')
  return save_entity(s,{'projectId':p['projectId'],'kind':'dataset','name':file.name,'data':{'text':file.read_text(),'format':file.suffix.lower()[1:],'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'source':'user_import','analysisPerformed':False}})
 if action=='editcraft_dataset_import':
  from fold_rapid.editcraft_singlecell import HDF_HEADER,MAX_BYTES
  file=pathlib.Path(p['path']).expanduser()
  if file.suffix.lower()!='.h5ad' or not 8<file.stat().st_size<=MAX_BYTES or len(file.name)>200:raise ValueError('Import a bounded AnnData H5AD file up to 8 MiB. Large dataset streaming remains a separate workflow.')
  raw=file.read_bytes()
  if raw[:8]!=HDF_HEADER:raise ValueError('This file does not have an HDF5/AnnData header; no scientific analysis was performed.')
  checksum=hashlib.sha256(raw).hexdigest();folder=s.root/'editcraft-datasets';folder.mkdir(exist_ok=True);asset=folder/(checksum+'.h5ad')
  if asset.exists() and hashlib.sha256(asset.read_bytes()).hexdigest()!=checksum:raise ValueError('An existing imported dataset asset changed; preserve it for inspection.')
  if not asset.exists():
   pending=folder/(uuid.uuid4().hex+'.pending');pending.write_bytes(raw);pending.replace(asset)
  return save_entity(s,{'projectId':p['projectId'],'kind':'dataset','name':file.name,'data':{'format':'h5ad','sha256':checksum,'bytes':len(raw),'asset':asset.name,'source':'user_import','analysisPerformed':False,'uploadPerformed':False,'scope':'Original bytes retained locally. H5AD contents are validated during an explicitly approved cloud analysis; import is not scientific qualification.'}})
 if action=='editcraft_prepare':
  if len(canonical(p['plan']))>4*1024**2:raise ValueError('Workflow exceeds the bounded input size.')
  plan=validate_plan(p['plan']);limit=p.get('allowanceUSD')
  if type(limit)not in(int,float) or not .01<=limit<=10:raise ValueError('Choose a CPU analysis allowance between $0.01 and $10.')
  # Explicit reviewed CPU/memory reserve; provider invoice remains separate.
  profile=resources(plan);estimate=round((plan['seconds']+60)*(profile['cpu']*.0000131+profile['memoryGiB']*.00000222)+.10,4)
  row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'state':'prepared','plan':plan,'inputSha256':digest(plan),'created':utc(),'allowanceUSD':limit,'estimatedUSD':estimate,'accountId':__import__('cloud_accounts').get(s).get('activeId'),'cloudOnly':True,'gpuStarted':False,'externalSources':[op for op in ('Ensembl' if any(x['operation'] in ('gene_context','variant_vep') for x in plan['stages']) else None,'NCBI PubMed' if any(x['operation']=='literature' for x in plan['stages']) else None) if op],'pricingBasis':'Review before launch: 2 CPU cores at $0.0000131/core/s, 4 GiB at $0.00000222/GiB/s, 60s startup and $0.10 reserve. Estimate, not provider balance or billing cap.'}
  row['resources']=profile;row['pricingBasis']=f"Review before launch: {profile['cpu']} CPU cores at $0.0000131/core/s, {profile['memoryGiB']} GiB at $0.00000222/GiB/s, 60s startup and $0.10 reserve. Estimate, not provider balance or billing cap."
  return save_job(s,row)
 row=job(s,p) if p.get('id') else None
 if action in NETWORK and not os.environ.get('FOLD_EDITCRAFT_CHILD'):return provider(s,action,p,row)
 import modal
 from fold_rapid.editcraft_modal import APP
 if action=='editcraft_deploy':
  if p.get('approvedCPUDeployment')is not True or p.get('maxApprovedUSD')!=1:raise ValueError('Approve up to $1 CPU deployment and health checks; no GPU or trained models.')
  from fold_rapid.editcraft_modal import deploy
  import contextlib
  with contextlib.redirect_stdout(sys.stderr):result=deploy(include_models=p.get('includeModelRuntimes') is True,include_tools=p.get('includeToolRuntimes') is True,include_singlecell=p.get('includeSinglecellRuntime') is True)
  receipt={'state':'deployed','checked':utc(),'appId':result['appId'],'health':result['health'],'accountId':__import__('cloud_accounts').get(s).get('activeId')}
  with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('editcraftDeployment',canonical(receipt)))
  return receipt
 control=modal.Function.from_name(APP,'control')
 if action=='editcraft_health':
  result=control.remote('health',{});receipt=s.setting('editcraftDeployment',{});receipt.update(health=result,checked=utc())
  with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('editcraftDeployment',canonical(receipt)))
  return result
 if action=='editcraft_models_prepare':
  from fold_rapid.editcraft_models import MANIFEST,manifest_sha
  models=p.get('models')
  if p.get('approvedModelDownloads')is not True or p.get('maxApprovedUSD')!=1 or not isinstance(models,list) or not models or len(set(models))!=len(models) or set(models)-set(MANIFEST['models']):raise ValueError('Approve the listed cloud checkpoint downloads and up to $1 CPU setup separately.')
  deployment=s.setting('editcraftDeployment',{});health=deployment.get('health',{})
  from fold_rapid.editcraft_modal import source_identity
  if deployment.get('accountId')!=__import__('cloud_accounts').get(s).get('activeId') or health.get('sourceSha256')!=source_identity() or health.get('modelRuntimesIncluded')is not True:raise ValueError('Deploy this reviewed worker with the isolated model runtimes for the selected account first.')
  return control.remote('prepare_models',{'models':models,'manifestSha256':manifest_sha(),'approved':True})
 if action=='editcraft_reference_prepare':
  from fold_rapid.editcraft_toolchain import MANIFEST,manifest_sha as tool_manifest_sha
  from fold_rapid.editcraft_modal import source_identity
  identity=p.get('referenceId');deployment=s.setting('editcraftDeployment',{})
  if p.get('approvedReferenceDownload') is not True or p.get('maxApprovedUSD')!=.5 or identity not in MANIFEST['references']:raise ValueError('Approve this exact public reference download and up to $0.50 CPU preparation; no scientific search starts.')
  if deployment.get('accountId')!=__import__('cloud_accounts').get(s).get('activeId') or deployment.get('health',{}).get('sourceSha256')!=source_identity():raise ValueError('Deploy this reviewed reference adapter for the selected account first.')
  return control.remote('prepare_reference',{'referenceId':identity,'manifestSha256':tool_manifest_sha(),'approved':True})
 if action=='editcraft_dataset_prepare':
  from fold_rapid.editcraft_singlecell import MANIFEST as cells,manifest_sha as cell_manifest_sha
  from fold_rapid.editcraft_modal import source_identity
  if p.get('approvedTransfer') is not True or p.get('approvedCost') is not True or p.get('maxApprovedUSD')!=.5:raise ValueError('Approve this exact dataset transfer to Modal and up to $0.50 CPU preparation separately. No analysis starts.')
  deployment=s.setting('editcraftDeployment',{})
  if deployment.get('accountId')!=__import__('cloud_accounts').get(s).get('activeId') or deployment.get('health',{}).get('sourceSha256')!=source_identity():raise ValueError('Deploy this reviewed dataset adapter for the selected account first.')
  identity=p.get('datasetId')
  if p.get('kind')=='public':
   spec=cells['datasets'].get(identity)
   if not spec:raise ValueError('Choose a reviewed public dataset.')
   source={'kind':'public','id':identity};expected=spec['sha256']
  elif p.get('kind')=='user_upload':
   records=s.rows('SELECT data FROM editcraft_entities WHERE id=? AND project_id=? ORDER BY version DESC LIMIT 1',(identity,p['projectId']))
   entity=json.loads(records[0]['data']) if records else None
   if not entity or entity['kind']!='dataset' or entity['data'].get('format')!='h5ad':raise ValueError('Choose an imported H5AD dataset in this project.')
   import base64
   expected=entity['data']['sha256']
   if not re.fullmatch('[a-f0-9]{64}',str(expected)):raise ValueError('Imported dataset has no valid source checksum.')
   file=s.root/'editcraft-datasets'/(expected+'.h5ad')
   if not 8<file.stat().st_size<=8*1024**2:raise ValueError('Imported dataset exceeds its reviewed transfer limit.')
   raw=file.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Imported H5AD bytes changed after review.')
   source={'kind':'upload','sha256':expected,'name':entity['name'],'base64':base64.b64encode(raw).decode()}
  else:raise ValueError('Choose the explicit dataset source.')
  return control.remote('prepare_dataset',{'source':source,'expectedSha256':expected,'manifestSha256':cell_manifest_sha(),'approved':True})
 if row is None:raise ValueError('Select an EditCraft experiment.')
 if action=='editcraft_diagnostics':
  result=control.remote('diagnostics',{'id':row['id']});row['privateDiagnostic']=result;save_job(s,row);return row
 if action=='editcraft_artifact_export':
  if row['state']!='completed':raise ValueError('Retrieve a completed experiment before downloading its original artifact.')
  destination=pathlib.Path(p['path']).expanduser()
  if destination.suffix.lower()!='.h5ad' or not destination.parent.is_dir():raise ValueError('Choose an H5AD destination in an existing folder.')
  info=control.remote('artifact_info',{'id':row['id'],'artifactSha256':p.get('artifactSha256')})
  relative=pathlib.PurePosixPath(info['volumePath'])
  if relative.is_absolute() or '..' in relative.parts or not str(relative).startswith(row['id']+'/') or not 0<info['bytes']<=128*1024**2:raise ValueError('Cloud artifact metadata does not match this experiment.')
  pending=destination.with_name(destination.name+'.partial-'+uuid.uuid4().hex);checksum=hashlib.sha256();size=0
  try:
   volume=modal.Volume.from_name('fold-editcraft-research')
   with pending.open('xb') as output:
    for chunk in volume.read_file(str(relative)):
     size+=len(chunk)
     if size>info['bytes']:raise ValueError('Processed artifact exceeds its original byte receipt.')
     checksum.update(chunk);output.write(chunk)
   if size!=info['bytes'] or checksum.hexdigest()!=info['sha256']:raise ValueError('Downloaded artifact does not match the original cloud checksum; destination was not replaced.')
   pending.replace(destination);return {'state':'exported','path':str(destination),'bytes':size,'sha256':checksum.hexdigest(),'originalArtifactPreserved':True}
  finally:
   if pending.exists():pending.unlink()
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
