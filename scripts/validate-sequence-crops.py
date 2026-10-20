"""Compare native virtual FASTA states with actual pinned source preparation; no AF2."""
import argparse,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.settings import load_settings,build_design_settings,campaign_over_presets
from bindcraft.protein_preparation import prepare_targets
from bindcraft.protein import AMINO_ACIDS,ResidueFlags
from bindcraft_cpu import execution_config
from campaign_inputs import snapshots,prediction_targets,ranked_target,verify
from campaign_profile import resource_estimate,sequence_resources
import intelligence as mi
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated FASTA crop QA root.')
s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});project=s.project_create({'name':'Original multiple FASTA crop preparation QA'})
source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';sha=hashlib.sha256(source.read_bytes()).hexdigest();sequence=mi.parse_structure(source.read_text(),'pdb')['chains'][0]['sequence'];record=s.sequence_save({'projectId':project['id'],'name':'hPDL1 sequence only · technical crop QA, no disorder annotation','sequence':sequence})
common={'projectId':project['id'],'structureId':record['id'],'name':'Original multiple FASTA crops','modality':'peptide','targetChains':['A'],'binderLengths':[8],'candidates':1,'attempts':1,'seed':42};cases=[];refusals=[]
try:
 for count in (2,3):
  values={'idr_crop_count':count,'crop_fasta_sequence':16}
  job=s.dispatch('bindcraft_prepare',{**common,'scientificOptions':values});prep=job['data']['preparation'];folder=root/'jobs'/job['id'];verify(folder,prep);config,_=execution_config(prep['config'],folder);settings=load_settings(config);design=build_design_settings(settings)
  states=prediction_targets(prep);assert [state['name'] for state in states]==[state.name for state in design.prepared_states];assert len(snapshots(prep))==1 and len(config['targets'])==1
  baseline=load_settings({key:value for key,value in config.items() if key not in values})
  assert settings['filters']==baseline['filters'];estimate=sequence_resources(resource_estimate(os.path.abspath(sys.executable),config,ROOT/'vendor/bindcraft2'),prep);assert estimate['aggregatePaddedResidues']<=192
  observations=[]
  for seed in (42,2718):
   sampled=prepare_targets(design,seed);again=prepare_targets(design,seed);flanked=prepare_targets(design,seed,validation_crop=True);intervals=[]
   for state in states:
    name=state['name'];target=sampled[name];positions=target.residue_index.tolist();intervals.append((positions[0],positions[-1]));written=''.join(AMINO_ACIDS[int(i)] for i in target.sequence.argmax(-1).tolist())
    assert positions==again[name].residue_index.tolist();assert written==sequence[positions[0]-1:positions[-1]];assert not bool(target.atom_mask.any());assert all(int(flag)&int(ResidueFlags.SEQUENCE) for flag in target.flags.tolist())
    validation=flanked[name].residue_index.tolist();assert validation[0]<=positions[0] and validation[-1]>=positions[-1];assert not bool(flanked[name].atom_mask.any());assert ranked_target(prep,'design_'+name+'.cif','design')==state
    observations.append({'seed':seed,'name':name,'sourceTargetName':state['sourceTargetName'],'cropIndex':state['cropIndex'],'start':positions[0],'end':positions[-1],'sequence':written,'validationInterval':[validation[0],validation[-1]],'observedAtomMaskCount':int(target.atom_mask.sum())})
   assert len(set(intervals))==count
  repeated=s.dispatch('bindcraft_repeat',{'projectId':project['id'],'id':job['id']});assert prediction_targets(repeated['data']['preparation'])==states;assert (folder/'input.fasta').read_bytes()==('>A\n'+sequence+'\n').encode()
  cases.append({'jobId':job['id'],'state':'prepared_not_executed','cropCount':count,'originalStateNamesMatch':True,'physicalInputCount':1,'resourceEstimate':estimate,'actualOriginalCrops':observations,'defaultFiltersUnchanged':True,'repeatRetainsStates':True})
 # Distinct sampling is enforced by the original preparation function itself.
 job=s.dispatch('bindcraft_prepare',{**common,'scientificOptions':{'idr_crop_count':2,'crop_fasta_sequence':len(sequence)}});config,_=execution_config(job['data']['preparation']['config'],root/'jobs'/job['id'])
 try:resource_estimate(os.path.abspath(sys.executable),config,ROOT/'vendor/bindcraft2')
 except ValueError as error:assert 'distinct crop' in str(error);refusals.append({'case':'insufficient_distinct_original_windows','error':str(error)})
 else:raise AssertionError('Original duplicate-window refusal was bypassed.')
 job=s.dispatch('bindcraft_prepare',{**common,'binderLengths':[60],'scientificOptions':{'idr_crop_count':2}});prep=job['data']['preparation'];config,_=execution_config(prep['config'],root/'jobs'/job['id'])
 try:sequence_resources(resource_estimate(os.path.abspath(sys.executable),config,ROOT/'vendor/bindcraft2'),prep)
 except ValueError as error:assert '192 aggregate' in str(error);refusals.append({'case':'aggregate_memory_envelope','error':str(error)})
 else:raise AssertionError('Multiple-state memory accounting was bypassed.')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
 report={'state':'passed','scope':'Actual pinned source settings/preparation for two and three distinct, reproducible FASTA crops with original validation flanks. One immutable physical input, native per-state output mapping, unchanged original filters and aggregate192-residue guard. No trained-model computation or accepted-output claim.','root':str(root),'cases':cases,'refusals':refusals,'sourceSha256':sha,'sourceUnchanged':True}
 pathlib.Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':'passed','cases':len(cases),'refusals':len(refusals)}))
finally:s.db.close()
