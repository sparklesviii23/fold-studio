"""Original large-binder/multidomain preparation and runtime input preflight only."""
import argparse,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from bindcraft_cpu import execution_config
from campaign_profile import resource_estimate,ensemble_models
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--fragment',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated extended-format preparation root.')
s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});project=s.project_create({'name':'Original extended-format input QA'});source=pathlib.Path(a.fragment).resolve();original=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Previously preserved explicit 12-residue official hPDL1 fragment · technical QA only','source':'Explicit observed derivative; no biological epitope/domain claim'});cases=[]
try:
 for modality,length in [('large_binder',250),('multidomain',120)]:
  job=s.dispatch('bindcraft_prepare',{'projectId':project['id'],'structureId':record['id'],'name':'Original '+modality+' input QA','modality':modality,'targetChains':['A'],'hotspots':[],'coldspots':[],'binderLengths':[length],'candidates':1,'attempts':1,'seed':42});folder=root/'jobs'/job['id'];original_config=job['data']['preparation']['config'];config,heldout=execution_config(original_config,folder);estimate=resource_estimate(os.path.abspath(sys.executable),config,ROOT/'vendor/bindcraft2');selection=ensemble_models(os.path.abspath(sys.executable),{**original_config,'targets':config['targets']},ROOT/'vendor/bindcraft2');preset=json.loads((ROOT/'vendor/bindcraft2/settings/modality'/f'{modality}.json').read_text())
  for key,value in preset.items():
   if key not in ('description','binder_lengths'):assert original_config[key]==value,(key,modality)
  assert (folder/'input.cif').read_bytes()==source.read_bytes();assert estimate['paddedResidues']<=320;cases.append({'modality':modality,'jobId':job['id'],'state':'prepared_not_executed','explicitBinderLength':length,'upstreamPreset':preset,'resourceEstimate':estimate,'originalEnsembleSelection':selection,'singleModelDiagnosticHeldout':heldout,'sourceUnchanged':True})
 assert hashlib.sha256(source.read_bytes()).hexdigest()==original
 report={'state':'passed','scope':'Two real original extended-format preparations retain every original preset field, explicitly chosen fixed lengths and observed fragment coordinates. Actual original input/feature preflight and ensemble selection execute without model inference. New optional 320-residue CPU profile is bounded from existing 320-residue AF2 CPU forward/gradient and scaffold pipeline evidence; extended-format full design trajectories are not yet validated. No biological domain/epitope, folding or binding claim.','root':str(root),'sourceSha256':original,'cases':cases};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','cases':[(x['modality'],x['resourceEstimate'],x['originalEnsembleSelection']) for x in cases]},indent=2))
finally:s.db.close()
