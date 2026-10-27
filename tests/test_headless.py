import io,json,pathlib,sys,tempfile,unittest,urllib.error
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory
from capability_audit import assess

class HeadlessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=Service(self.temp.name);self.o=Observatory(self.s)
    def tearDown(self):self.s.db.close();self.temp.cleanup()
    def test_start_is_always_gui_free_and_owns_distinct_descriptor(self):
        with patch.object(self.o,'chimerax_status',return_value={'connected':False,'state':'installed_not_running'}),patch.object(self.o,'installations',return_value=[{'version':'1.12.0','executable':'/test/ChimeraX'}]),patch('observatory.subprocess.Popen') as launch:
            launch.return_value.pid=123;self.o.chimerax_start({'headless':False})
            command=launch.call_args[0][0];self.assertIn('--nogui',command);self.assertIn('--notools',command);self.assertEqual(self.o.descriptor.name,'chimerax-headless-session.json')
    def test_gui_session_cannot_be_reused(self):
        with patch.object(self.o,'chimerax_status',return_value={'connected':True,'gui':True}),patch('observatory.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError,'GUI'):self.o.chimerax_start({})
            launch.assert_not_called()
    def test_post_payload_and_real_engine_error_are_preserved(self):
        self.o.write_connection({'port':51234,'token':'test'})
        with patch('observatory.urllib.request.urlopen') as send:
            send.side_effect=urllib.error.HTTPError('local',500,'error',{},io.BytesIO(b'{"error":"Selection refers to an expired scene"}'))
            with self.assertRaisesRegex(ValueError,'expired scene'):self.o.chimerax_selection({'keys':['atom:old']})
            request=send.call_args[0][0];self.assertEqual(json.loads(request.data),{'keys':['atom:old']});self.assertEqual(request.get_method(),'POST')
    def test_audit_does_not_confuse_discovery_with_validation(self):
        x=assess({'capabilities':[{'kind':'command','name':'color','metadata':{'required':[]}}]})
        self.assertFalse(x['completeParityVerified']);self.assertFalse(x['originalUIExposed']);self.assertTrue(len(x['capabilities'])>1500)
        self.assertTrue(all(r['status'] in ('Complete','Partial','Blocked') for r in x['capabilities']))
        self.assertTrue(any(not r['scientificOutputValidated'] for r in x['capabilities']))
        self.assertEqual(next(r for r in x['capabilities'] if r['kind']=='command' and r['name']=='color')['status'],'Partial')
    def test_scripts_export_without_changing_content(self):
        for suffix in ('.py','.cxc'):
            path=pathlib.Path(self.temp.name)/('research'+suffix);text='print("scientific")\n' if suffix=='.py' else 'color #1/A cyan target c\n'
            self.s.export_file({'path':str(path),'text':text});self.assertEqual(path.read_text(),text)
    def test_tsv_export_preserves_table_and_quoted_fields(self):
        import csv
        path=pathlib.Path(self.temp.name)/'pathways.tsv'
        text='id\tpValue\tcollection\r\nset_1\t1e-250\t"Source\nwith ""quotes"""\r\n'
        self.s.export_file({'path':str(path),'text':text})
        self.assertEqual(path.read_bytes(),text.encode())
        with path.open(newline='') as stream: rows=list(csv.DictReader(stream,delimiter='\t'))
        self.assertEqual(rows,[{'id':'set_1','pValue':'1e-250','collection':'Source\nwith "quotes"'}])

if __name__=='__main__':unittest.main()
