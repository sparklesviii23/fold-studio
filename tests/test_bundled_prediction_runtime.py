"""Runtime discovery and signed-bundle bytecode contracts, no inference mocks."""
import json,os,pathlib,signal,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_project_metal import w

class BundledPredictionRuntime(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=w.Service(self.tmp.name)
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def test_bundled_runtime_discovered_without_install(self):
  with patch.object(pathlib.Path,'is_file',return_value=True):self.assertTrue(self.s.engine_python().endswith('/runtime-boltz/bin/python3.12'))
 def test_explicit_existing_runtime_preference_retained(self):
  self.s.setting_set({'key':'enginePython','value':'/explicit/scientific/python'})
  with patch.object(pathlib.Path,'is_file',return_value=True):self.assertEqual(self.s.engine_python(),'/explicit/scientific/python')
 def test_legacy_managed_environment_fallback_retained(self):
  with patch.object(pathlib.Path,'is_file',return_value=False):self.assertEqual(self.s.engine_python(),str(self.s.root/'engine/venv/bin/python'))
 def test_synchronous_compute_probe_cannot_write_signed_runtime_bytecode(self):
  probe=SimpleNamespace(returncode=0,stdout=json.dumps({'installed':True,'mpsAvailable':True,'version':'transport fixture'}))
  with patch.object(pathlib.Path,'is_file',return_value=True),patch.object(w.subprocess,'run',return_value=probe) as run:
   self.s.compute_for(os.sys.executable)
  self.assertEqual(run.call_args.args[0][1],'-B')
 def test_inference_redirects_numba_cache_outside_signed_app(self):
  # Stop at the process boundary: no mocked inference is counted as acceptance.
  import boltz_resources
  project=self.s.project_create({'name':'Cache boundary fixture'})
  job=self.s.job_new({'projectId':project['id'],'chains':[{'sequence':'AAA'}],'msa':'single','recycles':1,'steps':10,'samples':1,'seed':42},'boltz2','queued')
  (self.s.root/'jobs'/job['id']).mkdir();old_handler=signal.getsignal(signal.SIGTERM)
  try:
   with patch.object(boltz_resources,'ensure_checkpoint',return_value={}),patch.object(boltz_resources,'fingerprints',return_value={}),patch.object(w.subprocess,'run',return_value=SimpleNamespace(returncode=1)) as run:
    with self.assertRaisesRegex(RuntimeError,'Boltz exited'):w.execute_job(self.s,job['id'])
   self.assertEqual(run.call_args.kwargs['env']['NUMBA_CACHE_DIR'],str(self.s.root/'engine/cache/numba'))
   provenance=json.loads((self.s.root/'jobs'/job['id']/'provenance.json').read_text())
   self.assertEqual(provenance['environment']['NUMBA_CACHE_DIR'],str(self.s.root/'engine/cache/numba'))
   self.assertEqual(self.s.job(job['id'])['state'],'failed')
  finally:signal.signal(signal.SIGTERM,old_handler)
