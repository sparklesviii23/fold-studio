"""OpenMM short protein pilot through the common compute queue and library."""
import json,math,os,pathlib,re,subprocess
import fold_engine as fe
from coordinate_ensemble import inspect as inspect_ensemble
ACTIONS={'dynamics_start','dynamics_jobs','dynamics_status','dynamics_analyze'}
def runtime(s):
 bundled=fe.BASE/'runtime-openmm/bin/python3.12'
 return os.path.abspath(os.path.expanduser(os.environ.get('FOLD_OPENMM_PYTHON') or s.setting('openmmPython') or str(bundled if bundled.is_file() else s.root/'engine/openmm/bin/python')))
def start(s,p):
 if set(p)-{'projectId','structureId','name','seed','steps','reportInterval'}:raise ValueError('Unsupported dynamics field.')
 engine=fe.Engine(s);shared=engine.fold_structure(p);record,path=engine.lab.record(p['structureId']);raw=list(fe.mi.atom_rows(path.read_text(),record['data']['format']));st=shared['structure'];name=p.get('name','Protein pilot · '+record['name'])
 if not isinstance(name,str) or not name.strip() or len(name)>200 or any(ord(c)<32 for c in name):raise ValueError('Enter a pilot name of 1–200 characters without control characters.')
 if len(st['models'])!=1 or any(a['alt'] or a['occupancy']<=0 for a in raw):raise ValueError('Choose one resolved coordinate model without alternate or zero-occupancy atoms.')
 if not 1<=len(st['residues'])<=64 or any(a['resname'] not in fe.mi.CODES or a['element'] not in ('H','C','N','O','S') for a in raw):raise ValueError('Initial OpenMM pilots support 1–64 canonical protein residues without ligands, water or ions.')
 if any(not re.fullmatch('[A-Za-z0-9]',r['chain']) or not 1<=r['num']<=9999 or len(r['ins'])>1 for r in st['residues']):raise ValueError('Pilot PDB interchange requires one-character chain IDs and positive residue numbers below 10,000.')
 for chain in st['chains']:
  residues=[r for r in st['residues'] if r['chain']==chain['id']];previous=None
  for residue in residues:
   atoms={st['atoms'][i]['name']:st['atoms'][i] for i in residue['atoms']}
   if not {'N','CA','C','O'}.issubset(atoms):raise ValueError('Each protein residue needs a complete observed N/CA/C/O backbone; missing heavy atoms are not repaired.')
   if previous and (residue['num']!=previous[0]+1 or math.dist(previous[1],atoms['N']['xyz'])>2.):raise ValueError('Resolve sequence gaps or broken backbone geometry before preparing a pilot.')
   previous=(residue['num'],atoms['C']['xyz'])
 values={key:fe.integer(p.get(key,default),key,lo,hi) for key,default,lo,hi in [('seed',42,1,2147483647),('steps',1000,10,5000),('reportInterval',100,1,5000)]}
 if values['steps']%values['reportInterval'] or values['steps']//values['reportInterval']>100:raise ValueError('The reporting interval must divide steps, with at most 100 saved intervals.')
 python=runtime(s)
 if not pathlib.Path(python).is_file():raise ValueError('The OpenMM scientific runtime is unavailable. Check Local Compute.')
 runner=pathlib.Path(__file__).with_name('dynamics_runner.py');request={**values,'format':record['data']['format'],'inputSha256':record['data']['sha256']};request_text=fe.canonical(request)
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Another local compute job is active.')
 job=s.job_new({'projectId':p['projectId'],'name':name.strip(),'source':shared['reference'],'runtime':python,'request':request,'requestSha256':fe.checksum(request_text.encode()),'runnerSha256':fe.checksum(runner.read_bytes()),'outputs':[]},'openmm','queued');folder=s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True)
 try:
  source=path.read_bytes()
  if fe.checksum(source)!=request['inputSha256']:raise ValueError('Dynamics source changed while queueing.')
  (folder/('input.pdb' if request['format']=='pdb' else 'input.cif')).write_bytes(source);(folder/'request.json').write_text(request_text);return s.spawn(job,'--dynamics-job')
 except Exception as error:s.job_update(job['id'],'failed',{'error':str(error)});raise
def run(s,id):
 job=s.job(id);data=job['data'];folder=s.root/'jobs'/id;created=[];committed=False
 if job['engine']!='openmm' or job['state'] not in ('queued','running'):raise ValueError('Dynamics job cannot execute in this state.')
 try:
  s.job_update(id,'running',{'started':fe.mi.now(),'stage':'system_preparation'});runner=pathlib.Path(__file__).with_name('dynamics_runner.py');request=folder/'request.json'
  if fe.checksum(runner.read_bytes())!=data['runnerSha256'] or fe.checksum(request.read_bytes())!=data['requestSha256']:raise ValueError('Dynamics runner or saved input changed after queueing.')
  proc=subprocess.run([data['runtime'],'-I','-B',str(runner),str(request)],env={**os.environ,'OPENMM_CPU_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'},timeout=1800)
  if proc.returncode:raise ValueError('OpenMM could not complete this pilot. Review the execution log for force-field templates, missing atoms or numerical errors.')
  if s.job(id)['state']=='cancelled':return
  receipt=json.loads((folder/'result.json').read_text())
  if receipt['state']!='completed_pilot' or receipt['requestSha256']!=data['requestSha256'] or receipt['runnerSha256']!=data['runnerSha256'] or receipt['inputSha256']!=data['source']['sha256']:raise ValueError('Dynamics execution receipt differs from queued inputs.')
  if fe.checksum(request.read_bytes())!=data['requestSha256'] or fe.checksum(runner.read_bytes())!=data['runnerSha256']:raise ValueError('Dynamics inputs changed during execution.')
  expected={'prepared.pdb','minimized.pdb','trajectory.pdb','system.xml','integrator.xml','final-state.xml','checkpoint.chk'}
  if set(receipt['artifacts'])!=expected or any(fe.checksum((folder/name).read_bytes())!=sha for name,sha in receipt['artifacts'].items()):raise ValueError('Dynamics artifact checksum changed.')
  if len(receipt['series'])!=data['request']['steps']//data['request']['reportInterval']+1 or abs(receipt['durationPs']-data['request']['steps']*.001)>1e-7:raise ValueError('Dynamics frame count or physical duration differs from the saved request.')
  if any(not all(math.isfinite(row[key]) for key in ('timePs','potentialKjMol','kineticKjMol','forceRmsKjMolNm')) for row in receipt['series']):raise ValueError('Dynamics returned nonfinite state.')
  records=[];date=fe.mi.now()
  for name,label in [('trajectory.pdb','Short implicit-solvent trajectory'),('prepared.pdb','Prepared hydrogen model'),('minimized.pdb','Locally minimized model')]:
   raw=(folder/name).read_bytes();st=fe.mi.parse_structure(raw.decode(),'pdb')
   if len(st['atoms'])!=receipt['atoms']:raise ValueError('Dynamics coordinate atom count differs from the prepared system.')
   metadata={'jobId':id,'derivedFrom':data['source'],'dynamics':{'artifact':name,'receipt':receipt,'classification':'Short computational pilot; equilibrium and biological behavior unvalidated'}}
   if name=='trajectory.pdb':
    metadata['coordinateEnsemble']=inspect_ensemble(raw)
    if metadata['coordinateEnsemble']['frameIds']!=[row['frameId'] for row in receipt['series']]:raise ValueError('Trajectory MODEL identifiers differ from saved physical-time mapping.')
   asset=fe.mi.uid()+'.pdb';path=s.root/'assets'/asset;path.write_bytes(raw);created.append(path);rid=fe.mi.uid();info={'asset':asset,'format':'pdb','sha256':receipt['artifacts'][name],'source':'OpenMM 8.6.1 · Amber ff14SB / OBC2 · '+label,'confidenceKind':None,'metadata':metadata,'imported':date};records.append((rid,job['project_id'],'structure',job['name']+' · '+label,json.dumps(info),date))
  s.db.execute('BEGIN IMMEDIATE')
  if s.job(id)['state']=='cancelled':s.db.rollback();return
  s.db.executemany('INSERT INTO records VALUES(?,?,?,?,?,?)',records);s.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,job['project_id']));current=s.job(id)['data'];current.update(outputs=[r[0] for r in records],stage='completed',finished=date,resultSummary={'atoms':receipt['atoms'],'residues':receipt['residues'],'frames':len(receipt['series']),'durationPs':receipt['durationPs'],'method':receipt['method'],'runtime':receipt['runtime'],'limitations':receipt['limitations']});s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('completed',json.dumps(current),date,id));s.db.commit();committed=True
 except Exception as error:
  s.db.rollback()
  if s.job(id)['state']!='cancelled':s.job_update(id,'failed',{'error':str(error),'finished':fe.mi.now()})
  print('OpenMM pilot error:',error,flush=True)
 finally:
  if not committed:
   for path in created:path.unlink(missing_ok=True)
def dispatch(s,action,p):
 if action=='dynamics_start':return start(s,p)
 if action=='dynamics_analyze':
  from trajectory_analysis import analyze
  return analyze(s,p)
 if action=='dynamics_status':
  if p:raise ValueError('Runtime inspection takes no input fields.')
  python=runtime(s);result={'state':'unavailable','python':python,'backend':'CPU','scope':'Short implicit-solvent protein pilot; no Metal backend'}
  if not pathlib.Path(python).is_file():return result
  try:
   probe=subprocess.run([python,'-I','-B','-c','import openmm,json,platform;print(json.dumps({"version":openmm.__version__,"architecture":platform.machine(),"platforms":[openmm.Platform.getPlatform(i).getName() for i in range(openmm.Platform.getNumPlatforms())]}))'],capture_output=True,text=True,timeout=30)
   if probe.returncode:raise ValueError(probe.stderr[-2000:])
   result.update(json.loads(probe.stdout.strip().splitlines()[-1]));result['state']='available' if result['version']=='8.6.1' and 'CPU' in result['platforms'] else 'incompatible'
  except Exception as error:result['error']=str(error)
  return result
 s.project(p['projectId']);return [s.job(r['id']) for r in s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='openmm' ORDER BY created DESC",(p['projectId'],))]
