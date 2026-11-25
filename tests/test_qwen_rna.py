"""Scientific invariants and project/provenance boundaries; no network or pretrained model."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import qwen_rna as api
from qwen_rna_contract import accuracy, clean, decode, digest, pairs, result


class ContractTests(unittest.TestCase):
    def test_input_has_exact_rna_positions(self):
        self.assertEqual(clean('acgu\nACGU'), 'ACGUACGU')
        for s in ('ACGTACGT', 'ACGNACGU', 'ACGU', 'A'*129):
            with self.assertRaises(ValueError): clean(s)

    def test_decoder_does_not_reuse_bases_or_cross_pairs(self):
        p = [[0.]*12 for _ in range(12)]
        for i,j,v in [(0,8,.6),(2,10,.5),(0,11,.8),(3,7,.9)]:
            p[i][j]=p[j][i]=v
        fold=decode(p,.15);edges=pairs(fold)
        self.assertEqual(len({x for pair in edges for x in pair}),2*len(edges))
        self.assertFalse(any(i<k<j<l for i,j in edges for k,l in edges))
        self.assertIn((3,7),edges)

    def test_probabilities_preserve_positions_and_uncertainty(self):
        seq='GCAAAAGC';p=[[0.]*8 for _ in range(8)];p[0][7]=p[7][0]=.8
        out=result(seq,p,.15,{'engine':'synthetic-test'})
        self.assertEqual(out['structure'],'(......)')
        self.assertEqual(out['basePairProbabilities'],[[1,8,.8]])
        self.assertEqual(out['bases'][7]['partner'],1)
        self.assertAlmostEqual(out['bases'][0]['unpairedProbability'],.2)
        self.assertGreater(out['bases'][0]['entropyBits'],0)
        self.assertFalse(out['uncertainty']['calibrated'])

    def test_invalid_probabilities_and_reference_refused(self):
        p=[[0.]*8 for _ in range(8)];p[0][7]=.5
        with self.assertRaises(ValueError):result('GCAAAAGC',p,.15,{})
        p[7][0]=float('nan')
        with self.assertRaises(ValueError):result('GCAAAAGC',p,.15,{})
        for ref in ['(()','.......x','........)']:
            with self.assertRaises(ValueError):pairs(ref)

    def test_pair_accuracy_exact_positions(self):
        self.assertEqual(accuracy('(......)','(......)')['f1'],1.)
        self.assertEqual(accuracy('........','(......)')['f1'],0.)

    def test_frozen_family_split_and_seal(self):
        d=json.loads((ROOT/'reports/qwen-rna/data-v1/split.json').read_text())
        self.assertEqual(d['sha256'],digest({k:v for k,v in d.items() if k!='sha256'}))
        sets=[{r['family'] for r in d['splits'][s]} for s in ('train','validation','test')]
        self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
        self.assertEqual([len(d['splits'][s]) for s in ('train','validation','test')],[48,16,24])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        from worker import Service
        self.tmp=tempfile.TemporaryDirectory(prefix='fold-qwen-test-')
        self.s=Service(pathlib.Path(self.tmp.name));self.project=self.s.project_create({'name':'Synthetic RNA test'})['id']
        self.job=self.s.job_new({'projectId':self.project,'name':'Synthetic test'},'qwen-rna','completed')
        self.folder=self.s.root/'jobs'/self.job['id'];self.folder.mkdir()
        self.value=result('GCAAAAGC',[[0.]*8 for _ in range(8)],.15,{'engine':'synthetic-test'})
        self.value['runId']=self.job['id'];self.value['sha256']=digest({k:v for k,v in self.value.items() if k!='sha256'})
        (self.folder/'result.json').write_text(json.dumps(self.value))

    def tearDown(self):
        self.s.db.close();self.tmp.cleanup()

    def test_saved_result_idempotent_and_library_identity_matches_run(self):
        p={'projectId':self.project,'id':self.job['id']}
        a=api.save(self.s,p);b=api.save(self.s,p)
        self.assertEqual(a['id'],b['id'])
        self.assertEqual(a['data']['sha256'],self.value['sha256'])
        self.assertFalse(a['data']['hasAtomicCoordinates'])

    def test_cross_project_and_traversal_refused(self):
        other=self.s.project_create({'name':'Other'})['id']
        for identity,project in [(self.job['id'],other),('../result',self.project)]:
            with self.assertRaises(ValueError):api.run_folder(self.s,identity,project)

    def test_modified_result_not_saved(self):
        self.value['sequence']='ACGUACGU';(self.folder/'result.json').write_text(json.dumps(self.value))
        with self.assertRaises(ValueError):api.save(self.s,{'projectId':self.project,'id':self.job['id']})

    def test_later_outcome_does_not_change_prediction_or_train(self):
        p={'projectId':self.project,'id':self.job['id'],'structure':'(......)','source':'Synthetic test reference, not experimental'}
        measurement=api.dispatch(self.s,'qwen_rna_measure',p)
        self.assertFalse(measurement['usedForTraining'])
        self.assertEqual(api.read_result(self.folder)['sha256'],self.value['sha256'])

    def test_interpreter_failure_cannot_leave_an_endless_queued_job(self):
        import subprocess
        self.s.job_update(self.job['id'], 'queued')
        p=subprocess.run([sys.executable,'-B',str(ROOT/'scientific/qwen_rna_runtime.py'),
                          '--root',str(self.s.root),'--job',self.job['id'],
                          '--supervise','--python','/usr/bin/false'],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(self.s.job(self.job['id'])['state'],'failed')


try:
    import torch
except ImportError:
    torch=None


@unittest.skipUnless(torch is not None,'Run learned-weight tests with runtimes/gbcell/bin/python.')
class LearnedWeightTests(unittest.TestCase):
    def test_real_qwen_adapter_gradients_native_inference_and_reload(self):
        from transformers import Qwen2Config,Qwen2Model
        from qwen_rna_model import RNAModel,marginals
        torch.manual_seed(7)
        base=Qwen2Model(Qwen2Config(vocab_size=8,hidden_size=32,intermediate_size=64,num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2))
        model=RNAModel(base,dict(zip('ACGU',range(4))),adapters=True)
        before={n:p.detach().clone() for n,p in model.named_parameters() if not p.requires_grad}
        train=[p for p in model.parameters() if p.requires_grad];opt=torch.optim.AdamW(train,lr=.01)
        sequence='GCAAAAGC';target=torch.tensor([7,6,2,3,4,5,1,0])
        for _ in range(2):
            opt.zero_grad();loss=torch.nn.functional.cross_entropy(model(sequence),target);loss.backward();opt.step()
        self.assertTrue(any('.lora_b' in n and bool(p.abs().sum()>0) for n,p in model.named_parameters()))
        self.assertTrue(all(torch.equal(before[n],p) for n,p in model.named_parameters() if n in before))
        model.eval()
        with torch.no_grad():
            p=marginals(model(sequence));snapshot=copy.deepcopy(model.added_state());model.restore(snapshot);q=marginals(model(sequence))
        self.assertTrue(torch.equal(p,q));self.assertTrue(bool((p.sum(-1)<=1.000001).all()))
        self.assertTrue(torch.equal(p,p.T));self.assertEqual(float(p[0,1]),0.)
        result(sequence,p.tolist(),.15,{'engine':'tiny-random-Qwen-test','externalEngines':[]})


if __name__=='__main__':unittest.main()
