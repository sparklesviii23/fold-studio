"""Native conformational launch boundaries; no generated switches in fixtures."""
import os,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import campaign_profile as cp

class ConformationalContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def job(self,mode='fold_switch',lengths=(60,)):
  job=self.s.dispatch('bindcraft_prepare',self.config);prep=job['data']['preparation'];prep['modality']=mode;prep['config']['binder_lengths']=list(lengths);self.s.job_update(job['id'],'prepared',{'preparation':prep});return self.s.job(job['id'])
 def start(self,job,profile='experimental-cpu-float32-conformational'):
  return self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':profile})
 def test_conformational_preset_requires_the_real_resolver_even_without_properties(self):
  for mode in ('induced_fit','fold_switch'):
   self.s.setting_set({'key':'bindcraftPython','value':str(self.base/'missing')})
   with patch.object(cp.subprocess,'run') as process:
    with self.assertRaisesRegex(ValueError,'scientific runtime is required'):self.s.dispatch('bindcraft_prepare',{**self.config,'modality':mode})
    process.assert_not_called()
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_ordinary_cpu_and_metal_profiles_cannot_omit_the_extra_state_budget(self):
  job=self.job()
  for profile in ('experimental-cpu-float32-single-model','experimental-metal-float32-single-model','experimental-cpu-float32-ensemble','experimental-cpu-float32-320'):
   with patch.object(self.s,'spawn') as process:
    with self.assertRaisesRegex(ValueError,'separate bounded CPU'):self.start(job,profile)
    process.assert_not_called()
  self.assertEqual(self.s.job(job['id'])['state'],'prepared')
 def test_plain_binder_cannot_borrow_the_conformational_profile(self):
  job=self.job('binder')
  with self.assertRaisesRegex(ValueError,'profile requires'):self.start(job)
 def test_variable_length_is_refused_before_runtime_or_checkpoint_loading(self):
  job=self.job(lengths=(60,100))
  with self.assertRaisesRegex(ValueError,'fixed binder length'):self.start(job)
 def test_unavailable_original_resolver_does_not_save_an_incomplete_binder_preset(self):
  self.s.setting_set({'key':'bindcraftPython','value':os.sys.executable})
  with patch.object(cp.subprocess,'run',return_value=type('Result',(),{'returncode':1,'stderr':'scientific import failure'})()):
   with self.assertRaisesRegex(ValueError,'Original preset resolution refused'):self.s.dispatch('bindcraft_prepare',{**self.config,'modality':'induced_fit'})
  self.assertEqual(self.s.library({})['jobs'],[])
 def test_extra_state_memory_is_budgeted_and_never_silently_dropped(self):
  valid={'paddedResidues':96,'additionalPredictionStates':['binder_alone']};self.assertEqual(cp.conformational_resources(valid)['aggregatePaddedResidues'],192);self.assertNotIn('aggregatePaddedResidues',valid)
  with self.assertRaisesRegex(ValueError,'192 aggregate'):cp.conformational_resources({**valid,'paddedResidues':128})
  for states in (None,[],['target']):
   with self.assertRaisesRegex(ValueError,'expected unbound'):cp.conformational_resources({**valid,'additionalPredictionStates':states})
del Fixtures
