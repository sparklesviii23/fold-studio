"""Bounded original OpenMM protein pilot: explicit implicit-solvent assumptions.

Runs only in the isolated, pinned scientific runtime. Source coordinates remain
immutable; prepared/minimized/trajectory outputs are distinct artifacts.
"""
import hashlib,json,math,os,pathlib,platform,random,subprocess,sys,time
sys.dont_write_bytecode=True
os.environ['OPENMM_CPU_THREADS']='1'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def checkpoint_host():
 host={'system':platform.system(),'architecture':platform.machine(),'osRelease':platform.release()}
 if host['system']=='Darwin':
  host['hardwareModel']=subprocess.check_output(['/usr/sbin/sysctl','-n','hw.model'],text=True).strip()
  host['cpu']=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
 return host
def atom_identity(atom):
 residue=atom.residue
 # PDB uses a blank column for no insertion code; PDBxFile uses an empty string.
 return (residue.chain.id,residue.id,(residue.insertionCode or '').strip(),atom.name)
def run(request_path):
 import numpy as np
 import openmm as mm
 from openmm import app,unit
 if mm.__version__!='8.6.1':raise ValueError('This workflow requires pinned OpenMM 8.6.1.')
 request_path=pathlib.Path(request_path).absolute();folder=request_path.parent;request=json.loads(request_path.read_text());fmt=request.get('format','pdb');started=time.monotonic()
 if request.get('mode')=='continue':return continue_run(request_path,request)
 if fmt not in ('pdb','mmcif'):raise ValueError('Unsupported dynamics source format.')
 source=folder/('input.pdb' if fmt=='pdb' else 'input.cif')
 if sha(source)!=request['inputSha256']:raise ValueError('Dynamics input checksum changed.')
 for name,lo,hi in [('seed',1,2147483647),('steps',10,5000),('reportInterval',1,5000)]:
  value=request[name]
  if type(value) is not int or not lo<=value<=hi:raise ValueError('Invalid '+name+'.')
 if request['steps']%request['reportInterval'] or request['steps']//request['reportInterval']>100:raise ValueError('Choose an interval that divides the step count, with at most 100 saved intervals.')
 random.seed(request['seed']);np.random.seed(request['seed'])
 pdb=(app.PDBFile if fmt=='pdb' else app.PDBxFile)(str(source));residues=list(pdb.topology.residues());canonical={'ALA','ARG','ASN','ASP','CYS','GLN','GLU','GLY','HIS','ILE','LEU','LYS','MET','PHE','PRO','SER','THR','TRP','TYR','VAL'}
 if not 1<=len(residues)<=64 or any(r.name not in canonical for r in residues):raise ValueError('The initial pilot supports 1–64 canonical protein residues without ligands, water or ions.')
 if any(not a.element or a.element.symbol not in ('H','C','N','O','S') for a in pdb.topology.atoms()):raise ValueError('Unsupported protein element.')
 identity=atom_identity
 heavy={identity(a):np.asarray(pdb.positions[a.index].value_in_unit(unit.nanometer)) for a in pdb.topology.atoms() if a.element!=app.element.hydrogen}
 if len(heavy)!=sum(a.element!=app.element.hydrogen for a in pdb.topology.atoms()):raise ValueError('Protein atom identities are ambiguous.')
 xmls=['amber14/protein.ff14SB.xml','implicit/obc2.xml'];forcefield=app.ForceField(*xmls);modeller=app.Modeller(pdb.topology,pdb.positions);modeller.topology.setPeriodicBoxVectors(None);platform=mm.Platform.getPlatformByName('CPU')
 # The standard OpenMM selection is explicitly fixed at pH 7. Existing heavy
 # atoms are not reconstructed, capped, titrated by another method or repaired.
 variants=modeller.addHydrogens(forcefield,pH=7.,platform=platform)
 prepared=np.asarray(modeller.positions.value_in_unit(unit.nanometer));matched={identity(a):prepared[a.index] for a in modeller.topology.atoms() if a.element!=app.element.hydrogen}
 if heavy.keys()!=matched.keys():raise ValueError('Hydrogen preparation changed heavy-atom identity.')
 heavy_error=max(float(np.linalg.norm(matched[key]-point))*10 for key,point in heavy.items())
 if heavy_error>1e-6:raise ValueError('Hydrogen preparation moved original heavy atoms.')
 if modeller.topology.getNumAtoms()>1500:raise ValueError('Prepared pilot system exceeds 1,500 atoms.')
 system=forcefield.createSystem(modeller.topology,nonbondedMethod=app.NoCutoff,constraints=app.HBonds,removeCMMotion=True,soluteDielectric=1.,solventDielectric=78.5)
 integrator=mm.LangevinMiddleIntegrator(300*unit.kelvin,1/unit.picosecond,1*unit.femtosecond);integrator.setRandomNumberSeed(request['seed']);integrator.setConstraintTolerance(1e-6)
 simulation=app.Simulation(modeller.topology,system,integrator,platform,{'Threads':'1','DeterministicForces':'true'});simulation.context.setPositions(modeller.positions)
 def state():
  result=simulation.context.getState(getPositions=True,getVelocities=True,getEnergy=True,getForces=True);positions=result.getPositions(asNumpy=True).value_in_unit(unit.nanometer);energy=float(result.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole));kinetic=float(result.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole));forces=result.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometer)
  if not np.isfinite(positions).all() or not np.isfinite(forces).all() or not all(math.isfinite(v) for v in (energy,kinetic)):raise ValueError('OpenMM produced nonfinite coordinates, energy or forces.')
  return result,{'step':simulation.currentStep,'timePs':float(result.getTime().value_in_unit(unit.picosecond)),'potentialKjMol':energy,'kineticKjMol':kinetic,'forceRmsKjMolNm':float(np.sqrt(np.mean(np.sum(forces*forces,axis=1))))}
 initial,initial_energy=state()
 with open(folder/'prepared.pdb','w') as f:app.PDBFile.writeFile(modeller.topology,modeller.positions,f,keepIds=True)
 transported=app.PDBFile(str(folder/'prepared.pdb'));transported_heavy={identity(a):np.asarray(transported.positions[a.index].value_in_unit(unit.nanometer)) for a in transported.topology.atoms() if a.element!=app.element.hydrogen}
 if transported_heavy.keys()!=heavy.keys():raise ValueError('PDB interchange changed prepared heavy-atom identity.')
 rounding=max(float(np.linalg.norm(transported_heavy[key]-point))*10 for key,point in heavy.items())
 if rounding>.001:raise ValueError('Prepared PDB rounding exceeds 0.001 Å.')
 print('OpenMM: prepared protein; minimizing with original Amber ff14SB / OBC2.',flush=True)
 simulation.minimizeEnergy(tolerance=10*unit.kilojoule_per_mole/unit.nanometer,maxIterations=500);minimized,minimized_energy=state()
 if minimized_energy['potentialKjMol']>initial_energy['potentialKjMol']+1e-5:raise ValueError('Bounded minimization increased potential energy.')
 with open(folder/'minimized.pdb','w') as f:app.PDBFile.writeFile(modeller.topology,minimized.getPositions(),f,keepIds=True)
 simulation.context.setVelocitiesToTemperature(300*unit.kelvin,request['seed']);series=[]
 with open(folder/'trajectory.pdb','w') as f:
  app.PDBFile.writeHeader(modeller.topology,f)
  for index in range(request['steps']//request['reportInterval']+1):
   if index:simulation.step(request['reportInterval'])
   current,values=state();values['frameId']=index+1;series.append(values);app.PDBFile.writeModel(modeller.topology,current.getPositions(),f,modelIndex=index+1,keepIds=True)
   print('OpenMM: saved step '+str(simulation.currentStep)+' / '+str(request['steps']),flush=True)
  app.PDBFile.writeFooter(modeller.topology,f)
 for name,value in [('system.xml',system),('integrator.xml',integrator),('final-state.xml',current)]: (folder/name).write_text(mm.XmlSerializer.serialize(value))
 (folder/'checkpoint.chk').write_bytes(simulation.context.createCheckpoint())
 if sha(source)!=request['inputSha256']:raise ValueError('Original dynamics input changed during execution.')
 data_dir=pathlib.Path(app.__file__).parent/'data';parameters={name:sha(data_dir/name) for name in xmls+['hydrogens.xml','residues.xml'] if (data_dir/name).is_file()}
 names=['prepared.pdb','minimized.pdb','trajectory.pdb','system.xml','integrator.xml','final-state.xml','checkpoint.chk']
 result={'state':'completed_pilot','requestSha256':sha(request_path),'runnerSha256':sha(pathlib.Path(__file__)),'runtime':{'openmm':mm.__version__,'numpy':np.__version__,'platform':'CPU','properties':{'Threads':'1','DeterministicForces':'true'}},'inputSha256':request['inputSha256'],'atoms':modeller.topology.getNumAtoms(),'residues':len(residues),'heavyAtomPreparationMaximumErrorAngstrom':heavy_error,'hydrogenVariants':variants,'forceFieldFiles':parameters,'method':{'protein':'Amber ff14SB','solvent':'OBC2 implicit solvent','soluteDielectric':1.,'solventDielectric':78.5,'protonation':'Original OpenMM addHydrogens pH 7; existing atoms retained','nonbonded':'NoCutoff','constraints':'HBonds','constraintTolerance':1e-6,'integrator':'LangevinMiddleIntegrator','temperatureK':300.,'frictionPerPs':1.,'timestepFs':1.,'seed':request['seed'],'minimizationMaxIterations':500,'minimizationToleranceKjMolNm':10.},'initial':initial_energy,'afterMinimization':minimized_energy,'series':series,'durationPs':series[-1]['timePs'],'artifacts':{name:sha(folder/name) for name in names},'seconds':time.monotonic()-started,'limitations':['Short pilot, not equilibrated or validated sampling, stability, binding or free energy.','Implicit solvent and standard pH-7 hydrogen assumptions; no explicit water, salt or general ligand parameters.','Bounded local minimization does not establish a global minimum or independently certified convergence.','Exact trajectories are not promised across platforms or runtime versions.']}
 result['preparedPdbHeavyAtomRoundingMaximumErrorAngstrom']=rounding
 result['checkpointScope']='Original OpenMM checkpoint including internal integration/random state; restart requires matching OpenMM version, platform and compatible hardware.'
 result['checkpointHost']=checkpoint_host()
 (folder/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result

def continue_run(request_path,request):
 import numpy as np
 import openmm as mm
 from openmm import app,unit
 folder=request_path.parent;restart=folder/'restart';started=time.monotonic()
 if mm.__version__!='8.6.1':raise ValueError('Checkpoint continuation requires OpenMM 8.6.1.')
 for name,digest in request['restartFiles'].items():
  if pathlib.Path(name).name!=name or sha(restart/name)!=digest:raise ValueError('Checkpoint snapshot changed: '+name)
 parent=json.loads((restart/'result.json').read_text())
 if any(request['restartFiles'].get(name)!=digest for name,digest in parent['artifacts'].items()):raise ValueError('Parent receipt artifact mapping differs.')
 if parent.get('checkpointHost')!=checkpoint_host() or parent['runtime']!={'openmm':mm.__version__,'numpy':np.__version__,'platform':'CPU','properties':{'Threads':'1','DeterministicForces':'true'}}:raise ValueError('Checkpoint hardware, OS or runtime differs; exact continuation refused.')
 steps=request['steps'];interval=request['reportInterval']
 if type(steps) is not int or not 10<=steps<=5000 or type(interval) is not int or interval<1 or steps%interval or steps//interval>100:raise ValueError('Invalid bounded continuation interval.')
 if sha(folder/('input.pdb' if request['format']=='pdb' else 'input.cif'))!=request['inputSha256'] or parent['inputSha256']!=request['inputSha256']:raise ValueError('Original protein source differs.')
 pdb=app.PDBFile(str(restart/'prepared.pdb'));system=mm.XmlSerializer.deserialize((restart/'system.xml').read_text());integrator=mm.XmlSerializer.deserialize((restart/'integrator.xml').read_text());saved=mm.XmlSerializer.deserialize((restart/'final-state.xml').read_text())
 if system.getNumParticles()!=pdb.topology.getNumAtoms() or system.getNumParticles()!=parent['atoms']:raise ValueError('Checkpoint topology differs.')
 simulation=app.Simulation(pdb.topology,system,integrator,mm.Platform.getPlatformByName('CPU'),parent['runtime']['properties']);simulation.context.loadCheckpoint((restart/'checkpoint.chk').read_bytes())
 def state():
  value=simulation.context.getState(getPositions=True,getVelocities=True,getEnergy=True,getForces=True);positions=value.getPositions(asNumpy=True).value_in_unit(unit.nanometer);velocities=value.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond);forces=value.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometer);potential=float(value.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole));kinetic=float(value.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole));time_ps=float(value.getTime().value_in_unit(unit.picosecond))
  if not all(np.isfinite(a).all() for a in (positions,velocities,forces)) or not all(math.isfinite(a) for a in (potential,kinetic,time_ps)):raise ValueError('Nonfinite checkpoint continuation state.')
  return value,{'step':simulation.currentStep,'timePs':time_ps,'potentialKjMol':potential,'kineticKjMol':kinetic,'forceRmsKjMolNm':float(np.sqrt(np.mean(np.sum(forces*forces,axis=1))))}
 restored,initial=state();errors={'positionNm':float(np.max(np.abs(restored.getPositions(asNumpy=True).value_in_unit(unit.nanometer)-saved.getPositions(asNumpy=True).value_in_unit(unit.nanometer)))),'velocityNmPerPs':float(np.max(np.abs(restored.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)-saved.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)))),'timePs':abs(float((restored.getTime()-saved.getTime()).value_in_unit(unit.picosecond)))}
 if max(errors.values())>1e-12 or initial['step']!=parent['series'][-1]['step'] or abs(initial['timePs']-parent['series'][-1]['timePs'])>1e-12:raise ValueError('Restored checkpoint differs from saved final state.')
 # Never add hydrogens, minimize, reset velocities, reseed, or reset physical time.
 series=[]
 with (folder/'trajectory.pdb').open('w') as f:
  app.PDBFile.writeHeader(pdb.topology,f)
  for index in range(steps//interval+1):
   if index:simulation.step(interval)
   current,values=state();values['frameId']=index+1;series.append(values);app.PDBFile.writeModel(pdb.topology,current.getPositions(),f,modelIndex=index+1,keepIds=True);print('OpenMM continuation: saved absolute step '+str(values['step']),flush=True)
  app.PDBFile.writeFooter(pdb.topology,f)
 for name in ('prepared.pdb','minimized.pdb','system.xml','integrator.xml'):(folder/name).write_bytes((restart/name).read_bytes())
 (folder/'final-state.xml').write_text(mm.XmlSerializer.serialize(current));(folder/'checkpoint.chk').write_bytes(simulation.context.createCheckpoint())
 for name,digest in request['restartFiles'].items():
  if sha(restart/name)!=digest:raise ValueError('Checkpoint snapshot changed during continuation.')
 if sha(folder/('input.pdb' if request['format']=='pdb' else 'input.cif'))!=request['inputSha256']:raise ValueError('Original continuation source changed.')
 names=('prepared.pdb','minimized.pdb','trajectory.pdb','system.xml','integrator.xml','final-state.xml','checkpoint.chk');result={**parent,'requestSha256':sha(request_path),'runnerSha256':sha(pathlib.Path(__file__)),'series':series,'durationPs':series[-1]['timePs'],'seconds':time.monotonic()-started,'artifacts':{name:sha(folder/name) for name in names},'continuation':{'parentJobId':request['parentJobId'],'parentReceiptSha256':request['restartFiles']['result.json'],'checkpointSha256':request['restartFiles']['checkpoint.chk'],'startStep':initial['step'],'startTimePs':initial['timePs'],'addedSteps':steps,'addedDurationPs':series[-1]['timePs']-initial['timePs'],'restoredStateMaximumErrors':errors}}
 (folder/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
if __name__=='__main__':run(sys.argv[1])
