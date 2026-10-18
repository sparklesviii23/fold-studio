"""RDKit preparation through the common library, compute lock, jobs and exports."""
import hashlib,json,math,os,pathlib,subprocess
import fold_engine as fe
ACTIONS={'ligand_start','ligand_jobs','ligand_export'}

def start(s,p):
 if set(p)-{'projectId','name','smiles','seed','conformers'}:raise ValueError('Unsupported ligand preparation field.')
 s.project(p['projectId']);name=p.get('name','Prepared ligand');smiles=p.get('smiles')
 if not isinstance(name,str) or not name.strip() or len(name)>160 or any(ord(c)<32 for c in name):raise ValueError('Enter a ligand name of 1–160 characters without control characters.')
 if not isinstance(smiles,str) or not smiles.strip() or len(smiles)>4096 or any(c.isspace() for c in smiles.strip()):raise ValueError('Enter one connected isomeric SMILES string without a trailing name or annotations.')
 seed=fe.integer(p.get('seed',42),'Seed',0,2147483647);conformers=fe.integer(p.get('conformers',3),'Conformers',1,8)
 python=os.path.abspath(os.path.expanduser(s.engine_python()));runner=pathlib.Path(__file__).with_name('ligand_runner.py')
 if not pathlib.Path(python).is_file():raise ValueError('The local scientific runtime is unavailable. Check Local Compute.')
 request={'name':name.strip(),'smiles':smiles.strip(),'seed':seed,'conformers':conformers};request_sha=fe.checksum(fe.canonical(request).encode())
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Another local compute job is active. Wait for it to finish or cancel it before preparing a ligand.')
 job=s.job_new({'projectId':p['projectId'],'name':name.strip(),'request':request,'requestSha256':request_sha,'runnerSha256':fe.checksum(runner.read_bytes()),'runtime':python,'outputs':[]},'rdkit','queued');folder=s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True)
 try:
  (folder/'request.json').write_text(fe.canonical(request));return s.spawn(job,'--ligand-job')
 except Exception as error:s.job_update(job['id'],'failed',{'error':str(error)});raise

def run(s,id):
 job=s.job(id);data=job['data'];folder=s.root/'jobs'/id;created=[];committed=False
 if job['engine']!='rdkit' or job['state'] not in ('queued','running'):raise ValueError('Ligand job cannot execute in this state.')
 try:
  s.job_update(id,'running',{'started':fe.mi.now(),'stage':'conformer_preparation'})
  runner=pathlib.Path(__file__).with_name('ligand_runner.py');request=folder/'request.json'
  if fe.checksum(runner.read_bytes())!=data['runnerSha256'] or fe.checksum(request.read_bytes())!=data['requestSha256']:raise ValueError('Ligand runner or saved input changed after queueing.')
  result=subprocess.run([data['runtime'],'-I','-B',str(runner),str(request)],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','OMP_NUM_THREADS':'1'},timeout=120)
  if result.returncode:raise ValueError('RDKit could not prepare this molecule. Review the actual execution log for stereochemistry, connectivity or force-field errors.')
  if s.job(id)['state']=='cancelled':return
  prepared=json.loads((folder/'result.json').read_text())
  if prepared['requestSha256']!=data['requestSha256'] or fe.checksum(request.read_bytes())!=data['requestSha256'] or prepared['runnerSha256']!=data['runnerSha256']:raise ValueError('Ligand execution receipt differs from its saved inputs.')
  if prepared['state']!='prepared_conformer' or not math.isfinite(prepared['energyKcalMol']):raise ValueError('Ligand preparation produced no finite converged conformer.')
  raw={name:(folder/name).read_bytes() for name in ('ligand.cif','ligand.sdf')}
  if any(fe.checksum(value)!=prepared['artifacts'][name] for name,value in raw.items()):raise ValueError('Ligand output checksum changed.')
  st=fe.mi.parse_structure(raw['ligand.cif'].decode(),'mmcif')
  if len(st['atoms'])!=len(prepared['atoms']) or any(r['polymer'] for r in st['residues']):raise ValueError('Ligand coordinate transport differs from its explicit nonprotein graph.')
  for atom,expected in zip(st['atoms'],prepared['atoms'],strict=True):
   if atom['name']!=expected['name'] or atom['element']!=expected['element'].upper() or atom['xyz']!=expected['xyz']:raise ValueError('Ligand atom correspondence changed during transport.')
  asset=fe.mi.uid()+'.cif';sdf_asset=fe.mi.uid()+'.sdf'
  for key,name in (('ligand.cif',asset),('ligand.sdf',sdf_asset)):
   path=s.root/'assets'/name;path.write_bytes(raw[key]);created.append(path)
  date=fe.mi.now();rid=fe.mi.uid();info={'asset':asset,'format':'mmcif','sha256':prepared['artifacts']['ligand.cif'],'source':'RDKit ETKDGv3 + MMFF94s prepared ligand','confidenceKind':None,'metadata':{'jobId':id,'ligand':{**prepared,'sdfAsset':sdf_asset,'sdfSha256':prepared['artifacts']['ligand.sdf'],'classification':'Generated molecular-mechanics conformer; biological activity unvalidated'}},'imported':date}
  s.db.execute('BEGIN IMMEDIATE')
  if s.job(id)['state']=='cancelled':s.db.rollback();return
  s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(rid,job['project_id'],'structure',job['name'],json.dumps(info),date));s.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,job['project_id']))
  current=s.job(id)['data'];current.update(outputs=[rid],finished=date,stage='completed',resultSummary={key:prepared[key] for key in ('canonicalIsomericSmiles','formula','molecularWeightDa','formalCharge','energyKcalMol','method','conformers','runtime','seconds','limitations')});s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('completed',json.dumps(current),date,id));s.db.commit();committed=True
 except Exception as error:
  s.db.rollback()
  if s.job(id)['state']!='cancelled':s.job_update(id,'failed',{'error':str(error),'finished':fe.mi.now()})
  print('Ligand preparation error:',error,flush=True)
 finally:
  if not committed:
   for path in created:path.unlink(missing_ok=True)

def dispatch(s,action,p):
 if action=='ligand_start':return start(s,p)
 if action=='ligand_export':
  if set(p)-{'projectId','structureId','path'}:raise ValueError('Unsupported ligand export field.')
  record,_=fe.Engine(s).lab.record(p['structureId'])
  if record['project_id']!=p['projectId']:raise ValueError('Choose a ligand in this project.')
  meta=record['data'].get('metadata',{}).get('ligand',{});asset=meta.get('sdfAsset','')
  if not asset or pathlib.Path(asset).name!=asset:raise ValueError('This structure has no prepared ligand SDF.')
  file=s.root/'assets'/asset
  if file.is_symlink() or not file.is_file() or fe.checksum(file.read_bytes())!=meta['sdfSha256']:raise ValueError('Saved ligand SDF checksum changed; export refused.')
  return s.export_file({'path':p['path'],'asset':asset})
 s.project(p['projectId']);return [s.job(row['id']) for row in s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='rdkit' ORDER BY created DESC",(p['projectId'],))]
