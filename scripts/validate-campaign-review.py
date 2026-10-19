"""Compare shared review actions with direct original code on genuine saved results."""
import argparse,hashlib,json,os,pathlib,shutil,sys,tempfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.rank import rerank_campaign
from bindcraft.campaign_filter import refilter_campaign
p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--directory',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);a=p.parse_args();source=pathlib.Path(a.source_root).resolve();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated review root.')
shutil.copytree(source,root,symlinks=True);s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});job=s.job(a.job);payload={'projectId':job['project_id'],'id':job['id']};output=root/'jobs'/job['id']/'output';original=source/'jobs'/job['id']/'output'
def hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
before=hashes(output);original_before=hashes(original)
try:
 tables=s.dispatch('bindcraft_results',payload);rank=s.dispatch('bindcraft_review',{**payload,'operation':'rank','table':'candidates','metrics':['i_pDAE']});filtered=s.dispatch('bindcraft_review',{**payload,'operation':'filter','table':'candidates'})
 with tempfile.TemporaryDirectory() as tmp:
  direct=pathlib.Path(tmp)/'snapshot';shutil.copytree(output,direct);_,expected_rank,_=rerank_campaign(str(direct),['i_pDAE'],'candidates',output=str(pathlib.Path(tmp)/'rank.csv'));expected_pass,expected_reject,expected_report,_=refilter_campaign(str(direct),table='candidates',output=str(pathlib.Path(tmp)/'filter.csv'))
 if rank['rows']!=expected_rank or filtered['rows']!=expected_pass or filtered['rejected']!=expected_reject or filtered['report']!=expected_report:raise AssertionError('Shared review differs from direct original BindCraft2 code.')
 if hashes(output)!=before or hashes(original)!=original_before:raise AssertionError('Review changed original scientific outputs.')
 if tables['tables']['accepted']['count']!=1 or tables['tables']['candidates']['count']!=3:raise AssertionError('Real accepted ensemble case differs from recorded outcome.')
 analysis_ids=[rank['analysisId'],filtered['analysisId']];saved=s.dispatch('observatory_library',{'projectId':job['project_id']})
 if not set(analysis_ids)<={x['id'] for x in saved}:raise AssertionError('Review history missing.')
 archive=root/'review-project.zip';s.export_project({'id':job['project_id'],'path':str(archive)})
 import zipfile
 with zipfile.ZipFile(archive) as z:
  for result in (rank,filtered):
   path='jobs/'+job['id']+'/'+result['reviewFolder']+'/result.json'
   if not z.read(path):raise AssertionError('Review provenance was not exported.')
 evidence={'state':'passed','scope':'Real previously completed accepted 175-residue ensemble campaign: original 1 trajectory / 3 independently refolded candidates / 1 accepted design inspected; shared table rank/filter results exactly match direct original pinned BindCraft2 functions on identical snapshots. No prediction rerun, no acceptance promotion, original outputs unchanged.','root':str(root),'sourceRoot':str(source),'jobId':job['id'],'stageRows':{k:v['count'] for k,v in tables['tables'].items()},'sourceUnchanged':True,'rankAnalysisId':rank['analysisId'],'filterAnalysisId':filtered['analysisId'],'rankedDesigns':[x['design'] for x in rank['rows']],'filterPassingDesigns':[x['design'] for x in filtered['rows']],'filterRejectedDesigns':[x['design'] for x in filtered['rejected']],'upstreamFilterReport':filtered['report'],'archive':str(archive),'upstream':rank['upstream']};pathlib.Path(a.report).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
finally:s.db.close()
