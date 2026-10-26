"""Private failure details remain owner-scoped and are not provider log output."""
import contextlib,io,json,os,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid import editcraft_execute
class DiagnosticTests(unittest.TestCase):
 def test_private_message_is_retained_without_being_printed_or_put_in_public_error(self):
  with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,{'FOLD_ENGINE_ROLE':'editcraft_cloud'}):
   folder=pathlib.Path(temporary);(folder/'plan.json').write_text('{}');out=io.StringIO()
   with patch.object(editcraft_execute,'run_plan',side_effect=ValueError('PRIVATE_SYNTHETIC_INPUT')),contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):code=editcraft_execute.main(folder)
   self.assertEqual(code,1);self.assertNotIn('PRIVATE_SYNTHETIC_INPUT',out.getvalue());self.assertNotIn('PRIVATE_SYNTHETIC_INPUT',(folder/'failure.json').read_text());private=json.loads((folder/'failure.private.json').read_text());self.assertEqual(private['message'],'PRIVATE_SYNTHETIC_INPUT');self.assertIn('ValueError',private['traceback'])
