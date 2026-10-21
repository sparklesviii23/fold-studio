"""Inspect genuine saved stage coordinates and original Fab output settings.

No model calculation or fabricated acceptance. All writes use an isolated copy.
"""
import argparse,hashlib,json,os,pathlib,shutil,sys,zipfile
sys.dont_write_bytecode=True
REPO=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--directory',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);p.add_argument('--engine-root');a=p.parse_args()
ENGINE=pathlib.Path(a.engine_root).resolve(strict=True) if a.engine_root else REPO
sys.path[:0]=[str(ENGINE/'scientific'),str(ENGINE/'vendor/bindcraft2')]
from worker import Service
from bindcraft.settings import load_settings
from bindcraft.design_identity import design_setting_values
source=pathlib.Path(a.source_root).resolve(strict=True);root=pathlib.Path(a.directory).absolute()
if root.exists():raise SystemExit('Choose a new isolated coordinate validation root.')
def hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and not p.is_symlink()}
shutil.copytree(source,root,symlinks=True);s=Service(root)
try:
 s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)})
 job=s.job(a.job);payload={'projectId':job['project_id'],'id':job['id']};output=root/'jobs'/job['id']/'output';original=source/'jobs'/job['id']/'output'
 before=hashes(output);source_before=hashes(original);outcomes=s.dispatch('bindcraft_results',payload);saved=[]
 for stage in ('trajectories','candidates'):
  table=outcomes['tables'][stage]
  for row in table['rows'][:100]:
   for entry in table['coordinates'].get(row['design'],[]):
    request={**payload,'operation':'save_coordinates','table':stage,'design':row['design'],'file':entry['file'],'sha256':entry['sha256']}
    result=s.dispatch('bindcraft_review',request);record=result['record'];info=record['data']
    assert (root/'assets'/info['asset']).read_bytes()==(output/entry['file']).read_bytes()
    assert 'not accepted' in record['name'] and info['metadata']['campaignStagePreview']['computationalAcceptance']=='not_asserted'
    assert info['confidenceKind'] is None and 'nativeRun' not in info['metadata']
    assert s.dispatch('bindcraft_review',request)['record']['id']==record['id']
    saved.append({'stage':stage,'design':row['design'],'recordId':record['id'],'asset':info['asset'],'sha256':entry['sha256']})
 assert saved and s.job(job['id'])==job and hashes(output)==before and hashes(original)==source_before
 archive=root/'stage-inspection-project.zip';s.export_project({'id':job['project_id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  for entry in saved:assert hashlib.sha256(z.read('assets/'+entry['asset'])).hexdigest()==entry['sha256']
 target=s.import_structure({'projectId':job['project_id'],'path':str(ENGINE/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb')})
 prepared=[]
 reference=load_settings({'modality':'Fab'})
 for keep in (True,False):
  options={'save_design_trajectory':keep,'save_failed_trajectories':keep}
  original_options=load_settings({'modality':'Fab',**options})
  assert design_setting_values(reference)==design_setting_values(original_options), 'Output choices changed original scientific design identity.'
  fresh=s.dispatch('bindcraft_prepare',{'projectId':job['project_id'],'structureId':target['id'],'name':'Fab output-retention validation','modality':'Fab','targetChains':['A'],'candidates':1,'attempts':1,'seed':42,'scientificOptions':options})
  prep=fresh['data']['preparation'];settings=root/'jobs'/fresh['id']/'settings.json';config=json.loads(settings.read_text())
  assert {key:config[key] for key in options}==options and prep['scientificOptions']['values']==options
  assert config['design_models']==3 and config['validation_model']=='multimer'
  assert (settings.parent/'scaffold.cif').read_bytes()==(ENGINE/'vendor/bindcraft2/scaffolds/Fab.cif').read_bytes()
  prepared.append({'jobId':fresh['id'],'keepTrajectoryCoordinates':keep,'settingsSha256':prep['settingsSha256']})
 evidence={'state':'passed','scope':'Genuine saved standard-binder stage structures, exact library/project transport and original Fab output-only settings. No model rerun, accepted-Fab or rejected-Fab execution claim. Synthetic refusal/rollback cases are covered separately by unit tests.','sourceRoot':str(source),'root':str(root),'engineRoot':str(ENGINE),'jobId':job['id'],'originalJobUnchanged':True,'originalCoordinatesUnchanged':True,'projectExportByteExact':True,'stageSnapshots':saved,'newFabPreparation':prepared,'originalDesignIdentityUnchanged':True,'packagedRuntime':sys.version.split()[0],'fullFabCampaignComplete':False}
 pathlib.Path(a.report).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps({'state':'passed','savedSnapshots':len(saved),'newFabPreparations':len(prepared),'report':a.report}))
finally:s.db.close()
