"""Compare native original scoring with direct source on a saved genuine complex."""
import argparse,hashlib,json,os,pathlib,shutil,sys,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.score import score_design
from campaign_scoring import SITE_METRICS
p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--directory',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);a=p.parse_args();source=pathlib.Path(a.source_root).resolve();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Choose a new isolated scoring root.')
shutil.copytree(source,root,symlinks=True);s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});job=s.job(a.job);output=root/'jobs'/job['id']/'output';original=source/'jobs'/job['id']/'output'
def hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
before=hashes(output);original_before=hashes(original)
try:
 result=s.dispatch('bindcraft_review',{'projectId':job['project_id'],'id':job['id'],'operation':'score','table':'accepted'});assert len(result['rows'])==1
 for row,detail in zip(result['rows'],result['structures']):
  values=score_design(str(output/'3_Ranked'/detail['file']),binder=detail['binderChains'],target=detail['targetChains']);expected={key:value for key,value in values.items() if key not in SITE_METRICS};actual={key:value for key,value in row.items() if key not in ('design','coordinate_sha256')};assert actual==expected,(actual,expected);assert row['coordinate_sha256']==before['3_Ranked/'+detail['file']];assert not set(actual)&SITE_METRICS
 assert hashes(output)==before and hashes(original)==original_before
 archive=root/'scoring-project.zip';s.export_project({'id':job['project_id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:assert z.read('jobs/'+job['id']+'/'+result['reviewFolder']+'/result.json')
 report={'state':'passed','scope':'Real saved accepted 175-residue hPDL1/binder coordinates rescored through actual original score_design. Shared/native operation exactly matches direct original metric values with explicit roles. Site metrics omitted; stamped validation-model readings remain separate; missing unbound/PAE metrics are unavailable. No model prediction or change to original acceptance.','root':str(root),'sourceRoot':str(source),'jobId':job['id'],'analysisId':result['analysisId'],'sourceUnchanged':True,'structures':result['structures'],'scoredRows':result['rows'],'archive':str(archive),'upstream':result['upstream']};pathlib.Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':'passed','rows':len(result['rows']),'geometryFields':len(result['rows'][0]),'sourceUnchanged':True}))
finally:s.db.close()
