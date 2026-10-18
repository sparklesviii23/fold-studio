"""Check saved RDKit atoms/bonds in the installed original native scientific scene."""
import argparse,hashlib,json,math,os,pathlib,signal,sys,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--acceptance-report',required=True);p.add_argument('--report',required=True);a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
from worker import Service
from observatory import Observatory
acceptance=json.loads(pathlib.Path(a.acceptance_report).read_text())
if acceptance['state']!='passed':raise ValueError('Actual chemistry acceptance is required.')
s=Service(acceptance['root']);obs=Observatory(s);pid=None;checks=[]
try:
 pid=obs.chimerax_start({'headless':True})['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(.5)
 else:raise RuntimeError('Native scientific session did not connect.')
 for case in acceptance['cases']:
  record=obs.item(case['recordId']);source=s.root/'assets'/record['data']['asset'];before=hashlib.sha256(source.read_bytes()).hexdigest();ligand=record['data']['metadata']['ligand'];opened=obs.chimerax_open({'projectId':record['project_id'],'structureId':record['id'],'replace':True})
  if opened['state']!='completed' or not opened.get('mapping'):raise RuntimeError(opened)
  model_id=opened['mapping'][0]['modelId'];scene=obs.chimerax_scene({});model=next(m for m in scene['models'] if m['id']==model_id);native={atom['atom']:atom for atom in model['atoms']};expected={atom['name']:atom for atom in ligand['atoms']}
  if native.keys()!=expected.keys():raise AssertionError('Native ligand atom identities differ.')
  error=max(math.dist(native[name]['xyz'],atom['xyz']) for name,atom in expected.items())
  if error>1e-5:raise AssertionError('Native ligand coordinates changed.')
  pairs={tuple(sorted((model['atoms'][bond['a']]['atom'],model['atoms'][bond['b']]['atom']))) for bond in model['bonds']};expected_pairs={tuple(sorted((ligand['atoms'][bond['a']]['name'],ligand['atoms'][bond['b']]['name']))) for bond in ligand['bonds']}
  if pairs!=expected_pairs:raise AssertionError(('Native connectivity differs',pairs^expected_pairs))
  if not any(atom['shown'] for atom in model['atoms']):raise AssertionError('Native model hides every ligand atom.')
  if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise AssertionError('Source coordinates changed.')
  checks.append({'recordId':record['id'],'input':case['input'],'atoms':len(native),'bonds':len(pairs),'maximumCoordinateErrorAngstrom':error,'sourceUnchanged':True,'someAtomsDisplayed':True,'bondConnectivity':'exact original RDKit atom pairs'})
 report={'state':'passed','scope':'Actual prepared ligand coordinate atoms and explicit bond connectivity match the installed ChimeraX scientific scene on the saved small-molecule cases. Source assets unchanged. No native partial-charge assignment, renderer screenshot, docking or biological validation asserted.','engineRoot':str(ENGINE),'checks':checks}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:
 if pid:
  try:os.kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
