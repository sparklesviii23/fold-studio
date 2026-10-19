"""Verify a completed original-filter bounded conformational campaign, including rejection."""
import argparse,hashlib,json,math,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from bindcraft_cpu import execution_config
import fold_engine as fe
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.root).resolve();s=Service(root)
try:
 job=s.job(a.job);data=job['data'];prep=data['preparation'];folder=root/'jobs'/job['id'];assert job['state']=='completed',job['state'];assert prep['modality'] in ('fold_switch','induced_fit');assert data['profile']=='experimental-cpu-float32-conformational';assert not prep.get('scientificOptions') and not prep.get('properties')
 from campaign_inputs import verify
 verify(folder,prep)
 execution=json.loads((folder/'execution-settings.json').read_text());expected,_=execution_config(prep['config'],folder);assert fe.canonical(execution)==fe.canonical(expected);assert execution['max_trajectories']==1;assert fe.checksum(fe.canonical(execution).encode())==data['executionSettingsSha256']
 runtime=json.loads((folder/'runtime-provenance.json').read_text());assert runtime['state']=='finished' and runtime['exitCode']==0 and runtime['execution']=='cpu' and runtime['precision']=='float32';assert runtime['upstreamSource']==fe.verify_source()
 observations={}
 for line in (folder/'execution.log').read_text().splitlines():
  if not line.startswith('FOLD_PROGRESS '):continue
  value=json.loads(line.removeprefix('FOLD_PROGRESS '));assert value['sequenceUpdates']>0;assert all(not isinstance(v,(int,float)) or math.isfinite(v) for v in value.get('metrics',{}).values());observations[value['stage']]=value
 assert 'screen' in observations and 'screen_binder_alone' in observations
 result=s.dispatch('bindcraft_results',{'projectId':job['project_id'],'id':job['id']});counts={name:value['count'] for name,value in result['tables'].items()};assert counts['trajectories']==1;assert result['claimedProgress']['trajectories']==1;assert bool(data.get('outputs'))==bool(counts['accepted'])
 report={'state':'bounded_original_trajectory_completed','scope':'Actual single-model CPU float32 original conformational trajectory on an explicitly preserved 12-residue hPDL1 fragment plus 60-residue binder. Genuine bound and unbound optimization observed with finite emitted readings. Original rejection criteria and budgets unchanged; rejection is a valid outcome. No broad conformational, full-ensemble or biological validation claim.','jobId':job['id'],'root':str(root),'modality':prep['modality'],'stageRows':counts,'outcome':data['outcome'],'resourceEstimate':data['resourceEstimate'],'lastObservedUpdatesByStage':observations,'trajectoryRows':result['tables']['trajectories']['rows'],'candidateRows':result['tables']['candidates']['rows'],'acceptedRows':result['tables']['accepted']['rows'],'runtime':runtime,'inputSha256':hashlib.sha256((folder/'input.cif').read_bytes()).hexdigest(),'executionSettingsSha256':data['executionSettingsSha256'],'originalDefaultFiltersRetained':True,'modelSelection':data['modelSelection'],'checkpointSha256':data['checkpointSha256']}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':report['state'],'outcome':data['outcome'],'stageRows':counts,'seconds':runtime['totalSeconds'],'stages':list(observations)}))
finally:s.db.close()
