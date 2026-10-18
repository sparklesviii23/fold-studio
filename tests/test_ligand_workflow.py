"""Workflow contracts use synthetic inputs; real RDKit evidence is separate."""
import hashlib,json,os,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
import ligand

class LigandWorkflowContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def payload(self):return {'projectId':self.project['id'],'name':'Synthetic workflow QA','smiles':'CCO','seed':42,'conformers':3}
 def queue(self):
  self.s.setting_set({'key':'enginePython','value':os.sys.executable})
  with patch.object(self.s,'spawn',side_effect=lambda job,mode:job):return self.s.dispatch('ligand_start',self.payload())
 def test_only_bounded_explicit_inputs_are_accepted(self):
  for extra in ({'name':'bad\nname'},{'smiles':''},{'smiles':'CCO trailing_name'},{'seed':True},{'seed':-1},{'conformers':9},{'conformers':0},{'neutralize':True}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):self.s.dispatch('ligand_start',{**self.payload(),**extra})
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_queue_saves_exact_request_and_registers_common_local_compute_lock(self):
  job=self.queue();self.assertEqual(job['engine'],'rdkit');self.assertEqual(job['state'],'queued');self.assertEqual(self.s.active()['id'],job['id']);self.assertEqual(job['data']['outputs'],[])
  raw=(self.s.root/'jobs'/job['id']/'request.json').read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),job['data']['requestSha256']);self.assertEqual(json.loads(raw)['smiles'],'CCO')
  with self.assertRaisesRegex(ValueError,'Another local compute job'):self.s.dispatch('ligand_start',self.payload())
 def test_changed_queued_input_is_refused_before_any_rdkit_process_or_import(self):
  job=self.queue();(self.s.root/'jobs'/job['id']/'request.json').write_text('{}')
  with patch.object(ligand.subprocess,'run') as process:ligand.run(self.s,job['id']);process.assert_not_called()
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertEqual(self.s.job(job['id'])['data']['outputs'],[])
  self.assertEqual(len(self.s.library({})['records']),1)
 def test_common_cancel_releases_compute_lock_without_deleting_saved_request(self):
  job=self.queue();self.s.dispatch('job_cancel',{'id':job['id']});self.assertIsNone(self.s.active());self.assertEqual(self.s.job(job['id'])['state'],'cancelled');self.assertTrue((self.s.root/'jobs'/job['id']/'request.json').is_file())
 def test_missing_runtime_does_not_create_a_job(self):
  self.s.setting_set({'key':'enginePython','value':str(self.base/'missing-runtime')})
  with self.assertRaisesRegex(ValueError,'runtime is unavailable'):self.s.dispatch('ligand_start',self.payload())
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_sdf_export_checks_project_and_actual_saved_hash_before_overwriting(self):
  data=self.record['data'];file=self.s.root/'assets'/'synthetic-test-only.sdf';file.write_text('SYNTHETIC EXPORT HASH FIXTURE; not a molecule.');data['metadata']['ligand']={'sdfAsset':file.name,'sdfSha256':hashlib.sha256(file.read_bytes()).hexdigest()};self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(data),self.record['id']));self.s.db.commit();output=self.base/'export.sdf';payload={'projectId':self.project['id'],'structureId':self.record['id'],'path':str(output)}
  self.s.dispatch('ligand_export',payload);self.assertEqual(output.read_bytes(),file.read_bytes());file.write_text('changed');output.write_text('keep destination')
  with self.assertRaisesRegex(ValueError,'checksum changed'):self.s.dispatch('ligand_export',payload)
  self.assertEqual(output.read_text(),'keep destination');archive=self.base/'existing.zip';archive.write_bytes(b'keep existing archive')
  with self.assertRaisesRegex(ValueError,'checksum changed'):self.s.export_project({'id':self.project['id'],'path':str(archive)})
  self.assertEqual(archive.read_bytes(),b'keep existing archive');self.assertFalse(list(self.base.glob('.existing.zip.*.tmp')));other=self.s.project_create({'name':'Other'})
  with self.assertRaisesRegex(ValueError,'in this project'):self.s.dispatch('ligand_export',{**payload,'projectId':other['id']})
 def test_coordinate_integrity_failure_preserves_existing_archive(self):
  archive=self.base/'old-project.zip';archive.write_bytes(b'keep previous archive');(self.s.root/'assets'/self.record['data']['asset']).write_bytes(b'changed coordinate source')
  with self.assertRaisesRegex(ValueError,'checksum changed'):self.s.export_project({'id':self.project['id'],'path':str(archive)})
  self.assertEqual(archive.read_bytes(),b'keep previous archive');self.assertFalse(list(self.base.glob('.old-project.zip.*.tmp')))
 def test_jobs_are_scoped_to_project_and_native_resources_are_registered(self):
  job=self.queue();other=self.s.project_create({'name':'Other'});self.assertEqual(self.s.dispatch('ligand_jobs',{'projectId':other['id']}),[]);self.assertEqual(self.s.dispatch('ligand_jobs',{'projectId':self.project['id']})[0]['id'],job['id'])
  root=pathlib.Path(w.__file__).parents[1];native=(root/'src-tauri/src/main.rs').read_text();resources=json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
  for action in ligand.ACTIONS:self.assertIn('"'+action+'"',native)
  for file in ('ligand.py','ligand_runner.py'):self.assertIn('../scientific/'+file,resources)
del Fixtures
