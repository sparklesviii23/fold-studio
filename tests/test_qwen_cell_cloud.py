"""Offline engineering checks. Synthetic tiny Qwen; no cloud qualification claim."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import h5py,numpy as np,torch
from safetensors.torch import save_file
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import qwen_cell_expanded_data as D
import qwen_cell_cloud_training as T
import qwen_cell_cloud_job as J
from qwen_cell_cloud_entry import verify_assets
from qwen_cell_hybrid import HybridCellModel,detach_adapters
import gpu_tasks as G
import test_qwen_cell_hybrid as fixtures


class CompleteInputTests(unittest.TestCase):
    def test_no_input_truncation_and_context_overflow_is_rejected(self):
        class Tokenizer:
            pad_token_id=0
            def __call__(self,texts,**kw):
                self.kw=kw;return {'input_ids':[list(range(1,int(t)+1)) for t in texts]}
        tokenizer=Tokenizer();ids,attention,lengths=D.encode_complete(tokenizer,['128','283'])
        self.assertEqual(ids.shape,(2,288));self.assertEqual(attention.sum(1).tolist(),[128,283]);self.assertFalse(tokenizer.kw['truncation'])
        self.assertEqual(ids[1,-1],283)
        with self.assertRaisesRegex(ValueError,'position budget'):D.encode_complete(tokenizer,['32764'])

    def test_split_intervention_identity_is_deterministic_and_disjoint(self):
        names=[str(i) for i in range(200)];a=D.split_groups(names);b=D.split_groups(names[::-1])
        self.assertEqual(a,b);self.assertEqual([len(a[k]) for k in a],[128,32,32])
        self.assertEqual(len(set(sum(a.values(),[]))),192)

    def test_cell_sampling_excludes_heldout_groups_and_uses_distinct_cells(self):
        labels=np.array(['train']*8+['control']*4+['test']*20)
        rows=D.stratified_rows(labels,['train','control'],10,4)
        self.assertEqual(len(set(rows)),10);self.assertFalse(np.any(labels[rows]=='test'))
        np.testing.assert_array_equal(rows,D.stratified_rows(labels,['control','train'],10,4))
        with self.assertRaises(ValueError):D.stratified_rows(labels,['train'],10,4)

    def test_dense_and_csc_reads_use_full_library_totals_and_missing_gene_masks(self):
        from scipy.sparse import csc_matrix
        full=np.array([[1.,4.,5.],[3.,2.,15.],[5.,1.,4.]],np.float32);rows=np.array([0,2]);expected=np.log1p(full[rows,:2]*(1e4/full[rows].sum(1)[:,None]))
        with tempfile.TemporaryDirectory() as tmp:
            for sparse in [False,True]:
                path=Path(tmp)/str(sparse)
                with h5py.File(path,'w') as f:
                    v=f.create_group('var');v.attrs['_index']='gene_name';v['gene_name']=np.array(['A','B','C'],dtype='S')
                    if sparse:
                        matrix=csc_matrix(full);x=f.create_group('X');x['data']=matrix.data;x['indices']=matrix.indices;x['indptr']=matrix.indptr
                    else:f['X']=full
                values,measured=D.read_profiles(path,rows,['A','B','missing'],{'labels':np.array(['x']*3),'librarySize':full.sum(1)})
                np.testing.assert_allclose(values[:,:2],expected);np.testing.assert_array_equal(measured,[True,True,False]);self.assertTrue(np.all(values[:,2]==0))


class CloudTrainingTests(unittest.TestCase):
    def fixture(self):
        base,data,_=fixtures.HybridTests().fixture()
        for task in ['state','activation','inhibition','drug']:data[task+'Scale']=np.ones(19,np.float32)*(.1 if task!='drug' else 2.)
        for task,prefix in T.TASK_PREFIX.items():
            for key in ['X','Ids','Attention','Y','Mask']:data[prefix+key]=data['train'+key].copy()
        for key in ['X','Ids','Attention','Y','Mask']:data['state'+key]=np.tile(data['state'+key],(500,1))
        for task in ['inhibition','drug']:
            for split in ['Validation','Test']:
                for key in ['X','Ids','Attention','Mask']:data[task+split+key]=data['train'+key].copy()
                if split=='Validation':data[task+split+'Y']=data['trainY'].copy()
        return base,data

    def test_new_state_scale_survives_warm_start_and_heads_are_separate(self):
        base,data=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'warm';warm=HybridCellModel(base,data);save_file(warm.added_state(),str(path));detach_adapters(base)
            model=T.ExpandedHybrid(base,data);T.restore_warm(model,path)
            torch.testing.assert_close(model.auxiliary_scale,torch.tensor(data['stateScale']))
            self.assertIsNot(model.response_heads['activation'].weight,model.response_heads['drug'].weight)
            self.assertEqual(model.drug_scale[0].item(),2.)
            model.freeze_auxiliary();self.assertTrue(all(not p.requires_grad for p in model.response_heads.parameters()))
            self.assertFalse(any(p.requires_grad for p in model.experts.parameters()))
            self.assertTrue(torch.all(model.readout.full.weight==0))

    def test_bfloat16_sdpa_path_supports_complete_padded_context_and_adapter_gradients(self):
        base,data=self.fixture();base.set_attn_implementation('sdpa');base=base.to(torch.bfloat16)
        model=T.ExpandedHybrid(base,data);x=torch.tensor(data['trainX']);ids=torch.tensor(data['trainIds']);mask=torch.tensor(data['trainAttention']);mask[:,0]=0
        predicted=model.task_prediction('state',x,ids,mask);self.assertTrue(bool(torch.isfinite(predicted).all()))
        loss=(predicted-torch.tensor(data['trainY'])).square().mean();loss.backward()
        grads=[p.grad for n,p in model.named_parameters() if '.lora_b' in n]
        self.assertTrue(all(g is not None and bool(torch.isfinite(g).all()) for g in grads));self.assertTrue(any(bool(torch.any(g!=0)) for g in grads))
        other=ids.clone();other[:,0]=31
        with torch.no_grad():torch.testing.assert_close(predicted,model.task_prediction('state',x,other,mask),rtol=1e-4,atol=1e-5)

    def test_end_to_end_synthetic_worker_preserves_expert_and_seals_answer_free_predictions(self):
        base,data=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs=root/'inputs';inputs.mkdir();np.savez_compressed(inputs/'data.npz',**data)
            warm=HybridCellModel(base,data);expert={n:v for n,v in warm.added_state().items() if n.startswith('experts.')}
            save_file(warm.added_state(),str(inputs/'warm.safetensors'));detach_adapters(base)
            J.write(inputs/'manifest.json',{'schema':'fold.qwen-cell.expanded-data/1','dataSha256':J.digest(inputs/'data.npz'),'noTruncation':True,'testAnswersUploaded':False,'units':{'inhibition':'log1p','drug':'log2FC'}})
            J.write(inputs/'ASSET_MANIFEST.json',{'files':[{'path':n,'bytes':(inputs/n).stat().st_size,'sha256':J.digest(inputs/n)} for n in ['data.npz','warm.safetensors','manifest.json']]})
            events=[]
            protocol={**T.PROTOCOL,'seeds':[42],'batchSize':512,'maximumEpochs':2,'patienceEpochs':2}
            with mock.patch.object(T,'PROTOCOL',protocol):
                report=T.run(inputs,root/'out',root/'archive',lambda phase,**k:events.append((phase,k)),device='cpu',loader=lambda:base)
            self.assertEqual(report['state'],'done');self.assertFalse(report['testAnswersEvaluated']);self.assertTrue(report['selectedWeightReloadPassed'])
            self.assertEqual(len(report['trials']),2);self.assertTrue(any(p=='foundation' and k['task']=='state' and k['examples']==2000 for p,k in events))
            from safetensors.torch import load_file
            selected=load_file(str(root/'out/selected-hybrid.safetensors'))
            for n,v in expert.items():torch.testing.assert_close(v,selected[n],rtol=0,atol=0)
            for task in ['inhibition','drug']:
                with np.load(root/'out'/(task+'-sealed-test-predictions.npz')) as z:self.assertEqual(z['prediction'].shape,(4,19))

    def test_staged_manifest_rejects_path_escape_before_reading(self):
        with self.assertRaisesRegex(ValueError,'Unsafe'):verify_assets(Path('/tmp'),{'files':[{'path':'../escape','bytes':0,'sha256':'x'}]})


class CloudStagingTests(unittest.TestCase):
    def fixture(self,root):
        data=root/'data';checkpoint=root/'checkpoint';data.mkdir();checkpoint.mkdir();out=root/'prepared';repo=Path(__file__).resolve().parents[1]
        np.savez(data/'data.npz',trainY=np.zeros(2));J.write(data/'manifest.json',{'schema':'fold.qwen-cell.expanded-data/1','dataSha256':J.digest(data/'data.npz'),'noTruncation':True,'testAnswersUploaded':False})
        (data/'LOCAL_SEALED_TEST_ANSWERS.npz').write_bytes(b'must never upload')
        (checkpoint/'config.json').write_text('{}');(checkpoint/'LICENSE').write_text('test');warm=root/'warm';warm.write_bytes(b'warm')
        fixed={'config.json':(2,J.digest(checkpoint/'config.json'))}
        with mock.patch.object(J,'CHECKPOINT',fixed):plan=J.prepare(repo,data,checkpoint,warm,out)
        return plan,fixed

    def test_upload_commit_and_remote_check_precede_gpu_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,fixed=self.fixture(Path(tmp));order=[];volume=mock.MagicMock()
            assets=J.remote_assets(plan)
            volume.batch_upload.return_value.__exit__.side_effect=lambda *a:order.append('committed')
            def listed(prefix,**kw):
                order.append('verified');return [SimpleNamespace(path=a['remote'],size=a['bytes']) for a in assets if a['remote'].startswith(prefix+'/')]
            volume.listdir.side_effect=listed
            with mock.patch.object(J,'CHECKPOINT',fixed):
                result=J.stage_and_launch(plan,volume,lambda:order.append('launched') or {'sandboxId':'synthetic'},lambda:False,lambda *a,**k:None)
            self.assertEqual(order[0],'committed');self.assertEqual(order[-1],'launched');self.assertTrue(all(o=='verified' for o in order[1:-1]));self.assertEqual(result['sandboxId'],'synthetic')
            self.assertFalse(any('SEALED_TEST' in a['local'] for a in assets))

    def test_missing_remote_file_and_user_cancel_never_allocate_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,fixed=self.fixture(Path(tmp));volume=mock.MagicMock();volume.listdir.return_value=[];launch=mock.Mock()
            with mock.patch.object(J,'CHECKPOINT',fixed):
                with self.assertRaisesRegex(ValueError,'incomplete'):J.stage_and_launch(plan,volume,launch,lambda:False,lambda *a,**k:None)
                with self.assertRaises(InterruptedError):J.stage_and_launch(plan,volume,launch,lambda:True,lambda *a,**k:None)
            launch.assert_not_called()

    def test_changed_local_asset_is_rejected_and_generic_submit_cannot_bypass_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,fixed=self.fixture(Path(tmp));Path(plan['assets'][0]['local']).write_text('changed')
            with mock.patch.object(J,'CHECKPOINT',fixed):
                with self.assertRaisesRegex(ValueError,'changed'):J.verify_plan(plan)
            with mock.patch.object(G,'_provider') as provider:
                with self.assertRaisesRegex(ValueError,'prepared launcher'):G.submit(SimpleNamespace(root=Path(tmp)),{'recipe':J.RECIPE_ID,'approvedRemoteCost':True})
            provider.assert_not_called()

    def test_test_answers_are_blocked_before_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.npz';np.savez(path,inhibitionTestY=np.ones((2,3)))
            with self.assertRaisesRegex(ValueError,'stay local'):J.verify_answer_free(path)


class LocalEvaluationTests(unittest.TestCase):
    def test_answers_open_only_after_selection_seal_and_changed_predictions_cannot_rescore(self):
        import qwen_cell_cloud_evaluation as E
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out';data=root/'data';upload=data/'cloud-inputs';out.mkdir();upload.mkdir(parents=True)
            arrays={'genes':np.array(['A','B'])};answers={}
            for task in ['inhibition','drug']:
                arrays[task+'TrainY']=np.ones((2,2));arrays[task+'TrainMask']=np.ones((2,2),bool);arrays[task+'TestMask']=np.ones((2,2),bool);answers[task+'TestY']=np.ones((2,2))*.5
                np.savez(out/(task+'-sealed-test-predictions.npz'),prediction=np.ones((2,2))*.5,genes=arrays['genes'])
            np.savez(upload/'data.npz',**arrays);np.savez(data/'LOCAL_SEALED_TEST_ANSWERS.npz',**answers)
            J.write(upload/'manifest.json',{'units':{'inhibition':'log1p','drug':'log2'}})
            J.write(data/'SPLIT_MANIFEST.json',{'cloudDataSha256':J.digest(upload/'data.npz'),'sealedAnswersSha256':J.digest(data/'LOCAL_SEALED_TEST_ANSWERS.npz'),
                                             'groups':{'inhibition':{'test':['G1','G2']},'drug':{'test':['drug1']}}})
            J.write(out/'RESULTS.json',{'state':'done','selectedWeightReloadPassed':True,'testAnswersUploaded':False,'testAnswersEvaluated':False,'dataSha256':J.digest(upload/'data.npz')})
            (out/'selected-hybrid.safetensors').write_bytes(b'selected')
            original=E.np.load
            def guarded(path,*a,**kw):
                if Path(path).name=='LOCAL_SEALED_TEST_ANSWERS.npz':self.assertTrue((out/'SELECTION_SEAL.json').exists())
                return original(path,*a,**kw)
            with mock.patch.object(E.np,'load',side_effect=guarded):r=E.evaluate(out,data)
            self.assertEqual(r['drug']['mse'],0);self.assertEqual(r['inhibition']['trainingMeanBaselineMse'],.25)
            (out/'LOCAL_TEST_EVALUATION.json').unlink();(out/'selected-hybrid.safetensors').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed after'):E.evaluate(out,data)


if __name__=='__main__':unittest.main()
