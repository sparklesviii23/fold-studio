"""Runtime discovery and signed-bundle bytecode contracts, no inference mocks."""
import json,os,pathlib,tempfile,unittest
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
