"""Preset selection contracts; scientific objective validation is separate."""
import json,os,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import campaign_profile as cp
import fold_engine as fe
class CampaignPropertyContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def test_no_properties_preserve_the_existing_preparation_exactly(self):
  one=self.s.dispatch('bindcraft_validate',self.config);two=self.s.dispatch('bindcraft_validate',{**self.config,'properties':[]});self.assertEqual(one,two);self.assertNotIn('propertyPresets',one)
 def test_unknown_duplicates_and_wrong_types_are_refused_before_resolution(self):
  for names in (None,'humanize',['humanize','humanize'],['invented'],[['humanize']]):
   with self.subTest(names=names),patch.object(cp.subprocess,'run') as process:
    with self.assertRaises(ValueError):self.s.dispatch('bindcraft_validate',{**self.config,'properties':names})
    process.assert_not_called()
 def test_missing_scientific_runtime_cannot_fall_back_to_a_local_preset_merger(self):
  self.s.setting_set({'key':'bindcraftPython','value':str(self.base/'missing')})
  with self.assertRaisesRegex(ValueError,'scientific runtime is required'):self.s.dispatch('bindcraft_validate',{**self.config,'properties':['humanize']})
 def test_catalogue_matches_all_nine_pinned_original_property_files(self):
  catalog=self.engine.fold_engine_status({})['properties'];self.assertEqual(len(catalog),9)
  for entry in catalog:self.assertEqual(entry['sha256'],fe.checksum((fe.UPSTREAM/entry['source']).read_bytes()));self.assertEqual(entry['status'],'integrated_unvalidated')
 def test_original_resolver_failure_never_creates_a_prepared_job(self):
  self.s.setting_set({'key':'bindcraftPython','value':os.sys.executable})
  with patch.object(cp.subprocess,'run',return_value=type('Result',(),{'returncode':1,'stderr':'Original preset refusal'})()):
   with self.assertRaisesRegex(ValueError,'Original preset resolution refused'):self.s.dispatch('bindcraft_prepare',{**self.config,'properties':['humanize']})
  self.assertEqual(self.s.library({})['jobs'],[])
del Fixtures
