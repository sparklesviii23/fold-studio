"""Persistent ProteinMPNN workflow on the shared library/jobs, isolated from UI."""
import json,os,pathlib,subprocess,sys
import fold_engine as fe
ACTIONS={'mpnn_start','mpnn_jobs'}

def runtime(s):
 bundled=fe.BASE/'runtime/bin/python3.12'
 return os.environ.get('FOLD_BINDCRAFT_PYTHON') or s.setting('bindcraftPython') or str(bundled if bundled.is_file() else s.root/'engine/bindcraft/bin/python')

def start(s,p):
 if set(p)-{'projectId','structureId','designChains','count','seed','temperature','variant','designResidues','tiedChains','omitAminoAcids','aminoAcidBias'}:raise ValueError('Unsupported ProteinMPNN field.')
 engine=fe.Engine(s);shared=engine.fold_structure(p);st=shared['structure'];chains=p.get('designChains')
 if not isinstance(chains,list) or not chains or any(not isinstance(ch,str) for ch in chains) or len(set(chains))!=len(chains):raise ValueError('Select distinct chains to redesign.')
 all_chains=[ch['id'] for ch in st['chains']]
 if set(chains)-set(all_chains):raise ValueError('Unknown redesign chain.')
 from mpnn_constraints import prepare
 constraints=prepare(st,chains,p)
 engine.bindcraft_validate({'projectId':p['projectId'],'structureId':p['structureId'],'targetChains':all_chains})
 if sum(len(ch['sequence']) for ch in st['chains'])>600:raise ValueError('Initial CPU workflow is limited to 600 total observed residues.')
 count=fe.integer(p.get('count',1),'Count',1,8);seed=fe.integer(p.get('seed',42),'Seed',0,2147483647);temperature=p.get('temperature',0.1)
 if type(temperature) not in (int,float) or not 0.01<=temperature<=1:raise ValueError('Temperature must be 0.01–1.')
 variant=p.get('variant','neutral')
 if variant not in ('neutral','negative','positive'):raise ValueError('Unknown checkpoint variant.')
 python=os.path.abspath(os.path.expanduser(runtime(s)))
 if not pathlib.Path(python).is_file():raise ValueError('ProteinMPNN runtime unavailable. Configure the isolated BindCraft Python runtime first.')
 fe.verify_source();record,path=engine.lab.record(p['structureId'])
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Another local compute job is active.')
 job=s.job_new({'projectId':p['projectId'],'name':'ProteinMPNN · '+record['name'],'source':shared['reference'],'count':count,'seed':seed,'temperature':temperature,'variant':variant,'designChains':chains,'constraints':constraints,'upstreamRevision':fe.PIN,'runtime':python,'sequences':{ch['id']:ch['sequence'] for ch in st['chains']},'outputs':[]},'proteinmpnn','queued')
 folder=s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True)
 try:
  raw=path.read_bytes()
  if fe.checksum(raw)!=record['data']['sha256']:raise ValueError('Source changed during snapshot.')
  (folder/('input'+path.suffix)).write_bytes(raw)
  return s.spawn(job,'--mpnn-job')
 except Exception as error:s.job_update(job['id'],'failed',{'error':str(error)});raise

def run(s,id):
 job=s.job(id);data=job['data'];folder=s.root/'jobs'/id
 if job['engine']!='proteinmpnn' or job['state'] not in ('queued','running'):raise ValueError('Job cannot execute in this state.')
 try:
  s.job_update(id,'running',{'stage':'inference','started':fe.mi.now()})
  source=next(folder.glob('input.*'));request={'input':str(source),'sha256':data['source']['sha256'],**{k:data[k] for k in ('sequences','count','seed','temperature','variant','designChains')}}
  if 'constraints' in data:request['constraints']=data['constraints']
  (folder/'request.json').write_text(json.dumps(request,indent=2))
  proc=subprocess.run([data['runtime'],'-B',str(pathlib.Path(__file__).with_name('mpnn_runner.py')),str(folder/'request.json'),str(folder/'result.json')],env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONUNBUFFERED':'1','XLA_PYTHON_CLIENT_PREALLOCATE':'false'},timeout=1800)
  if proc.returncode:raise RuntimeError('ProteinMPNN exited with code '+str(proc.returncode)+'. Review execution log.')
  if s.job(id)['state']=='cancelled':return
  result=json.loads((folder/'result.json').read_text());records=[];fasta=[]
  # Commit every sequence and the completed job in one transaction.
  s.db.execute('BEGIN IMMEDIATE')
  if s.job(id)['state']=='cancelled':s.db.rollback();return
  for i,candidate in enumerate(result['candidates'],1):
   for ch in data['designChains']:
    sequence=candidate['chains'][ch];rid=fe.mi.uid();name=f'ProteinMPNN candidate {i} · chain {ch}'
    meta={'sequence':sequence,'source':'Upstream ProteinMPNN fixed-backbone redesign','jobId':id,'structureId':data['source']['structureId'],'sourceSha256':data['source']['sha256'],'chain':ch,'constraints':data.get('constraints'),'metrics':candidate['metrics'],'seed':data['seed'],'checkpointSha256':result['checkpointSha256'],'upstreamRevision':fe.PIN,'validationStatus':'sequence_only_unvalidated_fold'}
    s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(rid,job['project_id'],'sequence',name,json.dumps(meta),fe.mi.now()));records.append(rid);fasta.append(f'>candidate_{i}_chain_{ch}\n{sequence}')
  (folder/'sequences.fasta').write_text('\n'.join(fasta)+'\n')
  data.update(outputs=records,stage='completed',finished=fe.mi.now(),resultSummary={k:result[k] for k in ('execution','devices','timing','peakProcessRSSBytes','checkpointSha256','limitations')})
  s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('completed',json.dumps(data),fe.mi.now(),id));s.db.commit()
 except Exception as error:
  s.db.rollback()
  if s.job(id)['state']!='cancelled':s.job_update(id,'failed',{'error':str(error),'finished':fe.mi.now()})
  print('ProteinMPNN error:',error,flush=True)

def dispatch(s,action,p):
 if action=='mpnn_start':return start(s,p)
 s.project(p['projectId']);return [s.job(r['id']) for r in s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='proteinmpnn' ORDER BY created DESC",(p['projectId'],))]
