"""Real full-Fab downstream components on a genuine gradient-prediction fixture.

This deliberately does not pretend a rejected/unfinished trajectory passed its
upstream stage gates. Component results are labelled engineering artifacts.
"""
import contextlib,hashlib,json,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')];sys.dont_write_bytecode=True
folder=ROOT/'reports/architect-fab-components-v2';report_path=folder/'result.json'
if '--worker' not in sys.argv:
 from amme_worker import run_guarded
 if folder.exists():raise SystemExit('Choose a fresh component-report directory.')
 folder.mkdir();result=run_guarded([os.path.abspath(sys.executable),'-I','-u','-B',str(pathlib.Path(__file__).resolve()),'--worker'],env=os.environ,folder=folder,scratch_parent=ROOT.parent/'validation/architect-fab-ssd',timeout_seconds=1800)
 raise SystemExit(result.returncode)
import jax,numpy as np
import jax.numpy as jnp
import fold_engine as fe
from af2_native import float32_states,model_class
from bindcraft.settings import load_settings,build_design_settings
from bindcraft.protein_preparation import initialize_design_trajectory
from bindcraft.protein import Protein,ResidueFlags,has_residue_flag,write_structure
from bindcraft.proteinmpnn import ProteinMPNNSequenceModel
from bindcraft.model_weights import proteinmpnn_weights
from bindcraft import trajectory
from amme_campaign import atomic_json
from unittest.mock import patch
from bindcraft.sequence_optimization import SemigreedySequenceSampler
from bindcraft.target_schedule import FixedTargetSchedule
from bindcraft.MPNN_stage import redesign_and_validate_binders
from bindcraft.rank import rerank_campaign
from worker import Service
start=time.monotonic();baseline_path=ROOT/'reports/amme-fab-memory-scheduler-gradient.json';baseline=json.loads(baseline_path.read_text());source=fe.verify_source();assert source==baseline['source'] and baseline['state']=='full_gradient_passed'
settings=load_settings({**baseline['settings'],'mutate_steps':2,'sequence_candidates':1,'kept_sequences':1,'enough_passing_sequences':1,'save_failed_refolds':True,'project_folder':str(folder/'COMPONENT_OUTPUT')});design=build_design_settings(settings);original,_,losses=initialize_design_trajectory(design,jax.random.PRNGKey(42));original=float32_states(original)
fixture=ROOT/'reports/amme-fab-memory-scheduler-gradient_target.cif';observed=Protein.from_structure(str(fixture));arrays=np.load(baseline_path.with_suffix('.npz'),allow_pickle=False);mapping={'target_target':'A','binder_0':'B','binder_1':'C'};states={};fixed={}
for state,chains in original.items():
 states[state]={}
 for name,protein in chains.items():
  known=observed[mapping[name]];positions=arrays[state+'_'+name+'_positions'];assert len(protein)==len(known) and positions.shape==protein.atoms.shape
  assert np.array_equal(np.asarray(protein.sequence).argmax(-1),np.asarray(known.sequence).argmax(-1)),name
  states[state][name]=protein.replace(atoms=jnp.asarray(positions,dtype=jnp.float32),atom_mask=known.atom_mask)
  fixed[name]=np.asarray(protein.sequence).argmax(-1)
assert {name:len(p) for name,p in states['target'].items()}=={'binder_0':231,'binder_1':213,'target_target':115}
if '--preflight' in sys.argv:
 print(json.dumps({'state':'component_fixture_preflight_passed','chains':{name:len(p) for name,p in states['target'].items()}}));raise SystemExit(0)
parameters=ROOT.parent/'models/alphafold';pool=tuple(baseline['originalModelSelection']['designModels']);validation=tuple(baseline['originalModelSelection']['validationModels']);base=model_class();inferences=[]
class ObservedModel(base):
 def _resolve_model_name(self,value):
  chosen=super()._resolve_model_name(value);self.last_resolved=chosen;return chosen
 def predict(self,protein_states,*args,**kwargs):
  before=time.monotonic();atomic_json(folder/'component-stage.json',{'stage':'prediction_started','completedPredictions':len(inferences),'states':list(protein_states),'requestedModel':kwargs.get('model'),'elapsedSeconds':time.monotonic()-start});value=super().predict(protein_states,*args,**kwargs)
  for prediction in value.values():jax.block_until_ready([p.atoms for p in prediction.protein_complex.values()])
  self.last_states=protein_states;inferences.append({'model':self.last_resolved,'requestedModel':kwargs.get('model'),'states':list(protein_states),'seconds':time.monotonic()-before});atomic_json(folder/'component-stage.json',{'stage':'prediction_completed','inferences':inferences,'elapsedSeconds':time.monotonic()-start});print('FOLD_COMPONENT '+json.dumps(inferences[-1]),flush=True);return value
model=ObservedModel(presets=pool,models=pool,data_dir=str(parameters),key=jax.random.PRNGKey(42),max_cache_size=1,num_recycle=settings['design_recycles'],subbatch_size=4,attention_backend='stock',use_cueq=False)
mutations={'proposals':0}
class ObservedSampler(SemigreedySequenceSampler):
 def propose_sequence_mutation(self,*args,**kwargs):mutations['proposals']+=1;return super().propose_sequence_mutation(*args,**kwargs)
with patch.object(trajectory,'SemigreedySequenceSampler',ObservedSampler):
 mutated,predicted,mutation_gate=trajectory.run_mutation_polish(design,model,states,original,losses,None,(),jax.random.PRNGKey(42),jax.random.PRNGKey(43),('target',),None)
assert mutations['proposals']==1
atomic_json(folder/'mutation-result.json',{'state':'executed','originalMutationGate':mutation_gate,'actualProposals':mutations['proposals'],'inferences':inferences,'scope':'Original single-target Fab mutation stage; retained original gate outcome, not production acceptance.'})
for name,p in mutated['target'].items():
 mask=~np.asarray(has_residue_flag(original['target'][name].flags,ResidueFlags.DESIGN));assert np.array_equal(np.asarray(p.sequence).argmax(-1)[mask],fixed[name][mask])
del model;jax.clear_caches()
validator=ObservedModel(presets=validation,models=validation,data_dir=str(parameters),key=jax.random.PRNGKey(42),max_cache_size=1,num_recycle=settings['validation_recycles'],dropout=False,subbatch_size=4,attention_backend='stock',use_cueq=False)
mpnn=ProteinMPNNSequenceModel(str(proteinmpnn_weights()),model_name=settings['mpnn_model'],variant=settings['mpnn_variant'],key=jax.random.PRNGKey(42),max_cache_size=1,amino_acid_bias=design.binder.amino_acid_bias)
mpnn_calls=[];original_candidates=mpnn.predict_candidates
# Observe the real decoder and assert every non-designed framework/context stays fixed.
def candidates(protein_states,*args,**kwargs):
 value=original_candidates(protein_states,*args,**kwargs)
 for result in value:
  for state,prediction in result.items():
   for name,protein in prediction.protein_complex.items():
    before=protein_states[state][name];mask=~np.asarray(has_residue_flag(before.flags,ResidueFlags.DESIGN));assert np.array_equal(np.asarray(protein.sequence).argmax(-1)[mask],np.asarray(before.sequence).argmax(-1)[mask])
 mpnn_calls.append(len(value));return value
mpnn.predict_candidates=candidates
output=folder/'COMPONENT_OUTPUT';output.mkdir();csv=output/'2_Refolded/!_Refolded.csv'
kept=redesign_and_validate_binders(predicted['target'].protein_complex,validator,mpnn,design,validation,binder=design.designed_binder_chain,target='target_target',prediction_state='target',target_states=original,predicted_states={name:value.protein_complex for name,value in predicted.items()},trajectory_seed=42,design='engineering_full_fab_fixture',candidates_csv=str(csv),project_folder=str(output))
assert mpnn_calls and csv.is_file();assert mutations['proposals']==1
from bindcraft.filters import design_stage_filters,evaluate_design_filters
additional_validation=[]
for heldout in validation:
 if any(item['model']==heldout for item in inferences):continue
 probe_states=validator.last_states;probe=validator.predict(probe_states,model=heldout);filters=design_stage_filters(design,probe_states,'final',campaign_filters=design.filters);outcome,metrics=evaluate_design_filters(filters,probe_states,probe)
 additional_validation.append({'model':heldout,'scope':'Separate downstream fixture inference after upstream short-circuit; does not override its original rejection.','filterOutcome':True if outcome is True else list(outcome)})
assert set(validation).issubset({item['model'] for item in inferences})
_,ranked,directions=rerank_campaign(str(output),['i_pDAE'],'candidates',output=str(folder/'engineering-candidate-rank.csv'));assert ranked
library=Service(folder/'INSPECTION_LIBRARY');project=library.project_create({'name':'Fab component validation · not production'});records=[]
for coordinate in (output/'2_Refolded/Complexes').glob('*.cif'):
 record=library.import_structure({'projectId':project['id'],'path':str(coordinate),'name':'Engineering Fab refold · acceptance not asserted','source':'Full Fab component validation · not a production campaign','metadata':{'engineeringValidation':{'fixtureSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'sourceRevision':fe.PIN,'scope':'Original downstream component test on genuine gradient fixture; no production-trajectory acceptance claim.'},'computationalAcceptance':'not_asserted'}});records.append(record['id'])
 assert (library.root/'assets'/record['data']['asset']).read_bytes()==coordinate.read_bytes()
assert records;library.export_project({'id':project['id'],'path':str(folder/'component-inspection-project.zip')});library.db.close()
report={'state':'passed','scope':'Separate full559-residue Fab component tests on an authentic single-gradient prediction fixture. The original trajectory was not completed or promoted past its filters. No full production or accepted-Fab claim.','fixture':str(fixture),'fixtureSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'source':source,'inputChainLengths':{k:len(v) for k,v in states['target'].items()},'subbatchSize':4,'mutationEvaluations':2,'postMutationRecheck':True,'originalMutationGate':mutation_gate,'actualMutationProposals':mutations['proposals'],'fixedFrameworkAndTargetRetained':True,'mpnnDecoderCalls':mpnn_calls,'validationModels':list(validation),'originalValidationRecycles':settings['validation_recycles'],'separateHeldoutProbes':additional_validation,'originalFiltersRetained':True,'sequenceCandidateBudget':1,'originalKeptCandidates':len(kept),'inferences':inferences,'rankedCandidateRows':len(ranked),'rankingDirections':directions,'inspectionRecords':records,'libraryCoordinateBytesExact':True,'wallSeconds':time.monotonic()-start,'fullOriginalScientificRunCompleted':False};assert fe.verify_source()==source;report_path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
