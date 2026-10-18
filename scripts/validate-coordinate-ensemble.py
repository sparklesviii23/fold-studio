"""Actual native frame switching on explicitly artificial coordinate ensembles."""
import argparse,hashlib,json,math,os,pathlib,signal,subprocess,sys,time,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine-root',default=str(ROOT));p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
def seal():
 if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
seal()
from worker import Service
from observatory import Observatory
folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Use a new isolated ensemble validation directory.')
folder.mkdir(parents=True);path=folder/'ARTIFICIAL_three_frames.pdb';raw='REMARK Artificial coordinate ensemble: geometry testing, not molecular dynamics.\n';expected={}
base=[('N','N',(0.,0.,0.)),('CA','C',(1.45,0.,0.)),('C','C',(2.9,0.,0.)),('O','O',(3.9,0.,0.))]
for frame in (3,7,11):
 raw+=f'MODEL     {frame:4d}\n';expected[frame]={}
 for i,(name,element,point) in enumerate(base,1):
  x,y,z=point
  if frame==7:x+=3
  if frame==11 and name=='CA':y+=4
  expected[frame][name]=[x,y,z];raw+=f'ATOM  {i:5d} {name:>4s} ALA A   1    {x:8.3f}{y:8.3f}{z:8.3f}{1.:6.2f}{0.:6.2f}          {element:>2s}\n'
 raw+='ENDMDL\n'
raw+='END\n';path.write_text(raw);sha=hashlib.sha256(path.read_bytes()).hexdigest();s=Service(folder/'library');obs=Observatory(s);pid=None
try:
 project=s.project_create({'name':'Artificial coordinate ensemble QA'});record=s.import_structure({'projectId':project['id'],'path':str(path),'coordinateSets':True,'name':'Artificial frames · integration QA only'});pid=obs.chimerax_start({'headless':True})['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(.5)
 else:raise RuntimeError('Native helper failed to connect.')
 opened=obs.chimerax_open({'projectId':project['id'],'structureId':record['id']});model_id=opened['mapping'][0]['modelId'];receipts=[];handles=None
 for frame in (3,7,11,7,3):
  command='coordset #'+model_id+' '+str(frame);result=obs.chimerax_execute({'projectId':project['id'],'command':command,'confirmed':True})
  if result['state']!='completed':raise AssertionError(result)
  scene=obs.chimerax_scene({});model=next(m for m in scene['models'] if m['id']==model_id)
  if model['coordsets']!=[3,7,11] or model['activeCoordset']!=frame:raise AssertionError(('Native frame IDs changed',model['coordsets'],model['activeCoordset']))
  current={atom['atom']:atom for atom in model['atoms']};keys={name:atom['key'] for name,atom in current.items()}
  if handles is None:handles=keys
  elif handles!=keys:raise AssertionError('Frame switching changed authoritative atom identity.')
  error=max(math.dist(atom['xyz'],expected[frame][name]) for name,atom in current.items())
  if error>1e-5:raise AssertionError(('Frame coordinates differ',error))
  rmsd=math.sqrt(sum(math.dist(atom['xyz'],expected[3][name])**2 for name,atom in current.items())/len(current));analytic={3:0.,7:3.,11:2.}[frame]
  if abs(rmsd-analytic)>1e-5:raise AssertionError('Unfitted frame displacement differs from analytic RMSD.')
  receipts.append({'command':command,'frame':frame,'maximumCoordinateErrorAngstrom':error,'rmsdToFirstFrameAngstrom':rmsd,'expectedRmsdAngstrom':analytic,'geometryRevision':model['geometry']})
 if len({r['geometryRevision'] for r in receipts})!=3 or receipts[0]['geometryRevision']!=receipts[-1]['geometryRevision']:raise AssertionError('Frame geometry fingerprints are not repeatable.')
 asset=s.root/'assets'/record['data']['asset']
 if hashlib.sha256(asset.read_bytes()).hexdigest()!=sha:raise AssertionError('Original ensemble asset changed.')
 archive=folder/'ensemble-project.zip';s.export_project({'id':project['id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  if z.read('assets/'+asset.name)!=path.read_bytes():raise AssertionError('Project export lost original coordinate frames.')
 report={'state':'passed','scope':'Artificial three-frame multi-MODEL PDB: original ChimeraX coordset commands preserve frame IDs, atom handles, exact coordinates, repeatable scene fingerprints and raw unfitted RMSD. Source/export retain every supplied frame. No simulation, time axis, force field, dynamics or biological validation claim.','root':str(folder),'engineRoot':str(ENGINE),'recordId':record['id'],'sourceUnchanged':True,'sourceSha256':sha,'frameIds':[3,7,11],'checks':receipts,'projectExport':'exact complete original multi-frame PDB'}
 seal();report['signatureAfterFrameSwitches']='passed' if app else 'not_applicable'
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','frames':[3,7,11],'switches':len(receipts)}))
finally:
 if pid:
  try:os.kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
