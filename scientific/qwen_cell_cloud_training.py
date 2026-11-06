"""CUDA expansion study. Full context, 2,000 cells, typed intervention heads.

No downloads, retries, held-out answers or automatic app promotion. The original
RNA expert and its zero-correction reference remain available in every trial.
"""
import gc,json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import load_file,save_file
from qwen_cell_hybrid import HybridCellModel,detach_adapters
from qwen_cell_hybrid_training import tensors,predict,expert_predictions,train_pair
from qwen_cell_model import masked_mse
from qwen_cell_data import sha,write

PROTOCOL={'maximumSeconds':2700,'seeds':[20261106,20261107,20261108],
          'batchSize':8,'maximumEpochs':12,'patienceEpochs':3,'minimumDelta':1e-6,
          'learningRate':2e-5,'foundationLearningRate':2e-5,'correctionPenalty':.1,'seed':20261106}
TASK_PREFIX={'state':'state','activation':'activation','inhibition':'inhibitionTrain','drug':'drugTrain'}


class ExpandedHybrid(HybridCellModel):
    def __init__(self,base,data):
        super().__init__(base,data,'qwen');h=base.config.hidden_size;g=len(data['genes'])
        self.response_heads=nn.ModuleDict({k:nn.Linear(h,g) for k in ['activation','inhibition','drug']})
        for head in self.response_heads.values():nn.init.normal_(head.weight,std=.0001);nn.init.zeros_(head.bias)
        self.register_buffer('state_scale',torch.tensor(data['stateScale'],dtype=torch.float32))
        self.auxiliary_scale.copy_(self.state_scale)
        for k in self.response_heads:self.register_buffer(k+'_scale',torch.tensor(data[k+'Scale'],dtype=torch.float32))
    def task_prediction(self,task,x,ids,attention):
        hidden=self.hidden(x,ids,attention)
        return self.auxiliary(hidden)*self.auxiliary_scale if task=='state' else self.response_heads[task](hidden)*getattr(self,task+'_scale')
    def freeze_auxiliary(self):
        super().freeze_auxiliary()
        for p in self.response_heads.parameters():p.requires_grad_(False)


def restore_warm(model,path):
    initial=model.added_state();old=load_file(str(path))
    if not set(old)<=set(initial):raise ValueError('Warm-start architecture differs.')
    initial.update(old);model.restore(initial)
    # Preserve the strong expert reference while representations change.
    with torch.no_grad():
        model.readout.full.weight.zero_();model.readout.full.bias.zero_();model.readout.graph_query.weight.zero_()
        model.auxiliary_scale.copy_(model.state_scale)


def fit_foundation(model,data,seed,event):
    model.freeze_readout();device=next(model.parameters()).device
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=PROTOCOL['foundationLearningRate'],weight_decay=.01)
    rng=np.random.default_rng(seed);trace=[]
    for task,prefix in TASK_PREFIX.items():
        order=rng.permutation(len(data[prefix+'X']));scale=model.auxiliary_scale if task=='state' else getattr(model,task+'_scale')
        for start in range(0,len(order),PROTOCOL['batchSize']):
            ix=order[start:start+PROTOCOL['batchSize']];get=lambda key,dtype:torch.as_tensor(data[prefix+key][ix],device=device,dtype=dtype)
            model.train();optimizer.zero_grad(set_to_none=True)
            predicted=model.task_prediction(task,get('X',torch.float32),get('Ids',torch.long),get('Attention',torch.long))
            loss=masked_mse(predicted/scale,get('Y',torch.float32)/scale,get('Mask',torch.float32))
            if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite typed foundation loss; no retry.')
            loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True);optimizer.step()
            if start%128==0 or start+len(ix)==len(order):
                row={'seed':seed,'task':task,'examples':min(start+len(ix),len(order)),'totalExamples':len(order),'standardizedObjective':float(loss.detach().cpu())};trace.append(row);event('foundation',**row)
    return trace


def response_predictions(model,data,task,split):
    prefix=task+split.title();device=next(model.parameters()).device;values=[];model.eval()
    with torch.no_grad():
        for i in range(0,len(data[prefix+'X']),PROTOCOL['batchSize']):
            get=lambda k,dtype:torch.as_tensor(data[prefix+k][i:i+PROTOCOL['batchSize']],device=device,dtype=dtype)
            values.append(model.task_prediction(task,get('X',torch.float32),get('Ids',torch.long),get('Attention',torch.long)).cpu().numpy())
    return np.concatenate(values)


def run(inputs,out,archive,event,device='cuda',loader=None):
    from transformers import Qwen2Model
    inputs=Path(inputs);out=Path(out);archive=Path(archive);out.mkdir(parents=True,exist_ok=True);archive.mkdir(parents=True,exist_ok=True)
    meta=json.loads((inputs/'manifest.json').read_text())
    if meta['schema']!='fold.qwen-cell.expanded-data/1' or not meta['noTruncation'] or meta['testAnswersUploaded']:
        raise ValueError('The cloud study requires complete inputs and local-only test answers.')
    if sha(inputs/'data.npz')!=meta['dataSha256']:raise ValueError('Cloud data integrity failed.')
    with np.load(inputs/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    if len(data['stateX'])!=2000:raise ValueError('Exactly 2,000 distinct source profiles are required.')
    if any('test' in k.lower() and k.endswith('Y') for k in data):raise ValueError('Test answers must not enter the cloud learner.')
    if loader is None:
        for prefix,count in [('train',77),('validation',26),('activation',102),('inhibitionTrain',128),('inhibitionValidation',32),('inhibitionTest',32),('drugTrain',128),('drugValidation',32),('drugTest',32)]:
            if len(data[prefix+'X'])!=count:raise ValueError('Unexpected intervention split: '+prefix)
        if len(data['genes'])!=2132:raise ValueError('Unexpected gene panel.')
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('The approved CUDA GPU is missing; no local fallback.')
    if device!='cuda' and loader is None:raise ValueError('CPU execution is limited to injected synthetic test fixtures.')
    torch.set_num_threads(8)
    if device=='cuda':torch.backends.cuda.matmul.allow_tf32=False
    checkpoint=inputs/'checkpoint';expected=json.loads((inputs/'ASSET_MANIFEST.json').read_text())
    from qwen_cell_cloud_entry import verify_assets
    verify_assets(inputs,expected)
    base=loader() if loader else Qwen2Model.from_pretrained(str(checkpoint),local_files_only=True,trust_remote_code=False,use_safetensors=True,dtype=torch.bfloat16,attn_implementation='sdpa')
    base=base.to(device);trials=[];global_best=None
    for seed in PROTOCOL['seeds']:
        event('seed_started',seed=seed);torch.manual_seed(seed)
        model=ExpandedHybrid(base,data).to(device);restore_warm(model,inputs/'warm.safetensors')
        history=fit_foundation(model,data,seed,event);state=model.added_state();seed_path=archive/str(seed);seed_path.mkdir()
        save_file(state,str(seed_path/'foundation.safetensors'));detach_adapters(base);del model;gc.collect()
        for arm in ['qwen','frozen_qwen']:
            model=ExpandedHybrid(base,data).to(device);model.restore(state)
            protocol={**PROTOCOL,'seed':seed};result=train_pair(model,data,seed_path/arm,event,arm,protocol)
            result['seed']=seed;result['foundation']=history
            for task in ['inhibition','drug']:
                predicted=response_predictions(model,data,task,'validation');y=data[task+'ValidationY'];mask=data[task+'ValidationMask']
                err=((predicted.astype(float)-y)**2*mask).sum(1)/mask.sum(1)
                train_y=data[task+'TrainY'];train_m=data[task+'TrainMask'];mean=(train_y*train_m).sum(0)/np.maximum(train_m.sum(0),1)
                baseline=((mean-y)**2*mask).sum(1)/mask.sum(1)
                result[task+'Validation']={'mse':float(err.mean()),'trainingMeanBaselineMse':float(baseline.mean()),'conditions':len(y),'unit':meta['units'][task]}
            write(seed_path/arm/'expanded-receipt.json',result);trials.append(result)
            if global_best is None or result['selectedDevelopmentMse']<global_best['selectedDevelopmentMse']:
                global_best=result;save_file(model.added_state(),str(out/'selected-hybrid.safetensors'))
                with torch.no_grad():primary=predict(model,tensors(data,'validation',device)).cpu().numpy();reference=expert_predictions(model,tensors(data,'validation',device)[3]).cpu().numpy()
                np.savez_compressed(out/'selected-development-predictions.npz',prediction=primary,internalExpert=reference,genes=data['genes'],conditions=data['validationConditions'])
            detach_adapters(base);del model;gc.collect()
    # Model selection is finished. Only now generate sealed-input predictions;
    # answers are not mounted or uploaded and cannot influence this checkpoint.
    chosen=ExpandedHybrid(base,data).to(device);chosen.restore(load_file(str(out/'selected-hybrid.safetensors')))
    for task in ['inhibition','drug']:
        values=response_predictions(chosen,data,task,'test');np.savez_compressed(out/(task+'-sealed-test-predictions.npz'),prediction=values,genes=data['genes'])
    selected=predict(chosen,tensors(data,'validation',device)).cpu().numpy()
    with np.load(out/'selected-development-predictions.npz',allow_pickle=False) as z:expected_pred=z['prediction']
    np.testing.assert_allclose(selected,expected_pred,rtol=1e-4,atol=1e-5)
    summary={arm:{'mseBySeed':[r['selectedDevelopmentMse'] for r in trials if r['arm']==arm],
                  'meanMse':float(np.mean([r['selectedDevelopmentMse'] for r in trials if r['arm']==arm]))} for arm in ['qwen','frozen_qwen']}
    report={'schema':'fold.qwen-cell.cloud-study/1','state':'done','protocol':PROTOCOL,'dataSha256':meta['dataSha256'],'trials':trials,'summary':summary,
            'selected':{'seed':global_best['seed'],'arm':global_best['arm'],'developmentMse':global_best['selectedDevelopmentMse']},
            'distinctFoundationCells':2000,'inputTruncation':False,'testAnswersUploaded':False,'selectedWeightReloadPassed':True,
            'testAnswersEvaluated':False,'legacyNormanTestEvaluated':False,'automaticPromotion':False,'automaticRetry':False,
            'interpretation':'Repeated seeds and reused primary development cases; auxiliary test inputs predicted only after selection. Test answers remain local. No independent-study accuracy or whole-cell capability claimed.',
            'software':{'torch':torch.__version__,'transformers':__import__('transformers').__version__},'device':device}
    write(out/'RESULTS.json',report);write(out/'DATA_MANIFEST.json',meta)
    (out/'REPORT.md').write_text('# Expanded biological Qwen training\n\n2,000 distinct training-only profiles; complete untruncated inputs; separate activation, inhibition and drug response heads.\n\n'+
        '\n'.join(f"- {arm}: mean primary development MSE {values['meanMse']:.8f}; seeds {values['mseBySeed']}" for arm,values in summary.items())+
        '\n\n'+report['interpretation']+'\n')
    event('study_finished',selected=report['selected']);return report
