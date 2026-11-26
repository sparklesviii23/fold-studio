"""Controller orchestration checks; synthetic outputs do not validate biology."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
from worker import Service
import biology_controller as C
import gpu_tasks as G


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Service(pathlib.Path(self.tmp.name));self.project=self.s.project_create({'name':'Controller synthetic QA'})['id']
        self.p={'projectId':self.project}

    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def call(self,action,**p):return self.s.dispatch(action,{**self.p,**p})
    def plan(self,**kwargs):
        data={'name':'Reference fixture','organism':'Synthetic software context','accession':'fixture:1-8','source':'Synthetic numerical fixture', 'question':'What outputs exist?','dna':'ACGTACGT','protein':'MAAC','includeStructure':True}
        data.update(kwargs);return self.call('bio_controller_create',**data)
    def run_step(self,report,step='dna',**kwargs):
        return self.call('bio_controller_run',id=report['plan']['id'],expectedSha256=report['plan']['data']['sha256'],stepId=step,**kwargs)
    def submit_fake(self,service,payload):
        inputs=G._clean_inputs(payload['recipe'],payload['inputs'])
        tid=hashlib.md5((payload['recipe']+str(len(list(G._folder(self.s).iterdir())))).encode()).hexdigest()
        task={'id':tid,'projectId':self.project,'recipe':payload['recipe'],'inputs':inputs,'state':'running','created':'fixture',
              'inputsSha256':hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()}
        G._write(self.s,task);return task

    def test_routes_inputs_to_relevant_engines_and_never_infers_compatibility(self):
        r=self.plan();self.assertEqual([x['engine'] for x in r['steps']],['bio_evo2','bio_esmc','bio_esmfold2'])
        self.assertEqual(r['compatibility'],{'state':'not_modelled','value':None,'confidence':None})
        self.assertFalse(r['sequenceGeneration']);self.assertEqual(r['predictionsAvailable'],0)
        self.assertTrue(all(x['state']=='awaiting_approval' for x in r['steps']))
        self.assertEqual(len(r['inputChecks']),2)
        self.assertFalse(any(x['engine']=='bio_borzoi' for x in r['steps']))

    def test_validates_missing_and_oversized_inputs_without_creating_records(self):
        for args in ({'dna':'','protein':''},{'dna':'ACGU'},{'protein':'A'*601,'includeStructure':True},{'dna':'A'*4001},{'accession':''}):
            with self.assertRaises(ValueError):self.plan(**args)
        self.assertEqual(self.call('bio_controller_plans'),[])
        r=self.plan(dna='',includeStructure=False);self.assertEqual([s['engine'] for s in r['steps']],['bio_esmc'])

    def test_approval_gate_creates_no_submission_claim(self):
        r=self.plan()
        with patch.object(G,'submit') as submit:
            with self.assertRaisesRegex(ValueError,'Approve'):self.run_step(r)
            submit.assert_not_called()
        self.assertEqual(C._claims(self.s,r['plan']['id']),{})

    def test_double_submit_is_refused_and_inputs_come_from_saved_plan(self):
        r=self.plan()
        with patch.object(G,'submit',side_effect=self.submit_fake) as submit:
            result=self.run_step(r,approvedRemoteCost=True)
            self.assertEqual(result['steps'][0]['state'],'running')
            self.assertEqual(submit.call_args.args[1]['inputs'],{'sequence':'ACGTACGT'})
            with self.assertRaisesRegex(ValueError,'twice'):self.run_step(r,approvedRemoteCost=True)
            self.assertEqual(submit.call_count,1)

    def test_submission_failure_requires_review_without_auto_retry(self):
        r=self.plan()
        with patch.object(G,'submit',side_effect=RuntimeError('Synthetic uncertain provider failure')) as submit:
            with self.assertRaises(RuntimeError):self.run_step(r,approvedRemoteCost=True)
            state=self.call('bio_controller_report',id=r['plan']['id'])['steps'][0]['state']
            self.assertEqual(state,'submission_requires_review')
            with self.assertRaisesRegex(ValueError,'twice'):self.run_step(r,approvedRemoteCost=True)
            self.assertEqual(submit.call_count,1)

    def test_completed_predictions_are_separate_and_do_not_become_success_claims(self):
        r=self.plan()
        with patch.object(G,'submit',side_effect=self.submit_fake):
            for step in ('dna','protein','structure'):self.run_step(r,step,approvedRemoteCost=True)
        for claim in C._claims(self.s,r['plan']['id']).values():
            task=G._read(self.s,claim['task_id']);folder=G._folder(self.s)/task['id']/'outputs';folder.mkdir()
            data={'schema':'fold.biological-model-result.v1','recipe':task['recipe'],'inputsSha256':task['inputsSha256'],'model':'synthetic','note':'Synthetic output; not biological evidence.'}
            if task['recipe']=='bio_evo2':data['scores']=[-1.0]
            elif task['recipe']=='bio_esmc':data['embeddingShape']=[4,8]
            else:data['pTM']=0.5
            raw=json.dumps(data).encode();(folder/'result.json').write_bytes(raw)
            task.update(state='done',outputs=[{'path':'result.json','sha256':hashlib.sha256(raw).hexdigest()}]);G._write(self.s,task)
        result=self.call('bio_controller_report',id=r['plan']['id'])
        self.assertEqual(result['predictionsAvailable'],3);self.assertEqual(result['status'],'analyses_available')
        self.assertIsNone(result['compatibility']['value']);self.assertIsNone(result['compatibility']['confidence'])
        self.assertNotIn('ranking',result);self.assertIn('undetermined',result['answer'])
        (folder/'result.json').write_text('{}')
        result=self.call('bio_controller_report',id=r['plan']['id'])
        self.assertEqual(result['predictionsAvailable'],2);self.assertEqual(result['status'],'analyses_incomplete')
        self.assertEqual(result['steps'][-1]['state'],'result_unavailable')

    def test_project_isolation_integrity_and_removed_plan_gate(self):
        r=self.plan();other=self.s.project_create({'name':'Other'})['id']
        with self.assertRaises(ValueError):C.report(self.s,{'projectId':other,'id':r['plan']['id']})
        self.s.record_remove({'projectId':self.project,'id':r['plan']['id']})
        self.assertEqual(self.call('bio_controller_plans'),[])
        with self.assertRaisesRegex(ValueError,'Restore'):self.call('bio_controller_report',id=r['plan']['id'])
        self.s.record_restore({'projectId':self.project,'id':r['plan']['id']})
        d=r['plan']['data'];d['content']['organism']='changed'
        with self.s.db:self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(d),r['plan']['id']))
        with self.assertRaisesRegex(ValueError,'integrity'):self.call('bio_controller_report',id=r['plan']['id'])

    def test_plan_and_claims_survive_service_restart(self):
        r=self.plan()
        with patch.object(G,'submit',side_effect=self.submit_fake):self.run_step(r,approvedRemoteCost=True)
        root=self.s.root;self.s.db.close();self.s=Service(root)
        again=self.call('bio_controller_report',id=r['plan']['id'])
        self.assertEqual(again['plan']['data']['sha256'],r['plan']['data']['sha256'])
        self.assertEqual(again['steps'][0]['state'],'running');self.assertEqual(len(self.call('bio_controller_plans')),1)


if __name__=='__main__':unittest.main()
