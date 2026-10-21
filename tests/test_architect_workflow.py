"""Real recipe preparation/receipt guards; these tests perform no model calculation."""
import json,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
from bindcraft_cpu import failure_from_log,fab_subbatch
class ArchitectWorkflow(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def fab(self,**extra):return {**{k:v for k,v in self.config.items() if k!='binderLengths'},'modality':'Fab','candidates':1,'attempts':1,**extra}
 def test_engineering_recipe_is_distinct_and_preserves_original_scaffold_and_science(self):
  original=self.s.dispatch('bindcraft_prepare',self.fab());short=self.s.dispatch('bindcraft_prepare',self.fab(validationMode='engineering'));a=original['data']['preparation'];b=short['data']['preparation'];receipt=b['engineeringValidation'];keys=receipt['workloadOverrides']
  self.assertEqual(receipt['originalRecipeSha256'],a['settingsSha256']);self.assertNotEqual(b['settingsSha256'],a['settingsSha256']);self.assertIn('Engineering validation',short['name'])
  self.assertEqual({k:v for k,v in a['config'].items() if k not in keys},{k:v for k,v in b['config'].items() if k not in keys})
  self.assertEqual((self.s.root/'jobs'/original['id']/'scaffold.cif').read_bytes(),(self.s.root/'jobs'/short['id']/'scaffold.cif').read_bytes());self.assertNotIn('engineeringValidation',a)
  for key in ('screen_steps','refine_steps','anneal_steps','harden_steps'):self.assertEqual(b['config'][key],1)
  self.assertEqual(b['config']['mutate_steps'],2)
  self.assertEqual(json.loads((self.s.root/'jobs'/short['id']/'provenance.json').read_text())['engineeringValidation'],receipt)
 def test_engineering_mode_never_silently_changes_production_or_an_unbounded_workload(self):
  for extra in ({'validationMode':'invented'},{'validationMode':'engineering','attempts':20},{'validationMode':'engineering','modality':'peptide','binderLengths':[12]}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):self.s.dispatch('bindcraft_prepare',self.fab(**extra))
 def test_original_failure_diagnostic_does_not_classify_all_peptide_failures_as_memory(self):
  self.assertIsNone(failure_from_log('Exit code 1'))
  error=failure_from_log('jax.errors.JaxRuntimeError: RESOURCE_EXHAUSTED: metaljax out of memory at flush: over6.0GB METALJAX_MEM_BUDGET_MB')
  self.assertEqual(error['category'],'metal_memory_limit');self.assertFalse(error['retryIsAutomatic'])
  self.assertEqual(failure_from_log('ValueError: Unknown chain B')['category'],'upstream_exception')
 def test_faster_chunk_policy_preserves_frozen_recovery_and_explicit_slow_policy(self):
  self.assertEqual(fab_subbatch({}),4);self.assertEqual(fab_subbatch({'subbatch_size':'auto'}),4)
  self.assertEqual(fab_subbatch({'subbatch_size':1}),1)
  self.assertEqual(fab_subbatch({}, {'settings':{'subbatch_size':1}}),1)
  for value in (True,2,3,None):
   with self.subTest(value=value),self.assertRaises(ValueError):fab_subbatch({'subbatch_size':value})
del Fixtures
