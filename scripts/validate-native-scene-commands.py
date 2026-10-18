"""Scoped original-command behavior through FOLD's real native scene adapter.

Uses a disposable library and a helper process owned by this invocation. Camera
and display checks establish adapter behavior, not visual renderer equivalence.
"""
import argparse,base64,hashlib,json,math,os,pathlib,signal,sys,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args()
sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory
folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Choose a new isolated validation directory.')
folder.mkdir(parents=True);s=Service(folder/'library',ROOT/'fixtures');obs=Observatory(s);pid=None;checks=[]
def check(name,command,condition,details=None,numerical=False):
 row={'name':name,'command':command,'passed':bool(condition),'details':details,'numerical':numerical};checks.append(row)
 if not condition:raise AssertionError(row)
def execute(command):
 result=obs.chimerax_execute({'projectId':project,'command':command,'confirmed':True})
 if result['state']!='completed':raise AssertionError(result)
 return result
def scene():return obs.chimerax_scene({})
def atoms(snapshot):return next(m['atoms'] for m in snapshot['models'] if m['id']==model)
def script(code):
 result=obs.chimerax_python({'projectId':project,'confirmed':True,'code':code})
 if result['state']!='completed':raise AssertionError(result)
 return result
try:
 project=s.library({})['projects'][0]['id'];record=next(r for r in s.library({})['records'] if r['kind']=='structure');source=s.root/'assets'/record['data']['asset'];sha=hashlib.sha256(source.read_bytes()).hexdigest()
 pid=obs.chimerax_start({'headless':True})['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(1)
 else:raise RuntimeError('Native helper failed to connect.')
 model=obs.chimerax_open({'projectId':project,'structureId':record['id']})['mapping'][0]['modelId'];spec='#'+model
 original=scene();xyz={x['key']:x['xyz'] for x in atoms(original)}
 command='hide '+spec+' atoms';execute(command);hidden=scene();check('hide',command,all(not x['shown'] for x in atoms(hidden)))
 command='show '+spec+'/A:20 atoms';execute(command);shown=scene();visible=[x for x in atoms(shown) if x['shown']];check('show',command,bool(visible) and all(x['chain']=='A' and x['residue']==20 for x in visible),{'visibleAtoms':len(visible)})
 execute('hide '+spec+' cartoons');command='cartoon '+spec+'/A:20-30';execute(command);ribbons=scene();enabled={x['residue'] for x in atoms(ribbons) if x['ribbonShown']};check('cartoon',command,enabled==set(range(20,31)),{'enabledResidues':sorted(enabled)})
 command='transparency '+spec+'/A:20 50 target a';execute(command);transparent=scene();selected=[x for x in atoms(transparent) if x['residue']==20];check('transparency',command,all(x['color'][3]==128 for x in selected) and all(x['color'][3]==255 for x in atoms(transparent) if x['residue']!=20),{'selectedAlphaBytes':sorted({x['color'][3] for x in selected})})
 execute('transparency '+spec+' 0 target a')
 # A copied model with an exact translation has sqrt(mean(|delta|^2))=3 Å.
 duplicate=s.import_structure({'projectId':project,'path':str(source),'name':'Duplicate reference for analytic translation QA'})
 copied=obs.chimerax_open({'projectId':project,'structureId':duplicate['id'],'replace':False});other=copied['mapping'][0]['modelId']
 if other==model:raise AssertionError('RMSD fixture needs distinct native models.')
 execute('move x 3 models #'+other+' coordinateSystem #'+model)
 command='rmsd #'+other+'/A@CA to '+spec+'/A@CA';result=execute(command);value=result['output']['python values'][0];check('rmsd',command,abs(value-3.)<1e-6,{'expectedAngstrom':3.,'observedAngstrom':value,'atomPairs':460},True)
 mismatch=obs.chimerax_execute({'projectId':project,'command':'rmsd #'+other+'/A:20@CA to '+spec+'/A:20-21@CA','confirmed':True});check('rmsd unequal sets refused','rmsd',mismatch['state']=='failed' and mismatch['output']['error']['type']=='UserError')
 before=scene();command='turn z 90 center 0,0,0 coordinateSystem #'+model+' models '+spec;execute(command);turned=scene()
 error=max(math.dist(x['xyz'],[-xyz[x['key']][1],xyz[x['key']][0],xyz[x['key']][2]]) for x in atoms(turned));check('turn',command,error<1e-4,{'maximumCoordinateErrorAngstrom':error},True)
 # Restore the known camera explicitly through the existing scene camera route.
 obs.chimerax_camera({'position':[0.,0.,200.],'target':[0.,0.,0.],'up':[0.,1.,0.]})
 before=scene()['camera'];command='zoom 2';execute(command);after=scene()['camera']
 if before.get('fieldWidth') is not None:
  error=abs(after['fieldWidth']-before['fieldWidth']/2)
 else:error=abs(math.dist(after['position'],after['target'])-math.dist(before['position'],before['target'])/2)
 check('zoom',command,error<1e-5,{'before':before,'after':after,'error':error},True)
 # Calculate actual native molecular surface geometry and verify transferred
 # buffers against the installed engine's mesh, without initializing OpenGL.
 command='surface '+spec;execute(command);surf=scene();meshes=surf['meshes'];check('surface',command,bool(meshes) and all(m['vertexCount']>0 and m['triangleCount']>0 for m in meshes),{'meshes':[{'id':m['id'],'vertices':m['vertexCount'],'triangles':m['triangleCount']} for m in meshes]})
 for mesh in meshes:
  import struct
  vertices=struct.unpack('<'+'f'*(len(base64.b64decode(mesh['vertices']))//4),base64.b64decode(mesh['vertices']));indices=struct.unpack('<'+'I'*(len(base64.b64decode(mesh['triangles']))//4),base64.b64decode(mesh['triangles']))
  if len(vertices)!=3*mesh['vertexCount'] or len(indices)!=3*mesh['triangleCount'] or not all(math.isfinite(v) for v in vertices) or max(indices)>=mesh['vertexCount']:raise AssertionError('Invalid native surface transport buffers.')
 check('source assets unchanged','all tested commands',hashlib.sha256(source.read_bytes()).hexdigest()==sha,{'sha256':sha})
 report={'state':'passed','scope':'Installed ChimeraX commands reflected into the shared FOLD scene: author selection display, cartoons, alpha bytes, unfitted RMSD, explicit model rotation, camera zoom and genuine surface buffers. Narrow fixture/syntax checks; no complete command parity or visual equivalence claim.','chimeraxVersion':obs.chimerax_status({}).get('version'),'sourceUnchanged':True,'checks':checks}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','checks':len(checks),'report':a.report}))
finally:
 if pid:
  try:os.kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
