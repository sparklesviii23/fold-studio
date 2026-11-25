"""Replay the actual peptide resource failure safely, then run original filters on CPU.

A separately labelled one-attempt engineering schedule, never a production repeat.
"""
import hashlib,json,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from bindcraft_cpu import failure_from_log
from unittest.mock import patch
source=ROOT.parent/'validation/bindcraft-fab-amme-native';id='1d0dc714-2456-4bf7-935e-c3501787fa16';original=source/'jobs'/id;log=(original/'execution.log').read_text();diagnostic=failure_from_log(log);assert diagnostic['category']=='metal_memory_limit'
root=ROOT.parent/'validation/architect-peptide-cpu';root.mkdir(exist_ok=False);s=Service(root);s.setting_set({'key':'bindcraftPython','value':str((ROOT.parent/'runtimes/jax-cpu/bin/python').absolute())});s.setting_set({'key':'bindcraftMetalPython','value':str((ROOT.parent/'runtimes/jax-metaljax/bin/python').absolute())});s.setting_set({'key':'af2Parameters','value':str(ROOT.parent/'models/alphafold')});project=s.project_create({'name':'Peptide engineering validation · original filters'})
try:
 target=s.import_structure({'projectId':project['id'],'path':str(original/'input.pdb')});settings=json.loads((original/'settings.json').read_text());before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()}
 base={'projectId':project['id'],'structureId':target['id'],'name':'Engineering only · ANGPTL3 peptide · CPU','modality':'peptide','targetChains':settings['targets'][0]['chains'].split(','),'binderLengths':settings['binder_lengths'],'candidates':1,'attempts':1,'seed':settings['campaign_seed']}
 job=s.dispatch('bindcraft_prepare',base)
 with patch.object(s,'spawn',side_effect=AssertionError('Unsafe Metal launch must never spawn.')):
  try:s.dispatch('bindcraft_start',{'projectId':project['id'],'id':job['id'],'profile':'experimental-metal-float32-single-model'})
  except ValueError as error:assert '192-residue envelope' in str(error);refusal=str(error)
  else:raise AssertionError('Unsafe Metal envelope was not refused.')
 opts={name:1 for name in ('screen_steps','refine_steps','anneal_steps','harden_steps','mutate_steps')};opts.update(betasheet_reopt_extra_refine_steps=0,betasheet_reopt_extra_anneal_steps=0,save_design_trajectory=True,save_failed_trajectories=True)
 job=s.dispatch('bindcraft_prepare',{**base,'scientificOptions':opts});s.job_metadata(job['id'],{'engineeringValidation':{'scope':'Short one-attempt engineering run, original complete saved target and peptide length bounds; original model, losses, recycles and filters retained. Not full production validation.','sourceCampaignId':id,'explicitWorkloadOverrides':opts}})
 started=time.monotonic();s.dispatch('bindcraft_start',{'projectId':project['id'],'id':job['id'],'profile':'experimental-cpu-float32-single-model'});print(json.dumps({'state':'running','jobId':job['id'],'root':str(root),'originalFailure':diagnostic,'metalLaunchRefusedBeforeSpawn':True}),flush=True)
 while True:
  value=s.job_read({'id':job['id']})
  if value['state'] not in ('queued','running'):break
  if time.monotonic()-started>1800:s.dispatch('job_cancel',{'id':job['id']});raise TimeoutError('Bounded engineering run exceeded30minutes; cancelled safely.')
  time.sleep(3)
 assert value['state']=='completed',value['data'].get('error')
 output=root/'jobs'/job['id']/'output';rows=s.dispatch('bindcraft_results',{'projectId':project['id'],'id':job['id']});assert rows['tables']['trajectories']['count']==1
 assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()}
 evidence={'state':'passed','sourceCampaignId':id,'sourceRoot':str(source),'originalFailure':diagnostic,'metalLaunchRefusedBeforeSpawn':True,'refusal':refusal,'root':str(root),'jobId':job['id'],'wallSeconds':time.monotonic()-started,'engineeringWorkload':opts,'originalUserCampaignUnchanged':True,'outcome':value['data'].get('outcome'),'stageRows':{k:v['count'] for k,v in rows['tables'].items()},'originalFiltersRetained':True,'fullProductionValidation':False}
 (ROOT/'reports/architect-linear-peptide.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
finally:s.db.close()
