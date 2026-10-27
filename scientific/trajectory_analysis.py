"""Bounded source-preserving motion measurement in the shared Observatory."""
import json,math,pathlib,subprocess,tempfile
import fold_engine as fe
from coordinate_ensemble import inspect

def analyze(s,p):
 from dynamics import runtime
 from observatory import Observatory
 if set(p)-{'projectId','structureId','align'} or type(p.get('align',True)) is not bool:raise ValueError('Choose an explicit rigid-fit option for a saved ensemble.')
 record,path=fe.Engine(s).lab.record(p['structureId'])
 if record['project_id']!=p['projectId']:raise ValueError('Choose a coordinate ensemble in this project.')
 expected=record['data'].get('metadata',{}).get('coordinateEnsemble')
 if not expected or record['data']['format']!='pdb' or inspect(path.read_bytes())!=expected:raise ValueError('Choose an intact, explicitly imported coordinate ensemble or saved pilot trajectory.')
 python=runtime(s)
 if not pathlib.Path(python).is_file():raise ValueError('The scientific analysis runtime is unavailable in this build.')
 runner=pathlib.Path(__file__).with_name('trajectory_metrics.py');runner_sha=fe.checksum(runner.read_bytes());obs=Observatory(s)
 # Short bounded analysis shares the database write reservation with job starts.
 # It cannot begin alongside an active local job or publish a partial analysis.
 s.db.execute('BEGIN IMMEDIATE')
 try:
  if s.active():raise ValueError('Another local compute job is active. Finish it before analyzing saved frames.')
  with tempfile.TemporaryDirectory(prefix='motion-',dir=s.root/'cache') as tmp:
   folder=pathlib.Path(tmp);request={'input':str(path),'inputSha256':record['data']['sha256'],'align':p.get('align',True)};(folder/'request.json').write_text(fe.canonical(request));process=subprocess.run([python,'-I','-B',str(runner),str(folder/'request.json'),str(folder/'result.json')],capture_output=True,text=True,timeout=30)
   if process.returncode:raise ValueError(process.stderr.strip().splitlines()[-1] if process.stderr.strip() else 'Motion analysis failed.')
   result=json.loads((folder/'result.json').read_text())
  if result['inputSha256']!=record['data']['sha256'] or result['runnerSha256']!=runner_sha or fe.checksum(runner.read_bytes())!=runner_sha or fe.checksum(path.read_bytes())!=record['data']['sha256']:raise ValueError('Motion source or calculation implementation changed.')
  if result['frameIds']!=expected['frameIds'] or len(result['rmsdAngstrom'])!=len(expected['frameIds']) or len(result['rmsfAngstrom'])!=len(result['atoms']) or len(result.get('radiusOfGyrationAngstrom',[]))!=len(expected['frameIds']):raise ValueError('Motion result correspondence differs from its source.')
  if any(not math.isfinite(v) or v<0 for v in result['rmsdAngstrom']+result['rmsfAngstrom']+result['radiusOfGyrationAngstrom']):raise ValueError('Motion calculation returned invalid values.')
  dynamics=record['data'].get('metadata',{}).get('dynamics',{});receipt=dynamics.get('receipt',{});series=receipt.get('series',[])
  if dynamics.get('artifact')=='trajectory.pdb' and receipt.get('artifacts',{}).get('trajectory.pdb')==record['data']['sha256'] and [row.get('frameId') for row in series]==result['frameIds']:
   result['physicalTimePs']=[row['timePs'] for row in series];result['timeSource']='Matching saved OpenMM trajectory receipt; not inferred from MODEL IDs.'
  result['source']={'structureId':record['id'],'sha256':record['data']['sha256'],'name':record['name']};result['kind']='trajectory-motion';result['sourceUnchanged']=True
  entry=obs.observatory_save({'projectId':p['projectId'],'kind':'analysis','name':'Cα motion · '+record['name'],'data':result});return {**result,'analysisId':entry['id']}
 except Exception:
  s.db.rollback();raise
