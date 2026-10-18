"""Actual RDKit/common-job acceptance; no biological or docking claims."""
import argparse,hashlib,json,math,pathlib,sys,time,zipfile,subprocess
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--python',required=True);p.add_argument('--directory',required=True);p.add_argument('--report',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--bundled-runtime',action='store_true');a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
def seal():
 if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
seal()
from worker import Service
from intelligence import parse_structure
root=pathlib.Path(a.directory).resolve()
if root.exists() and not a.resume:raise SystemExit('Use a new isolated validation root or explicitly resume its recorded cases.')
s=Service(root);expected_python=str(pathlib.Path(a.python).absolute())
if a.resume:
 projects=[p for p in s.library({})['projects'] if p['name']=='Ligand chemistry and shared workflow QA']
 if len(projects)!=1 or (s.engine_python() if a.bundled_runtime else s.setting('enginePython'))!=expected_python:raise ValueError('Saved acceptance project/runtime differs; choose a new directory.')
 project=projects[0]
else:
 project=s.project_create({'name':'Ligand chemistry and shared workflow QA'})
 if a.bundled_runtime:
  if s.setting('enginePython') or s.engine_python()!=expected_python:raise ValueError('Automatic bundled runtime discovery differs from the supplied app interpreter.')
 else:s.setting_set({'key':'enginePython','value':expected_python})
def run(name,smiles,success=True):
 payload={'projectId':project['id'],'name':name+' · technical QA','smiles':smiles,'seed':42,'conformers':3}
 previous=[j for j in s.library({})['jobs'] if j['project_id']==project['id'] and j['name']==payload['name']] if a.resume else []
 if len(previous)>1:raise ValueError('Ambiguous saved case; no calculation resubmitted.')
 if previous and (previous[0]['data']['runnerSha256']!=hashlib.sha256((ENGINE/'scientific/ligand_runner.py').read_bytes()).hexdigest() or previous[0]['data']['request']!={k:v for k,v in payload.items() if k!='projectId'}):raise ValueError('Saved case runner/input differs; no calculation resubmitted.')
 job=previous[0] if previous else s.dispatch('ligand_start',payload);deadline=time.monotonic()+120
 while True:
  result=s.job(job['id'])
  if result['state'] not in ('queued','running'):break
  if time.monotonic()>deadline:raise RuntimeError('Ligand preparation timeout.')
  time.sleep(.1)
 if success and result['state']!='completed':raise RuntimeError((result,(root/'jobs'/job['id']/'execution.log').read_text()))
 if not success:
  if result['state']!='failed' or result['data']['outputs']:raise AssertionError('Invalid chemistry produced a saved ligand.')
  return {'jobId':job['id'],'input':smiles,'state':'refused','error':result['data']['error']}
 record=next(r for r in s.library({})['records'] if r['id']==result['data']['outputs'][0]);info=record['data']['metadata']['ligand'];assert record['data']['confidenceKind'] is None
 coordinate=s.root/'assets'/record['data']['asset'];st=parse_structure(coordinate.read_text(),'mmcif');assert len(st['atoms'])==len(info['atoms']) and all(not r['polymer'] for r in st['residues']) and info['sdfCoordinateMaxErrorAngstrom']<=.0001
 assert info['method']['stereochemistryFrom3D']=='verified' and info['conformers']['converged']>0 and math.isfinite(info['energyKcalMol'])
 exported=root/(record['id']+'.sdf');s.dispatch('ligand_export',{'projectId':project['id'],'structureId':record['id'],'path':str(exported)});assert hashlib.sha256(exported.read_bytes()).hexdigest()==info['sdfSha256']
 return {'jobId':job['id'],'recordId':record['id'],'input':smiles,'formula':info['formula'],'formalCharge':info['formalCharge'],'atoms':len(info['atoms']),'energyKcalMol':info['energyKcalMol'],'sdfCoordinateMaxErrorAngstrom':info['sdfCoordinateMaxErrorAngstrom'],'method':info['method'],'runtime':info['runtime'],'coordinates':[atom['xyz'] for atom in st['atoms']],'coordinateAsset':record['data']['asset'],'sdfAsset':info['sdfAsset']}
try:
 cases=[run('Ethanol','CCO'),run('Benzene','c1ccccc1'),run('Explicit alanine stereochemistry','C[C@H](N)C(=O)O'),run('Explicit methylammonium charge','C[NH3+]'),run('Explicit alkene stereochemistry','F/C=C/F')]
 expected=[('C2H6O',0,9),('C6H6',0,12),('C3H7NO2',0,13),('CH6N+',1,8),('C2H2F2',0,6)]
 for case,(formula,charge,atoms) in zip(cases,expected,strict=True):assert (case['formula'],case['formalCharge'],case['atoms'])==(formula,charge,atoms)
 repeat=run('Ethanol repeat','CCO');assert repeat['coordinates']==cases[0]['coordinates'] and abs(repeat['energyKcalMol']-cases[0]['energyKcalMol'])<1e-10
 refused=[run('Disconnected input','CCO.O',False),run('Unspecified stereochemistry','CC(O)C(=O)O',False),run('Unsupported force-field coverage','[Xe]',False),run('Isotopic transport scope','[13CH3]CO',False)]
 archive=root/'ligand-project.zip';s.export_project({'id':project['id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  manifest={item['file']:item for item in json.loads(z.read('project.json'))['assetManifest']}
  for case in cases+[repeat]:
   for key in ('coordinateAsset','sdfAsset'):
    path=s.root/'assets'/case[key];sha=hashlib.sha256(path.read_bytes()).hexdigest();assert hashlib.sha256(z.read('assets/'+case[key])).hexdigest()==sha;assert manifest['assets/'+case[key]]=={'file':'assets/'+case[key],'sha256':sha,'bytes':path.stat().st_size}
 seal()
 report={'state':'passed','automaticBundledRuntime':a.bundled_runtime,'signatureAfterCalculation':'passed' if app else 'not_applicable','scope':'Real pinned RDKit calculations through common jobs/library. Formula, charge, explicit-H count, 3D stereochemistry, same-seed repeatability, coordinate/SDF transport and project export verified on small molecules. This is technical integration evidence, not independent force-field accuracy, docking or biological validation.','engineRoot':str(ENGINE),'root':str(root),'cases':cases,'sameSeedRepeatability':'exact saved coordinates and energy','refusedInputs':refused,'projectExport':'all coordinate and SDF hashes matched','resumedSavedCases':a.resume,'projectArchive':str(archive),'sourceLicense':'RDKit BSD-3-Clause, retained with the bundled runtime'}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('cases','refusedInputs')},indent=2))
finally:s.db.close()
