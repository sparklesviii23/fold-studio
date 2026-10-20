"""Actual original filtering and archive round trip on saved genuine results."""
import argparse,hashlib,json,os,pathlib,shutil,sys,tempfile,zipfile
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--directory',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);p.add_argument('--engine-root');a=p.parse_args()
if a.engine_root:ROOT=pathlib.Path(a.engine_root).resolve(strict=True)
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')]
from worker import Service
from bindcraft.campaign_filter import refilter_campaign
from bindcraft.campaign_output import summarize_campaign
from bindcraft.rank import rerank_campaign,recorded_metrics,derive_sequence_metrics,derive_state_metrics,campaign_settings,design_rows
from campaign_review import manifest
source=pathlib.Path(a.source_root).resolve();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated validation root.')
shutil.copytree(source,root,symlinks=True)
s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)})
job=s.job(a.job);payload={'projectId':job['project_id'],'id':job['id']};output=root/'jobs'/job['id']/'output';original=source/'jobs'/job['id']/'output'
def hashes(folder):return {name:hashlib.sha256(raw).hexdigest() for name,raw in manifest(folder).items()}
before=hashes(output);untouched=hashes(original);summary=summarize_campaign(str(output),campaign=job['id']);expressions=['i_pTM>=0.83','i_pDAE<=0.5']
try:
 reviewed=s.dispatch('bindcraft_review',{**payload,'operation':'filter','table':'candidates','expressions':expressions})
 with tempfile.TemporaryDirectory() as directory:
  direct=pathlib.Path(directory)/'snapshot';shutil.copytree(output,direct)
  passed,rejected,report,_=refilter_campaign(str(direct),expressions=expressions,table='candidates',output=str(pathlib.Path(directory)/'filtered.csv'))
 assert reviewed['rows']==passed and reviewed['rejected']==rejected and reviewed['report']==report
 assert reviewed['usesOriginalCampaignFilters'] is False and hashes(output)==before
 assert len(passed)==2 and len(rejected)==1
 listed=s.dispatch('bindcraft_review',{**payload,'operation':'metrics','table':'candidates'})
 _,recorded=design_rows(str(output),'candidates');settings=campaign_settings(str(output));expected_directions={**recorded_metrics(recorded),**derive_sequence_metrics(recorded),**derive_state_metrics(recorded,settings)}
 assert listed['directions']==expected_directions
 ranked=s.dispatch('bindcraft_review',{**payload,'operation':'rank','table':'candidates','metrics':['i_pTM','i_pDAE'],'higher':True})
 with tempfile.TemporaryDirectory() as directory:
  direct=pathlib.Path(directory)/'snapshot';shutil.copytree(output,direct);_,rows,directions=rerank_campaign(str(direct),['i_pTM','i_pDAE'],'candidates',higher=True,output=str(pathlib.Path(directory)/'ranked.csv'))
 assert ranked['rows']==rows and ranked['directions']==directions
 from observatory import Observatory
 with patch.object(Observatory,'observatory_save',side_effect=RuntimeError('injected history persistence failure')):
  try:s.dispatch('bindcraft_review',{**payload,'operation':'archive'})
  except RuntimeError as error:assert 'injected' in str(error)
  else:raise AssertionError('Persistence failure should refuse the operation.')
 assert hashes(output)==before, 'Failed persistence did not restore the exact original stage.'
 assert any(json.loads(path.read_text()).get('state')=='rolled_back' for path in (root/'jobs'/job['id']/'reviews').glob('*/storage-receipt.json'))
 packed=s.dispatch('bindcraft_review',{**payload,'operation':'archive'})
 assert packed['logicalContentUnchanged'] and packed['storageReceipt']['state']=='applied'
 assert len(list((output/'1_Trajectories').glob('*.zip')))==len(packed['convertedPaths'])>0
 assert summarize_campaign(str(output),campaign=job['id'])==summary
 # A second compression must refuse without changing the first conversion.
 archived=hashes(output)
 try:s.dispatch('bindcraft_review',{**payload,'operation':'archive'})
 except ValueError:pass
 else:raise AssertionError('Empty duplicate archive action was not refused.')
 assert hashes(output)==archived
 restored=s.dispatch('bindcraft_review',{**payload,'operation':'unarchive'})
 assert restored['logicalContentUnchanged'] and hashes(output)==before
 assert s.job(job['id'])==job and hashes(original)==untouched
 assert summarize_campaign(str(output),campaign=job['id'])==summary
 destination=root/'verified-utilities-project.zip';s.export_project({'id':job['project_id'],'path':str(destination)})
 with zipfile.ZipFile(destination) as archive:
  for result in (reviewed,packed,restored):assert archive.read('jobs/'+job['id']+'/'+result['reviewFolder']+'/result.json')
  for result in (packed,restored):assert json.loads(archive.read('jobs/'+job['id']+'/'+result['reviewFolder']+'/storage-receipt.json'))['state']=='applied'
 evidence={'state':'passed','scope':'Actual original functions on a copy of genuine saved native175-residue ensemble campaign. No model rerun. Custom thresholds exactly match independent original code; archive/restore preserve every scientific byte, all original summary statistics, job state and accepted outputs. Original source QA root remains unchanged.','sourceRoot':str(source),'root':str(root),'jobId':job['id'],'expressions':expressions,'passingDesigns':[row['design'] for row in passed],'rejectedDesigns':[row['design'] for row in rejected],'packedPaths':packed['convertedPaths'],'restoredPaths':restored['convertedPaths'],'logicalFiles':packed['logicalFileCount'],'summaryRowsUnchanged':len(summary),'roundTripByteExact':True,'originalSourceUnchanged':True,'analysisIds':[result['analysisId'] for result in (reviewed,packed,restored)],'upstream':packed['upstream'],'exportedProject':str(destination)}
 pathlib.Path(a.report).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
finally:s.db.close()
