"""Rank and transport genuine rejected Fab refold artifacts without model inference."""
import hashlib,json,pathlib,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')];sys.dont_write_bytecode=True
from bindcraft.rank import rerank_campaign
from bindcraft.protein import Protein
from worker import Service
import fold_engine as fe
source=fe.verify_source();original=ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT'
coordinate=original/'2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif';table=original/'2_Refolded/!_Refolded.csv'
inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [coordinate,table]}
root=ROOT.parent/'validation/architect-fab-component-artifacts'
if root.exists():raise SystemExit('Choose a fresh artifact-validation directory.')
root.mkdir();_,rows,directions=rerank_campaign(str(original),['i_pDAE'],'candidates',output=str(root/'engineering-rejected-candidate-rank.csv'))
assert len(rows)==1 and rows[0]['outcome']=='rejected'
lengths={k:len(p) for k,p in Protein.from_structure(str(coordinate)).items()};assert lengths=={'A':115,'B':231,'C':213}
s=Service(root/'library')
try:
 project=s.project_create({'name':'Fab component inspection · not a production result'})
 record=s.import_structure({'projectId':project['id'],'path':str(coordinate),'name':'Engineering full Fab refold · rejected by original i_pTM filter','source':'Genuine original ProteinMPNN/model2 Fab fixture test; not a completed production campaign','metadata':{'engineeringValidation':{'scope':'Saved actual rejected refold from separate downstream full559-residue fixture test. Original mutation/trajectory gate not bypassed for acceptance.','source':source,'inputSha256':inputs,'chainLengths':lengths},'computationalAcceptance':'not_asserted','originalCandidateOutcome':'rejected'}})
 assert (s.root/'assets'/record['data']['asset']).read_bytes()==coordinate.read_bytes()
 archive=root/'component-inspection-project.zip';s.export_project({'id':project['id'],'path':str(archive)})
 with zipfile.ZipFile(archive) as z:assert z.read('assets/'+record['data']['asset'])==coordinate.read_bytes()
 assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==v for p,v in inputs.items())
 report={'state':'passed','scope':'Original candidate-table ranking and exact Research Library/project transport of one genuine rejected fullFab model2refold fixture. No model run, fullmodel2/4ensemble, acceptedFab or completedproduction claim.','source':source,'inputSha256':inputs,'chainLengths':lengths,'rankedRows':len(rows),'originalOutcome':'rejected','rankingDirections':directions,'recordId':record['id'],'libraryCoordinateBytesExact':True,'projectArchiveBytesExact':True,'sourceArtifactsUnchanged':True,'fullFabComplete':False,'fullSizeCacheFixVerified':False}
 (ROOT/'reports/architect-fab-component-artifacts.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','rows':len(rows),'chainLengths':lengths}))
finally:s.db.close()
