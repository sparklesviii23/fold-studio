"""Verify actual packaged FASTA execution without treating rejected outputs as accepted."""
import argparse,hashlib,json,math,pathlib,re,subprocess,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from campaign_inputs import verify
from bindcraft_cpu import execution_config
from bindcraft_provenance import chain_roles
from sequence_targets import predicted_crop
import fold_engine as fe
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--job',required=True);p.add_argument('--app',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.root).resolve();app=pathlib.Path(a.app).resolve();s=Service(root)
try:
 job=s.job(a.job);data=job['data'];prep=data['preparation'];folder=root/'jobs'/job['id'];assert job['state']=='completed',job['state'];assert data['profile']=='experimental-cpu-float32-sequence';assert prep['sequenceTarget'] and not prep.get('scientificOptions') and not prep.get('properties');verify(folder,prep)
 assert pathlib.Path(data['runtime']).is_relative_to(app) and pathlib.Path(data['parameters']).is_relative_to(app);assert not s.setting('bindcraftPython') and not s.setting('af2Parameters')
 config=json.loads((folder/'execution-settings.json').read_text());expected,_=execution_config(prep['config'],folder);assert fe.canonical(config)==fe.canonical(expected);assert config['max_trajectories']==1
 runtime=json.loads((folder/'runtime-provenance.json').read_text());assert runtime['state']=='finished' and runtime['exitCode']==0 and runtime['execution']=='cpu' and runtime['precision']=='float32';assert runtime['upstreamSource']==fe.verify_source()
 observations={};log=(folder/'execution.log').read_text()
 for line in log.splitlines():
  if not line.startswith('FOLD_PROGRESS '):continue
  value=json.loads(line.removeprefix('FOLD_PROGRESS '));assert value['sequenceUpdates']>0;assert all(not isinstance(v,(int,float)) or math.isfinite(v) for v in value.get('metrics',{}).values());observations[value['stage']]=value
 assert observations and any('target.target_plddt' in value['metrics'] for value in observations.values())
 coordinate_crops=[]
 for path in sorted((folder/'output').rglob('*.cif')):
  raw=path.read_bytes();structure=fe.mi.parse_structure(raw.decode(),'mmcif');roles=chain_roles(raw,structure)
  if roles and any(role['role']=='target' for role in roles.values()):coordinate_crops.append({'file':str(path.relative_to(folder)),'sha256':hashlib.sha256(raw).hexdigest(),'predictedCrop':predicted_crop(prep,structure,roles)})
 result=s.dispatch('bindcraft_results',{'projectId':job['project_id'],'id':job['id']});counts={name:value['count'] for name,value in result['tables'].items()};assert counts['trajectories']==1 and result['claimedProgress']['trajectories']==1;assert bool(data.get('outputs'))==bool(counts['accepted'])
 signature=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True);assert signature.returncode==0,signature.stderr
 report={'state':'native_original_sequence_trajectory_completed','scope':'Actual native button launched a one-attempt original FASTA-target campaign with app-owned CPU runtime and checkpoints. Genuine sequence-target losses/optimization observed; original rejection criteria retained. Any failed trajectory coordinates remain technical outputs, not accepted predictions. This does not establish biological disorder or binding, full ensemble or broad target validation.','jobId':job['id'],'root':str(root),'app':str(app),'runtime':runtime,'interpreter':data['runtime'],'parameters':data['parameters'],'stageRows':counts,'outcome':data['outcome'],'lastObservedUpdatesByStage':observations,'sourceCropLogReadings':[{'start':int(m[0]),'end':int(m[1]),'sourceLength':int(m[2])} for m in re.findall(r'target=target crop=(\d+)-(\d+)/(\d+)',log)],'coordinateCrops':coordinate_crops,'trajectoryRows':result['tables']['trajectories']['rows'],'resourceEstimate':data['resourceEstimate'],'fastaSha256':hashlib.sha256((folder/'input.fasta').read_bytes()).hexdigest(),'originalDefaultFiltersRetained':True,'signatureAfterExecution':'passed','outputs':data.get('outputs',[]),'modelSelection':data['modelSelection']}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':report['state'],'outcome':data['outcome'],'stageRows':counts,'seconds':runtime['totalSeconds'],'coordinateCrops':len(coordinate_crops)}))
finally:s.db.close()
