"""Shared OpenMM workflow contracts; synthetic input is never a scientific result."""
import hashlib,json,os,pathlib,types,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w,pdb
import dynamics
from dynamics_runner import atom_identity

class DynamicsWorkflowContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def payload(self):return {'projectId':self.project['id'],'structureId':self.record['id'],'name':'Synthetic queue fixture','seed':42,'steps':20,'reportInterval':5}
 def queue(self):
  self.s.setting_set({'key':'openmmPython','value':os.sys.executable})
  with patch.object(self.s,'spawn',side_effect=lambda job,mode:job):return self.s.dispatch('dynamics_start',self.payload())
 def test_request_bounds_refuse_implicit_seed_unsupported_methods_and_excessive_frames(self):
  for extra in ({'seed':0},{'seed':True},{'steps':0},{'steps':5001},{'reportInterval':0},{'steps':1000,'reportInterval':1},{'steps':20,'reportInterval':3},{'platform':'Metal'},{'temperature':300},{'name':'bad\nname'}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):self.s.dispatch('dynamics_start',{**self.payload(),**extra})
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_queue_pins_source_request_runner_and_uses_shared_compute_lock(self):
  job=self.queue();self.assertEqual(job['engine'],'openmm');self.assertEqual(job['state'],'queued');self.assertEqual(self.s.active()['id'],job['id']);folder=self.s.root/'jobs'/job['id'];self.assertEqual((folder/'input.pdb').read_bytes(),self.file.read_bytes());self.assertEqual(hashlib.sha256((folder/'request.json').read_bytes()).hexdigest(),job['data']['requestSha256'])
  with self.assertRaisesRegex(ValueError,'Another local compute job'):self.s.dispatch('dynamics_start',self.payload())
 def test_saved_input_tampering_is_refused_before_launch_or_import(self):
  job=self.queue();(self.s.root/'jobs'/job['id']/'request.json').write_text('{}')
  with patch.object(dynamics.subprocess,'run') as process:dynamics.run(self.s,job['id']);process.assert_not_called()
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertEqual(len(self.s.library({})['records']),1)
 def test_runtime_failure_creates_no_partial_research_outputs(self):
  job=self.queue()
  with patch.object(dynamics.subprocess,'run',side_effect=RuntimeError('Synthetic runtime failure')):dynamics.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertEqual(self.s.job(job['id'])['data']['outputs'],[]);self.assertEqual(len(self.s.library({})['records']),1);self.assertIsNone(self.s.active())
 def test_common_cancel_retains_request_and_releases_compute_lock(self):
  job=self.queue();self.s.dispatch('job_cancel',{'id':job['id']});self.assertEqual(self.s.job(job['id'])['state'],'cancelled');self.assertIsNone(self.s.active());self.assertTrue((self.s.root/'jobs'/job['id']/'request.json').is_file())
 def test_missing_runtime_and_cross_project_inputs_create_no_job(self):
  self.s.setting_set({'key':'openmmPython','value':str(self.base/'missing')})
  with self.assertRaisesRegex(ValueError,'runtime is unavailable'):self.s.dispatch('dynamics_start',self.payload())
  other=self.s.project_create({'name':'Other'})
  with self.assertRaisesRegex(ValueError,'another project'):self.s.dispatch('dynamics_start',{**self.payload(),'projectId':other['id']})
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_ambiguous_nonprotein_and_missing_backbone_inputs_are_refused(self):
  for text in (pdb().replace(' ALA ',' UNL '),pdb().replace('   O ','  XX '),'MODEL        1\n'+pdb()+'ENDMDL\nMODEL        2\n'+pdb()+'ENDMDL\n'):
   self.file.write_text(text);record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file)})
   with self.subTest(text=text),self.assertRaises(ValueError):self.s.dispatch('dynamics_start',{**self.payload(),'structureId':record['id']})
 def test_native_resources_and_engine_actions_are_registered(self):
  root=pathlib.Path(w.__file__).parents[1];native=(root/'src-tauri/src/main.rs').read_text();resources=json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
  for action in dynamics.ACTIONS:self.assertIn('"'+action+'"',native)
  for file in ('dynamics.py','dynamics_runner.py'):self.assertIn('../scientific/'+file,resources)
  self.assertIn('../../runtime-build/python-openmm/',resources)
 def test_empty_insertion_codes_match_between_original_pdb_and_cif_readers(self):
  def atom(code):return types.SimpleNamespace(name='CA',residue=types.SimpleNamespace(chain=types.SimpleNamespace(id='A'),id='12',insertionCode=code))
  self.assertEqual(atom_identity(atom('')),atom_identity(atom(' ')));self.assertEqual(atom_identity(atom('A')),('A','12','A','CA'));self.assertNotEqual(atom_identity(atom('A')),atom_identity(atom('')))
del Fixtures
