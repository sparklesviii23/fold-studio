"""Original OpenMM checkpoint restoration and same-platform continuation check."""
import argparse,hashlib,json,pathlib
import numpy as np
import openmm as mm
from openmm import unit
p=argparse.ArgumentParser();p.add_argument('--workflow-report',required=True);p.add_argument('--report',required=True);a=p.parse_args();evidence=json.loads(pathlib.Path(a.workflow_report).read_text())
if evidence['state']!='passed':raise ValueError('A completed actual pilot is required.')
folder=pathlib.Path(evidence['root'])/'jobs'/evidence['jobId'];receipt=evidence['receipt']
for name,sha in receipt['artifacts'].items():
 if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha:raise ValueError('Saved simulation artifact changed: '+name)
saved=mm.XmlSerializer.deserialize((folder/'final-state.xml').read_text());checkpoint=(folder/'checkpoint.chk').read_bytes();contexts=[];integrators=[];systems=[];results=[]
for _ in range(2):
 system=mm.XmlSerializer.deserialize((folder/'system.xml').read_text());integrator=mm.XmlSerializer.deserialize((folder/'integrator.xml').read_text());context=mm.Context(system,integrator,mm.Platform.getPlatformByName('CPU'),{'Threads':'1','DeterministicForces':'true'});context.loadCheckpoint(checkpoint);state=context.getState(getPositions=True,getVelocities=True,getEnergy=True)
 position_error=float(np.max(np.abs(state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)-saved.getPositions(asNumpy=True).value_in_unit(unit.nanometer))));velocity_error=float(np.max(np.abs(state.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)-saved.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond))));time_error=abs(float((state.getTime()-saved.getTime()).value_in_unit(unit.picosecond)))
 if max(position_error,velocity_error,time_error)>1e-12:raise AssertionError('Checkpoint restoration differs from recorded final state.')
 integrator.step(5);continued=context.getState(getPositions=True,getVelocities=True,getEnergy=True);results.append({'positions':continued.getPositions(asNumpy=True).value_in_unit(unit.nanometer),'velocities':continued.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond),'timePs':float(continued.getTime().value_in_unit(unit.picosecond)),'energyKjMol':float(continued.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))});contexts.append(context);integrators.append(integrator);systems.append(system)
errors={'positionNm':float(np.max(np.abs(results[0]['positions']-results[1]['positions']))),'velocityNmPerPs':float(np.max(np.abs(results[0]['velocities']-results[1]['velocities']))),'timePs':abs(results[0]['timePs']-results[1]['timePs']),'energyKjMol':abs(results[0]['energyKjMol']-results[1]['energyKjMol'])}
if max(errors.values())>1e-10:raise AssertionError(('Same-platform checkpoint continuations differ',errors))
if abs(results[0]['timePs']-receipt['durationPs']-.005)>1e-10:raise AssertionError('Continuation time differs from five 1 fs steps.')
report={'state':'passed','scope':'Original OpenMM binary checkpoint restores recorded positions, velocities and time, then two independent CPU contexts produce matching five-step continuations on this machine/runtime. Includes internal stochastic integration state. Not a cross-platform, cross-version or long-run reproducibility claim.','jobId':evidence['jobId'],'openmmVersion':mm.__version__,'checkpointSha256':receipt['artifacts']['checkpoint.chk'],'restoredStateMaximumErrors':{'positionNm':position_error,'velocityNmPerPs':velocity_error,'timePs':time_error},'fiveStepContinuationMaximumDifferences':errors,'continuedTimePs':results[0]['timePs']};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
