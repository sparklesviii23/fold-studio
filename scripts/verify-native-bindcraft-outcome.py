"""Verify the actual isolated packaged campaign and its exported immutable results."""
import argparse,hashlib,json,pathlib,sys,zipfile
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from bindcraft_provenance import native_receipt
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--job',required=True);p.add_argument('--app',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.root).resolve();app=pathlib.Path(a.app).resolve();s=Service(root);job=s.job(a.job);data=job['data'];folder=root/'jobs'/job['id'];output=folder/'output'
def hashes():return {str(file.relative_to(output)):hashlib.sha256(file.read_bytes()).hexdigest() for file in output.rglob('*') if file.is_file()}
before=hashes()
try:
 assert job['state']=='completed' and data['outcome']=='accepted_predictions' and len(data['outputs'])==1
 assert pathlib.Path(data['runtime']).is_relative_to(app) and pathlib.Path(data['parameters']).is_relative_to(app)
 assert not s.setting('bindcraftPython') and not s.setting('af2Parameters')
 metadata=json.loads((output/'campaign_metadata.json').read_text());receipt=native_receipt(s,job,output,metadata);assert receipt['state']=='native_receipts_verified';assert receipt['execution']=='metal'
 table=s.dispatch('bindcraft_results',{'projectId':job['project_id'],'id':job['id']});counts={name:value['count'] for name,value in table['tables'].items()};assert counts=={'trajectories':1,'candidates':3,'accepted':1};assert all(row['outcome']=='passed' for row in table['tables']['candidates']['rows'])
 record_id=data['outputs'][0];inspected=s.dispatch('intelligence_inspect',{'structureId':record_id});record=inspected['record'];assert len(inspected['structure']['residues'])==175;assert sorted(chain['residues'] for chain in inspected['structure']['chains'])==[60,115];assert record['data']['confidenceKind']=='BindCraft2 AlphaFold2 pLDDT';assert record['data']['metadata']['provenanceMatch']=='native_receipts_verified';raw=(root/'assets'/record['data']['asset']).read_bytes();assert hashlib.sha256(raw).hexdigest()==record['data']['sha256'];assert len(inspected['confidence']['plddt'])==175
 s.record_update({'id':record_id,'projectId':job['project_id'],'name':'Native packaged ensemble acceptance · hPDL1–binder','notes':'Actual native app-owned Metal runtime and checkpoints; one trajectory, three passed refolds, best one retained by original ranking. Computational prediction; no biological binding validation.'})
 archive=root/'native-bindcraft-accepted-project.zip';s.export_project({'id':job['project_id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:
  assert z.read('jobs/'+job['id']+'/runtime-provenance.json');assert z.read('jobs/'+job['id']+'/output/3_Ranked/!_Ranked.csv')
 assert hashes()==before
 prior=json.loads(pathlib.Path(a.report).read_text()) if pathlib.Path(a.report).exists() else {}
 prior.update(state='native_computational_pipeline_passed',root=str(root),jobId=job['id'],app=str(app),stageRows=counts,claimedProgress=table['claimedProgress'],modelSelection=data['modelSelection'],runtime=data['runtime'],parameters=data['parameters'],runtimeReceipt=receipt['runtime'],nativeReceiptState=receipt['state'],outputRecordId=record_id,outputSha256=record['data']['sha256'],outputAtoms=len(inspected['structure']['atoms']),outputResidues=len(inspected['structure']['residues']),confidenceMeanByChain=inspected['confidence']['meanByChain'],acceptedRow=table['tables']['accepted']['rows'][0],refoldRows=table['tables']['candidates']['rows'],archive=str(archive),originalOutputsUnchanged=True,scope='Actual native launch of complete packaged full original ensemble campaign on 115-residue official hPDL1 + 60-residue binder: design/hallucination, real ProteinMPNN, two held-out AF2 model validations, original filters, source ranking and native verified library import. Three candidate refolds passed; upstream kept the best one. No biological binding claim; full upstream option/modality parity and updated bundle UI acceptance remain pending.')
 pathlib.Path(a.report).write_text(json.dumps(prior,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':prior['state'],'stageRows':counts,'recordId':record_id,'runtimeSeconds':receipt['runtime']['totalSeconds'],'archive':str(archive)}))
finally:s.db.close()
