"""Synthetic protocol outputs only; authentic execution is qualified separately."""
import copy,json,pathlib,sys,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'tests')]
import mpnn,mpnn_results as results
from test_mpnn import MPNNTests as Fixture


class ResultContracts(unittest.TestCase):
 def request(self):
  return {'input':'software-fixture.pdb','sha256':'a'*64,'sequences':{'A':'ACDE','B':'ACDE'},'designChains':['A'],'count':2,'seed':7,'temperature':.1,'variant':'neutral','constraints':{'residues':{ch:[{'aminoAcid':aa,'design':ch=='A' and i in (2,4),'excluded':'Y' if i==2 else ''} for i,aa in enumerate('ACDE',1)] for ch in ('A','B')},'omitAminoAcids':'W','tiedChains':[]}}
 def output(self,request):return {'schemaVersion':1,'execution':'cpu','settings':copy.deepcopy(request),'sourceSha256':request['sha256'],'checkpointSha256':'b'*64,'candidates':[{'chains':{'A':'AKDL','B':'ACDE'},'metrics':{'score':.8,'seqid':.5}} for _ in range(2)]}
 def test_complete_context_fixed_positions_and_sequence_provenance_are_retained(self):
  request=self.request();output=self.output(request);samples=results.validate(output,request,'b'*64)
  rows=results.summarize(samples,'job','c'*64,'d'*64,['A'])
  self.assertEqual(rows[0]['chains'],{'A':'AKDL'});self.assertEqual(rows[0]['fixedContextChains'],['B'])
  self.assertNotEqual(rows[0]['candidateId'],rows[1]['candidateId']);self.assertEqual(rows[1]['duplicateOfSample'],1)
  self.assertIsNone(rows[0]['duplicateOfSample']);self.assertFalse(rows[0]['structurePredicted']);self.assertTrue(rows[0]['requiresFreshStructuralPrediction'])
 def test_invalid_context_length_alphabet_fixed_and_excluded_residues_are_refused(self):
  request=self.request()
  for chains in ({'A':'AKDL'},{'A':'AKDL','B':'AAAA'},{'A':'AKD','B':'ACDE'},{'A':'AKDX','B':'ACDE'},{'A':'VKDL','B':'ACDE'},{'A':'AWDL','B':'ACDE'},{'A':'AYDL','B':'ACDE'}):
   output=self.output(request);output['candidates'][0]['chains']=chains
   with self.subTest(chains=chains),self.assertRaises(ValueError):results.validate(output,request,'b'*64)
 def test_ties_are_verified_again_after_the_model_returns(self):
  request=self.request();request['designChains']=['A','B'];request['constraints']['residues']['B']=copy.deepcopy(request['constraints']['residues']['A']);request['constraints']['tiedChains']=[['A','B']]
  with self.assertRaisesRegex(ValueError,'tied-chain'):results.validate(self.output(request),request,'b'*64)
 def test_different_model_settings_sample_count_and_nonfinite_metrics_are_refused(self):
  request=self.request()
  for key,value in [('execution','metal'),('schemaVersion',True),('checkpointSha256','e'*64),('sourceSha256','e'*64),('settings',{}),('candidates',[])]:
   output=self.output(request);output[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):results.validate(output,request,'b'*64)
  for value in (float('nan'),float('inf'),True,'0.9'):
   output=self.output(request);output['candidates'][0]['metrics']['score']=value
   with self.assertRaises(ValueError):results.validate(output,request,'b'*64)


class ImportAdmission(unittest.TestCase):
 setUp=Fixture.setUp
 tearDown=Fixture.tearDown
 def queued(self):
  with patch.dict('os.environ',{'FOLD_BINDCRAFT_PYTHON':sys.executable}),patch.object(self.s,'spawn',side_effect=lambda job,mode:job):return self.s.dispatch('mpnn_start',self.p)
 def test_queue_snapshots_request_runner_and_existing_checkpoint_before_spawn(self):
  job=self.queued();data=job['data'];file=self.s.root/'jobs'/job['id']/'request.json'
  self.assertEqual(mpnn.fe.checksum(file.read_bytes()),data['requestSha256']);self.assertEqual(len(data['runnerSha256']),64);self.assertEqual(len(data['checkpointSha256']),64)
 def test_request_code_source_and_checkpoint_drift_are_refused_before_model_execution(self):
  for key in ('runnerSha256','sourceManifestSha256','checkpointSha256','requestSha256'):
   job=self.queued();self.s.job_metadata(job['id'],{key:'0'*64})
   with patch('mpnn.subprocess.run',side_effect=AssertionError('No model execution after drift')):mpnn.run(self.s,job['id'])
   self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertFalse(self.s.job(job['id'])['data']['outputs'])
 def test_mismatched_runtime_result_cannot_import_sequences(self):
  job=self.queued();folder=self.s.root/'jobs'/job['id']
  def returned(*args,**kwargs):
   request=json.loads((folder/'request.json').read_text());output={'schemaVersion':1,'execution':'cpu','settings':request,'sourceSha256':'0'*64,'checkpointSha256':job['data']['checkpointSha256'],'candidates':[]};(folder/'result.json').write_text(json.dumps(output));return type('Exit',(),{'returncode':0})()
  with patch('mpnn.subprocess.run',side_effect=returned):mpnn.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertEqual(len(self.s.library({})['records']),1)
 def test_request_mutation_during_execution_cannot_leave_a_successful_import(self):
  job=self.queued();folder=self.s.root/'jobs'/job['id']
  def mutated(*args,**kwargs):
   with (folder/'request.json').open('a') as stream:stream.write('\n')
   return type('Exit',(),{'returncode':0})()
  with patch('mpnn.subprocess.run',side_effect=mutated):mpnn.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertEqual(len(self.s.library({})['records']),1)

del Fixture
