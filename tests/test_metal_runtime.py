"""Explicit backend/resource guards; mocked probes are not scientific results."""
import json,os,pathlib,unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import metal_runtime

class MetalRuntimeGuards(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 def test_missing_metal_runtime_cannot_queue(self):
  j=self.prepared()
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_METAL_PYTHON':'/missing/metal/python'}),patch.object(self.s,'spawn') as spawn:
   with self.assertRaisesRegex(ValueError,'Metal runtime is not installed'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id'],'profile':'experimental-metal-float32-single-model'})
   spawn.assert_not_called()
  self.assertEqual(self.s.job(j['id'])['state'],'prepared')
 def result(self,platform='metal',versions=None):
  return SimpleNamespace(returncode=0,stdout=json.dumps({'versions':versions or metal_runtime.PINS,'architecture':'arm64','memoryBytes':24*1024**3,'devices':[{'platform':platform,'kind':'test probe fixture'}]}),stderr='')
 def test_cpu_fallback_is_refused(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_METAL_PYTHON':os.sys.executable}),patch.object(metal_runtime.subprocess,'run',return_value=self.result('cpu')):
   self.assertIn('fallback refused',metal_runtime.probe(self.s)['error'])
 def test_incompatible_package_versions_are_refused(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_METAL_PYTHON':os.sys.executable}),patch.object(metal_runtime.subprocess,'run',return_value=self.result(versions={**metal_runtime.PINS,'metaljax':'0.0'})):
   self.assertIn('versions differ',metal_runtime.probe(self.s)['error'])
 def test_accepted_probe_is_bounded_and_explicit(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_METAL_PYTHON':os.sys.executable}),patch.object(metal_runtime.subprocess,'run',return_value=self.result()) as run:
   result=metal_runtime.probe(self.s)
   self.assertEqual(result['state'],'experimental');self.assertEqual(result['precision'],'float32')
   env=run.call_args.kwargs['env'];self.assertEqual(env['JAX_PLATFORMS'],'metal');self.assertEqual(env['METALJAX_MEM_BUDGET_MB'],'6144');self.assertEqual(env['PYTHONDONTWRITEBYTECODE'],'1')
 def test_changed_queued_settings_are_refused_before_model_execution(self):
  import bindcraft_cpu
  j=self.prepared();folder=self.s.root/'jobs'/j['id'];(folder/'execution-settings.json').write_text('{}')
  self.s.job_update(j['id'],'queued',{'runtime':os.sys.executable,'parameters':'/unused','execution':'metal','executionSettingsSha256':'invalid'})
  with patch.object(bindcraft_cpu.subprocess,'run') as run:bindcraft_cpu.run(self.s,j['id']);run.assert_not_called()
  self.assertEqual(self.s.job(j['id'])['state'],'failed');self.assertIn('settings changed',self.s.job(j['id'])['data']['error'])
 def test_ensemble_envelope_keeps_governor_and_system_limit_enabled(self):
  envelope=metal_runtime.environment('ensemble');self.assertEqual(envelope['METALJAX_MEM_GOVERNOR'],'1');self.assertEqual(envelope['METALJAX_MEM_BUDGET_MB'],'8192');self.assertEqual(envelope['METALJAX_MEM_SYS_MB'],metal_runtime.ENV['METALJAX_MEM_SYS_MB'])
  with self.assertRaises(ValueError):metal_runtime.environment('unlimited')
del Fixtures
