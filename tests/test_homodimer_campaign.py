"""Native original two-copy campaigns preserve tying semantics and validation pools."""
import json,os,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
from bindcraft_cpu import execution_config

class HomodimerCampaignContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def config_homodimer(self):return {**self.config,'modality':'homo_oligomer','binderLengths':[12]}
 def test_two_copies_and_original_scientific_filters_are_saved(self):
  result=self.s.dispatch('bindcraft_prepare',self.config_homodimer());prep=result['data']['preparation'];preset=json.loads((w.fold_engine.UPSTREAM/'settings/modality/homo_oligomer.json').read_text())
  self.assertEqual(prep['config']['copies'],2);self.assertEqual(prep['config']['min_monomer_plddt_final'],preset['min_monomer_plddt_final']);self.assertEqual(prep['config']['filters'],preset['filters']);self.assertEqual(prep['config']['binder_lengths'],[12]);self.assertFalse(prep['executionReady']);self.assertIn('per chain',' '.join(prep['warnings']))
 def test_original_multimer_default_is_preserved_without_explicit_preset_pool(self):
  prep=self.s.dispatch('bindcraft_validate',self.config_homodimer());config,held_out=execution_config(prep['config'],pathlib.Path('/synthetic/unused'))
  self.assertEqual(config['validation_model'],'multimer');self.assertEqual(held_out,'model_2_multimer_v3');self.assertNotIn(held_out,config['design_models']);self.assertEqual(config['copies'],2)
  self.assertEqual(execution_config({'copies':2,'targets':[],'validation_model':'monomer'},pathlib.Path('/unused'))[1],'model_1_ptm')
  with self.assertRaisesRegex(ValueError,'Unknown upstream'):execution_config({'copies':2,'targets':[],'validation_model':'invalid_fixture'},pathlib.Path('/unused'))
 def test_limits_count_both_copies_before_reading_models_or_spawning(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config_homodimer(),'binderLengths':[130]})
  with patch.object(self.s,'spawn') as spawn:
   with self.assertRaisesRegex(ValueError,'256 total residues'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-single-model'})
   spawn.assert_not_called()
  self.assertEqual(self.s.job(job['id'])['state'],'prepared')
 def test_copy_count_and_unvalidated_symmetry_overrides_are_not_silently_accepted(self):
  for extra in ({'copies':3},{'oligomer_tie':'none'},{'ignore_symmetry':True}):
   with self.assertRaisesRegex(ValueError,'Unsupported'):self.s.dispatch('bindcraft_prepare',{**self.config_homodimer(),**extra})
del Fixtures
