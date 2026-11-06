"""Synthetic Qwen-architecture checks; no pretrained download or accuracy claim."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

import numpy as np
import torch
from transformers import Qwen2Config,Qwen2Model,Qwen2ForCausalLM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from qwen_cell_model import QwenCellPredictor,masked_mse,objective,trainable_state,load_trainable_state
import qwen_cell_data as D
from qwen_cell_training import validate_checkpoint


class QwenCellTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7);torch.set_num_threads(1)

    def model(self,device='cpu',half=False):
        config=Qwen2Config(vocab_size=32,hidden_size=24,intermediate_size=48,num_hidden_layers=2,
                           num_attention_heads=3,num_key_value_heads=1,attention_dropout=0.)
        config._attn_implementation='eager'
        base=Qwen2Model(config)
        if half:base=base.half()
        return QwenCellPredictor(base,6,np.eye(3),np.zeros(3),np.ones(3),rank=2,layers=2).to(device)

    def exercise(self,device,half=False):
        model=self.model(device,half);model.eval();restore=copy.deepcopy(model)
        frozen={n:p.detach().cpu().clone() for n,p in model.named_parameters() if not p.requires_grad}
        before={n:p.clone() for n,p in trainable_state(model).items()}
        x=torch.randn(6,6,device=device);y=torch.stack([x[:,0]*.2,x[:,1]*.1,x[:,2]*-.3],1)
        mask=torch.ones_like(y);opt=torch.optim.Adam([p for p in model.parameters() if p.requires_grad],lr=.005)
        first=float(masked_mse(model(x),y,mask).detach().cpu())
        for _ in range(24):
            opt.zero_grad();loss=objective(model(x),y,mask);loss.backward();opt.step()
        last=float(masked_mse(model(x),y,mask).detach().cpu());self.assertLess(last,first)
        for n,p in model.named_parameters():
            if not p.requires_grad:self.assertTrue(torch.equal(frozen[n],p.detach().cpu()),n)
        after=trainable_state(model)
        self.assertTrue(any('.lora_a' in n and not torch.equal(before[n],after[n]) for n in after))
        self.assertTrue(any('.lora_b' in n and not torch.equal(before[n],after[n]) for n in after))
        self.assertFalse(any(n.startswith('qwen.') and '.lora_' not in n for n in after))
        load_trainable_state(restore,after)
        torch.testing.assert_close(model(x),restore(x),atol=1e-6,rtol=1e-5)
        # Changing an internal Qwen adapter must affect numerical predictions.
        pred=model(x).detach().clone()
        with torch.no_grad():model.qwen.layers[-1].self_attn.v_proj.lora_b.add_(.3)
        self.assertFalse(torch.allclose(pred,model(x)))
        report=model.parameter_report();self.assertGreater(report['qwenAdapterParameters'],0)
        self.assertFalse(report['baseQwenWeightsTrainable'])
        return {'device':device,'firstSyntheticMse':first,'lastSyntheticMse':last,'qwenAdapterParameters':report['qwenAdapterParameters']}

    def test_qwen_adapters_learn_and_base_stays_identical_cpu(self):self.exercise('cpu')

    @unittest.skipUnless(torch.backends.mps.is_available(),'Apple GPU absent')
    def test_qwen_adapters_learn_on_apple_gpu(self):self.exercise('mps')

    @unittest.skipUnless(torch.backends.mps.is_available(),'Apple GPU absent')
    def test_half_precision_qwen_with_float_adapters_on_apple_gpu(self):self.exercise('mps',True)

    def test_mask_excludes_activated_targets_and_teacher_is_optional(self):
        p=torch.tensor([[900.,2.,4.]]);y=torch.tensor([[0.,0.,0.]]);m=torch.tensor([[0.,1.,1.]])
        self.assertEqual(float(masked_mse(p,y,m)),10.)
        self.assertEqual(float(objective(p,y,m,teacher_weight=0)),10.)
        with self.assertRaisesRegex(ValueError,'supplied'):objective(p,y,m,teacher_weight=.1)
        self.assertAlmostEqual(float(objective(p,y,m,torch.zeros_like(p),.1)),11.)
        with self.assertRaises(ValueError):masked_mse(p,y,torch.zeros_like(m))

    def test_invalid_adapter_bundle_rejected_before_any_weight_changes(self):
        model=self.model();state={n:p.clone() for n,p in trainable_state(model).items()}
        key=next(iter(state));state[key]=torch.full_like(state[key],float('nan'))
        with self.assertRaises(ValueError):load_trainable_state(model,state)
        with self.assertRaises(ValueError):load_trainable_state(model,{})

    def test_legacy_test_outcomes_blocked_before_aggregation(self):
        aggregate=Mock()
        with self.assertRaisesRegex(ValueError,'excluded'):D.allowed_aggregate(aggregate,None,None,None,['A+B'],['A+B'])
        aggregate.assert_not_called()
        D.allowed_aggregate(aggregate,None,None,None,['A+C'],['A+B']);aggregate.assert_called_once()

    def test_validation_values_do_not_fit_new_input_or_output_transforms(self):
        rng=np.random.default_rng(7);genes=np.array(['A','B','C','D','E','F'])
        plan={'split':{'train':['A+B','A+C','B+C','C+D'],'validation':['D+E'],'test':['A+F']}}
        model={'genes':genes,'singleGenes':genes,'singleEffects':rng.normal(size=(6,6)),'encoder':rng.normal(size=(6,2)),'baseline':np.ones(6)}
        y=rng.normal(size=(5,6));teacher=rng.normal(size=(4,6));one=D.assemble(plan,model,y,teacher)
        y[-1]=1e6;two=D.assemble(plan,model,y,teacher)
        for key in ['inputCenter','inputScale','decoder','targetCenter','targetScale','trainX','trainY']:
            np.testing.assert_array_equal(one[key],two[key],err_msg=key)
        self.assertFalse(np.array_equal(one['validationY'],two['validationY']))
        np.testing.assert_array_equal(one['trainX'],D.assemble(plan,{**model},np.zeros_like(y),teacher)['trainX'])

    def test_training_receipt_and_safe_weight_files_with_synthetic_qwen_fixture(self):
        import qwen_cell_training as T
        from safetensors.torch import load_file
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';data.mkdir();rng=np.random.default_rng(3)
            x=rng.normal(size=(4,6)).astype(np.float32);y=.1*x[:,:3]
            np.savez(data/'data.npz',trainX=x,trainY=y,trainMask=np.ones_like(y),trainTeacher=y,
                     validationX=x[:2],validationY=y[:2],validationMask=np.ones_like(y[:2]),
                     decoder=np.eye(3),targetCenter=np.zeros(3),targetScale=np.ones(3),
                     validationConditions=['A+B','A+C'],genes=['A','B','C'],
                     validationAdditive=np.zeros_like(y[:2]),validationScaledAdditive=np.zeros_like(y[:2]))
            D.write(data/'manifest.json',{'schema':'fold.qwen-cell.data/1','legacyTestOutcomesIncluded':False,'dataSha256':D.sha(data/'data.npz')})
            D.write(root/'metadata.json',{'model':'synthetic Qwen fixture, not pretrained','revision':'test-only'})
            base=self.model().qwen
            # Exercise actual offline Safetensors/prefix loading from a causal-LM
            # checkpoint, using random tiny fixture weights instead of a download.
            Qwen2ForCausalLM(base.config).save_pretrained(root/'tiny-checkpoint',safe_serialization=True)
            with patch.object(T,'validate_checkpoint',return_value=[]):
                receipt=T.run(root/'tiny-checkpoint',data,root/'run',root/'metadata.json',steps=2,max_seconds=60,device='cpu')
            self.assertEqual(receipt['state'],'done');self.assertTrue(receipt['qwenAdapterWeightsUpdated'])
            self.assertFalse(receipt['independentTestEvaluated']);self.assertFalse(receipt['legacyTestOutcomesAggregated'])
            state=load_file(str(root/'run/final-step-adapters.safetensors'))
            self.assertTrue(any('.lora_b' in n for n in state))
            self.assertFalse(any(n.startswith('qwen.') and '.lora_' not in n for n in state))
            self.assertTrue((root/'run/events.jsonl').is_file())
            with self.assertRaisesRegex(ValueError,'preserved'):
                T.run(root/'unused',data,root/'run',root/'metadata.json',steps=1,device='cpu')

    def test_data_tampering_and_unapproved_checkpoint_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data.npz').write_bytes(b'original')
            D.write(root/'manifest.json',{'schema':'fold.qwen-cell.data/1','legacyTestOutcomesIncluded':False,'dataSha256':D.sha(root/'data.npz')})
            D.verify_bundle(root);(root/'data.npz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'):D.verify_bundle(root)
            with self.assertRaises(ValueError):validate_checkpoint(root,{'model':'remote/unapproved'})


if __name__=='__main__':unittest.main()
