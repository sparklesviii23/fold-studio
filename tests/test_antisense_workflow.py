"""Numerical and orchestration checks for the explicitly exploratory PNA chain."""
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import antisense_engine as E
import antisense_workflow as W
import biology_controller as C
import gpu_tasks as G
import modal_terminal as T
from worker import Service


class AntisenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.s = Service(pathlib.Path(self.temp.name))
        self.pid = self.s.project_create({'name': 'Isolated PNA software checks'})['id']

    def tearDown(self): self.s.db.close(); self.temp.cleanup()
    def call(self, action, **p): return self.s.dispatch(action, {'projectId': self.pid, **p})
    def plan(self, **extra):
        return self.call('bio_controller_create', name='PNA test', organism='Synthetic context', accession='fixture', source='Synthetic software fixture',
                         question='Check software and numerical behaviour', antisenseRequest={'mode':'benchmark','source':'Public benchmark'}, **extra)

    def test_bundled_evidence_qualifiers_and_grouped_holdouts(self):
        r = E.run({'mode':'benchmark','source':'Public benchmark'}, W.data())
        self.assertEqual((r['dataset']['measurementRows'], r['dataset']['uniqueSequences']), (51,44))
        b = r['benchmark']; self.assertEqual(b['exactTrainingRows'],26); self.assertEqual(b['foldCount'],10)
        self.assertTrue(all(f['sharedSequences']==0 for f in b['folds']))
        self.assertAlmostEqual(b['maeLog2Mic'],0.9926779679337792,places=10)
        self.assertAlmostEqual(b['medianBaselineMaeLog2Mic'],1.1014492753623188,places=10)
        self.assertFalse(b['externalValidation']);self.assertFalse(b['calibratedUncertainty'])
        self.assertEqual([s['name'] for s in r['stages']][:3],['Validate inputs','Load published evidence','Train and test baseline'])

    def test_draft_orientation_background_and_out_of_domain_withholding(self):
        r=E.run({'mode':'draft','source':'Synthetic numerical fragment','target':'AACCGGUUA','length':9,'background':'TAACCGGTT','backgroundSource':'Synthetic negative reference'},W.data())
        c=r['candidates'][0];self.assertEqual(c['sequence'],'TAACCGGTT')
        self.assertIsNone(c['model']['log2Mic']);self.assertIsNone(c['model']['confidenceInterval'])
        self.assertEqual(E.background_check('AACCGGTT','AACCGGTT')['exact'],1)
        self.assertEqual(E.background_check('AACCGGTT','AACCGGTA')['oneMismatch'],1)
        self.assertFalse(r['activityValidated'])

    def test_boundaries_never_crop_or_accept_unknown_context(self):
        for p in [{'mode':'draft','target':'A'*64},{'mode':'analyse','candidates':'A'*12},{'strain':'unknown'},
                  {'mode':'analyse','candidates':'ACGTACGT','background':'ACGT'},{'length':True},{'mode':'draft','target':'ACGNACGTG'}]:
            with self.assertRaises(ValueError): E.clean({'mode':'benchmark','source':'fixture',**p})

    def test_plan_local_run_persists_and_is_idempotent(self):
        p=self.plan();args={'id':p['plan']['id'],'expectedSha256':p['plan']['data']['sha256']}
        with patch.object(G,'submit') as submit:
            r=self.call('bio_controller_local_run',**args);submit.assert_not_called()
        self.assertEqual(r['steps'][0]['state'],'done');self.assertEqual(r['predictionsAvailable'],1)
        self.assertEqual(self.call('bio_controller_local_run',**args)['steps'][0]['result'],r['steps'][0]['result'])
        root=self.s.root;self.s.db.close();self.s=Service(root)
        self.assertEqual(self.call('bio_controller_report',id=args['id'])['steps'][0]['result'],r['steps'][0]['result'])
        self.s.db.execute("UPDATE bio_controller_local_results SET result='{}' WHERE plan_id=?",(args['id'],));self.s.db.commit()
        self.assertEqual(self.call('bio_controller_report',id=args['id'])['steps'][0]['state'],'result_unavailable')

    def test_cloud_mode_prohibits_local_fallback(self):
        p=self.plan();self.s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('executionBackend',json.dumps({'mode':'modal'})));self.s.db.commit()
        with self.assertRaisesRegex(ValueError,'prohibits local'): self.call('bio_controller_local_run',id=p['plan']['id'],expectedSha256=p['plan']['data']['sha256'])
        self.assertEqual(C._claims(self.s,p['plan']['id']),{})

    def test_remote_recipe_uses_identical_engine_and_no_model_download(self):
        recipe=W.recipe();self.assertIsNone(recipe['gpu']);self.assertEqual(recipe['cpu'],2)
        code=recipe['script'].split("<<'FOLD_PNA_PY'\n",1)[1].rsplit('\nFOLD_PNA_PY',1)[0]
        compile(code,'remote-pna','exec');self.assertLess(len(recipe['script'].encode()),120000)
        self.assertIn(pathlib.Path(E.__file__).read_text(),code)
        self.assertEqual(recipe['image']['pip'],['numpy==2.2.6'])

    def test_batch_approval_duplicate_exclusion_and_stop_on_uncertain_launch(self):
        p=self.plan(dna='ACGT');args={'id':p['plan']['id'],'expectedSha256':p['plan']['data']['sha256']}
        with patch.object(G,'submit') as submit:
            with self.assertRaisesRegex(ValueError,'Approve'):self.call('bio_controller_automate',**args)
            submit.assert_not_called()
        def fake(s,payload):
            inputs=G._clean_inputs(payload['recipe'],payload['inputs']);tid=hashlib.md5(payload['recipe'].encode()).hexdigest()
            task={'id':tid,'projectId':self.pid,'recipe':payload['recipe'],'inputs':inputs,'state':'running','created':'fixture','inputsSha256':hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()}
            G._write(s,task);return task
        with patch.object(G,'submit',side_effect=fake) as submit:
            self.call('bio_controller_automate',**args,approvedRemoteCost=True)
            self.call('bio_controller_automate',**args,approvedRemoteCost=True)
            self.assertEqual(submit.call_count,2)
        q=self.plan(dna='ACGT');more={'id':q['plan']['id'],'expectedSha256':q['plan']['data']['sha256'],'approvedRemoteCost':True}
        with patch.object(G,'submit',side_effect=RuntimeError('Uncertain synthetic submission')) as submit:
            r=self.call('bio_controller_automate',**more);self.assertEqual(submit.call_count,1)
            self.assertEqual(r['steps'][0]['state'],'submission_requires_review')
            with self.assertRaisesRegex(ValueError,'review'):self.call('bio_controller_automate',**more)
            self.assertEqual(submit.call_count,1)

    def test_terminal_project_account_and_input_scope(self):
        tid='a'*32;task={'id':tid,'projectId':self.pid,'provider':'modal','state':'running','sandboxId':'fixture','accountId':'owner'};G._write(self.s,task)
        with patch('cloud_accounts.get',return_value={'activeId':'owner'}),patch.object(G,'_rpc',return_value={'data':'','offset':0,'ready':False,'closed':False}) as remote:
            with self.assertRaisesRegex(ValueError,'explicitly'):self.call('gpu_task_terminal',taskId=tid,start=True)
            r=self.call('gpu_task_terminal',taskId=tid,start=True,approvedRemoteCommand=True)
            self.assertTrue(repr(r['sessionId']));self.assertEqual(remote.call_count,1)
            with self.assertRaisesRegex(ValueError,'cursor'):self.call('gpu_task_terminal',taskId=tid,sessionId=r['sessionId'],offset=-1)
            with self.assertRaisesRegex(ValueError,'event identity'):self.call('gpu_task_terminal',taskId=tid,sessionId=r['sessionId'],data=base64.b64encode(b'pwd\n').decode())
            other=self.s.project_create({'name':'Other'})['id']
            with self.assertRaisesRegex(ValueError,'project'):self.s.dispatch('gpu_task_terminal',{'projectId':other,'taskId':tid,'start':True,'approvedRemoteCommand':True})
        with patch('cloud_accounts.get',return_value={'activeId':'different'}):
            with self.assertRaisesRegex(ValueError,'owns'):self.call('gpu_task_terminal',taskId=tid,start=True,approvedRemoteCommand=True)

    @unittest.skipUnless(sys.platform in ('darwin','linux'),'POSIX PTY required')
    def test_real_pty_broker_shell_state_cursor_and_replayed_input(self):
        folder=pathlib.Path(self.temp.name)/'pty';proc=subprocess.Popen([sys.executable,'-c',T.DAEMON,str(folder)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            end=time.monotonic()+5
            while not (folder/'ready').exists() and time.monotonic()<end:time.sleep(.03)
            self.assertTrue((folder/'ready').exists())
            event={'id':'a'*32,'data':base64.b64encode(b'cd /; printf "FOLD_PTY_OK:%s\\n" "$PWD"\n').decode()}
            def poll(offset=0,event=None):
                return json.loads(subprocess.check_output([sys.executable,'-c',T.POLL,str(folder),str(offset),json.dumps(event or {})],text=True))
            poll(event=event);poll(event=event);output=b'';cursor=0;end=time.monotonic()+5
            while time.monotonic()<end:
                r=poll(cursor);cursor=r['offset'];output+=base64.b64decode(r['data'])
                if b'FOLD_PTY_OK:/\r\n' in output:break
                time.sleep(.04)
            self.assertIn(b'FOLD_PTY_OK:/\r\n',output)
            self.assertEqual(output.count(b'FOLD_PTY_OK:/\r\n'),1)
            self.assertEqual(poll(cursor)['data'],'')
            poll(cursor,{'id':'b'*32,'close':True});proc.wait(timeout=5)
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
            proc.stderr.close()


if __name__=='__main__':unittest.main()
