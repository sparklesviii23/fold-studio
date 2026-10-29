"""Bounded, explicit single-species periodic Lennard-Jones model in OpenMM."""
import datetime,hashlib,json,math,os,pathlib,signal,subprocess,sys,uuid
ACTIONS={'periodic_lj_status','periodic_lj_run','periodic_lj_results','periodic_lj_jobs'}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def validate(p):
 if set(p)-{'projectId','name','positionsNm','boxLengthsNm','sigmaNm','epsilonKJMol','massDalton','cutoffNm','temperatureK','frictionPerPs','stepPs','steps','seed','reportInterval'}:raise ValueError('Unsupported periodic model field.')
 positions=p.get('positionsNm');box=p.get('boxLengthsNm')
 if not isinstance(positions,list) or not 2<=len(positions)<=64 or any(not isinstance(v,list) or len(v)!=3 for v in positions) or not isinstance(box,list) or len(box)!=3:raise ValueError('Supply 2–64 explicit XYZ positions and three orthorhombic box lengths in nanometres.')
 def number(v,lo,hi):return type(v)in(int,float) and math.isfinite(v) and lo<=v<=hi
 if any(not number(v,1,10) for v in box) or any(not number(v,0,box[i]) or v==box[i] for a in positions for i,v in enumerate(a)):raise ValueError('Box lengths must be 1–10 nm, with every initial particle inside [0,L).')
 bounds={'sigmaNm':(.1,1),'epsilonKJMol':(.01,10),'massDalton':(1,250),'cutoffNm':(.2,4),'temperatureK':(0,1000),'frictionPerPs':(.1,10),'stepPs':(.0001,.002)}
 if any(not number(p.get(k),*b) for k,b in bounds.items()):raise ValueError('Supply finite explicit model parameters in their labelled bounded units.')
 for key,lo,hi in [('steps',0,2000),('seed',1,2147483647),('reportInterval',1,2000)]:
  if type(p.get(key))is not int or not lo<=p[key]<=hi:raise ValueError('Invalid integer periodic model '+key+'.')
 if p['steps']%p['reportInterval'] or p['steps']//p['reportInterval']>100:raise ValueError('Reporting interval must divide steps, with at most 100 saved intervals.')
 if not 1.1*p['sigmaNm']<p['cutoffNm']<.5*min(box):raise ValueError('Cutoff must exceed 1.1 sigma and be strictly below half every box length.')
 for i,a in enumerate(positions):
  for b in positions[i+1:]:
   distance=math.sqrt(sum((d-round(d/L)*L)**2 for d,L in zip((x-y for x,y in zip(a,b)),box)))
   if distance<.75*p['sigmaNm']:raise ValueError('Initial minimum-image separation below 0.75 sigma is rejected; particles are not repaired or minimized implicitly.')
 return {k:v for k,v in p.items() if k not in ('projectId','name')}
def run(s,request,job=None):
 import dynamics
 process=subprocess.Popen([dynamics.runtime(s),'-I','-B',str(pathlib.Path(__file__).resolve())]+(['--job-id',job['id']] if job else []),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={**os.environ,'OPENMM_CPU_THREADS':'1','OMP_NUM_THREADS':'1'})
 if job:s.job_metadata(job['id'],{'pid':process.pid,'workerPath':str(pathlib.Path(__file__).resolve())})
 try:stdout,stderr=process.communicate(canonical(request),timeout=120)
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGKILL);process.communicate();raise ValueError('Periodic model exceeded 120 seconds; owned worker stopped.') from None
 if process.returncode:raise ValueError('OpenMM periodic model stopped: '+stderr[-1500:].strip())
 return json.loads(stdout)
def dispatch(s,action,p):
 s.project(p['projectId'])
 if action=='periodic_lj_status':
  try:return run(s,{'mode':'status'})
  except Exception as error:return {'available':False,'error':str(error)}
 if action=='periodic_lj_results':return [{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='periodic_lj' ORDER BY created DESC",(p['projectId'],))]
 if action=='periodic_lj_jobs':return [{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM jobs WHERE project_id=? AND engine='periodic_lj' ORDER BY created DESC LIMIT 20",(p['projectId'],))]
 request=validate(p);source_sha=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();identity=hashlib.sha256(canonical({'request':request,'implementationSha256':source_sha,'openmm':'8.6.1','platform':'CPU'}).encode()).hexdigest()
 existing=next((r for r in dispatch(s,'periodic_lj_results',{'projectId':p['projectId']}) if r['data']['inputSha256']==identity),None)
 if existing:return existing
 s.db.execute('BEGIN IMMEDIATE')
 if s.active():s.db.rollback();raise ValueError('Finish the active local scientific job before running a periodic model.')
 name=str(p.get('name') or 'Explicit periodic Lennard-Jones model')[:200];job=s.job_new({'projectId':p['projectId'],'name':name,'request':request,'inputSha256':identity},'periodic_lj','running')
 try:
  result=run(s,request,job);data={'domain':'periodic_lj','request':request,'result':result,'inputSha256':identity,'implementationSha256':source_sha,'resultSha256':hashlib.sha256(canonical(result).encode()).hexdigest(),'jobId':job['id']};s.db.execute('BEGIN IMMEDIATE')
  if s.job(job['id'])['state']!='running':raise ValueError('Periodic model cancelled; no result record published.')
  record={'id':str(uuid.uuid4()),'project_id':p['projectId'],'kind':'analysis','name':name,'data':data};date=datetime.datetime.now(datetime.timezone.utc).isoformat();s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(record['id'],p['projectId'],'analysis',name,canonical(data),date));s.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,p['projectId']));s.job_update(job['id'],'completed',{'recordId':record['id']});return record
 except Exception as error:
  s.db.rollback()
  if s.job(job['id'])['state']!='cancelled':s.job_update(job['id'],'failed',{'error':str(error)})
  raise
def calculate(p):
 import openmm as mm
 from openmm import unit
 if mm.__version__!='8.6.1':raise ValueError('The qualified OpenMM 8.6.1 runtime is required.')
 if p.get('mode')=='status':return {'available':True,'openmm':mm.__version__,'platform':'CPU','scope':'Explicit bounded Lennard-Jones model only; no general materials force-field qualification.'}
 system=mm.System();force=mm.CustomNonbondedForce('4*epsilon*((sigma/r)^12-(sigma/r)^6)');force.addGlobalParameter('epsilon',p['epsilonKJMol']);force.addGlobalParameter('sigma',p['sigmaNm']);force.setNonbondedMethod(force.CutoffPeriodic);force.setCutoffDistance(p['cutoffNm']);force.setUseSwitchingFunction(True);force.setSwitchingDistance(.9*p['cutoffNm']);force.setUseLongRangeCorrection(False)
 for _ in p['positionsNm']:system.addParticle(p['massDalton']);force.addParticle([])
 system.addForce(force);system.addForce(mm.CMMotionRemover(1));a,b,c=p['boxLengthsNm'];system.setDefaultPeriodicBoxVectors(mm.Vec3(a,0,0),mm.Vec3(0,b,0),mm.Vec3(0,0,c));integrator=mm.LangevinMiddleIntegrator(p['temperatureK'],p['frictionPerPs'],p['stepPs']);integrator.setRandomNumberSeed(p['seed']);context=mm.Context(system,integrator,mm.Platform.getPlatformByName('CPU'),{'Threads':'1'});context.setPositions(p['positionsNm']);context.setVelocitiesToTemperature(p['temperatureK'],p['seed']);frames=[];initial_forces=None;dof=3*len(p['positionsNm'])-3
 for step in range(0,p['steps']+1,p['reportInterval']):
  if step:integrator.step(p['reportInterval'])
  state=context.getState(getPositions=True,getEnergy=True,getForces=True,enforcePeriodicBox=False);potential=state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole);kinetic=state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole);positions=state.getPositions(asNumpy=True).value_in_unit(unit.nanometer).tolist();forces=state.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometer).tolist()
  if any(not math.isfinite(x) for row in positions+forces for x in row) or not math.isfinite(potential+kinetic):raise ValueError('Periodic model produced nonfinite coordinates, forces or energies; result withheld.')
  if initial_forces is None:initial_forces=forces
  frames.append({'step':step,'timePs':float(state.getTime().value_in_unit(unit.picosecond)),'potentialKJMol':potential,'kineticKJMol':kinetic,'positionsNm':positions})
 return {'state':'fixed_geometry_energy' if p['steps']==0 else 'bounded_trajectory_completed','openmmVersion':mm.__version__,'platform':'CPU','threads':1,'boundaryConditions':'Orthorhombic 3D periodic, minimum-image cutoff','potential':'4 epsilon [(sigma/r)^12 − (sigma/r)^6], OpenMM quintic switching from 0.9 cutoff to cutoff; no long-range correction','integrator':'LangevinMiddle; centre-of-mass velocity removed every step','initialForcesKJMolPerNm':initial_forces,'frames':frames,'degreesOfFreedomAfterCOMRemoval':dof,'reproducibility':'Explicit seed, parameters, original coordinates and OpenMM version retained. Same seed does not certify bitwise trajectories across hardware or future runtimes.','scope':'User-defined single-species spherical-particle model and short nonequilibrium trajectory. No chemical bonds, electrostatics, quantum effects, parameter fitting, structural optimization, equilibrated material properties, phase stability or real-material predictive accuracy are inferred. Initial positions remain in the request; saved trajectory positions are unwrapped Cartesian coordinates in nm. No thermalization or energy-conservation certification.'}
if __name__=='__main__':print(canonical(calculate(json.load(sys.stdin))))
