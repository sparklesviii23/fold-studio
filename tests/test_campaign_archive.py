"""Archive transport guards and atomic exchange; no invented model results."""
import pathlib,sys,tempfile,unittest,zipfile
from test_project_metal import w
from campaign_archive import logical_manifest,exchange_directories

class ArchiveGuards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.stage=self.root/'1_Trajectories';self.stage.mkdir()
 def tearDown(self):self.tmp.cleanup()
 def test_packed_and_unpacked_content_has_identical_logical_hashes(self):
  (self.stage/'example').mkdir();file=self.stage/'example'/'losses.csv';file.write_text('step,loss\n1,2\n');before=logical_manifest(self.root)
  with zipfile.ZipFile(self.stage/'example.zip','w') as z:z.write(file,'example/losses.csv')
  file.unlink();file.parent.rmdir();self.assertEqual(logical_manifest(self.root),before)
 def test_unsafe_members_and_restore_collisions_are_refused(self):
  for name in ('../escape','/escape','example/../escape','example\\escape','other/data'):
   with self.subTest(name=name):
    with zipfile.ZipFile(self.stage/'example.zip','w') as z:z.writestr(name,b'unsafe')
    with self.assertRaisesRegex(ValueError,'Unsafe'):logical_manifest(self.root)
  with zipfile.ZipFile(self.stage/'example.zip','w') as z:
   info=zipfile.ZipInfo('example/link');info.external_attr=0o120777<<16;z.writestr(info,b'../escape')
  with self.assertRaisesRegex(ValueError,'Unsafe'):logical_manifest(self.root)
  with zipfile.ZipFile(self.stage/'example.zip','w') as z:z.writestr('example/FILE',b'a');z.writestr('example/file',b'b')
  with self.assertRaisesRegex(ValueError,'conflicting'):logical_manifest(self.root)
 @unittest.skipUnless(sys.platform=='darwin','macOS atomic directory exchange')
 def test_atomic_exchange_preserves_both_directory_contents(self):
  second=self.root/'second';second.mkdir();(self.stage/'a').write_bytes(b'original');(second/'b').write_bytes(b'converted')
  exchange_directories(self.stage,second);self.assertEqual((self.stage/'b').read_bytes(),b'converted');self.assertEqual((second/'a').read_bytes(),b'original')
  exchange_directories(self.stage,second);self.assertEqual((self.stage/'a').read_bytes(),b'original')
