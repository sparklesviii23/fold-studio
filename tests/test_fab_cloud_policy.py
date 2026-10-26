"""Cloud-only Fab admission: no full-Fab calculation, weights or GPU used."""
import copy,json,os,pathlib,subprocess,sys,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'tests')]
import scientific_capabilities as cap
import bindcraft_cpu,campaign_recovery,campaign_repeat,fold_engine
from test_project_metal import ProjectMetalTests as Fixtures
from test_biology_pipeline import Fixture as BiologyFixture

class FabCloudPolicyTests(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def prepared_fab(self):return self.s.dispatch('bindcraft_prepare',{**{k:v for k,v in self.config.items() if k!='binderLengths'},'modality':'Fab'})
 def test_all_local_launch_recovery_and_repeat_profiles_fail_before_spawn_or_history_mutation(self):
  job=self.prepared_fab();before=copy.deepcopy(self.s.job(job['id']));folder=self.s.root/'jobs'/job['id'];files={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
  with patch.object(self.s,'spawn',side_effect=AssertionError('No local Fab worker')):
   for action in ('bindcraft_start','bindcraft_resume','bindcraft_repeat'):
    payload={'projectId':self.project['id'],'id':job['id']}
    if action=='bindcraft_start':payload['profile']='experimental-cpu-single-model'
    with self.subTest(action=action),self.assertRaisesRegex(ValueError,'cloud-only'):self.s.dispatch(action,payload)
  self.assertEqual(self.s.job(job['id']),before);self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()},files)
 def test_direct_native_worker_cannot_bypass_dispatch_with_a_saved_queued_job(self):
  job=self.prepared_fab();self.s.job_update(job['id'],'queued');before=self.s.job(job['id'])
  with patch('bindcraft_cpu.subprocess.run',side_effect=AssertionError('No scientific child')):
   with self.assertRaisesRegex(ValueError,'cloud-only'):bindcraft_cpu.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id']),before)
 def test_direct_runner_fails_before_jax_or_checkpoint_loading(self):
  settings=self.base/'fab-direct.json';settings.write_text(json.dumps({'modality':['Fab']}))
  result=subprocess.run([sys.executable,str(ROOT/'scientific/bindcraft_runner.py'),str(settings),str(self.base/'absent-weights'),'cpu'],capture_output=True,text=True,timeout=10)
  self.assertNotEqual(result.returncode,0);self.assertIn('cloud-only',result.stderr);self.assertNotIn('ModuleNotFoundError',result.stderr)
 def test_renamed_exact_fab_scaffold_is_recognized_without_chain_length_guessing(self):
  file=self.base/'renamed.cif';file.write_bytes((fold_engine.UPSTREAM/'scaffolds/Fab.cif').read_bytes())
  with self.assertRaisesRegex(ValueError,'cloud-only'):cap.require_local_settings_allowed({'binder_scaffold':str(file)},fold_engine.UPSTREAM)
  for format in ('VHH','scFv','ARP','binder','peptide'):self.assertFalse(cap.full_fab({'modality':format}))
 def test_heavy_redesign_of_a_known_fab_record_is_blocked_but_viewing_remains_available(self):
  job=self.prepared_fab();record=next(r for r in self.s.library({})['records'] if r['id']==self.record['id']);record['data']['metadata']={'campaignId':job['id']}
  with self.s.db:self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(record['data']),self.record['id']))
  with patch('mpnn.start',side_effect=AssertionError('No local inference')):
   with self.assertRaisesRegex(ValueError,'cloud-only'):self.s.dispatch('mpnn_start',{'projectId':self.project['id'],'structureId':self.record['id']})
  self.assertTrue(self.s.dispatch('fold_structure',{'projectId':self.project['id'],'structureId':self.record['id']})['structure']['atoms'])
 def test_local_small_protein_dispatch_and_read_only_history_are_preserved(self):
  with patch('mpnn.dispatch',return_value={'local':True}) as local:self.assertEqual(self.s.dispatch('mpnn_start',{}),{'local':True});local.assert_called_once()
  self.assertFalse(self.s.dispatch('execution_backend_get',{})['fullFab']['localExecutionAllowed'])

class FabCandidateAdmission(BiologyFixture):
 def stamp(self):
  record=self.s.rows('SELECT data FROM records WHERE id=?',(self.record['id'],))[0]
  data=json.loads(record['data']);data['metadata']['rapidCandidate']={'executionPolicy':{'domain':'full_fab','localExecutionAllowed':False}}
  with self.s.db:self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(data),self.record['id']))
 def test_candidate_only_launch_resolves_fab_provenance_before_creating_a_job(self):
  import biology_pipeline
  self.stamp();before=len(self.s.rows('SELECT id FROM jobs'))
  with patch.object(self.s,'spawn',side_effect=AssertionError('No local Fab controller')):
   with self.assertRaisesRegex(ValueError,'cloud-only'):biology_pipeline.start(self.s,self.params(approved=True))
  self.assertEqual(len(self.s.rows('SELECT id FROM jobs')),before)
 def test_old_queued_controller_cannot_bypass_provenance_check(self):
  import biology_pipeline
  manifest=biology_pipeline.plan(self.s,self.params());self.stamp()
  job=self.s.job_new({'projectId':self.project,'name':'Synthetic admission test','manifest':manifest},'bgmee','queued')
  before=self.s.job(job['id'])
  with self.assertRaisesRegex(ValueError,'cloud-only'):biology_pipeline.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id']),before)
 def test_cloud_preview_reuse_keeps_fab_provenance_without_changing_original_metadata(self):
  import base64,hashlib,cloud_monitor
  before=self.s.rows('SELECT data FROM records WHERE id=?',(self.record['id'],))[0]['data']
  raw=self.file.read_bytes();node={'scientificDomain':'full_fab','coordinates':{'format':'pdb','contentBase64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()},'generator':'synthetic_transport_fixture'}
  with patch('cloud_monitor.candidate',return_value=node):
   value=cloud_monitor.open_candidate(self.s,{'projectId':self.project,'campaignId':'fixture'},'a'*64)
  self.assertEqual(value['id'],self.record['id']);self.assertTrue(cap.record_is_fab(self.s,value['id'],self.project))
  self.assertEqual(self.s.rows('SELECT data FROM records WHERE id=?',(self.record['id'],))[0]['data'],before)
  with self.assertRaisesRegex(ValueError,'cloud-only'):cap.enforce(self.s,'mpnn_start',{'projectId':self.project,'structureId':value['id']})
  import zipfile
  archive=self.root/'synthetic-export.zip';self.s.export_project({'id':self.project,'path':str(archive)})
  with zipfile.ZipFile(archive) as package:domains=json.loads(package.read('project.json'))['scientificExecutionDomains']
  self.assertEqual(domains,[{'record_id':self.record['id'],'domain':'full_fab','source':'verified_cloud_preview:'+'a'*64}])

del Fixtures
del BiologyFixture
