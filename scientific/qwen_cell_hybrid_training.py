"""One offline hybrid experiment: internal expert, real gene text, staged learning.

All candidates retain an untouched zero-correction reference. Development scoring
uses the old 26 cases and is explicitly not an independent accuracy evaluation.
"""
import gc,json,time
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file,load_file
from qwen_cell_hybrid import HybridCellModel,detach_adapters
from qwen_cell_model import masked_mse
from qwen_cell_data import sha,write

PROTOCOL={'maximumSeconds':900,'maximumEpochs':6,'batchSize':2,'patienceEpochs':3,'minimumDelta':1e-6,
          'learningRate':2e-5,'foundationLearningRate':1e-4,'correctionPenalty':.1,'seed':20261106}
ARMS=[('small','Small correction + internal RNA expert'),('qwen','Gene-aware Qwen + internal RNA expert'),('frozen_qwen','Fixed gene-aware Qwen + internal RNA expert')]


def tensors(data,split,device):
    return [torch.as_tensor(data[split+key],device=device,dtype=dtype) for key,dtype in
            [('X',torch.float32),('Ids',torch.long),('Attention',torch.long),('PairIndices',torch.long),('Y',torch.float32),('Mask',torch.float32)]]


def predict(model,items,batch=2):
    model.eval();x,ids,attention,pairs=items[:4]
    with torch.no_grad():return torch.cat([model(x[i:i+batch],ids[i:i+batch],attention[i:i+batch],pairs[i:i+batch]) for i in range(0,len(x),batch)])


def expert_predictions(model,pairs,batch=2):
    # Same batching as the hybrid path: MPS may round equivalent GEMMs
    # differently for batch 2 versus batch 26. Keep exact equality meaningful.
    with torch.no_grad():return torch.cat([model.experts(pairs[i:i+batch]) for i in range(0,len(pairs),batch)])


def warm_start(model,path):
    old=load_file(str(path));params=dict(model.named_parameters());count=0
    with torch.no_grad():
        for name,value in old.items():
            target=name.replace('qwen.','backbone.',1).replace('input_projection.','numeric.',1)
            if ('.lora_' in target or target.startswith('numeric.') or target=='query') and target in params:
                if value.shape!=params[target].shape:raise ValueError('Warm-start tensor shape differs.')
                params[target].copy_(value.to(params[target].device));count+=1
    if count!=11:raise ValueError('Expected eight attention adapters, numerical projection and query from the previous Qwen checkpoint.')
    return count


def foundation(model,data,event,steps=None):
    model.freeze_readout();device=next(model.parameters()).device
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=PROTOCOL['foundationLearningRate'],weight_decay=.01)
    rows=[]
    for task in ['masked','single']:
        count=len(data[task+'X']) if steps is None else min(steps,len(data[task+'X']))
        for start in range(0,count,2):
            get=lambda key,dtype:torch.as_tensor(data[task+key][start:start+2],device=device,dtype=dtype)
            model.train();optimizer.zero_grad(set_to_none=True)
            pred=model.pretrain(get('X',torch.float32),get('Ids',torch.long),get('Attention',torch.long))
            loss=masked_mse(pred,get('Y',torch.float32),get('Mask',torch.float32))
            if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite foundation loss; no retry.')
            loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True);optimizer.step()
            row={'task':task,'examples':min(start+2,count),'objective':float(loss.detach().cpu())};rows.append(row);event('foundation',mode=model.mode,**row)
    return rows


def train_pair(model,data,folder,event,arm,protocol=PROTOCOL):
    folder=Path(folder);folder.mkdir();device=next(model.parameters()).device;model.freeze_auxiliary()
    for p in model.readout.parameters():p.requires_grad_(True)
    if arm=='frozen_qwen':model.freeze_qwen()
    train=tensors(data,'train',device);dev=tensors(data,'validation',device);x,ids,attention,pairs,y,mask=train
    frozen={n:p._version for n,p in model.named_parameters() if not p.requires_grad}
    original=model.added_state();optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=.01)
    with torch.no_grad():expert=expert_predictions(model,pairs);dev_expert=expert_predictions(model,dev[3])
    initial=predict(model,dev);torch.testing.assert_close(initial,dev_expert,rtol=0,atol=0)
    initial_mse=float(masked_mse(initial,dev[4],dev[5]).cpu());best_score=initial_mse;best=model.added_state();best_epoch=0;stale=0;trace=[];updates=0
    save_file(best,str(folder/'hybrid.safetensors'));event('arm_started',arm=arm,baselineDevelopmentMse=initial_mse,outputChannels=len(model.experts.genes),zeroCorrectionVerified=True)
    for epoch in range(1,protocol['maximumEpochs']+1):
        order=np.random.default_rng(np.random.SeedSequence([protocol['seed'],epoch])).permutation(len(x));seen=[]
        for start in range(0,len(x),protocol['batchSize']):
            rows=order[start:start+protocol['batchSize']];ix=torch.as_tensor(rows,device=device,dtype=torch.long)
            model.train();optimizer.zero_grad(set_to_none=True);pred=model(x[ix],ids[ix],attention[ix],pairs[ix])
            loss=masked_mse(pred,y[ix],mask[ix])+protocol['correctionPenalty']*masked_mse(pred,expert[ix],mask[ix])
            if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite pair loss; no retry.')
            loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True);optimizer.step();updates+=1;seen.extend(rows.tolist())
        if sorted(seen)!=list(range(len(x))):raise ValueError('Training epoch omitted a condition.')
        value=float(masked_mse(predict(model,dev),dev[4],dev[5]).cpu())
        row={'epoch':epoch,'updates':updates,'developmentMse':value,'trainingConditionsSeen':len(seen)};trace.append(row);event('epoch',arm=arm,**row)
        if value<best_score-protocol['minimumDelta']:
            best_score=value;best_epoch=epoch;best=model.added_state();save_file(best,str(folder/'hybrid.safetensors'));stale=0
        else:stale+=1
        if stale>=protocol['patienceEpochs']:break
    final=model.added_state();save_file(final,str(folder/'final-hybrid.safetensors'))
    unchanged=all(p._version==frozen[n] for n,p in model.named_parameters() if not p.requires_grad)
    if not unchanged:raise ValueError('A frozen parameter version changed during pair learning.')
    adapter_changed=any('.lora_' in n and not torch.equal(value,original[n]) for n,value in final.items())
    if model.mode=='qwen' and adapter_changed!=(arm!='frozen_qwen'):raise ValueError('Adapter/control update check failed.')
    model.restore(best);prediction=predict(model,dev).cpu().numpy();model.restore(load_file(str(folder/'hybrid.safetensors')))
    restored=predict(model,dev).cpu().numpy();np.testing.assert_allclose(restored,prediction,rtol=1e-4,atol=1e-5)
    np.savez_compressed(folder/'development-predictions.npz',prediction=prediction,conditions=data['validationConditions'],genes=data['genes'])
    result={'arm':arm,'baselineDevelopmentMse':initial_mse,'selectedDevelopmentMse':best_score,'selectedEpoch':best_epoch,'epochsCompleted':len(trace),'updates':updates,
            'trainableParameters':sum(p.numel() for p in model.parameters() if p.requires_grad),'geneOutputChannels':len(model.experts.genes),'fixedOutputBasis':False,
            'internalExpertFrozen':True,'zeroCorrectionMatchesExpert':True,'frozenParameterVersionsUnchanged':unchanged,'furtherQwenAdaptersUpdated':adapter_changed,
            'selectedInternalAdaptersChangedDuringPairs':any('.lora_' in n and not torch.equal(value,original[n]) for n,value in best.items()),
            'selectedWeightReloadPassed':True,'reloadMaxAbsDifference':float(np.max(np.abs(restored-prediction))),'trace':trace,
            'files':{p.name:sha(p) for p in folder.iterdir() if p.suffix in ['.safetensors','.npz']}}
    write(folder/'receipt.json',result);return result


def verify_dependencies(plan):
    if plan.get('schema')!='fold.qwen-cell.hybrid-plan/1' or plan.get('protocol')!=PROTOCOL:
        raise ValueError('This study requires the fixed reviewed hybrid protocol.')
    data=Path(plan['data']);manifest=json.loads((data/'manifest.json').read_text())
    if manifest.get('schema')!='fold.qwen-cell.hybrid-data/1' or manifest.get('legacyTestOutcomesIncluded') is not False:
        raise ValueError('Invalid protected biological data.')
    if sha(data/'data.npz')!=plan['dataSha256'] or manifest['dataSha256']!=plan['dataSha256']:raise ValueError('Biology bundle changed.')
    for path,digest in plan['dependencies'].items():
        if sha(path)!=digest:raise ValueError('Frozen dependency changed: '+path)
    return manifest


def run(plan,folder,event):
    from transformers import Qwen2Model
    from qwen_cell_training import validate_checkpoint
    manifest=verify_dependencies(plan);folder=Path(folder);data_folder=Path(plan['data'])
    if manifest['schema']!='fold.qwen-cell.hybrid-data/1' or manifest['legacyTestOutcomesIncluded'] is not False:raise ValueError('Invalid protected biology bundle.')
    if sha(data_folder/'data.npz')!=plan['dataSha256'] or manifest['dataSha256']!=plan['dataSha256']:raise ValueError('Biology bundle changed.')
    for path,digest in plan['dependencies'].items():
        if sha(path)!=digest:raise ValueError('Frozen dependency changed: '+path)
    if plan['protocol']!=PROTOCOL:raise ValueError('Unexpected study budget or protocol.')
    checks=validate_checkpoint(plan['checkpoint'],json.loads(Path(plan['metadata']).read_text()))
    with np.load(data_folder/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    if len(data['trainX'])!=77 or len(data['validationX'])!=26:raise ValueError('Unexpected data split.')
    torch.set_num_threads(2);torch.manual_seed(PROTOCOL['seed'])
    base=Qwen2Model.from_pretrained(plan['checkpoint'],local_files_only=True,trust_remote_code=False,use_safetensors=True,dtype=torch.float16,attn_implementation='eager').to('mps')
    results=[];foundations={}
    # Small architecture receives the same gene text as pooled frozen embeddings.
    for mode in ['small','qwen']:
        torch.manual_seed(PROTOCOL['seed']);model=HybridCellModel(base,data,mode).to('mps')
        if mode=='qwen':warm_start(model,plan['warmAdapters'])
        foundations[mode]=foundation(model,data,event)
        # Pair-output weights stay zero during foundation learning.
        dev=tensors(data,'validation','mps')
        with torch.no_grad():torch.testing.assert_close(predict(model,dev),expert_predictions(model,dev[3]),rtol=0,atol=0)
        state=model.added_state();save_file(state,str(folder/(mode+'-foundation.safetensors')))
        if mode=='small':results.append(train_pair(model,data,folder/'small',event,'small'))
        detach_adapters(base);del model;gc.collect()
        if mode=='qwen':
            for arm in ['qwen','frozen_qwen']:
                torch.manual_seed(PROTOCOL['seed']);model=HybridCellModel(base,data,'qwen').to('mps');model.restore(state)
                results.append(train_pair(model,data,folder/arm,event,arm));detach_adapters(base);del model;gc.collect()
    winner=min(results,key=lambda x:x['selectedDevelopmentMse'])
    output={'schema':'fold.qwen-cell.hybrid-study/1','state':'done','protocol':PROTOCOL,'arms':results,'foundation':foundations,
            'selectedArm':winner['arm'],'selectedDevelopmentMse':winner['selectedDevelopmentMse'],'checkpointFiles':checks,'dataSha256':plan['dataSha256'],
            'internalExpert':'Frozen learned 988-parameter RNA predictor, calibration arrays and all numerical transformations are embedded in each hybrid checkpoint.',
            'upstreamReuse':'Pinned C2S generate_sentences and GEARS np_pearson_cor helpers; no complete upstream model reproduction claimed.',
            'output':'Independent numerical channels for all 2132 panel genes; no fixed rank-12 response decoder. New panels still require data and compatible expert calibration.',
            'independentTestEvaluated':False,'legacyTestOutcomesAggregated':False,'automaticPromotion':False,'automaticRetry':False,'cloudJobs':0}
    write(folder/'RESULTS.json',output)
    lines=['# Combined cell engine — first bounded study','','The RNA predictor is an internal neural module. Every version starts with its predictions exactly. Lower development MSE is better.','',
           '| Version | Best development MSE | Selected epoch | Gene outputs |','| --- | ---: | ---: | ---: |']
    labels=dict(ARMS)
    for r in results:lines.append(f"| {labels[r['arm']]} | {r['selectedDevelopmentMse']:.8f} | {r['selectedEpoch']} | {r['geneOutputChannels']} |")
    lines+=['',f"Internal RNA reference MSE: **{results[0]['baselineDevelopmentMse']:.8f}**. Selection at epoch zero means the unchanged internal expert remains best.",
            '', 'Stages completed: masked training-profile reconstruction, known single-activation practice, then paired-activation residual training. These are small calibration exercises, not large-scale biological pretraining.',
            '', 'The full per-gene head removes the previous fixed 12-pattern output basis. Capacity remains finite and expanding the panel requires supporting data. Graph edges are training-profile co-expression associations, not causal regulation.',
            '', 'The same 26 development cases were reused for selection. No independent generalization, whole-cell simulation, C2S/GEARS reproduction or automatic improvement from added models is claimed. No default app predictor was replaced.']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n');event('study_finished',selectedArm=winner['arm'],developmentMse=winner['selectedDevelopmentMse']);return output
