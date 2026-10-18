"""Integrity/status API fixtures are synthetic bytes, never trained model outputs."""
import hashlib,os,pathlib,tempfile,unittest
from unittest.mock import patch
from test_project_metal import w
import boltz_resources as resources

class ModelStatusContracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=w.Service(self.tmp.name);self.cache=self.s.root/'engine/models';self.cache.mkdir();self.file=self.cache/'boltz2_conf.ckpt';self.raw=b'SYNTHETIC integrity fixture only';self.pin={'file':self.file.name,'bytes':len(self.raw),'sha256':hashlib.sha256(self.raw).hexdigest()};self.pin_patch=patch.object(resources,'model_pin',return_value=self.pin);self.pin_patch.start()
 def tearDown(self):self.pin_patch.stop();self.s.db.close();self.tmp.cleanup()
 def check(self,verify=False):return self.s.dispatch('prediction_resources',{'verify':verify})['checkpoint']
 def test_default_status_does_not_hash_large_models_or_claim_verification(self):
  self.file.write_bytes(self.raw)
  with patch.object(resources,'file_digest') as digest:self.assertEqual(self.check()['state'],'present_unverified');digest.assert_not_called()
 def test_explicit_verification_matches_actual_file_hash_without_modifying_cache(self):
  self.file.write_bytes(self.raw);self.assertEqual(self.check(True)['state'],'verified');self.assertEqual(self.file.read_bytes(),self.raw)
  self.file.write_bytes(b'X'*len(self.raw));self.assertEqual(self.check(True)['state'],'checksum_mismatch');self.assertEqual(self.file.read_bytes(),b'X'*len(self.raw))
 def test_missing_partial_and_placeholder_states_do_not_start_downloads(self):
  with patch.object(resources.urllib.request,'urlopen') as download:
   self.assertEqual(self.check()['state'],'missing');self.file.with_suffix('.partial').write_bytes(b'partial');self.assertEqual(self.check()['state'],'incomplete_download')
   self.file.write_bytes(b'version https://git-lfs.github.com/spec/v1\n');self.assertEqual(self.check(True)['state'],'placeholder');download.assert_not_called()
 def test_wrong_sized_file_is_preserved_and_not_deserialized(self):
  self.file.write_bytes(b'incomplete')
  with patch.object(resources,'file_digest') as digest:self.assertEqual(self.check(True)['state'],'size_mismatch');digest.assert_not_called()
  self.assertEqual(self.file.read_bytes(),b'incomplete')
 def test_changed_file_cannot_pass_using_a_previous_valid_hash(self):
  self.file.write_bytes(self.raw);before=self.file.stat()
  def changed(path):
   self.file.write_bytes(b'X'*len(self.raw));os.utime(self.file,ns=(before.st_atime_ns,before.st_mtime_ns+10000000));return self.pin['sha256']
  with patch.object(resources,'file_digest',side_effect=changed):self.assertEqual(self.check(True)['state'],'changed_during_check')
 def test_native_ipc_registration_and_payload_restriction(self):
  native=(pathlib.Path(w.__file__).parents[1]/'src-tauri/src/main.rs').read_text();self.assertIn('"prediction_resources"',native)
  for value in ({'path':'/arbitrary'},{'verify':'yes'}):
   with self.assertRaises(ValueError):self.s.dispatch('prediction_resources',value)
