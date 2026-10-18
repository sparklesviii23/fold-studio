"""Real OpenMM/Amber calculations and CPU-versus-original-Reference checks."""
import argparse,hashlib,json,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Choose a new isolated OpenMM validation directory.')
folder.mkdir(parents=True)
import numpy as np
import openmm as mm
from openmm import app,unit
from dynamics_runner import run
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
fixture=pathlib.Path(app.__file__).parent/'data/test.pdb';pdb=app.PDBFile(str(fixture));model=app.Modeller(pdb.topology,pdb.positions);model.delete([r for r in model.topology.residues() if r.name in ('HOH','Cl')]);model.topology.setPeriodicBoxVectors(None)
source=folder/'input.pdb'
with source.open('w') as f:app.PDBFile.writeFile(model.topology,model.positions,f,keepIds=True)
request={'inputSha256':sha(source),'seed':42,'steps':20,'reportInterval':5};request_file=folder/'request.json';request_file.write_text(json.dumps(request,sort_keys=True,separators=(',',':')))
result=run(request_file)
# The exact same serialized force field is evaluated at the same coordinates by
# the original Reference and optimized CPU platforms, without a surrogate model.
system_xml=(folder/'system.xml').read_text();comparisons=[]
for name in ('prepared.pdb','minimized.pdb'):
 positions=app.PDBFile(str(folder/name)).positions;values={}
 for platform in ('Reference','CPU'):
  system=mm.XmlSerializer.deserialize(system_xml);integrator=mm.VerletIntegrator(1*unit.femtosecond);backend=mm.Platform.getPlatformByName(platform);context=mm.Context(system,integrator,backend,{'Threads':'1','DeterministicForces':'true'} if platform=='CPU' else {});context.setPositions(positions);state=context.getState(getEnergy=True,getForces=True);values[platform]={'energy':float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)),'forces':state.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometer)};del context,integrator,system
 reference,cpu=values['Reference'],values['CPU'];difference=np.abs(reference['forces']-cpu['forces']);error=abs(reference['energy']-cpu['energy'])
 if not np.allclose(reference['forces'],cpu['forces'],rtol=2e-4,atol=.02) or error>max(.02,abs(reference['energy'])*2e-5):raise AssertionError(('CPU versus Reference differs',name,error,float(difference.max())))
 comparisons.append({'file':name,'referenceEnergyKjMol':reference['energy'],'cpuEnergyKjMol':cpu['energy'],'absoluteEnergyErrorKjMol':error,'maximumForceComponentErrorKjMolNm':float(difference.max()),'forceComparison':{'relativeTolerance':2e-4,'absoluteToleranceKjMolNm':.02}})
# Independent analytic force/energy: 0.5*k*(r-r0)^2 = 0.05 kJ/mol,
# F0=+10 and F1=-10 kJ/mol/nm along x at separation 0.11 nm.
analytic=[]
for name in ('Reference','CPU'):
 system=mm.System();system.addParticle(12);system.addParticle(12);bond=mm.HarmonicBondForce();bond.addBond(0,1,.1,1000.);system.addForce(bond);integrator=mm.VerletIntegrator(.001);backend=mm.Platform.getPlatformByName(name);context=mm.Context(system,integrator,backend,{'Threads':'1'} if name=='CPU' else {});context.setPositions([[0,0,0],[.11,0,0]]);state=context.getState(getEnergy=True,getForces=True);energy=float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole));forces=state.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometer)
 if abs(energy-.05)>1e-6 or not np.allclose(forces,[[10,0,0],[-10,0,0]],atol=1e-5,rtol=0):raise AssertionError('Analytic harmonic energy/force differs.')
 analytic.append({'platform':name,'energyKjMol':energy,'forceKjMolNm':forces.tolist()});del context,integrator,system
if result['atoms']<100 or len(result['series'])!=5 or abs(result['durationPs']-.02)>1e-10 or sha(source)!=request['inputSha256']:raise AssertionError('Actual protein trajectory/units/source differs.')
report={'state':'passed','scope':'Original OpenMM 8.6.1 CPU/Reference force and energy checks on the bundled protein fixture with explicitly removed waters/chloride, Amber ff14SB/OBC2; independent analytic harmonic energy/forces. Real 20-step CPU protein pilot produces five frames, finite state and immutable source. Narrow numerical/integration evidence, not equilibrated sampling, biological stability, binding or a Metal backend.','root':str(folder),'upstreamFixture':str(fixture),'upstreamFixtureSha256':sha(fixture),'derivedInputSha256':sha(source),'cpuReference':comparisons,'analytic':analytic,'pilot':result}
pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','atoms':result['atoms'],'residues':result['residues'],'frames':len(result['series']),'durationPs':result['durationPs'],'seconds':result['seconds']}))
