"""Real original option resolution and preflight, without changing acceptance thresholds or running models."""
import argparse,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.settings import campaign_over_presets,load_settings
from bindcraft_cpu import execution_config
from campaign_profile import resource_estimate
from campaign_options import verify_preparation
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated original-options QA root.')
s=Service(root);python=os.path.abspath(sys.executable);s.setting_set({'key':'bindcraftPython','value':python});project=s.project_create({'name':'Original scientific option hierarchy QA'});source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';sha=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source)});common={'projectId':project['id'],'structureId':record['id'],'name':'Original scientific option resolution','targetChains':['A'],'binderLengths':[60],'candidates':1,'attempts':1,'seed':42,'modality':'binder'};cases=[]
try:
 checks=[('binder',{'design_recycles':1,'validation_recycles':1,'design_dropout':False}),('binder',{'mpnn_variant':'positive','sequence_candidates':4,'kept_sequences':2}),('binder',{'aa_bias':{'W':0.1},'losses':{'interface_contacts':{'params':{'cutoff':8.0}}}}),('binder',{'autotune_loss_weights':True,'compile_next_length':False}),('induced_fit',{'weights_induced_fit_interface':.3}),('fold_switch',{'weights_induced_fit_global':.8})]
 for modality,values in checks:
  job=s.dispatch('bindcraft_prepare',{**common,'modality':modality,'scientificOptions':values});prep=job['data']['preparation'];verify_preparation(prep);config,_=execution_config(prep['config'],root/'jobs'/job['id']);expected=load_settings(campaign_over_presets({'modality':modality,**values}));actual=load_settings(config)
  for key in values:assert actual[key]==expected[key],(key,actual[key],expected[key])
  defaults=load_settings(campaign_over_presets({'modality':modality}));assert actual['filters']==defaults['filters'],'No QA case may relax scientific acceptance filters.';estimate=resource_estimate(python,config,ROOT/'vendor/bindcraft2');assert (root/'jobs'/job['id']/'input.pdb').read_bytes()==source.read_bytes();cases.append({'jobId':job['id'],'modality':modality,'originalResolutionMatches':True,'scientificOptionReceipt':prep['scientificOptions'],'resourceEstimate':estimate,'defaultFiltersUnchanged':True,'state':'prepared_not_executed'})
 refusals=[]
 for values in ({'unrecognized_science_option':1},{'losses':{'interface_contacts':{'params':{'unknown_cutoff':8}}}},{'filters':{'Unknown_Filter':{'threshold':1}}}):
  before=len(s.library({})['jobs'])
  try:s.dispatch('bindcraft_prepare',{**common,'scientificOptions':values})
  except ValueError as error:assert len(s.library({})['jobs'])==before;refusals.append({'options':values,'error':str(error),'noJobCreated':True})
  else:raise AssertionError('Original settings validator must refuse unknown options.')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
 report={'state':'passed','scope':'Actual original override hierarchy, strict original option/metric parameter validation, immutable recipes and input preflight. Default acceptance filters unchanged in every QA case. No new neural computations, sequence optimization or scientific acceptance claim.','root':str(root),'cases':cases,'refusals':refusals,'sourceUnchanged':True,'sourceSha256':sha};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','cases':len(cases),'refusals':len(refusals)}))
finally:s.db.close()
