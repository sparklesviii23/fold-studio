"""Grounded engine engineering checks; tiny synthetic models, no paid execution."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import numpy as np,torch
from transformers import GPTNeoXConfig,GPTNeoXModel
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import cell_training_features as F
import cell_training_metrics as M
import cell_training_engine as E
import cell_training_pretrained as P
import cell_training_lab as L
import test_qwen_cell_hybrid as fixtures
from qwen_cell_data import sha,write


class Tokens:
    pad_token_id=0;eos_token_id=0
    def __call__(self,texts,**kw):
        rows=[[ord(c)%31+1 for c in text] for text in texts]
        if not kw.get('padding'):return {'input_ids':rows}
        width=max(map(len,rows));ids=torch.tensor([r+[0]*(width-len(r)) for r in rows]);return {'input_ids':ids,'attention_mask':(ids!=0).long()}


def encoder():
    torch.manual_seed(4);config=GPTNeoXConfig(vocab_size=64,hidden_size=24,intermediate_size=48,num_hidden_layers=2,num_attention_heads=4,max_position_embeddings=64,rotary_pct=.5);config._attn_implementation='sdpa'
    return Tokens(),GPTNeoXModel(config)


class EvidenceTests(unittest.TestCase):
    def test_structures_and_starting_state_change_numerical_features(self):
        a,_=F.molecular_features('CCO');b,_=F.molecular_features('c1ccccc1');self.assertEqual(len(a),264);self.assertFalse(np.array_equal(a,b))
        kw={'task':'drug','baseline':np.array([1.,2.]),'measured':[True,True],'genes':['A','B'],'annotations':{},'dose':1.}
        x=F.intervention_features(**kw,compound={'state':'resolved','molecularFeatures':a});y=F.intervention_features(**kw,compound={'state':'resolved','molecularFeatures':b})
        self.assertEqual(len(x),470);self.assertFalse(np.array_equal(x,y));kw['baseline']=np.array([8.,2.]);self.assertFalse(np.array_equal(x,F.intervention_features(**kw,compound={'state':'resolved','molecularFeatures':a})))

    def test_missing_evidence_is_explicit_and_unmeasured_expression_is_not_used(self):
        kw={'task':'inhibition','baseline':[1.,99999.],'measured':[True,False],'genes':['A','B'],'annotations':{},'targets':['A']}
        x=F.intervention_features(**kw);kw['baseline']=[1.,-999.];np.testing.assert_array_equal(x,F.intervention_features(**kw));self.assertEqual(x[-2:].tolist(),[0.,0.])
        self.assertEqual(F.intervention_features(**kw,remaining=0.,duration=0.)[-2:].tolist(),[1.,1.])

    def test_fresh_groups_exclude_every_previously_opened_identity(self):
        split=F.fresh_split([str(i) for i in range(40)],[str(i) for i in range(20)],(20,5,5),'test')
        self.assertFalse(set(split['test']+split['validation'])&set(map(str,range(20))));self.assertEqual(len(set(sum(split.values(),[]))),30)
        with self.assertRaisesRegex(ValueError,'untouched'):F.fresh_split(['a','b'],['a'],(0,1,1),'test')

    def test_gene_knowledge_is_target_specific_and_stable(self):
        annotations={'A':{'goComponent':['nucleus'],'reactome':[{'id':'R1'}]}}
        a,known=F.gene_features('A',annotations);b,missing=F.gene_features('B',annotations);self.assertTrue(known);self.assertFalse(missing);self.assertFalse(np.array_equal(a,b));np.testing.assert_array_equal(a,F.gene_features('A',annotations)[0])


class MetricTests(unittest.TestCase):
    def test_metrics_retain_direction_and_undefined_constant_correlation(self):
        y=np.array([[1.,-2.,0.],[2.,-1.,0.]]);m=np.ones_like(y,bool)
        r=M.metrics(y,y,m,['a','b']);self.assertEqual(r['mean']['mse'],0);self.assertEqual(r['mean']['topEffectDirectionAccuracy'],1);self.assertEqual(r['signatureTop1'],1)
        bad=M.metrics(np.zeros_like(y),y,m);self.assertIsNone(bad['mean']['centeredCorrelation']);self.assertIsNone(bad['mean']['topEffectOverlap']);self.assertLess(bad['mean']['topEffectDirectionAccuracy'],1)

    def test_signature_ties_do_not_receive_perfect_ranking(self):
        y=np.ones((3,2));r=M.metrics(y,y,np.ones_like(y,bool));self.assertEqual(r['signatureTop1'],0);self.assertLess(r['signatureMeanReciprocalRank'],1)

    def test_group_intervals_use_drugs_not_the_number_of_conditions(self):
        r=M.paired_group_interval([1,1,1,1],[2,2,2,2],['a','a','b','b'],draws=100);self.assertEqual(r['groups'],2);self.assertEqual(r['ci95'],[-1.,-1.])
        self.assertIsNone(M.paired_group_interval([1],[2],['a'])['ci95'])

    def test_ridge_learns_relation_and_fits_scaling_on_training_only(self):
        rng=np.random.default_rng(1);x=rng.normal(size=(40,3));weights=rng.normal(size=(3,5));y=x@weights;m=np.ones_like(y,bool);vx=rng.normal(size=(8,3));vy=vx@weights
        fit=M.fit_baselines(x,y,m,vx,vy,np.ones_like(vy,bool));pred=M.baseline_predictions(fit,vx);self.assertLess(np.mean((pred['ridge']-vy)**2),np.mean((pred['training_mean']-vy)**2));np.testing.assert_allclose(fit['center'],x.mean(0))


class EncoderTests(unittest.TestCase):
    def test_real_tiny_encoder_deduplicates_and_retains_context(self):
        rows=[];result=P.encode_local('/missing',['A B','C D','A B'],loader=encoder,event=lambda p,**kw:rows.append((p,kw)),batch=2)
        self.assertEqual(result.shape,(3,128));np.testing.assert_array_equal(result[0],result[2]);self.assertFalse(np.array_equal(result[0],result[1]));self.assertEqual(rows[-1][1]['uniqueProfiles'],2)
        with self.assertRaisesRegex(ValueError,'position budget'):P.encode_local('/missing',['A'*65],loader=encoder)

    def test_unapproved_new_weights_never_download(self):
        with mock.patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError,'approval'):P.download({},'/missing',approved=False)
        network.assert_not_called()


class EngineTests(unittest.TestCase):
    def fixture(self):
        base,old,_=fixtures.HybridTests().fixture();data={k:v for k,v in old.items() if k.startswith('expert_')};data['genes']=old['genes'];data['featureCenter']=np.zeros(6,np.float32);data['featureScale']=np.ones(6,np.float32);data['baselineCenter']=np.zeros(19,np.float32);data['baselineScale']=np.ones(19,np.float32)
        for task in [*E.TASKS,'state','activation']:
            data[task+'_Mean']=old['trainY'].mean(0);data[task+'_Scale']=np.ones(19,np.float32)*.1
            for part in ['train','validation','test']:
                if task in ['state','activation'] and part!='train':continue
                if task=='pair' and part=='test':continue
                prefix=task+'_'+part
                for key in ['X','Ids','Attention','Mask']:data[prefix+'_'+key]=old['train'+key].copy()
                if part!='test':data[prefix+'_Y']=old['trainY'].copy()
                if task=='pair':data[prefix+'_Pairs']=old['trainPairIndices'].copy()
                data[prefix+'_BioText']=np.array(['A B','B C','A B','C D']);data[prefix+'_Bio']=np.zeros((4,128),np.float32);data[prefix+'_Group']=np.array(['A','B','C','D']);data[prefix+'_Context']=np.array(['fixture']*4)
                data[prefix+'_Baseline']=np.ones((4,19),np.float32);data[prefix+'_BaselineMask']=np.ones((4,19),bool)
        return base,data

    def test_full_gene_heads_preserve_expert_and_biology_changes_qwen_inputs(self):
        base,data=self.fixture();p={**E.PROTOCOL,'adapterLayers':2,'adapterRank':4};model=E.CellEngine(base,data,'qwen_biology',p)
        x=E.batch(data,'pair_train',slice(None),'cpu');pred=model('pair',*x);torch.testing.assert_close(pred,model.expert(x[-1]),rtol=0,atol=0)
        self.assertEqual(model.heads['drug'].out_features,19);state=model.added_state('drug');self.assertTrue(any(k.startswith('expert.') for k in state));self.assertFalse(any(k.startswith('heads.pair.') for k in state))
        with torch.no_grad():torch.nn.init.normal_(model.heads['drug'].weight,std=.1)
        one=model('drug',*x);x[3]=torch.ones_like(x[3]);self.assertFalse(torch.allclose(one,model('drug',*x)))

    def test_per_task_training_checkpoint_and_frozen_control(self):
        base,data=self.fixture();p={**E.PROTOCOL,'adapterLayers':2,'adapterRank':4,'maximumEpochs':2,'patience':2,'batchSize':2}
        model=E.CellEngine(base,data,'qwen_frozen',p);before={n:v.clone() for n,v in model.added_state().items() if n.startswith('expert.') or '.lora_' in n}
        with tempfile.TemporaryDirectory() as tmp:
            receipt=E.fit_tasks(model,data,Path(tmp),lambda *a,**kw:None,p)
            self.assertEqual(set(receipt['tasks']),set(E.TASKS));self.assertFalse(receipt['adaptersChangedDuringResponseTraining'])
            for n,v in before.items():torch.testing.assert_close(v,model.added_state()[n],rtol=0,atol=0)

    def test_raw_measured_gene_values_and_checkpointed_bfloat16_receive_gradients(self):
        base,data=self.fixture();base.set_attn_implementation('sdpa');base=base.to(torch.bfloat16);base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model=E.CellEngine(base,data,'qwen',E.PROTOCOL);model.train()
        with torch.no_grad():torch.nn.init.normal_(model.heads['drug'].weight,std=.01)
        inputs=E.batch(data,'drug_train',slice(None),'cpu');a=model('drug',*inputs);other=[x.clone() if x is not None else None for x in inputs];other[4][:,7]+=2
        self.assertFalse(torch.allclose(a,model('drug',*other)));a.square().mean().backward()
        self.assertIsNotNone(model.starting_cell[0].weight.grad);self.assertTrue(bool(torch.isfinite(model.starting_cell[0].weight.grad).all()))
        grads=[p.grad for n,p in model.named_parameters() if '.lora_b' in n];self.assertTrue(all(g is not None and bool(torch.isfinite(g).all()) for g in grads))

    def test_complete_five_arm_pipeline_and_final_prediction_separation(self):
        base,data=self.fixture();p={**E.PROTOCOL,'adapterLayers':2,'adapterRank':4,'maximumEpochs':2,'patience':2,'batchSize':2}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs=root/'inputs';inputs.mkdir();np.savez_compressed(inputs/'data.npz',**data)
            write(inputs/'manifest.json',{'schema':'fold.cell-training-data/2','dataSha256':sha(inputs/'data.npz'),'testAnswersUploaded':False,'noTruncation':True,'units':{'pair':'unit','inhibition':'unit','drug':'unit'}})
            result=E.run(inputs,root/'out',root/'archive',lambda *a,**k:None,device='cpu',loader=lambda:base,encoder_loader=encoder,protocol=p)
            self.assertEqual(len(result['trials']),5);self.assertFalse(result['freshFinalAnswersEvaluated']);self.assertTrue((root/'out/SELECTION.json').exists())
            self.assertEqual(set(result['validationWinnersIncludingBaselines']),set(E.TASKS))
            with np.load(root/'out/final-predictions.npz') as z:self.assertFalse(any(k.startswith('pair_') for k in z.files));self.assertEqual(len(z.files),16)
            import cell_training_evaluation as V
            exp=root/'experiment';exp.mkdir();(exp/'cloud-inputs').symlink_to(inputs,target_is_directory=True)
            np.savez_compressed(exp/'LOCAL_FINAL_ANSWERS.npz',**{t+'_test_Y':data[t+'_train_Y'] for t in ['inhibition','drug']})
            write(exp/'SPLIT_MANIFEST.json',{'dataSha256':sha(inputs/'data.npz'),'answerSha256':sha(exp/'LOCAL_FINAL_ANSWERS.npz')})
            original=V.np.load
            def guarded(path,*args,**kw):
                if Path(path).name=='LOCAL_FINAL_ANSWERS.npz':self.assertTrue((root/'out/SELECTION_SEAL.json').exists())
                return original(path,*args,**kw)
            with mock.patch.object(V.np,'load',side_effect=guarded):evaluation=V.evaluate(root/'out',exp)
            self.assertEqual(len(evaluation['evaluations']['drug_test']),8);self.assertFalse(evaluation['automaticPromotion'])
            (root/'out/final-predictions.npz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed after'):V.evaluate(root/'out',exp)


class WorkspaceTests(unittest.TestCase):
    def test_empty_workspace_does_not_start_or_download_anything(self):
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(L.subprocess,'Popen') as start:
            r=L.status(Path(tmp));self.assertFalse(r['sourcesReady']);self.assertEqual(r['experiments'],[]);start.assert_not_called()
            with self.assertRaises(ValueError):L.experiment(tmp,'../escape')

    def test_launch_requires_explicit_paid_approval(self):
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(L.subprocess,'run') as start:
            p=Path(tmp)/'virtualcell/training/experiments'/('a'*32);p.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'approve'):L.dispatch(SimpleNamespace(root=Path(tmp)),'vcell_training_launch',{'experimentId':'a'*32})
            start.assert_not_called()


class UploadTests(unittest.TestCase):
    def fixture(self,root):
        import cell_training_cloud as C
        exp=root/'experiment';(exp/'cloud-inputs').mkdir(parents=True);np.savez(exp/'cloud-inputs/data.npz',train_Y=np.ones((2,2)))
        write(exp/'cloud-inputs/manifest.json',{'schema':'fold.cell-training-data/2','testAnswersUploaded':False,'dataSha256':sha(exp/'cloud-inputs/data.npz')})
        checkpoint=root/'qwen';checkpoint.mkdir();(checkpoint/'config.json').write_text('{}');(checkpoint/'LICENSE').write_text('test')
        constants={'config.json':(2,sha(checkpoint/'config.json'))};biology=root/'biology';review={'schema':'fold.cell-encoder-download/1','model':P.MODEL,'license':'cc-by-4.0','revision':'a'*40,'files':[]}
        for name in ['README.md','config.json','model.safetensors','special_tokens_map.json','tokenizer.json','tokenizer_config.json']:
            content=b'fixture';review['files'].append({'name':name,'bytes':len(content),'sha256':__import__('hashlib').sha256(content).hexdigest(),'gitBlob':None})
        write(root/'review.json',review)
        with mock.patch.object(C.OLD,'CHECKPOINT',constants):plan=C.prepare(Path(__file__).resolve().parents[1],exp,checkpoint,biology,root/'review.json',exp/'cloud-plan')
        return C,plan,constants

    def test_prepared_review_can_describe_missing_encoder_but_launch_cannot(self):
        with tempfile.TemporaryDirectory() as tmp:
            C,plan,constants=self.fixture(Path(tmp))
            with mock.patch.object(C.OLD,'CHECKPOINT',constants):
                C.verify_plan(plan,allow_missing_biology=True)
                with self.assertRaisesRegex(ValueError,'Missing'):C.verify_plan(plan)
                with mock.patch.object(P,'download') as download:
                    with self.assertRaisesRegex(ValueError,'approval'):C.download_encoder(plan,False,lambda *a,**k:None)
                download.assert_not_called()

    def test_upload_whitelist_excludes_local_final_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            C,plan,constants=self.fixture(Path(tmp));assets=C.remote_assets(plan)
            self.assertFalse(any('ANSWER' in a['local'] for a in assets));self.assertTrue(any(a['remote'].startswith('models/cell-encoder/') for a in assets))
            plan['assets'].append({'path':'LOCAL_FINAL_ANSWERS.npz','local':'/outside','bytes':1,'sha256':'x'})
            with mock.patch.object(C.OLD,'CHECKPOINT',constants):
                with self.assertRaisesRegex(ValueError,'Unreviewed'):C.verify_plan(plan,allow_missing_biology=True)

    def test_encoder_git_blob_and_path_integrity(self):
        from cell_training_entry import verify
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config.json').write_bytes(b'{}');row={'path':'config.json','bytes':2,'sha256':None,'gitBlob':hashlib.sha1(b'blob 2\0{}').hexdigest()}
            verify(root,{'files':[row]});(root/'config.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'mismatch'):verify(root,{'files':[row]})
            with self.assertRaisesRegex(ValueError,'Unsafe'):verify(root,{'files':[{**row,'path':'../outside'}]})


if __name__=='__main__':unittest.main()
