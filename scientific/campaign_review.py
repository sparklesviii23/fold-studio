"""Read real stage tables and persist source-preserving upstream reviews."""
import csv,io,json,os,pathlib,re,subprocess
import fold_engine as fe
TABLES={'trajectories':'1_Trajectories/!_Trajectories.csv','candidates':'2_Refolded/!_Refolded.csv','accepted':'3_Ranked/!_Ranked.csv'}
def table(path):
 if not path.is_file():return {'rows':[],'count':0,'csv':None,'sha256':None}
 if path.is_symlink() or path.stat().st_size>5*1024**2:raise ValueError('Campaign table exceeds the bounded inspection scope or is a symlink.')
 raw=path.read_bytes();rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 if len(rows)>10000 or any(not row.get('design') for row in rows):raise ValueError('Campaign table has too many rows or missing design identities.')
 return {'rows':rows,'count':len(rows),'csv':raw.decode('utf-8'),'sha256':fe.checksum(raw)}
def results(engine,p):
 if set(p)-{'id','projectId'}:raise ValueError('Unsupported campaign inspection field.')
 job=engine.campaign(p);output=engine.s.root/'jobs'/job['id']/'output';values={key:table(output/name) for key,name in TABLES.items()};state=output/'.campaign_state.json'
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
 from mpnn import runtime
 from observatory import Observatory
 if set(p)-{'id','projectId','operation','table','metrics'}:raise ValueError('Unsupported campaign review field.')
 job=engine.campaign(p);operation=p.get('operation');selected=p.get('table','candidates' if operation=='filter' else 'accepted');metrics=p.get('metrics',['i_pDAE'])
 if operation not in ('filter','rank','score','summary') or not isinstance(selected,str) or selected not in TABLES or not isinstance(metrics,list) or not 1<=len(metrics)<=3 or any(not isinstance(v,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_.]{0,79}',v) for v in metrics):raise ValueError('Choose an original saved-outcome operation, a recorded table and 1–3 metric names.')
 if operation in ('filter','score','summary') and 'metrics' in p:raise ValueError('This operation does not take ranking overrides.')
 if operation=='summary' and 'table' in p:raise ValueError('Campaign summaries cover all recorded stages; no table override is accepted.')
 if operation=='score' and selected!='accepted':raise ValueError('Coordinate scoring currently requires the saved accepted-complex table.')
 if job['state'] not in ('completed','failed','cancelled','interrupted','imported'):raise ValueError('Finish or stop the campaign before reviewing saved outcomes.')
 python=os.path.abspath(os.path.expanduser(runtime(engine.s)))
 if not pathlib.Path(python).is_file():raise ValueError('The BindCraft2 scientific runtime is unavailable.')
 source=fe.verify_source();campaign_folder=engine.s.root/'jobs'/job['id']
 if job['data'].get('preparation'):
  from campaign_inputs import verify
  verify(campaign_folder,job['data']['preparation'])
 output=campaign_folder/'output';reading=table(output/TABLES[selected])
 if operation!='summary' and not reading['rows']:raise ValueError('This campaign has no recorded rows in the selected stage.')
 s=engine.s;obs=Observatory(s);folder=engine.s.root/'jobs'/job['id']/'reviews'/fe.mi.uid();runner=pathlib.Path(__file__).with_name('campaign_review_runner.py');runner_sha=fe.checksum(runner.read_bytes());s.db.execute('BEGIN IMMEDIATE')
 try:
  if s.active():raise ValueError('Another local compute job is active. Wait before reviewing a campaign.')
  files=manifest(output);folder.mkdir(parents=True);snapshot=folder/'snapshot';snapshot.mkdir()
  for name,raw in files.items():dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  request={'operation':operation,'campaignId':job['id'],'table':selected,'metrics':metrics,'inputManifest':{name:fe.checksum(raw) for name,raw in files.items()},'upstream':source};text=fe.canonical(request);(folder/'request.json').write_text(text)
  process=subprocess.run([python,'-I','-B',str(runner),str(folder/'request.json')],env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60);(folder/'execution.log').write_text(process.stdout+'\n'+process.stderr)
  if process.returncode:raise ValueError('Upstream review refused: '+process.stderr.strip()[-2000:])
  result=json.loads((folder/'result.json').read_text())
  if result['requestSha256']!=fe.checksum(text.encode()) or result['runnerSha256']!=runner_sha or fe.checksum(runner.read_bytes())!=runner_sha or {name:fe.checksum(raw) for name,raw in manifest(output).items()}!=request['inputManifest'] or fe.verify_source()!=source:raise ValueError('Review source, implementation or upstream code changed during calculation.')
  if job['data'].get('preparation'):verify(campaign_folder,job['data']['preparation'])
  result.update(campaignId=job['id'],inputManifest=request['inputManifest'],upstream=source,sourceUnchanged=True,reviewFolder=str(folder.relative_to(s.root/'jobs'/job['id'])));entry=obs.observatory_save({'projectId':p['projectId'],'kind':'analysis','name':'BindCraft2 '+operation+' review · '+job['name'],'data':result});return {**result,'analysisId':entry['id']}
 except Exception as error:
  s.db.rollback()
  if folder.is_dir():(folder/'failure.json').write_text(json.dumps({'error':str(error),'state':'failed_no_analysis_published'})+'\n')
  raise
