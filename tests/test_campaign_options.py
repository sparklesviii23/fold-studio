"""Explicit original option input/receipt boundaries; no relaxed scientific QA runs."""
import json,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import campaign_options as options
import fold_engine as fe
class ScientificOptions(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def test_empty_options_preserve_original_preparation_without_new_runtime_requirement(self):
  self.assertEqual(self.s.dispatch('bindcraft_validate',self.config),self.s.dispatch('bindcraft_validate',{**self.config,'scientificOptions':{}}))
 def test_input_lifecycle_and_unbounded_state_changes_cannot_bypass_native_controls(self):
  for key in ('targets','project_folder','max_trajectories','campaign_seed','design_workers','design_models','binder_scaffold','copies','binder_shapes','weights_induced_fit_global','idr_crop_count','humanize'):
   with self.subTest(key=key),patch('campaign_profile.subprocess.run') as process:
    with self.assertRaisesRegex(ValueError,'Use native'):self.s.dispatch('bindcraft_prepare',{**self.config,'scientificOptions':{key:True}})
    process.assert_not_called()
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_unmeasured_dimensions_checkpoint_names_and_malformed_options_are_refused(self):
  for value in ([],False,{'design_recycles':4},{'validation_recycles':True},{'subbatch_size':None},{'subbatch_size':8},{'screen_steps':201},{'mpnn_model':'/external/model.npz'},{'mpnn_variant':'unknown'},{'binder_name':'../../outside'},{'binder_name':'bad\nname'},{'filters':'/external/filters.json'},{'crop_fasta_sequence':[1,1000000000]},{'losses':{'plddt_loss':{'params':{'prediction_state':'invented'}}}}):
   with self.subTest(value=value),self.assertRaises(ValueError):options.validate(value,fe.UPSTREAM)
  with self.assertRaises(ValueError):options.validate({'weights_compactness':float('nan')},fe.UPSTREAM)
 def test_original_numeric_objectives_and_nested_settings_survive_as_explicit_values(self):
  values={'design_recycles':1,'validation_recycles':3,'mpnn_variant':'positive','losses':{'interface_contacts':{'params':{'cutoff':8.0}}},'aa_bias':{'W':0.1}}
  self.assertEqual(options.validate(values,fe.UPSTREAM),values)
 def test_modified_option_receipt_or_effective_configuration_is_refused(self):
  values={'aa_bias':{'W':0.1}};prep={'config':{'aa_bias':{'W':0.1,'C':0}},'scientificOptions':{'values':values,'sha256':fe.checksum(fe.canonical(values).encode())}};options.verify_preparation(prep)
  prep['config']['aa_bias']['W']=0.2
  with self.assertRaisesRegex(ValueError,'option receipt'):options.verify_preparation(prep)
  prep['config']['aa_bias']['W']=0.1;prep['scientificOptions']['sha256']='changed'
  with self.assertRaisesRegex(ValueError,'option receipt'):options.verify_preparation(prep)
 def test_original_autotuning_and_compile_policy_have_explicit_boolean_values(self):
  self.assertEqual(options.validate({'autotune_loss_weights':True,'compile_next_length':False},fe.UPSTREAM),{'autotune_loss_weights':True,'compile_next_length':False})
  for key in ('autotune_loss_weights','compile_next_length'):
   for value in (1,'true',None,[]):
    with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'true or false'):options.validate({key:value},fe.UPSTREAM)
 def test_conformational_weights_require_the_native_conformational_state_adapter(self):
  values={'weights_induced_fit_interface':.3,'weights_induced_fit_global':.5}
  for modality in ('induced_fit','fold_switch'):self.assertEqual(options.validate(values,fe.UPSTREAM,modality),values)
  for modality in (None,'binder','peptide'):
   with self.subTest(modality=modality),self.assertRaisesRegex(ValueError,'Use native'):options.validate(values,fe.UPSTREAM,modality)
  for value in (True,float('inf'),'0.5'):
   with self.subTest(value=value),self.assertRaises(ValueError):options.validate({'weights_induced_fit_global':value},fe.UPSTREAM,'fold_switch')
 def test_native_bundle_carries_the_option_validation_adapter(self):
  root=pathlib.Path(__file__).parents[1];self.assertIn('../scientific/campaign_options.py',json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
 def test_trajectory_retention_choices_are_explicit_booleans(self):
  for key in ('save_design_trajectory','save_failed_trajectories'):
   for value in (True,False):self.assertEqual(options.validate({key:value},fe.UPSTREAM,'Fab'),{key:value})
   for value in (1,'false',None,[]):
    with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'true or false'):options.validate({key:value},fe.UPSTREAM,'Fab')
del Fixtures
