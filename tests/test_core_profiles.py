"""Source-owned core hierarchy and explicit selection boundaries."""
import unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import campaign_profile as cp
import fold_engine as fe
class CoreProfiles(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def test_reserved_core_names_are_not_offered_as_active_layers(self):
  entries=self.engine.fold_engine_status({})['coreProfiles'];self.assertEqual([entry['name'] for entry in entries],['benchmark']);self.assertEqual(entries[0]['sha256'],fe.checksum((fe.UPSTREAM/entries[0]['source']).read_bytes()))
 def test_absent_core_preserves_existing_preparation(self):
  self.assertEqual(self.s.dispatch('bindcraft_validate',self.config),self.s.dispatch('bindcraft_validate',{**self.config,'core':None}))
 def test_unsupported_or_reserved_core_never_silently_falls_back(self):
  for core in ('invented','default','reference','',True,[],['benchmark']):
   with self.subTest(core=core),patch.object(cp.subprocess,'run') as process:
    with self.assertRaisesRegex(ValueError,'original selectable core'):self.s.dispatch('bindcraft_prepare',{**self.config,'core':core})
    process.assert_not_called()
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_original_runtime_required_for_benchmark_precedence(self):
  self.s.setting_set({'key':'bindcraftPython','value':str(self.base/'missing')})
  with self.assertRaisesRegex(ValueError,'scientific runtime is required'):self.s.dispatch('bindcraft_validate',{**self.config,'core':'benchmark'})
del Fixtures
