"""Authentic original conformational configuration/state preflight, no AF2 model execution."""
import argparse,hashlib,json,os,pathlib,subprocess,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from bindcraft_cpu import execution_config
from campaign_profile import resource_estimate,ensemble_models
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--fragment',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated conformational-preflight root.')
s=Service(root);python=os.path.abspath(sys.executable);s.setting_set({'key':'bindcraftPython','value':python});project=s.project_create({'name':'Original conformational state preflight'});source=pathlib.Path(a.fragment).resolve();original=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Explicit preserved 12-residue hPDL1 derivative · technical state QA','source':'Observed fragment, no domain or epitope claim'});cases=[]
code='''
import sys,json,jax
sys.path.insert(0,sys.argv[2])
from bindcraft.settings import load_settings,campaign_over_presets,build_design_settings
from bindcraft.protein_preparation import initialize_design_trajectory
from bindcraft.trajectory import required_final_states
from bindcraft.target_schedule import build_design_schedule,InducedFitSchedule
config=json.loads(sys.argv[1]);settings=load_settings(config);expected=campaign_over_presets({'modality':config['modality']})
for key,value in expected.items():
 if key not in ('binder_lengths','modality'):assert config[key]==value,(key,config[key],value)
assert settings['aa_bias']['C']==0
assert settings['min_monomer_plddt_final']==0.7
assert settings['filters']['Binder_RMSD']['threshold'] is None
check='Induced_Fit_Interface_RMSD' if config['modality']=='induced_fit' else 'Induced_Fit_TM'
assert settings['filters'][check]['threshold']==(5.0 if config['modality']=='induced_fit' else 0.6)
design=build_design_settings(settings);states,copies,losses=initialize_design_trajectory(design,jax.random.PRNGKey(42));required=required_final_states(design,losses)
assert required==('binder_alone',)
schedule=build_design_schedule(design,states,losses,2,jax.random.PRNGKey(43));assert isinstance(schedule,InducedFitSchedule)
assert schedule.binder_shapes==(('target',),('binder_alone',))
print(json.dumps({'requiredAdditionalPredictionStates':required,'originalConformationSchedule':schedule.binder_shapes,'originalAcceptanceCheck':settings['filters'][check],'binderRmsdCheck':settings['filters']['Binder_RMSD'],'activeLossNames':list(losses),'presetMatchesOriginal':True,'implicitBinderPresetRetained':True}))
'''
try:
 for mode in ('induced_fit','fold_switch'):
  job=s.dispatch('bindcraft_prepare',{'projectId':project['id'],'structureId':record['id'],'name':'Original '+mode+' state preflight','modality':mode,'targetChains':['A'],'hotspots':[],'coldspots':[],'binderLengths':[60],'candidates':1,'attempts':1,'seed':42});folder=root/'jobs'/job['id'];original_config=job['data']['preparation']['config'];config,heldout=execution_config(original_config,folder);estimate=resource_estimate(python,config,ROOT/'vendor/bindcraft2');result=subprocess.run([python,'-I','-B','-c',code,json.dumps(config),str(ROOT/'vendor/bindcraft2')],capture_output=True,text=True,env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},timeout=60)
  if result.returncode:raise RuntimeError(result.stderr)
  actual=json.loads(result.stdout.splitlines()[-1]);assert estimate['additionalPredictionStates']==['binder_alone'];assert estimate['paddedResidues']*2<=192;assert (folder/'input.cif').read_bytes()==source.read_bytes();cases.append({'modality':mode,'jobId':job['id'],'state':'prepared_not_executed','originalStatePreflight':actual,'resourceEstimate':{**estimate,'aggregatePaddedResidues':estimate['paddedResidues']*2},'originalEnsembleSelection':ensemble_models(python,{**original_config,'targets':config['targets']},ROOT/'vendor/bindcraft2'),'singleModelDiagnosticHeldout':heldout,'sourceUnchanged':True})
 assert hashlib.sha256(source.read_bytes()).hexdigest()==original
 report={'state':'passed','scope':'Real original preset hierarchy, input/feature preparation, binder initialization, loss registration, bound/unbound schedule and final-state requirements. No trained model forward/gradient, conformational trajectory, free-fold correctness or binding validation is claimed. Separate CPU profile retains original filters but deliberately selects one design and one held-out model.','root':str(root),'sourceSha256':original,'cases':cases};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:s.db.close()
