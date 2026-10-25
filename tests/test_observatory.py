import hashlib,json,pathlib,sys,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory,command_risk,native_quote

class ObservatoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=Service(self.temp.name);self.project=self.s.project_create({'name':'Research'});self.o=Observatory(self.s)
    def tearDown(self):self.s.db.close();self.temp.cleanup()
    def test_multiline_transport_preserves_separate_native_commands(self):
        self.o.write_connection({'port':51234,'token':'test'})
        from email.parser import BytesParser
        from email.policy import default
        commands=['color #1/A cyan target c','color #1/B green target c','color #1/C gray target c']
        with patch('observatory.urllib.request.urlopen') as send:
            send.return_value.__enter__.return_value.read.return_value=b'{}'
            self.o.request('/run',command='\n'.join(commands))
            request=send.call_args[0][0]
            mime=BytesParser(policy=default).parsebytes(('Content-Type: '+request.headers['Content-type']+'\r\n\r\n').encode()+request.data)
            self.assertEqual([p.get_payload(decode=True).decode() for p in mime.iter_parts()],commands)
    def test_full_ribosome_scene_budget_does_not_expand_other_endpoints(self):
        self.o.write_connection({'port':51234,'token':'test'})
        class LargeSceneJSON(bytes):
            def __len__(self):return 105969696  # measured 4V9D transport size
        with patch('observatory.urllib.request.urlopen') as send:
            response=send.return_value.__enter__.return_value
            response.read.return_value=LargeSceneJSON(b'{"models":[]}')
            self.assertEqual(self.o.request('/fold/scene?known=old'),{'models':[]})
            with self.assertRaisesRegex(ValueError,'bounded transfer'):self.o.request('/fold/state')
        class OverBudgetJSON(bytes):
            def __len__(self):return 256*1024**2+1
        with patch('observatory.urllib.request.urlopen') as send:
            send.return_value.__enter__.return_value.read.return_value=OverBudgetJSON(b'{}')
            with self.assertRaisesRegex(ValueError,'bounded transfer'):self.o.request('/fold/scene')
    def test_native_session_asset_is_in_project_archive_and_checksum_checked(self):
        asset='native-session-qa.cxs';content=b'Native ChimeraX test session bytes'
        path=self.s.root/'assets'/asset;path.write_bytes(content)
        entry=self.o.observatory_save({'projectId':self.project['id'],'kind':'scene','name':'Native session','data':{'engine':'chimerax','asset':asset,'sha256':hashlib.sha256(content).hexdigest()}})
        export=self.s.root/'archive.zip';self.s.export_project({'id':self.project['id'],'path':str(export)})
        with zipfile.ZipFile(export) as archive:self.assertEqual(archive.read('assets/'+asset),content)
        other=self.s.project_create({'name':'Other'})
        with patch.object(self.o,'chimerax_execute') as execute:
            with self.assertRaisesRegex(ValueError,'missing'):self.o.chimerax_session_restore({'id':entry['id'],'projectId':other['id'],'confirmed':True})
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):self.o.chimerax_session_restore({'id':entry['id'],'projectId':self.project['id'],'confirmed':True})
            execute.assert_not_called()
        with self.assertRaisesRegex(ValueError,'checksum'):self.s.export_project({'id':self.project['id'],'path':str(export)})
    def test_authoritative_native_model_is_reused_after_edits(self):
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(ROOT/'fixtures/ANGPTL3.cif')})
        mapping={'structureId':item['id'],'sourceSha256':item['data']['sha256'],'sessionId':'session','modelId':'1','positionsSha256':'original'}
        state={'bridgeVersion':4,'integrated':False,'models':[{'id':'1','positionsSha256':'edited','sourceSha256':item['data']['sha256']}],'mapping':[mapping]}
        with patch.object(self.o,'chimerax_state',return_value=state),patch.object(self.o,'chimerax_execute') as execute:
            result=self.o.chimerax_open({'structureId':item['id'],'projectId':self.project['id']})
            self.assertEqual(result['mapping'],[mapping]);execute.assert_not_called()
    def test_additive_views_and_archive_preserve_coordinates(self):
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(ROOT/'fixtures/ANGPTL3.cif')})
        self.o.observatory_save({'projectId':self.project['id'],'kind':'scene','name':'Saved view','data':{'structureId':item['id'],'sourceSha256':item['data']['sha256']}})
        self.o.console_record({'projectId':self.project['id'],'engine':'viewer','command':'view'})
        path=pathlib.Path(self.temp.name)/'research.zip';self.s.export_project({'id':self.project['id'],'path':str(path)})
        with zipfile.ZipFile(path) as z:
            data=json.loads(z.read('project.json'));self.assertEqual(len(data['researchViews']),1);self.assertEqual(len(data['commandHistory']),1)
            self.assertEqual(hashlib.sha256(z.read('assets/'+item['data']['asset'])).hexdigest(),item['data']['sha256'])
    def test_native_execution_is_not_a_manual_command_whitelist(self):
        # An extension command, absent from any local command adapter, is passed
        # intact to the real interpreter transport after review.
        command='customBundleCommand #7 option "quoted path"'
        with patch.object(self.o,'chimerax_status',return_value={'connected':True,'version':'test','sessionId':'session'}),patch.object(self.o,'request',return_value={'error':None,'python values':['real result']} ) as request,patch.object(self.o,'chimerax_state',return_value={'models':[]}):
            review=self.o.chimerax_execute({'projectId':self.project['id'],'command':command});self.assertEqual(review['state'],'review_required');request.assert_not_called()
            result=self.o.chimerax_execute({'projectId':self.project['id'],'command':command,'confirmed':True});request.assert_called_once_with('/run',command=command,timeout=120);self.assertEqual(result['state'],'completed')
    def test_native_errors_are_failed_and_persisted(self):
        with patch.object(self.o,'chimerax_status',return_value={'connected':True,'version':'test','sessionId':'session'}),patch.object(self.o,'request',return_value={'error':{'type':'UserError','message':'Unknown command'}}),patch.object(self.o,'chimerax_state',return_value={'models':[]}):
            result=self.o.chimerax_execute({'projectId':self.project['id'],'command':'invalid','confirmed':True});self.assertEqual(result['state'],'failed');history=self.o.console_history({'projectId':self.project['id']});self.assertEqual(history[0]['state'],'failed');self.assertEqual(history[0]['data']['output']['error']['message'],'Unknown command')
    def test_missing_source_never_substitutes_another_asset(self):
        with self.assertRaisesRegex(ValueError,'No substitute'):self.o.item('missing')
    def test_script_file_and_mutation_commands_require_review(self):
        for command in ['runscript script.py','save result.cif','delete #1','swapaa ala :20','color red; open file.cif']:
            self.assertTrue(command_risk(command)['requiresReview'])
        self.assertFalse(command_risk('select #1/A:20@CA')['requiresReview'])
    def test_arguments_reject_line_break_injection(self):
        self.assertEqual(native_quote('a "quoted" file'),'"a \\"quoted\\" file"')
        with self.assertRaises(ValueError):native_quote('file\nopen other')
    def test_clear_requires_confirmation(self):
        with self.assertRaises(ValueError):self.o.console_clear({'projectId':self.project['id']})
    def test_busy_session_does_not_launch_a_second_process(self):
        with patch.object(self.o,'chimerax_status',return_value={'connected':False,'state':'starting_or_busy','pid':123}),patch('observatory.subprocess.Popen') as launch:
            self.assertEqual(self.o.chimerax_start({})['state'],'starting_or_busy');launch.assert_not_called()
    def test_nonfinite_coordinates_never_synchronize(self):
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(ROOT/'fixtures/ANGPTL3.cif')});mapping={'structureId':item['id'],'sourceSha256':item['data']['sha256'],'modelId':'1','positionsSha256':'same'}
        native={'chain':'A','residue':20,'insertion':'','atom':'CA','element':'C','altLoc':'','xyz':[0,1,2]}
        state={'mapping':[mapping],'models':[{'id':'1','positionsSha256':'same'}]}
        with patch.object(self.o,'chimerax_state',return_value=state),patch.object(self.o,'request',return_value={'atoms':[native]}),patch.object(self.o,'chimerax_execute') as execute:
            for value in [float('nan'),float('inf'),float('-inf')]:
                with self.assertRaises(ValueError):self.o.chimerax_select({'structureId':item['id'],'atoms':[{'authChain':'A','auth':20,'insertion':'','atomName':'CA','element':'C','altLoc':'','xyz':[value,1,2]}]})
            execute.assert_not_called()
    def test_pae_requires_an_attached_provider_source(self):
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(ROOT/'fixtures/ANGPTL3.cif')})
        with self.assertRaisesRegex(ValueError,'No confidence matrix'):self.o.confidence_fetch({'structureId':item['id']})

if __name__=='__main__':unittest.main()
