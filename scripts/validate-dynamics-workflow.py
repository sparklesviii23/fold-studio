"""Actual common-job OpenMM pilot, coordinate import and reproducibility export."""
import argparse,hashlib,json,pathlib,subprocess,sys,time,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--python',required=True);p.add_argument('--input',required=True);p.add_argument('--directory',required=True);p.add_argument('--report',required=True);p.add_argument('--bundled-runtime',action='store_true');a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
def seal():
 if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
seal()
from worker import Service
from dynamics import runtime
from coordinate_ensemble import inspect
root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated dynamics validation root.')
s=Service(root);source=pathlib.Path(a.input).resolve();before=hashlib.sha256(source.read_bytes()).hexdigest();project=s.project_create({'name':'OpenMM short protein pilot QA'})
try:
 if a.bundled_runtime:
  if s.setting('openmmPython') or runtime(s)!=str(pathlib.Path(a.python).absolute()):raise ValueError('Automatic app-owned OpenMM discovery differs; no job launched.')
 else:s.setting_set({'key':'openmmPython','value':str(pathlib.Path(a.python).absolute())})
 parent=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Original upstream protein test fixture · technical QA only'});job=s.dispatch('dynamics_start',{'projectId':project['id'],'structureId':parent['id'],'name':'Real OpenMM common-job pilot · technical QA','seed':42,'steps':20,'reportInterval':5});deadline=time.monotonic()+180
 while True:
  job=s.job(job['id'])
  if job['state'] not in ('queued','running'):break
  if time.monotonic()>deadline:raise ValueError('Job did not finish within acceptance time limit. Inspect it before any restart.')
  time.sleep(.2)
 if job['state']!='completed':raise AssertionError((job,(root/'jobs'/job['id']/'execution.log').read_text()))
 outputs=[next(r for r in s.library({})['records'] if r['id']==id) for id in job['data']['outputs']]
 if len(outputs)!=3 or any(r['data']['confidenceKind'] is not None for r in outputs):raise AssertionError('Prepared, minimized and trajectory records must be separate with no prediction confidence.')
 trajectory=outputs[0];ensemble=inspect((root/'assets'/trajectory['data']['asset']).read_bytes());receipt=trajectory['data']['metadata']['dynamics']['receipt']
 if ensemble['frameIds']!=[1,2,3,4,5] or [r['step'] for r in receipt['series']]!=[0,5,10,15,20] or [r['frameId'] for r in receipt['series']]!=ensemble['frameIds'] or abs(receipt['durationPs']-.02)>1e-9:raise AssertionError('Physical-time mapping differs from supplied trajectory frames.')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=before or hashlib.sha256((root/'assets'/parent['data']['asset']).read_bytes()).hexdigest()!=before:raise AssertionError('Original protein source changed.')
 archive=root/'openmm-project.zip';s.export_project({'id':project['id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  for record in [parent]+outputs:
   if hashlib.sha256(z.read('assets/'+record['data']['asset'])).hexdigest()!=record['data']['sha256']:raise AssertionError('Exported coordinate checksum differs.')
  for name,sha in receipt['artifacts'].items():
   if hashlib.sha256(z.read('jobs/'+job['id']+'/'+name)).hexdigest()!=sha:raise AssertionError('Exported reproducibility artifact differs.')
 seal();report={'state':'passed','scope':'Real OpenMM protein preparation/minimization/20-step pilot through shared queue, library, immutable parent, frame/time mapping and exact coordinate/System/Integrator/State project export. Narrow integration evidence; not equilibrium, stability, binding or free-energy validation.','root':str(root),'engineRoot':str(ENGINE),'automaticBundledRuntime':a.bundled_runtime,'signatureAfterCalculation':'passed' if app else 'not_applicable','jobId':job['id'],'inputRecordId':parent['id'],'outputRecordIds':[r['id'] for r in outputs],'sourceSha256':before,'sourceUnchanged':True,'summary':job['data']['resultSummary'],'receipt':receipt,'archive':str(archive)};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('state','jobId','summary','sourceUnchanged','automaticBundledRuntime')}))
finally:s.db.close()
