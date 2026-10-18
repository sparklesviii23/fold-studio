"""Repeats keep all immutable scientific inputs and preserve the original job."""
import json,pathlib,unittest,zipfile
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w

class CampaignRepeatContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 def repeat(self,job,**extra):return self.s.dispatch('bindcraft_repeat',{'id':job['id'],'projectId':self.project['id'],**extra})
 def test_failed_run_copies_exact_inputs_and_never_starts_compute(self):
  original=self.prepared();self.s.job_update(original['id'],'failed',{'error':'Synthetic engine failure fixture'});before=self.s.job(original['id'])
  with patch.object(self.s,'spawn') as spawn:child=self.repeat(before);spawn.assert_not_called()
  self.assertNotEqual(child['id'],before['id']);self.assertEqual(child['state'],'prepared');self.assertEqual(child['data']['outputs'],[]);self.assertNotIn('error',child['data']);self.assertEqual(self.s.job(before['id']),before)
  self.assertEqual(child['data']['preparation']['config'],before['data']['preparation']['config']);self.assertEqual((self.s.root/'jobs'/child['id']/'input.pdb').read_bytes(),(self.s.root/'jobs'/before['id']/'input.pdb').read_bytes());self.assertEqual(child['data']['repeatOf']['changedScientificFields'],[])
 def test_explicit_seed_is_the_only_changed_scientific_field(self):
  job=self.prepared();child=self.repeat(job,seed=123,name='New seed comparison');original=job['data']['preparation']['config'];new=child['data']['preparation']['config'];self.assertEqual({**original,'campaign_seed':123},new);self.assertEqual(child['data']['repeatOf']['originalSeed'],original['campaign_seed']);self.assertEqual(child['data']['repeatOf']['changedScientificFields'],['campaign_seed']);self.assertNotEqual(child['data']['preparation']['settingsSha256'],job['data']['preparation']['settingsSha256'])
 def test_scaffold_and_all_additional_target_snapshots_survive_repeat_and_export(self):
  config={**{k:v for k,v in self.config.items() if k!='binderLengths'},'modality':'VHH'}
  other=self.base/'secondary.pdb';other.write_text(self.file.read_text().replace('1.450','1.451'));second=self.s.import_structure({'projectId':self.project['id'],'path':str(other)});config['additionalTargets']=[{'structureId':second['id'],'targetChains':['A'],'objective':'detarget','weight':.5}]
  job=self.s.dispatch('bindcraft_prepare',config);child=self.repeat(job);p=child['data']['preparation'];self.assertEqual(p['config']['targets'][1]['weight'],-.5)
  for name in ('input.pdb','target2.pdb','scaffold.cif'):self.assertEqual((self.s.root/'jobs'/job['id']/name).read_bytes(),(self.s.root/'jobs'/child['id']/name).read_bytes())
  archive=self.base/'repeated-project.zip';self.s.export_project({'id':self.project['id'],'path':str(archive)})
  with zipfile.ZipFile(archive) as z:self.assertEqual(json.loads(z.read('jobs/'+child['id']+'/provenance.json'))['repeatedFrom']['campaignId'],job['id']);self.assertIn('jobs/'+child['id']+'/scaffold.cif',z.namelist())
 def test_tampered_target_or_settings_is_refused_before_child_creation(self):
  for file in ('input.pdb','settings.json'):
   job=self.prepared();folder=self.s.root/'jobs'/job['id'];(folder/file).write_text('{}');count=len(self.s.library({})['jobs'])
   with self.assertRaises(ValueError):self.repeat(job)
   self.assertEqual(len(self.s.library({})['jobs']),count)
 def test_running_cross_project_invalid_seed_or_override_cannot_repeat(self):
  job=self.prepared()
  for extra in ({'seed':True},{'seed':-1},{'seed':float('nan')},{'name':''},{'ignore_filters':True}):
   with self.assertRaises(ValueError):self.repeat(job,**extra)
  other=self.s.project_create({'name':'Other'})
  with self.assertRaises(ValueError):self.s.dispatch('bindcraft_repeat',{'id':job['id'],'projectId':other['id']})
  self.s.job_update(job['id'],'running')
  with self.assertRaisesRegex(ValueError,'current run'):self.repeat(job)
 def test_revision_mismatch_does_not_silently_rebase_prepared_science(self):
  job=self.prepared();job['data']['preparation']['upstream']['revision']='different-fixture-pin';self.s.job_update(job['id'],'prepared',{'preparation':job['data']['preparation']})
  with self.assertRaisesRegex(ValueError,'revision differs'):self.repeat(job)
 def test_native_registration_includes_code_resource_and_ipc(self):
  root=pathlib.Path(w.__file__).parents[1];self.assertIn('"bindcraft_repeat"',(root/'src-tauri/src/main.rs').read_text());self.assertIn('../scientific/campaign_repeat.py',json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
del Fixtures
