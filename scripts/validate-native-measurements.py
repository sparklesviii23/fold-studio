"""Known Euclidean geometry through original ChimeraX and FOLD's ordered atom route.
Artificial geometry only: neither a predicted nor an experimental molecule.
"""
import argparse,hashlib,json,math,pathlib,signal,sys,time,os,re
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args()
sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory
folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Choose a new private QA directory.')
folder.mkdir(parents=True)
points=[('N',(1.,0.,0.),'N'),('CA',(0.,0.,0.),'C'),('C',(0.,1.,0.),'C'),('O',(0.,1.,1.),'O'),('CB',(0.,1.,-1.),'C')]
raw='REMARK Artificial orthogonal coordinates for measurement QA only.\n'
for i,(name,xyz,element) in enumerate(points,1):raw+=f'ATOM  {i:5d} {name:>4s} ALA A   1    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{1.:6.2f}{0.:6.2f}          {element:>2s}\n'
raw+='END\n';path=folder/'ARTIFICIAL_orthogonal_geometry.pdb';path.write_text(raw);sha=hashlib.sha256(path.read_bytes()).hexdigest()
s=Service(folder/'library');obs=Observatory(s);pid=None
try:
 project=s.project_create({'name':'Ordered native geometry QA'});record=s.import_structure({'projectId':project['id'],'path':str(path),'name':'Artificial orthogonal geometry · QA only'})
 pid=obs.chimerax_start({'headless':True})['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(1)
 else:raise RuntimeError('Native scientific session did not connect.')
 model=obs.chimerax_open({'projectId':project['id'],'structureId':record['id']})['mapping'][0]['modelId']
 scene=obs.chimerax_scene({});atoms=next(m for m in scene['models'] if m['id']==model)['atoms'];handles={atom['atom']:atom['key'] for atom in atoms}
 results=[]
 # Signed convention: atan2((b1_hat cross v) dot w, v dot w), where
 # v/w are the outer bonds projected perpendicular to the central bond.
 # Here b1_hat=(0,1,0), v=(1,0,0), w=(0,0,+/-1): -/+90 degrees.
 cases=[(['N','O'],math.sqrt(3)),(['N','CA','C'],90.),(['N','CA','C','O'],-90.),(['N','CA','C','CB'],90.)]
 for names,expected in cases:
  actual=obs.chimerax_measure({'keys':[handles[name] for name in names]})
  if abs(actual['value']-expected)>1e-6:raise AssertionError((names,actual,expected))
  results.append({'orderedAtoms':names,'expected':expected,'result':actual})
 # Original angle reports three-point bond angles. Four-point signed torsions
 # use the native torsion command; angle with four atoms means two bond vectors.
 # The explicit fixture atom sets have matching model/measurement order.
 commands=[]
 for names,expected in cases[1:]:
  cmd=('angle' if len(names)==3 else 'torsion')+' #'+model+'/A:1@'+','.join(names)
  script="value=run(session,"+repr(cmd)+")"+("\nprint('FOLD_GEOMETRY:'+repr(float(value)))" if len(names)==3 else '')
  result=obs.chimerax_python({'projectId':project['id'],'confirmed':True,'code':script})
  if result['state']!='completed':raise AssertionError(result)
  value=float(next(row.split(':',1)[1] for row in result['stdout'].splitlines() if row.startswith('FOLD_GEOMETRY:'))) if len(names)==3 else float(re.search(r'is (-?[0-9.]+)°',result['log'])[1])
  if abs(value-expected)>1e-6:raise AssertionError((cmd,value,expected))
  commands.append({'command':cmd,'value':value,'expected':expected})
 try:obs.chimerax_measure({'keys':[handles['N'],handles['N'],handles['C']]})
 except ValueError as error:
  if 'distinct' not in str(error):raise
 else:raise AssertionError('Duplicate atoms produced a spurious measurement.')
 # Independently confirm source bytes and native coordinates did not change.
 refreshed=obs.chimerax_scene({});current=next(m for m in refreshed['models'] if m['id']==model)['atoms']
 original={atom['atom']:atom['xyz'] for atom in atoms};observed={atom['atom']:atom['xyz'] for atom in current}
 if original!=observed:raise AssertionError('Measuring changed molecular coordinates.')
 saved=obs.item(record['id']);asset=s.root/'assets'/saved['data']['asset']
 if hashlib.sha256(asset.read_bytes()).hexdigest()!=sha:raise AssertionError('Source asset changed.')
 report={'state':'passed','scope':'Artificial orthogonal coordinate fixture: distance, angle, signed and mirrored dihedrals agree with analytic values and original ChimeraX angle/torsion commands. No molecular quality or biological claim.','chimeraxVersion':obs.chimerax_status({}).get('version'),'results':results,'commands':commands,'duplicateAtomsRefused':True,'sourceSha256':sha,'sourceUnchanged':True,'nativeCoordinatesUnchanged':True}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:
 if pid:
  try:os.kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
