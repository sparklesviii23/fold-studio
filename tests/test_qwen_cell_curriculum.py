"""Full-pass, teacher and frozen-backbone controls on tiny genuine Qwen fixtures."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import torch
from transformers import Qwen2Config,Qwen2Model
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import qwen_cell_curriculum as C
from qwen_cell_model import QwenCellPredictor


class CurriculumTests(unittest.TestCase):
    def fixture(self,device='cpu'):
        torch.manual_seed(5);torch.set_num_threads(1)
        config=Qwen2Config(vocab_size=32,hidden_size=24,intermediate_size=48,num_hidden_layers=2,num_attention_heads=3,num_key_value_heads=1,attention_dropout=0.)
        config._attn_implementation='eager';base=Qwen2Model(config).to(device)
        rng=np.random.default_rng(4);x=rng.normal(size=(14,6)).astype(np.float32);y=x[:,:3]*.05
        data={'trainX':x,'trainY':y,'trainMask':np.ones_like(y),'trainTeacher':y*.9,
              'validationX':x[:4],'validationY':y[:4],'validationMask':np.ones_like(y[:4]),
              'decoder':np.eye(3,dtype=np.float32),'targetCenter':np.zeros(3,dtype=np.float32),'targetScale':np.ones(3,dtype=np.float32),
              'validationConditions':np.array(['A+B','A+C','B+C','C+D']),'genes':np.array(['A','B','C'])}
        model=QwenCellPredictor(base,6,data['decoder'],data['targetCenter'],data['targetScale'],rank=8,layers=2).to(device)
        initial=C.added_state(model);C.unwrap(base);return base,data,initial

    def test_every_epoch_visits_every_condition_once_and_reshuffles(self):
        one=np.concatenate(C.batches(77,1));two=np.concatenate(C.batches(77,2))
        np.testing.assert_array_equal(np.sort(one),np.arange(77));self.assertFalse(np.array_equal(one,two))
        np.testing.assert_array_equal(one,np.concatenate(C.batches(77,1)))
        sizes=[len(x) for x in C.batches(15,1)];self.assertEqual(sizes,[7,7,1])

    def exercise(self,device):
        base,data,initial=self.fixture(device);protocol={**C.PROTOCOL,'maximumEpochs':2,'patienceEpochs':2}
        frozen={n:p.detach().cpu().clone() for n,p in base.named_parameters()};results=[]
        with tempfile.TemporaryDirectory() as t:
            for arm in C.ARMS:
                r=C.train_arm(base,data,initial,arm,Path(t)/arm['id'],lambda *a,**k:None,protocol);results.append(r)
                self.assertEqual(r['conditionPresentations'],28);self.assertEqual(r['updates'],4)
                self.assertEqual(r['qwenAdaptersUpdatedDuringTraining'],arm['trainQwenAdapters'])
                self.assertFalse(any(hasattr(layer.self_attn.q_proj,'lora_a') for layer in base.layers))
                for n,p in base.named_parameters():self.assertTrue(torch.equal(frozen[n],p.detach().cpu()),n)
            starts=[r['initialDevelopmentMse'] for r in results]
            np.testing.assert_allclose(starts,starts[0],rtol=1e-5,atol=1e-7)
            self.assertEqual(results[-1]['qwenAdapterTrainableParameters'],0)
            self.assertGreater(results[0]['qwenAdapterTrainableParameters'],0)
            self.assertEqual(results[1]['arm']['teacherWeight'],.2)

    def test_three_controlled_arms_same_start_and_base_cpu(self):self.exercise('cpu')

    @unittest.skipUnless(torch.backends.mps.is_available(),'Apple GPU absent')
    def test_three_controlled_arms_same_start_and_base_mps(self):self.exercise('mps')

    def test_failure_restores_backbone_and_does_not_retry(self):
        base,data,initial=self.fixture();broken=copy.deepcopy(data);broken['trainY'][:]=np.nan;events=[]
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'Nonfinite'):
                C.train_arm(base,broken,initial,C.ARMS[0],Path(t)/'arm',lambda *a,**k:events.append(a))
            self.assertEqual(events,[('arm_started',)])
            self.assertFalse(any(hasattr(layer.self_attn.q_proj,'lora_a') for layer in base.layers))

    def test_development_labels_do_not_update_training_weights(self):
        from safetensors.torch import load_file
        base,data,initial=self.fixture();protocol={**C.PROTOCOL,'maximumEpochs':2,'patienceEpochs':2}
        altered=copy.deepcopy(data);altered['validationY']+=10
        with tempfile.TemporaryDirectory() as t:
            for name,values in [('one',data),('two',altered)]:
                C.train_arm(base,values,initial,C.ARMS[1],Path(t)/name,lambda *a,**k:None,protocol)
            one=load_file(str(Path(t)/'one/final-step-adapters.safetensors'))
            two=load_file(str(Path(t)/'two/final-step-adapters.safetensors'))
            for n in one:self.assertTrue(torch.equal(one[n],two[n]),n)

    def test_warm_start_tampering_is_rejected(self):
        import json
        from qwen_cell_data import sha,write
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);data=root/'data';data.mkdir();(data/'data.npz').write_bytes(b'training bundle')
            digest=sha(data/'data.npz');write(data/'manifest.json',{'schema':'fold.qwen-cell.data/1','legacyTestOutcomesIncluded':False,'dataSha256':digest})
            weights=root/'weights';weights.write_bytes(b'original');receipt=root/'receipt.json'
            write(receipt,{'state':'done','selectedStep':20,'dataSha256':digest,'files':{'adapters.safetensors':sha(weights)}})
            reference=root/'reference.json';write(reference,{})
            plan={'schema':'fold.qwen-cell.curriculum-plan/1','protocol':C.PROTOCOL,'arms':C.ARMS,'data':str(data),'dataSha256':digest,
                  'initialAdapters':str(weights),'initialAdaptersSha256':sha(weights),'initialReceipt':str(receipt),'initialReceiptSha256':sha(receipt),
                  'referenceComparison':str(reference),'referenceComparisonSha256':sha(reference),'sourceSha256':{}}
            C.verify_dependencies(plan);weights.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Warm-start'):C.verify_dependencies(plan)

    def test_unreviewed_protocol_is_rejected_before_data_access(self):
        with self.assertRaisesRegex(ValueError,'fixed'):C.verify_dependencies({'schema':'other'})


if __name__=='__main__':unittest.main()
