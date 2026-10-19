"""Original extended-format settings and explicit bounded CPU launch guards."""
import json,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
class ExtendedModalityContracts(unittest.TestCase):
 _fixture_setup=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def config(self,modality,**extra):return {**{k:v for k,v in self.config_base.items() if k!='binderLengths'},'modality':modality,**extra}
 def setUp(self):
  self._fixture_setup();self.config_base=self.config;del self.config
 def test_default_lengths_and_original_domain_and_optimization_objectives_survive(self):
  for name,lengths in [('large_binder',[250,600]),('multidomain',[120,300])]:
   result=self.s.dispatch('bindcraft_validate',self.config(name));self.assertEqual(result['config']['binder_lengths'],lengths);preset=json.loads((pathlib.Path(__file__).parents[1]/'vendor/bindcraft2/settings/modality'/f'{name}.json').read_text())
   for key,value in preset.items():
    if key not in ('description','binder_lengths'):self.assertEqual(result['config'][key],value)
 def test_extended_inputs_are_prepared_without_starting_or_changing_coordinates(self):
  for name in ('large_binder','multidomain'):
   with patch.object(self.s,'spawn') as process:job=self.s.dispatch('bindcraft_prepare',self.config(name,binderLengths=[250]));process.assert_not_called()
   self.assertEqual(job['state'],'prepared');self.assertEqual((self.s.root/'jobs'/job['id']/'input.pdb').read_bytes(),self.file.read_bytes())
 def test_320_profile_refuses_variable_length_scaffold_and_unmeasured_dimensions(self):
  for name,lengths in [('binder',[60,100]),('large_binder',[600]),('homo_oligomer',[60])]:
   job=self.s.dispatch('bindcraft_prepare',self.config(name,binderLengths=lengths))
   with patch.object(self.s,'spawn') as process:
    with self.assertRaisesRegex(ValueError,'fixed-length|320'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-320'})
    process.assert_not_called()
   self.assertEqual(self.s.job(job['id'])['state'],'prepared')
 def test_larger_profile_refuses_an_unmeasured_smaller_host_before_model_loading(self):
  job=self.s.dispatch('bindcraft_prepare',self.config('binder',binderLengths=[60]))
  with patch('bindcraft_cpu.platform.system',return_value='Darwin'),patch('bindcraft_cpu.platform.machine',return_value='arm64'),patch('bindcraft_cpu.subprocess.check_output',return_value=str(16*1024**3)),patch.object(self.s,'spawn') as process:
   with self.assertRaisesRegex(ValueError,'24 GiB'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-320'})
   process.assert_not_called()
 def test_regular_profile_does_not_silently_borrow_the_larger_cpu_limit(self):
  job=self.s.dispatch('bindcraft_prepare',self.config('large_binder',binderLengths=[300]))
  with self.assertRaisesRegex(ValueError,'256'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-single-model'})
  self.assertEqual(self.s.job(job['id'])['state'],'prepared')
del Fixtures
