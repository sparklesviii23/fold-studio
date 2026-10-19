"""Compare saved campaign aggregation with the actual original implementation."""
import argparse,hashlib,json,os,pathlib,shutil,sys,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.campaign_output import summarize_campaign
p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--directory',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);a=p.parse_args();source=pathlib.Path(a.source_root).resolve();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated summary root.')
shutil.copytree(source,root,symlinks=True);s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});job=s.job(a.job);original=source/'jobs'/job['id']/'output';output=root/'jobs'/job['id']/'output'
def hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
before=hashes(original);copied=hashes(output)
try:
 result=s.dispatch('bindcraft_review',{'projectId':job['project_id'],'id':job['id'],'operation':'summary'});expected=summarize_campaign(str(output),campaign=job['id']);assert result['rows']==expected
 counts={row['metric']:row['mean'] for row in result['rows'] if row['scope']=='campaign'}
 assert counts['trajectories']==1 and counts['redesign_candidates']==3 and counts['accepted_designs']==1,counts
 assert hashes(original)==before and hashes(output)==copied
 archive=root/'summary-project.zip';s.export_project({'id':job['project_id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:assert z.read('jobs/'+job['id']+'/'+result['reviewFolder']+'/result.json')
 report={'state':'passed','scope':'Original summarize_campaign executed on a private snapshot of genuine saved native ensemble results. Every original count and statistical row exactly matches an independent direct source invocation; no model rerun or acceptance change.','jobId':job['id'],'root':str(root),'sourceRoot':str(source),'analysisId':result['analysisId'],'rows':result['rows'],'originalCountReadings':counts,'sourceUnchanged':True,'exportedReviewArchive':str(archive),'upstream':result['upstream']};pathlib.Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':'passed','rows':len(result['rows']),'counts':counts,'sourceUnchanged':True}))
finally:s.db.close()
