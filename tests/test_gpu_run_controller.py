"""Controller persistence/admission with a simulated provider; no paid execution."""
import json
from pathlib import Path
import sys,tempfile,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import gpu_tasks as G

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.service=types.SimpleNamespace(root=Path(self.tmp.name),setting=lambda k,d=None:d)
        self.task={'id':'a'*32,'recipe':'bio_borzoi','state':'running','sandboxId':'sb-test'};G._write(self.service,self.task)
    def tearDown(self):self.tmp.cleanup()
    def test_command_and_returned_output_survive_reopening(self):
        with patch.object(G,'_rpc',return_value={'stdout':'actual provider reply','stderr':'warning','exitCode':2}) as rpc:
            G.dispatch(self.service,'gpu_task_exec',{'taskId':self.task['id'],'command':'example','approvedRemoteCommand':True})
            self.assertEqual(rpc.call_count,1)
        record=G.dispatch(self.service,'gpu_task_record',{'taskId':self.task['id']});r=record['commandHistory'][0]
        self.assertEqual((r['command'],r['stdout'],r['stderr'],r['exitCode']),('example','actual provider reply','warning',2))
    def test_unapproved_or_finished_commands_never_reach_provider(self):
        with patch.object(G,'_rpc') as rpc:
            with self.assertRaisesRegex(ValueError,'Approve'):G.dispatch(self.service,'gpu_task_exec',{'taskId':self.task['id'],'command':'example'})
            self.task['state']='done';G._write(self.service,self.task)
            with self.assertRaisesRegex(ValueError,'only while'):G.dispatch(self.service,'gpu_task_exec',{'taskId':self.task['id'],'command':'example','approvedRemoteCommand':True})
            rpc.assert_not_called()
    def test_uncertain_command_outcome_is_saved_without_retry(self):
        with patch.object(G,'_rpc',side_effect=ValueError('Connection lost')) as rpc:
            with self.assertRaises(ValueError):G.dispatch(self.service,'gpu_task_exec',{'taskId':self.task['id'],'command':'example','approvedRemoteCommand':True})
            self.assertEqual(rpc.call_count,1)
        r=G.dispatch(self.service,'gpu_task_record',{'taskId':self.task['id']})['commandHistory'][0]
        self.assertEqual(r['status'],'unknown');self.assertIsNone(r['exitCode'])
    def test_completed_log_and_bounded_recent_history_remain_readable(self):
        d=G._folder(self.service)/self.task['id'];(d/'stdout.txt').write_text('model output');(d/'stderr.txt').write_text('failure detail');(d/'build.log').write_text('image build')
        (d/'terminal.jsonl').write_text('broken partial line\n'+''.join(json.dumps({'command':str(i),'exitCode':0})+'\n' for i in range(80)))
        self.task['state']='failed';G._write(self.service,self.task)
        r=G.dispatch(self.service,'gpu_task_record',{'taskId':self.task['id']})
        self.assertEqual((r['stdout'],r['stderr'],r['buildLog']),('model output','failure detail','image build'))
        self.assertEqual(len(r['commandHistory']),50);self.assertEqual(r['commandHistory'][0]['command'],'30')

if __name__=='__main__':unittest.main()
