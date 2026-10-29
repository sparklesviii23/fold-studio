"""Bounded local PySCF molecular electronic structure, stored as research evidence."""
import collections,uuid,datetime,signal,fcntl,hashlib,json,math,os,pathlib,subprocess,sys
ACTIONS={'quantum_status','quantum_list','quantum_jobs','quantum_calculate','quantum_reaction','quantum_reactions'}
ELEMENTS={symbol:i for i,symbol in enumerate(('H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S','Cl','Ar'),1)}
VERSION='pyscf-small-molecule-v1'
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def validate(p):
 if set(p)-{'projectId','name','xyz','unit','method','basis','charge','spin','gradients','densityGrid'}:raise ValueError('Unsupported quantum calculation field.')
 text=p.get('xyz');unit=p.get('unit');method=p.get('method');basis=p.get('basis');charge=p.get('charge');spin=p.get('spin');gradients=p.get('gradients',False);density_grid=p.get('densityGrid',False)
 if not isinstance(text,str) or len(text.encode())>20000:raise ValueError('Supply a bounded XYZ molecule, including atom-count and comment lines.')
 lines=text.strip().splitlines()
 if not lines or not lines[0].strip().isdigit():raise ValueError('XYZ requires its atom-count header and comment line.')
 count=int(lines[0].strip())
 if not 1<=count<=24 or len(lines)!=count+2:raise ValueError('Supply exactly 1–24 XYZ atoms, with one comment line.')
 atoms=[]
 for line in lines[2:]:
  cells=line.split()
  if len(cells)!=4 or cells[0] not in ELEMENTS:raise ValueError('XYZ supports explicit H–Ar symbols and three coordinates per atom.')
  xyz=[float(v) for v in cells[1:]]
  if any(not math.isfinite(v) or abs(v)>10000 for v in xyz):raise ValueError('Coordinates must be finite and within the bounded molecular range.')
  atoms.append([cells[0],xyz])
 if any(sum((a-b)**2 for a,b in zip(x[1],y[1]))<1e-6 for i,x in enumerate(atoms) for y in atoms[i+1:]):raise ValueError('Coincident/nearly coincident nuclei are not supported.')
 if unit not in ('Angstrom','Bohr') or method not in ('HF','PBE') or basis not in ('sto-3g','6-31g'):raise ValueError('Choose explicit Angstrom/Bohr coordinates, HF/PBE and STO-3G/6-31G.')
 if type(charge)is not int or not -4<=charge<=4 or type(spin)is not int or type(gradients)is not bool or type(density_grid)is not bool:raise ValueError('Supply integer charge −4…4, explicit alpha-minus-beta electron spin and a gradient checkbox.')
 electrons=sum(ELEMENTS[a[0]] for a in atoms)-charge
 if not 1<=electrons<=80 or not 0<=spin<=electrons or (electrons-spin)%2:raise ValueError('Electron count/spin parity is inconsistent or exceeds the 80-electron bound.')
 return {'atoms':atoms,'originalXYZ':text,'unit':unit,'method':method,'basis':basis,'charge':charge,'spin':spin,'gradients':gradients,'densityGrid':density_grid,'densityGridPointsPerAxis':24,'densityMarginBohr':3.0,'electrons':electrons,'maximumAOs':96,'maximumCycles':80,'convToleranceHartree':1e-9,'memorySettingMB':1024,'requestedThreads':2,'PBEGridLevel':2,'algorithm':VERSION}
def run(s,request,job_id=None):
 env={**os.environ,'PYSCF_CONFIG_FILE':'/dev/null','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','VECLIB_MAXIMUM_THREADS':'2'}
 command=[s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())]+(['--job-id',job_id] if job_id else [])
 process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
 if job_id:s.job_metadata(job_id,{'pid':process.pid,'workerPath':str(pathlib.Path(__file__).resolve())})
 try:stdout,stderr=process.communicate(canonical(request),timeout=120 if request.get('mode')!='status' else 30)
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGKILL);process.communicate();raise ValueError('Local quantum calculation exceeded its recorded time limit; the worker was stopped.') from None
 if process.returncode:raise ValueError('Local quantum runtime stopped: '+stderr.strip()[-2000:])
 result=json.loads(stdout)
 if stderr.strip():result['runtimeWarnings']=stderr.strip()[-4000:]
 return result
def manifest():return json.loads((pathlib.Path(__file__).resolve().parents[1]/'vendor/quantum-runtime.json').read_text())
def dispatch(s,action,p):
 s.project(p['projectId'])
 if action=='quantum_reaction':return reaction(s,p)
 if action=='quantum_reactions':return [{**row,'data':json.loads(row['data'])} for row in s.rows("SELECT id,name,created,data FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='quantum_reaction' ORDER BY created DESC",(p['projectId'],))]
 if action=='quantum_list':return [{'id':row['id'],'name':row['name'],'created':row['created'],'data':json.loads(row['data'])} for row in s.rows("SELECT id,name,created,data FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='quantum_calculation' ORDER BY created DESC",(p['projectId'],))]
 if action=='quantum_jobs':return [{**row,'data':json.loads(row['data'])} for row in s.rows("SELECT * FROM jobs WHERE project_id=? AND engine='pyscf' ORDER BY created DESC LIMIT 20",(p['projectId'],))]
 if action=='quantum_status':
  try:result=run(s,{'mode':'status'})
  except Exception as error:return {'available':False,'error':str(error),'scope':'No molecular calculation started.'}
  expected={**manifest()['requiredExisting'],**{r['package']:r['version'] for r in manifest()['packages']}};result['pinnedRuntime']=result.get('versions')==expected and result.get('architecture')=='arm64'
  import execution_policy
  result['executionMode']=execution_policy.selected(s)['mode'];return result
 request=validate(p);implementation=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
 with (s.root/'cache'/'quantum-calculation.lock').open('a') as lease:
  try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('One local quantum calculation is already running in this Library; wait for its result.') from None
  status=dispatch(s,'quantum_status',{'projectId':p['projectId']})
  if not status.get('available') or not status.get('pinnedRuntime'):raise ValueError('The pinned CPU quantum runtime is unavailable or differs from the qualified dependency versions.')
  identity=hashlib.sha256(canonical({'request':request,'versions':status['versions'],'implementation':implementation}).encode()).hexdigest()
  existing=next((row for row in dispatch(s,'quantum_list',{'projectId':p['projectId']}) if row['data']['inputSha256']==identity and row['data']['result']['converged']),None)
  if existing:return existing
  s.db.execute('BEGIN IMMEDIATE')
  if s.active():s.db.rollback();raise ValueError('Finish the active local scientific job before starting a quantum calculation.')
  name=str(p.get('name','Local molecular electronic structure'))[:200];job=s.job_new({'projectId':p['projectId'],'name':name,'request':request,'inputSha256':identity,'localCPUOnly':True},'pyscf','running')
  try:
   result=run(s,request,job['id']);value={'domain':'quantum_calculation','jobId':job['id'],'inputSha256':identity,'implementationSha256':implementation,'runtimeVersions':status['versions'],'request':request,'result':result,'resultSha256':hashlib.sha256(canonical(result).encode()).hexdigest(),'classification':'Computational electronic structure at the recorded method/basis and supplied geometry; not experimental or biological validation.'}
   s.db.execute('BEGIN IMMEDIATE')
   try:
    if s.job(job['id'])['state']!='running':raise ValueError('Quantum job was cancelled; its unfinished result was not published.')
    record={'id':str(uuid.uuid4()),'project_id':p['projectId'],'kind':'analysis','name':name,'data':value};created=datetime.datetime.now(datetime.timezone.utc).isoformat()
    s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(record['id'],p['projectId'],'analysis',name,canonical(value),created));s.db.execute('UPDATE projects SET updated=? WHERE id=?',(created,p['projectId']))
    s.job_update(job['id'],'completed' if result['converged'] else 'failed',{'recordId':record['id'],'scientificOutcome':result['state']})
   except Exception:s.db.rollback();raise
   return record
  except Exception as error:
   if s.job(job['id'])['state']!='cancelled':s.job_update(job['id'],'failed',{'error':str(error)})
   raise
def reaction(s,p):
 if set(p)-{'projectId','name','terms'}:raise ValueError('Unsupported electronic reaction-energy field.')
 terms=p.get('terms')
 if not isinstance(terms,list) or not 2<=len(terms)<=12:raise ValueError('Supply 2–12 explicit signed integer stoichiometric terms; products positive, reactants negative.')
 records={r['id']:r for r in dispatch(s,'quantum_list',{'projectId':p['projectId']})};selected=[];seen=set();balance=collections.Counter();charge=0;versions=None;model=None
 for term in terms:
  if not isinstance(term,dict) or set(term)!={'recordId','coefficient'} or term.get('recordId') in seen:raise ValueError('Choose distinct saved quantum results with explicit coefficients.')
  seen.add(term.get('recordId'));coefficient=term.get('coefficient')
  if type(coefficient)is not int or not 1<=abs(coefficient)<=12:raise ValueError('Stoichiometric coefficients must be nonzero integers from −12 to 12.')
  record=records.get(term.get('recordId'))
  if not record:raise ValueError('Every quantum term must belong to this project.')
  data=record['data'];request=data['request'];result=data['result']
  if not result.get('converged') or not math.isfinite(result.get('totalEnergyHartree',float('nan'))):raise ValueError('Only converged saved electronic energies can be combined.')
  if hashlib.sha256(canonical(result).encode()).hexdigest()!=data.get('resultSha256'):raise ValueError('A quantum result has no matching integrity receipt. Recalculate it with the current engine before combining energies.')
  signature={key:request[key] for key in ('method','basis','convToleranceHartree','PBEGridLevel')};runtime=data['runtimeVersions']
  if hashlib.sha256(canonical({'request':request,'versions':runtime,'implementation':data['implementationSha256']}).encode()).hexdigest()!=data['inputSha256']:raise ValueError('A source calculation input receipt changed; recompute it before comparing energies.')
  if model is not None and (signature!=model or runtime!=versions):raise ValueError('All terms require the same electronic method, basis, grid/tolerance and pinned runtime versions.')
  model=signature;versions=runtime
  for symbol,_ in request['atoms']:balance[symbol]+=coefficient
  charge+=coefficient*request['charge'];selected.append({'recordId':record['id'],'name':record['name'],'coefficient':coefficient,'totalEnergyHartree':result['totalEnergyHartree'],'resultSha256':data['resultSha256'],'inputSha256':data['inputSha256'],'spinAlphaMinusBeta':request['spin']})
 if not any(r['coefficient']>0 for r in selected) or not any(r['coefficient']<0 for r in selected) or any(balance.values()) or charge:raise ValueError('Reaction requires reactants and products with exactly balanced element counts and net charge; no missing atoms or electrons are supplied implicitly.')
 value={'domain':'quantum_reaction','terms':selected,'method':model,'runtimeVersions':versions,'electronicReactionEnergyHartree':math.fsum(t['coefficient']*t['totalEnergyHartree'] for t in selected),'balance':dict(balance),'netChargeBalance':charge,'algorithm':'signed-balanced-electronic-energy-v1','scope':'Products minus reactants at the separately supplied fixed geometries and recorded method/basis. No geometry relaxation, wavefunction-stability analysis, zero-point/thermal/entropy/solvation terms or basis-set-superposition correction. This is not a reaction free energy, barrier, kinetic prediction, affinity or experimentally validated bond energy. Separate spin states are retained; spin conservation is not certified.'}
 identity=hashlib.sha256(canonical(value).encode()).hexdigest();value['inputSha256']=identity
 existing=next((row for row in dispatch(s,'quantum_reactions',{'projectId':p['projectId']}) if row['data'].get('inputSha256')==identity),None)
 return existing or s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name') or 'Balanced electronic reaction energy')[:200],'data':value})

def calculate(p):
 import numpy as np,pyscf,h5py,scipy,platform
 from pyscf import gto,scf,dft
 if p.get('mode')=='status':return {'available':True,'versions':{'pyscf':pyscf.__version__,'h5py':h5py.__version__,'numpy':np.__version__,'scipy':scipy.__version__},'architecture':platform.machine(),'CPUOnly':True,'trainedModels':False,'scope':'Library availability only; no molecular calculation started.'}
 pyscf.lib.num_threads(p['requestedThreads']);mol=gto.M(atom=p['atoms'],unit=p['unit'],basis=p['basis'],charge=p['charge'],spin=p['spin'],verbose=0,max_memory=p['memorySettingMB']);nao=mol.nao_nr()
 if nao>p['maximumAOs'] or p['gradients'] and nao>64:raise ValueError('This bounded quantum tool supports at most 96 atomic orbitals, or 64 with gradients.')
 if p['method']=='HF':solver=scf.RHF(mol) if p['spin']==0 else scf.UHF(mol)
 else:
  solver=dft.RKS(mol) if p['spin']==0 else dft.UKS(mol);solver.xc='PBE';solver.grids.level=p['PBEGridLevel']
 history=[]
 def iteration(data):
  def finite(key):
   value=data.get(key);return float(value) if value is not None and math.isfinite(float(value)) else None
  history.append({'cycleIndexZeroBased':int(data['cycle']),'energyHartree':finite('e_tot'),'orbitalGradientNorm':finite('norm_gorb'),'densityChangeNorm':finite('norm_ddm')})
 solver.callback=iteration
 solver.chkfile=None;solver.max_cycle=p['maximumCycles'];solver.conv_tol=p['convToleranceHartree'];energy=float(solver.kernel());converged=bool(solver.converged);dm=solver.make_rdm1();density=dm if dm.ndim==2 else dm.sum(axis=0);overlap=mol.intor('int1e_ovlp');trace=float(np.einsum('ij,ji',density,overlap))
 if abs(trace-p['electrons'])>1e-5:raise ValueError('Calculated density does not reproduce the requested electron count.')
 electronic=float(solver.energy_elec()[0]);nuclear=float(mol.energy_nuc())
 if abs(electronic+nuclear-energy)>1e-7:raise ValueError('Electronic/nuclear energy accounting differs from SCF total.')
 channels=[];energies=[solver.mo_energy] if solver.mo_energy.ndim==1 else solver.mo_energy;occupations=[solver.mo_occ] if solver.mo_occ.ndim==1 else solver.mo_occ
 for i,(values,occupied) in enumerate(zip(energies,occupations)):
  occ=values[occupied>1e-8];empty=values[occupied<=1e-8];channels.append({'spin':'restricted' if len(energies)==1 else ('alpha' if i==0 else 'beta'),'energiesHartree':values.tolist(),'occupations':occupied.tolist(),'meanFieldOrbitalGapHartree':float(empty.min()-occ.max()) if len(occ) and len(empty) and converged else None})
 spin_square=float(solver.spin_square()[0]) if converged and p['spin'] else (0.0 if converged else None)
 charges=solver.mulliken_pop(verbose=0)[1].tolist() if converged else None;dipole=solver.dip_moment(unit='Debye',verbose=0).tolist() if converged else None;gradient=solver.nuc_grad_method().kernel().tolist() if converged and p['gradients'] else None
 field=None
 if converged and p['densityGrid']:
  import tempfile
  from pyscf.tools import cubegen
  with tempfile.TemporaryDirectory(prefix='fold-electron-density-') as folder:
   path=pathlib.Path(folder)/'density.cube';n=p['densityGridPointsPerAxis'];cube=cubegen.Cube(mol,n,n,n,resolution=None,margin=p['densityMarginBohr'],origin=None,extent=None);coords=cube.get_coords();rho=np.empty(len(coords))
   for first,last in pyscf.lib.prange(0,len(coords),2000):rho[first:last]=dft.numint.eval_rho(mol,mol.eval_gto('GTOval',coords[first:last]),density)
   rho=rho.reshape(n,n,n)
   if not np.all(np.isfinite(rho)) or float(rho.min()) < -1e-8:raise ValueError('Electron-density grid contains nonfinite or materially negative values.')
   cube.write(rho,str(path),comment='Fold Studio electron density, e/Bohr^3; fixed finite box and grid');raw=path.read_bytes();spacing=np.diag(cube.box)/(n-1);integral=rho
   for step in spacing[::-1]:integral=np.trapezoid(integral,dx=float(step),axis=-1)
   mid=n//2
   field={'kind':'electron_density','unit':'electrons/Bohr^3','dimensions':[n,n,n],'marginBohr':p['densityMarginBohr'],'originBohr':cube.boxorig.tolist(),'axisStepVectorsBohr':(cube.box/(n-1)).tolist(),'minimum':float(rho.min()),'maximum':float(rho.max()),'boxTrapezoidalElectronIntegral':float(integral),'exactDensityOverlapElectronTrace':trace,'cubeText':raw.decode(),'cubeSha256':hashlib.sha256(raw).hexdigest(),'slice':{'zIndex0Based':mid,'zCoordinateBohr':float(cube.boxorig[2]+spacing[2]*mid),'valuesXThenY':rho[:,:,mid].tolist()},'scope':'Finite 24×24×24 sampling of the converged density in a box extending 3 Bohr beyond the nuclei. The trapezoidal box integral is an approximate discretization/truncation diagnostic, not the exact electron trace. Grid/basis convergence, density accuracy, electrostatic potential and measured charge distributions are not certified.'}
 return {'densityField':field,'requestedAlphaMinusBeta':p['spin'],'spinSquareExpectation':spin_square,'converged':converged,'state':'converged_scf' if converged else 'not_converged','totalEnergyHartree':energy if converged else None,'diagnosticLastEnergyHartree':energy,'electronicEnergyHartree':electronic if converged else None,'nuclearRepulsionHartree':nuclear,'densityOverlapElectronTrace':trace,'atomicOrbitals':nao,'electronCount':mol.nelectron,'coordinateUnit':'Angstrom','coordinatesAngstrom':mol.atom_coords(unit='Angstrom').tolist(),'orbitalChannels':channels,'mullikenAtomicCharges':charges,'dipoleDebye':dipole,'gradientHartreePerBohr':gradient,'SCFIterationHistory':history,'iterationHistoryScope':'Actual library callbacks; direct one-electron solutions may emit no iterative history. History is committed with the final result, not a durable checkpoint of an interrupted run.','reportedOpenMPThreads':pyscf.lib.num_threads(),'convergenceEnergyToleranceHartree':p['convToleranceHartree'],'maximumCycles':p['maximumCycles'],'PBEGridLevel':p['PBEGridLevel'] if p['method']=='PBE' else None,'memorySettingMB':p['memorySettingMB'],'completedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'citations':['https://doi.org/10.1063/5.0006074']+(['https://doi.org/10.1016/j.softx.2017.11.002'] if p['method']=='PBE' else []),'scope':'Converged SCF is a stationary mean-field solution at the supplied fixed geometry and finite basis/grid. Open-shell solutions can be spin contaminated; the spin-square expectation is diagnostic. Wavefunction stability, basis/grid convergence, higher correlation, geometry optimization and independent chemical accuracy remain unverified. Orbital eigenvalue gaps and Mulliken charges are model-dependent; no observed spectra, binding, affinity or therapeutic effect is inferred. PySCF memory setting is not an operating-system hard memory limit.'}
if __name__=='__main__':
 import contextlib
 request=json.load(sys.stdin)
 with contextlib.redirect_stdout(sys.stderr):result=calculate(request)
 print(canonical(result))
