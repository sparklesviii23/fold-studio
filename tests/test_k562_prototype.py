"""Numerics, permutation invariance and holdout admission; synthetic data only."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import h5py
from scipy import sparse

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import k562_prototype as P


class PrototypeTests(unittest.TestCase):
    def test_backpropagation_matches_independent_finite_differences(self):
        rng=np.random.default_rng(3);x=rng.normal(size=(5,3));y=rng.normal(size=(5,2));p=P.initialize(3,4,2,1)
        _,g=P.loss_gradient(x,y,p,.03)
        for key in p:
            for index in [tuple(0 for _ in p[key].shape),tuple(n-1 for n in p[key].shape)]:
                old=p[key][index];eps=1e-6;p[key][index]=old+eps;hi=P.loss_gradient(x,y,p,.03)[0]
                p[key][index]=old-eps;lo=P.loss_gradient(x,y,p,.03)[0];p[key][index]=old
                self.assertAlmostEqual(g[key][index],(hi-lo)/(2*eps),places=7)

    def test_held_out_values_do_not_change_training_feature_statistics(self):
        rows=np.array([0,1,2,3,0,1,2,3]);cols=np.repeat([0,1],4);train=np.array([True,True,False,False]);library=np.full(4,100.)
        values=np.arange(1,9,dtype=float);before=P.training_variance(rows,cols,values,library,train,2)
        values[~train[rows]]=9000
        np.testing.assert_array_equal(before,P.training_variance(rows,cols,values,library,train,2))

    def test_whole_condition_split_is_disjoint_and_reproducible(self):
        genes=[f'G{i}' for i in range(20)];pairs=[a+'+'+b for i,a in enumerate(genes) for b in genes[i+1:]][:100]
        labels=np.repeat(['control']+genes+pairs,20);meta={'labels':labels,'cellIds':np.array([str(i) for i in range(len(labels))]),'genes':np.array(genes),'cellLine':np.repeat('K562',len(labels)),'organism':np.repeat('human',len(labels)),'batch':np.repeat('1',len(labels)),'encoding':'csc_matrix'}
        a=P.split_metadata(meta);b=P.split_metadata(meta)
        self.assertEqual(a['split'],b['split']);self.assertFalse(set(a['split']['train'])&set(a['split']['test']))
        self.assertEqual(P.condition('G2_G1'),P.condition('G1+G2'))
        mask=P.target_mask(['G1+G2'],np.array(['G1','G2','G3']))
        np.testing.assert_array_equal(mask,[[False,False,True]])

    def test_test_aggregation_is_blocked_without_a_prediction_seal(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(P,'aggregate') as aggregate:
            with self.assertRaises(FileNotFoundError):P.evaluate('absent',tmp,{},None,None)
            aggregate.assert_not_called()

    def test_portable_prediction_is_order_invariant_and_rejects_unsupported_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.npz';p=P.initialize(3,4,1,3)
            np.savez(path,singleGenes=['A','B'],singleEffects=[[1.,2.,3.],[2.,1.,4.]],encoder=np.ones((3,1)),featureCenter=np.zeros(3),featureScale=np.ones(3),alpha=.8,codeScale=np.ones(1),decoder=np.ones((3,1)),residualCenter=np.zeros(3),**p)
            np.testing.assert_array_equal(P.predict(path,['A+B']),P.predict(path,['B+A']))
            with self.assertRaisesRegex(ValueError,'measured'):P.predict(path,['A+C'])

    def test_manifest_and_source_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source';path.write_bytes(b'original');plan={'source':{'sha256':P.digest(path)},'protocol':{'seed':1}};plan['sha256']=P.fingerprint(plan)
            P.verify_plan(plan,path)
            altered=copy.deepcopy(plan);altered['protocol']['seed']=2
            with self.assertRaisesRegex(ValueError,'integrity'):P.verify_plan(altered,path)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'):P.verify_plan(plan,path)

    def test_end_to_end_raw_counts_seal_before_test_and_portable_reproduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'synthetic.h5ad';out=root/'result';rng=np.random.default_rng(7)
            genes=[f'G{i}' for i in range(20)];pairs=[a+'+'+b for i,a in enumerate(genes) for b in genes[i+1:]][:100]
            labels=np.repeat(['control']+genes+pairs,20);matrix=sparse.csc_matrix(rng.poisson(3,size=(len(labels),len(genes))).astype(np.float32))
            with h5py.File(source,'w') as f:
                x=f.create_group('X');x.attrs['encoding-type']='csc_matrix';x.attrs['shape']=matrix.shape
                for key,values in [('data',matrix.data),('indices',matrix.indices),('indptr',matrix.indptr)]:x.create_dataset(key,data=values)
                obs=f.create_group('obs');var=f.create_group('var');text=h5py.string_dtype('utf-8')
                for key,values in [('perturbation',labels),('_index',[str(i) for i in range(len(labels))]),('gemgroup',['1']*len(labels)),('cell_line',['K562']*len(labels)),('organism',['human']*len(labels))]:obs.create_dataset(key,data=np.array(values,dtype=object),dtype=text)
                obs.create_dataset('ncounts',data=np.asarray(matrix.sum(1)).ravel())
                for key in ['_index','ensemble_id']:var.create_dataset(key,data=np.array(genes,dtype=object),dtype=text)
            protocol=copy.deepcopy(P.PROTOCOL);protocol.update(variableGenes=8,inputRank=3,residualRank=3,hidden=4,epochs=40,weightDecay=[.01])
            plan=P.freeze(source,out,protocol,verify_pinned=False);meta=P.metadata(source);selected,audit=P.select_genes(source,meta,plan,out)
            aggregate=P.aggregate
            def guarded(*args):
                if set(args[3])&set(plan['split']['test']):self.assertTrue((out/'TRAINING_LOCK.json').is_file())
                return aggregate(*args)
            with patch.object(P,'aggregate',side_effect=guarded):
                P.train(source,out,plan,meta,selected);report=P.evaluate(source,out,plan,meta,selected)
            self.assertTrue(report['portablePredictionReproductionPassed']);self.assertEqual(report['split']['test'],20)
            self.assertEqual(P.digest(source),plan['source']['sha256'])
            with self.assertRaisesRegex(ValueError,'already'):P.evaluate(source,out,plan,meta,selected)


if __name__=='__main__':unittest.main()
