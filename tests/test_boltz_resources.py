"""Integrity receipt contracts on explicitly synthetic byte fixtures, no model execution."""
import pathlib,tempfile,unittest
from test_project_metal import w
from boltz_resources import fingerprints,receipt

class ResourceReceipts(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);(self.root/'mols').mkdir();(self.root/'boltz2_conf.ckpt').write_bytes(b'byte fixture, not weights');(self.root/'mols/ALA.pkl').write_bytes(b'chemical byte fixture')
 def tearDown(self):self.tmp.cleanup()
 def files(self):return fingerprints(self.root,[{'sequence':'AA'}])
 def test_repeated_residues_have_one_resource_fingerprint(self):
  files=self.files();self.assertEqual(set(files),{'boltz2_conf.ckpt','mols/ALA.pkl'});self.assertEqual(receipt(files,files)['files'],files)
 def test_changed_usable_model_refuses_false_reproducibility(self):
  before=self.files();(self.root/'boltz2_conf.ckpt').write_bytes(b'changed fixture')
  with self.assertRaisesRegex(ValueError,'changed during'):receipt(before,self.files())
 def test_new_download_and_empty_placeholder_recovery_are_recorded(self):
  self.assertTrue(receipt({},self.files())['files']);(self.root/'boltz2_conf.ckpt').write_bytes(b'');before=self.files();(self.root/'boltz2_conf.ckpt').write_bytes(b'replacement fixture');self.assertEqual(receipt(before,self.files())['repairedPlaceholders'],['boltz2_conf.ckpt'])
 def test_no_checkpoint_cannot_be_reported_as_completed_model(self):
  with self.assertRaises(ValueError):receipt({}, {})
