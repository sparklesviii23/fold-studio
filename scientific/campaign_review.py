"""Read real stage tables and persist source-preserving upstream reviews."""
import csv,io,json,math,os,pathlib,re,shutil,subprocess
import fold_engine as fe
TABLES={'trajectories':'1_Trajectories/!_Trajectories.csv','candidates':'2_Refolded/!_Refolded.csv','accepted':'3_Ranked/!_Ranked.csv'}
def coordinate_path(output,relative):
 path=output/relative
 if not path.resolve().is_relative_to(output.resolve()) or path.suffix!='.cif':raise ValueError('Stage coordinates must remain inside the campaign output.')
 for item in (path,*path.parents):
  if item.is_symlink():raise ValueError('Stage coordinates cannot follow symlinks.')
  if item==output:break
 if not path.is_file() or not 0<path.stat().st_size<=100*1024**2:raise ValueError('Saved stage coordinates are missing or exceed100MiB.')
 return path

def coordinates(output,stage,rows):
 """List only existing complex snapshots for the first100displayed stage rows."""
 if stage not in ('trajectories','candidates'):return {}
 found={};total=0;count=0
 for row in rows[:100]:
  design=row['design']
  if not re.fullmatch('[A-Za-z0-9_.-]{1,200}',design) or design in ('.','..'):raise ValueError('Unsafe saved stage design identity.')
  prefix=design+'_trajectory' if stage=='trajectories' else design
  folder=output/'1_Trajectories'/design if stage=='trajectories' else output/'2_Refolded/Complexes'
  if not folder.resolve().is_relative_to(output.resolve()):raise ValueError('Stage coordinate folder escapes the campaign output.')
  for directory in (folder,*folder.parents):
   if directory.is_symlink():raise ValueError('Stage coordinates cannot follow symlinks.')
   if directory==output:break
  matches=[p for p in folder.glob(prefix+'*.cif') if (p.stem==prefix or p.stem.startswith(prefix+'_')) and not p.stem.endswith('_monomer')]
  if len(matches)>16:raise ValueError('Too many coordinate snapshots for one saved design.')
  entries=[]
  for path in sorted(matches):
   relative=path.relative_to(output).as_posix();path=coordinate_path(output,relative);total+=path.stat().st_size;count+=1
   if total>100*1024**2 or count>300:raise ValueError('Stage coordinate inspection exceeds its bounded scope.')
   raw=path.read_bytes();entries.append({'file':relative,'sha256':fe.checksum(raw),'bytes':len(raw)})
  if entries:found[design]=entries
 return found

def save_coordinates(engine,p):
 """Save a stage snapshot for viewing without changing scientific acceptance."""
 if set(p)-{'id','projectId','operation','table','design','file','sha256'}:raise ValueError('Unsupported coordinate-preview field.')
 job=engine.campaign(p);stage=p.get('table')
 if stage not in ('trajectories','candidates'):raise ValueError('Stage previews cover trajectories or refolded candidates; ranked designs use the accepted-result importer.')
 if job['state'] not in ('completed','failed','cancelled','interrupted','imported'):raise ValueError('Finish or stop this campaign before saving its coordinate snapshots.')
 folder=engine.s.root/'jobs'/job['id'];output=folder/'output';pid=job['data'].get('pid')
 if pid:
  for line in subprocess.check_output(['/bin/ps','-axo','pgid=,command='],text=True).splitlines():
   parts=line.strip().split(None,1)
   if len(parts)==2 and parts[0]==str(pid) and (job['id'] in parts[1] or str(folder) in parts[1]):raise ValueError('The scientific worker is still stopping; wait before saving a stage snapshot.')
 reading=table(output/TABLES[stage]);matched=[row for row in reading['rows'][:100] if row['design']==p.get('design')]
 if len(matched)!=1:raise ValueError('Choose a unique recorded stage row from the displayed outcomes.')
 row=matched[0];available=coordinates(output,stage,[row]).get(row['design'],[]);entry=next((v for v in available if v['file']==p.get('file')),None)
 if entry is None or entry['sha256']!=p.get('sha256'):raise ValueError('Saved stage coordinates changed or are unavailable; read the outcomes again.')
 path=coordinate_path(output,entry['file']);raw=path.read_bytes();structure=fe.mi.parse_structure(raw.decode(),'mmcif')
 if not structure['atoms'] or fe.checksum(raw)!=entry['sha256']:raise ValueError('Stage coordinates are empty or changed during inspection.')
 from bindcraft_provenance import chain_roles
 roles=chain_roles(raw,structure)
 stamp={'campaignId':job['id'],'stage':stage,'design':row['design'],'file':entry['file'],'coordinateSha256':entry['sha256'],'tableSha256':reading['sha256'],'recordedStageRow':row,'computationalAcceptance':'not_asserted','scope':'Original saved stage coordinates for inspection. This preview does not add an accepted design or certify scaffold/validation criteria.'}
 key=fe.checksum(fe.canonical(stamp).encode());s=engine.s;dest=None
 s.db.execute('BEGIN IMMEDIATE')
 try:
  for record in s.library({})['records']:
   if record['project_id']==job['project_id'] and record['data'].get('metadata',{}).get('campaignStagePreviewKey')==key:
    saved=s.root/'assets'/record['data']['asset']
    if not saved.is_file() or fe.checksum(saved.read_bytes())!=entry['sha256']:raise ValueError('Earlier saved stage coordinate asset changed.')
    s.db.rollback();return {'record':record,'state':'already_saved','scope':stamp['scope']}
  if table(output/TABLES[stage])['sha256']!=reading['sha256'] or path.read_bytes()!=raw:raise ValueError('Stage output changed before the snapshot was saved.')
  identity=fe.mi.uid();dest=s.root/'assets'/(identity+'.cif');dest.write_bytes(raw)
  rejected=bool(row.get('terminated') or row.get('failed_filters') or row.get('outcome')=='rejected')
  label=('Rejected ' if rejected else '')+('trajectory preview' if stage=='trajectories' else 'refold preview')+' · not accepted'
  metadata={'campaignStagePreview':stamp,'campaignStagePreviewKey':key}
  if roles:metadata['chainRoles']=roles;s.db.execute('INSERT INTO intelligence_assignments VALUES(?,?,?,?)',(identity,job['project_id'],json.dumps(roles),fe.mi.now()))
  info={'asset':dest.name,'format':'mmcif','sha256':entry['sha256'],'source':'Saved BindCraft2 stage preview · acceptance not asserted','confidenceKind':None,'metadata':metadata,'imported':fe.mi.now()}
  record={'id':identity,'project_id':job['project_id'],'kind':'structure','name':(label+' · '+row['design'])[:200],'data':info}
  s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(identity,job['project_id'],'structure',record['name'][:200],json.dumps(info),fe.mi.now()))
  s.db.execute('UPDATE projects SET updated=? WHERE id=?',(fe.mi.now(),job['project_id']));s.db.commit()
  return {'record':record,'state':'saved_for_inspection','scope':stamp['scope']}
 except Exception:
  s.db.rollback()
  if dest is not None:dest.unlink(missing_ok=True)
  raise

def table(path):
 if not path.is_file():return {'rows':[],'count':0,'csv':None,'sha256':None}
 if path.is_symlink() or path.stat().st_size>5*1024**2:raise ValueError('Campaign table exceeds the bounded inspection scope or is a symlink.')
 raw=path.read_bytes();rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 if len(rows)>10000 or any(not row.get('design') for row in rows):raise ValueError('Campaign table has too many rows or missing design identities.')
 return {'rows':rows,'count':len(rows),'csv':raw.decode('utf-8'),'sha256':fe.checksum(raw)}
def results(engine,p):
 if set(p)-{'id','projectId'}:raise ValueError('Unsupported campaign inspection field.')
 job=engine.campaign(p);output=engine.s.root/'jobs'/job['id']/'output';values={key:table(output/name) for key,name in TABLES.items()};state=output/'.campaign_state.json'
 for stage,reading in values.items():reading['coordinates']=coordinates(output,stage,reading['rows'])
 return {'campaignId':job['id'],'state':job['state'],'tables':values,'claimedProgress':json.loads(state.read_text()) if state.is_file() and not state.is_symlink() else None,'scope':'Original upstream stage-table readings, preserved as written. Claimed attempts can include an interrupted trajectory with no completed row. Missing metrics are unreported; rejected candidates are not accepted designs.'}
def manifest(output):
 files={};total=0
 for path in sorted(output.rglob('*')):
  if path.is_symlink():raise ValueError('Review cannot follow output symlinks.')
  if not path.is_file():continue
  if path.stat().st_size>100*1024**2:raise ValueError('A review input exceeds 100 MiB.')
  raw=path.read_bytes();total+=len(raw)
  if total>512*1024**2 or len(files)>=20000:raise ValueError('Review snapshot exceeds its bounded scope.')
  files[str(path.relative_to(output))]=raw
 return files

def review(engine,p):
 if p.get('operation')=='save_coordinates':return save_coordinates(engine,p)
 from mpnn import runtime
 from observatory import Observatory
 if set(p)-{'id','projectId','operation','table','metrics','expressions','higher'}:raise ValueError('Unsupported campaign review field.')
 job=engine.campaign(p);operation=p.get('operation');storage=operation in ('archive','unarchive');selected=p.get('table','trajectories' if storage else 'candidates' if operation=='filter' else 'accepted');metrics=p.get('metrics',['i_pDAE'])
 if operation not in ('filter','rank','score','summary','archive','unarchive','metrics') or not isinstance(selected,str) or selected not in TABLES or not isinstance(metrics,list) or not 1<=len(metrics)<=3 or any(not isinstance(v,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_.]{0,79}',v) for v in metrics):raise ValueError('Choose an original saved-outcome operation, a recorded table and 1–3 metric names.')
 if operation!='rank' and 'metrics' in p:raise ValueError('This operation does not take ranking overrides.')
 if storage and 'table' in p:raise ValueError('Trajectory storage operations do not accept stage overrides.')
 higher=p.get('higher')
 if 'higher' in p and (operation!='rank' or higher is not None and type(higher) is not bool):raise ValueError('Choose the original ranking direction, highest first or lowest first.')
 if operation=='summary' and 'table' in p:raise ValueError('Campaign summaries cover all recorded stages; no table override is accepted.')
 if operation=='score' and selected!='accepted':raise ValueError('Coordinate scoring currently requires the saved accepted-complex table.')
 expressions=p.get('expressions',[])
 if 'expressions' in p and operation!='filter':raise ValueError('Threshold expressions apply only to filter reviews.')
 if not isinstance(expressions,list) or len(expressions)>32:raise ValueError('Choose at most 32 threshold expressions.')
 for expression in expressions:
  matched=re.fullmatch(r'([A-Za-z][A-Za-z0-9_.]{0,79})\s*(>=|<=|!=|==|>|<|=)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',expression.strip()) if isinstance(expression,str) and len(expression)<=128 else None
  if not matched or not math.isfinite(float(matched[3])):raise ValueError('Write each threshold as a metric, comparison and finite number, for example i_pTM>=0.7.')
 if job['state'] not in ('completed','failed','cancelled','interrupted','imported'):raise ValueError('Finish or stop the campaign before reviewing saved outcomes.')
 python=os.path.abspath(os.path.expanduser(runtime(engine.s)))
 if not pathlib.Path(python).is_file():raise ValueError('The BindCraft2 scientific runtime is unavailable.')
 source=fe.verify_source();campaign_folder=engine.s.root/'jobs'/job['id']
 if job['data'].get('preparation'):
  from campaign_inputs import verify
  verify(campaign_folder,job['data']['preparation'])
 output=campaign_folder/'output';reading=table(output/TABLES[selected])
 if operation!='summary' and not storage and not reading['rows']:raise ValueError('This campaign has no recorded rows in the selected stage.')
 s=engine.s;obs=Observatory(s);folder=engine.s.root/'jobs'/job['id']/'reviews'/fe.mi.uid();runner=pathlib.Path(__file__).with_name('campaign_review_runner.py');runner_sha=fe.checksum(runner.read_bytes());s.db.execute('BEGIN IMMEDIATE')
 exchanged=False;committed=False
 try:
  if s.active():raise ValueError('Another local compute job is active. Wait before reviewing a campaign.')
  files=manifest(output);folder.mkdir(parents=True);snapshot=folder/'snapshot';snapshot.mkdir()
  for name,raw in files.items():dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  request={'operation':operation,'campaignId':job['id'],'table':selected,'metrics':metrics,'higher':higher,'expressions':expressions,'inputManifest':{name:fe.checksum(raw) for name,raw in files.items()},'upstream':source};text=fe.canonical(request);(folder/'request.json').write_text(text)
  process=subprocess.run([python,'-I','-B',str(runner),str(folder/'request.json')],env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60);(folder/'execution.log').write_text(process.stdout+'\n'+process.stderr)
  if process.returncode:raise ValueError('Upstream review refused: '+process.stderr.strip()[-2000:])
  result=json.loads((folder/'result.json').read_text())
  if result['requestSha256']!=fe.checksum(text.encode()) or result['runnerSha256']!=runner_sha or fe.checksum(runner.read_bytes())!=runner_sha or {name:fe.checksum(raw) for name,raw in manifest(output).items()}!=request['inputManifest'] or fe.verify_source()!=source:raise ValueError('Review source, implementation or upstream code changed during calculation.')
  if job['data'].get('preparation'):verify(campaign_folder,job['data']['preparation'])
  if storage:
   from campaign_archive import logical_manifest,exchange_directories
   expected=logical_manifest(output)
   if result.get('logicalManifest')!=expected or logical_manifest(snapshot)!=expected:raise ValueError('Trajectory storage content verification failed before applying conversion.')
   receipt={'operation':operation,'state':'ready_to_exchange','logicalManifest':expected,'beforeManifest':request['inputManifest'],'afterManifest':{name:fe.checksum(raw) for name,raw in manifest(snapshot).items()}}
   (folder/'storage-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');exchange_directories(output/'1_Trajectories',snapshot/'1_Trajectories');exchanged=True
   if logical_manifest(output)!=expected:raise ValueError('Trajectory contents changed while applying storage conversion.')
   receipt['state']='applied';(folder/'storage-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');result['storageReceipt']=receipt
  result.update(campaignId=job['id'],inputManifest=request['inputManifest'],upstream=source,sourceUnchanged=not storage,reviewFolder=str(folder.relative_to(s.root/'jobs'/job['id'])));entry=obs.observatory_save({'projectId':p['projectId'],'kind':'analysis','name':'BindCraft2 '+operation+' review · '+job['name'],'data':result});committed=True
  if storage:
   try:shutil.rmtree(snapshot/'1_Trajectories')
   except OSError as error:result['cleanupWarning']='Conversion is complete; an extra verified working copy remains: '+str(error)
  return {**result,'analysisId':entry['id']}
 except Exception as error:
  s.db.rollback()
  if exchanged and not committed:
   exchange_directories(output/'1_Trajectories',snapshot/'1_Trajectories')
   (folder/'storage-receipt.json').write_text(json.dumps({**receipt,'state':'rolled_back'})+'\n')
  if folder.is_dir():(folder/'failure.json').write_text(json.dumps({'error':str(error),'state':'failed_no_analysis_published'})+'\n')
  raise
