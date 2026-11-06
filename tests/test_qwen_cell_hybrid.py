"""Numerical equivalence, biological representations and staged hybrid guards."""
import copy,json,tempfile,sys
from pathlib import Path
import unittest
import numpy as np
import torch
from transformers import Qwen2Config,Qwen2Model
from safetensors.torch import save_file,load_file
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from qwen_cell_hybrid import HybridCellModel,RNAExpert,ExpertBank,detach_adapters
import qwen_cell_biology as B
import qwen_cell_hybrid_training as T
import k562_prototype as K


class FakeTokenizer:
    def __call__(self,texts,**kwargs):
        rows=np.array([[sum(map(ord,w))%31+1 for w in t.split()[:8]]+[0]*max(0,8-len(t.split())) for t in texts],np.int64)
        return {'input_ids':rows,'attention_mask':(rows!=0).astype(np.int64)}


class HybridTests(unittest.TestCase):
    def fixture(self,device='cpu',half=False):
        torch.manual_seed(3);torch.set_num_threads(1);rng=np.random.default_rng(2);g=19;s=4
        a={'genes':np.array([f'G{i}' for i in range(g)]),'singleGenes':np.array([f'G{i}' for i in range(s)]),
           'singleEffects':rng.normal(size=(s,g))*.1,'encoder':rng.normal(size=(g,2))*.1,
           'featureCenter':np.zeros(6),'featureScale':np.ones(6),'alpha':np.array(.7),
           'w1':rng.normal(size=(6,4))*.1,'b1':np.zeros(4),'w2':rng.normal(size=(4,3))*.1,'b2':np.zeros(3),
           'codeScale':np.ones(3),'decoder':rng.normal(size=(g,3))*.1,'residualCenter':np.zeros(g),'baseline':np.ones(g)}
        n,w=B.graph(np.concatenate([a['singleEffects'],rng.normal(size=(8,g))]))
        data={**{'expert_'+k:v for k,v in a.items()},'trainX':rng.normal(size=(4,6)).astype(np.float32),
              'genes':a['genes'],'graphNeighbors':n,'graphWeights':w,'correctionScale':np.ones(g,dtype=np.float32)*.1,'auxiliaryScale':np.ones(g,dtype=np.float32)*.1}
        for split in ['train','validation']:
            data[split+'X']=data['trainX'].copy();data[split+'Ids']=np.array([[1,2,3,4]]*4,np.int64);data[split+'Attention']=np.ones((4,4),np.int64)
            data[split+'PairIndices']=np.array([[0,1],[0,2],[1,2],[1,3]],np.int64)
            data[split+'Y']=RNAExpert(a)(torch.tensor(data[split+'PairIndices'])).numpy()+.01
            data[split+'Mask']=np.ones((4,g),bool);data[split+'Conditions']=np.array(['G0+G1','G0+G2','G1+G2','G1+G3'])
        for task in ['masked','single']:
            for key in ['X','Ids','Attention','Y','Mask']:data[task+key]=data['train'+key].copy()
        c=Qwen2Config(vocab_size=64,hidden_size=24,intermediate_size=48,num_hidden_layers=2,num_attention_heads=3,num_key_value_heads=1,attention_dropout=0.);c._attn_implementation='eager'
        base=Qwen2Model(c)
        if half:base=base.half()
        return base.to(device),data,a

    def test_internal_expert_reproduces_original_portable_model_and_pair_order(self):
        _,data,a=self.fixture()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.npz';np.savez(p,**a);expected=K.predict(p,['G0+G1','G0+G2','G1+G2','G1+G3'])
            expert=RNAExpert(a);actual=expert(torch.tensor(data['trainPairIndices'])).numpy()
            np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=1e-6)
            np.testing.assert_array_equal(actual,expert(torch.tensor(data['trainPairIndices'][:,::-1].copy())).numpy())

    def test_zero_correction_and_full_gene_channels_and_complete_saved_expert(self):
        base,data,a=self.fixture();model=HybridCellModel(base,data);items=T.tensors(data,'train','cpu')
        torch.testing.assert_close(T.predict(model,items),model.experts(items[3]),rtol=0,atol=0)
        self.assertEqual(model.readout.full.out_features,19)
        state=model.added_state();self.assertIn('experts.models.rna.w1',state)
        self.assertFalse(any(n.startswith('backbone.') and '.lora_' not in n for n in state))
        with torch.no_grad():model.readout.full.bias[15]=1
        pred=T.predict(model,items)-model.experts(items[3]);self.assertTrue(bool(torch.all(pred[:,15]>.09)))
        self.assertTrue(bool(torch.all(pred[:,:15]==0)))
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'hybrid.safetensors';save_file(state,str(p));model.restore(load_file(str(p)))
            torch.testing.assert_close(T.predict(model,items),model.experts(items[3]),rtol=0,atol=0)

    def exercise(self,device,half=False):
        base,data,a=self.fixture(device,half);model=HybridCellModel(base,data).to(device)
        before=model.added_state();events=[];T.foundation(model,data,lambda *a,**k:events.append((a,k)),steps=4)
        items=T.tensors(data,'validation',device)
        torch.testing.assert_close(T.predict(model,items),model.experts(items[3]),rtol=0,atol=0)
        self.assertTrue(any('.lora_' in n and not torch.equal(v,before[n]) for n,v in model.added_state().items()))
        self.assertEqual({x[1]['task'] for x in events},{'masked','single'})
        protocol={**T.PROTOCOL,'maximumEpochs':2,'patienceEpochs':2,'batchSize':2}
        with tempfile.TemporaryDirectory() as t:
            r=T.train_pair(model,data,Path(t)/'trained',lambda *a,**k:None,'qwen',protocol)
            self.assertTrue(r['internalExpertFrozen']);self.assertTrue(r['selectedWeightReloadPassed']);self.assertEqual(r['geneOutputChannels'],19)
            self.assertLessEqual(r['selectedDevelopmentMse'],r['baselineDevelopmentMse'])
            for n,v in model.added_state().items():
                if n.startswith('experts.'):self.assertTrue(torch.equal(v,before[n]),n)
        detach_adapters(base)

    def test_staged_training_preserves_expert_cpu(self):self.exercise('cpu')

    @unittest.skipUnless(torch.backends.mps.is_available(),'Apple GPU absent')
    def test_staged_training_preserves_expert_half_mps(self):self.exercise('mps',True)

    def test_rank_sentences_uses_expression_and_preserves_random_state(self):
        np.random.seed(10);old=np.random.get_state();rows=B.rank_sentences([[1.,3.,0.,2.]],['A','B','C','D'],4)
        self.assertEqual(rows,['B D A']);now=np.random.get_state();np.testing.assert_array_equal(old[1],now[1]);self.assertEqual(old[2],now[2])

    def test_graph_is_normalized_and_foundation_ignores_validation_outcomes(self):
        _,data,a=self.fixture();n,w=B.graph(np.array([[1.,2.,3.],[2.,4.,1.],[3.,6.,2.]]),neighbors=2)
        np.testing.assert_allclose(w.sum(1),1);np.testing.assert_array_equal(n[:,0],np.arange(3))
        data['trainY']=data['trainY'][:3];one=B.foundation(data,a,n,FakeTokenizer(),steps=3)
        data['validationY'][:]=99999;two=B.foundation(data,a,n,FakeTokenizer(),steps=3)
        for k in one:np.testing.assert_array_equal(one[k],two[k])

    def test_gene_text_affects_correction_and_masked_padding_does_not(self):
        base,data,_=self.fixture();model=HybridCellModel(base,data);items=T.tensors(data,'validation','cpu')
        with torch.no_grad():torch.nn.init.normal_(model.readout.full.weight,std=.01)
        original=T.predict(model,items);changed=[v.clone() for v in items];changed[1][:,2]=12
        self.assertFalse(torch.allclose(original,T.predict(model,changed)))
        padded=[v.clone() for v in items];padded[2][:,0]=0
        other=[v.clone() for v in padded];other[1][:,0]=20
        torch.testing.assert_close(T.predict(model,padded),T.predict(model,other),rtol=1e-5,atol=1e-6)

    def test_unreviewed_study_is_rejected_before_data_access(self):
        with self.assertRaisesRegex(ValueError,'fixed'):T.verify_dependencies({'schema':'other'})

    def test_registry_refuses_incompatible_experts_and_fusion_is_explicit(self):
        _,_,a=self.fixture();bank=ExpertBank(RNAExpert(a));bank.register('second',RNAExpert(a));pairs=torch.tensor([[0,1]])
        torch.testing.assert_close(bank(pairs),bank(pairs,{'rna':.5,'second':.5}))
        wrong=RNAExpert(a);wrong.context='different cell'
        with self.assertRaises(ValueError):bank.register('wrong',wrong)
        with self.assertRaises(ValueError):bank(pairs,{'rna':2})
        with self.assertRaises(ValueError):bank(pairs,{'missing':1})


if __name__=='__main__':unittest.main()
