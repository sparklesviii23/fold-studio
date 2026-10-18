"""Measured motion on real pilot frames versus original ChimeraX alignment."""
import argparse,hashlib,json,math,os,pathlib,signal,subprocess,sys,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--pilot-report',required=True);p.add_argument('--python',required=True);p.add_argument('--directory',required=True);p.add_argument('--report',required=True);p.add_argument('--bundled-runtime',action='store_true');a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
def seal():
 if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
seal()
from worker import Service
from observatory import Observatory
from dynamics import runtime
evidence=json.loads(pathlib.Path(a.pilot_report).read_text())
if evidence['state']!='passed':raise ValueError('Actual native pilot evidence is required.')
original=Service(evidence['root']);record=next(r for r in original.library({})['records'] if r['id']==evidence['outputIds'][0]);original.db.close();source=pathlib.Path(evidence['root'])/'assets'/record['data']['asset'];before=hashlib.sha256(source.read_bytes()).hexdigest();folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Use a new isolated motion validation root.')
s=Service(folder);obs=Observatory(s);pid=None
try:
 project=s.project_create({'name':'Real pilot motion reference QA'})
 if a.bundled_runtime:
  if s.setting('openmmPython') or runtime(s)!=str(pathlib.Path(a.python).absolute()):raise ValueError('Automatic bundled motion runtime discovery differs.')
 else:s.setting_set({'key':'openmmPython','value':str(pathlib.Path(a.python).absolute())})
 copy=s.import_structure({'projectId':project['id'],'path':str(source),'coordinateSets':True,'name':'Copy of real short protein pilot · numerical QA','metadata':record['data']['metadata']});results={}
 for align,name in [(False,'raw'),(True,'aligned')]:
  result=s.dispatch('dynamics_analyze',{'projectId':project['id'],'structureId':copy['id'],'align':align});assert len(result['atoms'])==35 and len(result['frameIds'])==11 and result['sourceUnchanged'];assert result['physicalTimePs'][0]==0 and abs(result['physicalTimePs'][-1]-.1)<1e-9;results[name]=result
 pid=obs.chimerax_start({'headless':True})['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(.5)
 else:raise RuntimeError('Native reference helper failed to connect.')
 opened=obs.chimerax_open({'projectId':project['id'],'structureId':copy['id']});model=opened['mapping'][0]['modelId']
 code="""import json, numpy as np
from chimerax.atomic import AtomicStructure
from chimerax.geometry import align_points
model=next(m for m in session.models.list(type=AtomicStructure) if m.id_string==MODEL_ID)
indices=np.flatnonzero(model.atoms.names=='CA')
frames=np.array([model.coordset(int(i)).xyzs[indices] for i in model.coordset_ids],dtype=np.float64)
reference=frames[0];aligned=[];rmsd=[]
for frame in frames:
    transformation,native_rmsd=align_points(frame,reference)
    aligned.append(transformation.transform_points(frame.copy()))
    rmsd.append(float(native_rmsd))
aligned=np.array(aligned);mean=aligned.mean(axis=0)
native={'alignedRmsd':rmsd,'alignedRmsf':np.sqrt(np.mean(np.sum((aligned-mean)**2,axis=2),axis=0)).tolist(),'rawRmsd':np.sqrt(np.mean(np.sum((frames-reference)**2,axis=2),axis=1)).tolist(),'rawRmsf':np.sqrt(np.mean(np.sum((frames-frames.mean(axis=0))**2,axis=2),axis=0)).tolist()}
print('FOLD_MOTION:'+json.dumps(native))
""".replace('MODEL_ID',repr(model))
 native=obs.chimerax_python({'projectId':project['id'],'confirmed':True,'code':code})
 if native['state']!='completed':raise AssertionError(native)
 reference=json.loads(next(line.split(':',1)[1] for line in native['stdout'].splitlines() if line.startswith('FOLD_MOTION:')));errors={}
 for name in ('raw','aligned'):
  for metric,suffix in [('rmsdAngstrom','Rmsd'),('rmsfAngstrom','Rmsf')]:
   expected=reference[name+suffix];actual=results[name][metric]
   if len(expected)!=len(actual):raise AssertionError('Reference atom/frame count differs.')
   error=max(abs(x-y) for x,y in zip(expected,actual));errors[name+suffix]=error
   if error>1e-4:raise AssertionError(('Motion differs from original native alignment',name,metric,error))
 if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise AssertionError('Original pilot coordinates changed.')
 seal();report={'state':'passed','scope':'Actual 35-Cα, 11-frame, 0.1 ps pilot: unfitted and proper-rigid-fit RMSD/RMSF agree with original installed ChimeraX align_points and population coordinate moments within 0.0001 Å. Physical times come from matching saved OpenMM receipt. Source unchanged; no equilibrium, flexibility, stability or statistical-uncertainty inference.','root':str(folder),'engineRoot':str(ENGINE),'automaticBundledRuntime':a.bundled_runtime,'signatureAfterAnalysis':'passed' if app else 'not_applicable','sourceSha256':before,'sourceUnchanged':True,'maximumAbsoluteErrorAngstrom':errors,'results':results,'chimeraxReference':reference,'chimeraxVersion':obs.chimerax_status({}).get('version')};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','maximumErrorsAngstrom':errors}))
finally:
 if pid:
  try:os.kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
