"""Real shared-job checkpoint lineage against an independent original OpenMM context."""
import argparse,hashlib,json,pathlib,subprocess,sys,time,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--python',required=True);p.add_argument('--input',required=True);p.add_argument('--directory',required=True);p.add_argument('--report',required=True);p.add_argument('--bundled-runtime',action='store_true');a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
from worker import Service
from dynamics import runtime
import numpy as np
import openmm as mm
from openmm import unit
root=pathlib.Path(a.directory).absolute()
if root.exists():raise SystemExit('Use a new isolated continuation QA root.')
s=Service(root);project=s.project_create({'name':'OpenMM checkpoint continuation QA'});source=pathlib.Path(a.input).absolute();source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
def wait(job):
 deadline=time.monotonic()+180
 while job['state'] in ('queued','running'):
  if time.monotonic()>deadline:raise ValueError('Acceptance deadline reached; inspect existing job before another attempt.')
  time.sleep(.2);job=s.job(job['id'])
 if job['state']!='completed':raise AssertionError((job,(root/'jobs'/job['id']/'execution.log').read_text()))
 return job
try:
 if a.bundled_runtime:
  if runtime(s)!=str(pathlib.Path(a.python).absolute()):raise ValueError('Automatic bundled runtime discovery differs.')
 else:s.setting_set({'key':'openmmPython','value':str(pathlib.Path(a.python).absolute())})
 record=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Original OpenMM protein test derivative · technical QA'})
 parent=wait(s.dispatch('dynamics_start',{'projectId':project['id'],'structureId':record['id'],'name':'Checkpoint parent · technical QA','seed':42,'steps':20,'reportInterval':5}));folder=root/'jobs'/parent['id'];before={f.name:f.read_bytes() for f in folder.iterdir() if f.is_file()};parent_receipt=json.loads((folder/'result.json').read_text())
 child=wait(s.dispatch('dynamics_continue',{'projectId':project['id'],'parentJobId':parent['id'],'name':'Real checkpoint continuation · technical QA','steps':20,'reportInterval':5}));child_folder=root/'jobs'/child['id'];child_receipt=json.loads((child_folder/'result.json').read_text())
 grandchild=wait(s.dispatch('dynamics_continue',{'projectId':project['id'],'parentJobId':child['id'],'name':'Chained checkpoint continuation · technical QA','steps':10,'reportInterval':5}));last=root/'jobs'/grandchild['id'];last_receipt=json.loads((last/'result.json').read_text())
 # Independent original OpenMM context restored from the parent, never reset.
 system=mm.XmlSerializer.deserialize((folder/'system.xml').read_text());integrator=mm.XmlSerializer.deserialize((folder/'integrator.xml').read_text());context=mm.Context(system,integrator,mm.Platform.getPlatformByName('CPU'),{'Threads':'1','DeterministicForces':'true'});context.loadCheckpoint((folder/'checkpoint.chk').read_bytes());comparisons=[]
 for segment,added in [(child,20),(grandchild,10)]:
  integrator.step(added);actual=context.getState(getPositions=True,getVelocities=True,getEnergy=True);saved=mm.XmlSerializer.deserialize((root/'jobs'/segment['id']/'final-state.xml').read_text());errors={'positionsNm':float(np.max(np.abs(actual.getPositions(asNumpy=True).value_in_unit(unit.nanometer)-saved.getPositions(asNumpy=True).value_in_unit(unit.nanometer)))),'velocitiesNmPerPs':float(np.max(np.abs(actual.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)-saved.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)))),'timePs':abs(float((actual.getTime()-saved.getTime()).value_in_unit(unit.picosecond))),'potentialKjMol':abs(float((actual.getPotentialEnergy()-saved.getPotentialEnergy()).value_in_unit(unit.kilojoule_per_mole)))}
  if max(errors.values())>1e-10:raise AssertionError(('Direct original context differs',errors))
  comparisons.append({'jobId':segment['id'],'maximumAbsoluteErrors':errors})
 if before!={f.name:f.read_bytes() for f in folder.iterdir() if f.is_file()} or s.job(parent['id'])!=parent:raise AssertionError('Parent job/artifacts changed.')
 if [x['step'] for x in child_receipt['series']]!=[20,25,30,35,40] or [x['step'] for x in last_receipt['series']]!=[40,45,50]:raise AssertionError('Continuation reset absolute step numbers.')
 if len(child['data']['outputs'])!=1 or len(grandchild['data']['outputs'])!=1 or len(s.library({})['records'])!=6:raise AssertionError('Continuation duplicated prepared/minimized outputs.')
 measurement=s.dispatch('dynamics_analyze',{'projectId':project['id'],'structureId':grandchild['data']['outputs'][0],'align':True})
 if measurement['physicalTimePs']!=[x['timePs'] for x in last_receipt['series']] or abs(measurement['physicalTimePs'][-1]-.05)>1e-10:raise AssertionError('Motion analysis lost absolute physical times.')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=source_sha:raise AssertionError('Original protein changed.')
 # A corrupted private checkpoint copy must fail without importing any results.
 with __import__('unittest.mock',fromlist=['patch']).patch.object(s,'spawn',side_effect=lambda job,mode:job):bad=s.dispatch('dynamics_continue',{'projectId':project['id'],'parentJobId':parent['id'],'name':'Corruption refusal QA','steps':10,'reportInterval':5})
 bad_folder=root/'jobs'/bad['id'];(bad_folder/'restart/checkpoint.chk').write_bytes(b'corrupt QA snapshot');import dynamics;dynamics.run(s,bad['id']);bad=s.job(bad['id'])
 if bad['state']!='failed' or bad['data']['outputs'] or len(s.library({})['records'])!=6:raise AssertionError('Corrupted snapshot published a partial result.')
 archive=root/'continuation-project.zip';s.export_project({'id':project['id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  for job in (parent,child,grandchild):
   receipt=json.loads((root/'jobs'/job['id']/'result.json').read_text())
   for name,digest in receipt['artifacts'].items():
    if hashlib.sha256(z.read('jobs/'+job['id']+'/'+name)).hexdigest()!=digest:raise AssertionError('Exported artifact differs.')
   for name,digest in job['data']['request'].get('restartFiles',{}).items():
    if hashlib.sha256(z.read('jobs/'+job['id']+'/restart/'+name)).hexdigest()!=digest:raise AssertionError('Exported parent snapshot differs.')
 if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
 report={'state':'passed','scope':'Real 35-residue CPU parent pilot followed by 20-step and 10-step separate checkpoint continuations. Both final states match independently continued original OpenMM context within 1e-10. Exact parent preservation, chained lineage, absolute steps/time, one trajectory per continuation, shared motion analysis, corruption refusal and project ZIP bytes checked. Same hardware/runtime only; no equilibrium or biological claim.','engineRoot':str(ENGINE),'root':str(root),'sourceSha256':source_sha,'sourceUnchanged':True,'parentUnchanged':True,'jobId':parent['id'],'continuationJobIds':[child['id'],grandchild['id']],'parentReceipt':parent_receipt,'continuationReceipts':[child_receipt,last_receipt],'originalContextComparisons':comparisons,'motionAnalysisId':measurement['analysisId'],'corruptionJobId':bad['id'],'corruptionState':bad['state'],'corruptionOutputs':bad['data']['outputs'],'automaticBundledRuntime':a.bundled_runtime,'signatureAfterUse':'passed' if app else 'not_applicable','archive':str(archive)};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('state','jobId','continuationJobIds','originalContextComparisons','corruptionState','parentUnchanged')}))
finally:s.db.close()
