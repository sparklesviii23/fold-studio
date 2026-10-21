import base64,hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker')]
from worker import Service
from cloud_compute import CloudCompute
from rapid_remote import RapidRemote,ACTIVATE,INSTALL
from fold_rapid.store import Store

class RapidBridgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.service=Service(self.root);self.project=self.service.project_create({'name':'Isolated RAPID bridge fixture'})['id'];self.cloud=CloudCompute(self.service)
  self.id=self.cloud.gpu_profile_save({'name':'Fixture','provider':'custom','host':'fixture.invalid','port':22,'username':'root','keyPath':''})['id'];self.remote=RapidRemote(self.cloud,self.service)
 def tearDown(self):self.service.db.close();self.tmp.cleanup()
 def test_deployment_scripts_compile(self):compile(INSTALL,'install','exec');compile(ACTIVATE,'activate','exec')
 def test_core_transfer_requires_approval(self):
  with self.assertRaisesRegex(ValueError,'Approve'):self.remote.gpu_rapid_install({'id':self.id})
 def test_research_transfer_requires_approval(self):
  with self.assertRaisesRegex(ValueError,'Approve'):self.remote.gpu_rapid_submit({'id':self.id})
 def test_local_target_inspection_does_not_contact_server(self):
  record=self.service.import_structure({'projectId':self.project,'path':str(ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb')})
  with patch.object(self.cloud,'ssh',side_effect=AssertionError('No remote contact permitted')):
   value=self.remote.gpu_rapid_target({'targetId':record['id']})
  self.assertFalse(value['researchTransferred']);self.assertEqual(value['chains'][0]['residues'],115)
 def test_remote_call_protocol_identity(self):
  def wrong(entry,command,request,**kw):return {'apiVersion':2,'requestId':'different','result':{}}
  with patch.object(self.cloud,'ssh',side_effect=wrong),self.assertRaisesRegex(ValueError,'identity mismatch'):self.remote.call(self.cloud.profile(self.id),'health',{})
 def test_generic_submit_cannot_bypass_library_snapshot_approval(self):
  with self.assertRaisesRegex(ValueError,'dedicated'):self.remote.gpu_rapid_call({'id':self.id,'operation':'job_submit'})
 def test_export_stream_checksum_and_atomic_failure(self):
  raw=b'actual fixture package bytes';sha=hashlib.sha256(raw).hexdigest();path=self.root/'result.zip'
  def call(entry,op,p):
   if op=='artifact_list':return {'artifacts':[{'path':'results.zip','bytes':len(raw),'sha256':sha}]}
   return {'offset':0,'contentBase64':base64.b64encode(raw).decode(),'chunkSha256':sha}
  with patch.object(self.remote,'call',side_effect=call):result=self.remote.gpu_rapid_export({'id':self.id,'jobId':'a'*32,'path':str(path)})
  self.assertEqual(path.read_bytes(),raw);self.assertEqual(result['sha256'],sha)
  def broken(entry,op,p):
   v=call(entry,op,p)
   if op=='artifact_read':v['chunkSha256']='0'*64
   return v
  with patch.object(self.remote,'call',side_effect=broken),self.assertRaisesRegex(ValueError,'checksum'):self.remote.gpu_rapid_export({'id':self.id,'jobId':'a'*32,'path':str(path)})
  self.assertEqual(path.read_bytes(),raw);self.assertFalse(list(self.root.glob('*.partial')))
 def test_events_tail_and_cursor(self):
  # Uses a real persisted job created from the genuine public coordinate fixture.
  sys.path.insert(0,str(ROOT/'tests'));from test_rapid_worker import fixture
  store=Store(self.root/'remote');id=store.submit(fixture(),'events')['jobId']
  for i in range(140):store.event(id,{'kind':'fixture_event','number':i})
  tail=store.events(id);self.assertEqual(len(tail),100);self.assertEqual(tail[-1]['number'],139)
  first=store.events(id,0);self.assertLess(first[-1]['cursor'],tail[-1]['cursor']);self.assertTrue(store.events(id,first[-1]['cursor']))
 def test_sequence_only_candidate_import_is_lossless_and_idempotent(self):
  # Protocol fixture only: not a new ProteinMPNN model prediction.
  raw=b'>candidate_0|chain=B|fixed_backbone\nACDE\n>candidate_0|chain=C|fixed_backbone\nFGHI\n'
  candidate={'candidateId':'c'*64,'generator':'proteinmpnn','upstreamId':'sequence-0','binderSequence':'ACDE/FGHI','coordinates':None,'outcome':'sequence_redesigned','metrics':{'fastaArtifact':'output/sequence-0.fasta'}}
  def call(entry,op,p):
   if op=='candidate_list':return {'candidates':[candidate]}
   if op=='artifact_list':return {'artifacts':[{'path':'output/sequence-0.fasta','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]}
   return {'offset':0,'contentBase64':base64.b64encode(raw).decode(),'chunkSha256':hashlib.sha256(raw).hexdigest()}
  payload={'id':self.id,'jobId':'a'*32,'projectId':self.project}
  with patch.object(self.remote,'call',side_effect=call):
   first=self.remote.gpu_rapid_import(payload);second=self.remote.gpu_rapid_import(payload)
  self.assertEqual([r['data']['sequence'] for r in first['records']],['ACDE','FGHI'])
  self.assertEqual([r['id'] for r in first['records']],[r['id'] for r in second['records']])
  self.assertTrue(all(r['kind']=='sequence' and not r['data']['origin']['structurePredicted'] for r in first['records']))
  candidate['binderSequence']='ACDE/WRONG'
  with patch.object(self.remote,'call',side_effect=call),self.assertRaisesRegex(ValueError,'FASTA differs'):self.remote.gpu_rapid_import(payload)
 def test_artifact_read_cannot_overrun_advertised_size(self):
  raw=b'oversized'
  with patch.object(self.remote,'call',return_value={'offset':0,'contentBase64':base64.b64encode(raw).decode(),'chunkSha256':hashlib.sha256(raw).hexdigest()}),self.assertRaisesRegex(ValueError,'integrity'):
   self.remote.receive_artifact({},'a'*32,'fixture',{'fixture':{'bytes':1,'sha256':'0'*64}})

if __name__=='__main__':unittest.main()
