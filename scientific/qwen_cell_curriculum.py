"""Prespecified local continuation: full training passes, teacher and frozen-Qwen controls.

All arms warm-start from the same verified pilot. Validation is reused development
material. No test outcomes, downloads, automatic retry or predictor promotion.
"""
import gc
import json
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file,load_file
from qwen_cell_model import QwenCellPredictor,LoRALinear,objective,masked_mse,load_trainable_state
from qwen_cell_data import sha,write,verify_bundle

ARMS=[{'id':'measured','label':'Qwen · measured outcomes','teacherWeight':0.,'trainQwenAdapters':True},
      {'id':'teacher','label':'Qwen · RNA teacher + measurements','teacherWeight':.2,'trainQwenAdapters':True},
      {'id':'frozen_qwen','label':'Fixed Qwen · train numerical layers only','teacherWeight':.2,'trainQwenAdapters':False}]
PROTOCOL={'maximumEpochs':20,'batchSize':7,'learningRate':1e-4,'weightDecay':.01,
          'patienceEpochs':5,'minimumDelta':1e-6,'seed':20261106,'maximumSeconds':900}


def batches(count,epoch,seed=20261106,batch_size=7):
    if count<1 or batch_size<1:raise ValueError('Nonempty training data and batch size are required.')
    order=np.random.default_rng(np.random.SeedSequence([seed,epoch])).permutation(count)
    return [order[i:i+batch_size] for i in range(0,count,batch_size)]


def added_state(model):
    return {n:p.detach().cpu().contiguous().clone() for n,p in model.named_parameters()
            if not n.startswith('qwen.') or '.lora_' in n}


def unwrap(base):
    for layer in base.layers:
        for name in ['q_proj','v_proj']:
            module=getattr(layer.self_attn,name)
            if isinstance(module,LoRALinear):setattr(layer.self_attn,name,module.base)


def build(base,data,initial,train_qwen=True):
    if any(isinstance(layer.self_attn.q_proj,LoRALinear) for layer in base.layers):raise ValueError('Backbone already has adapters.')
    torch.manual_seed(PROTOCOL['seed'])
    model=QwenCellPredictor(base,data['trainX'].shape[1],data['decoder'],data['targetCenter'],data['targetScale'],rank=8,layers=2).to(base.embed_tokens.weight.device)
    load_trainable_state(model,initial)
    if not train_qwen:
        for p in model.qwen.parameters():p.requires_grad_(False)
    return model


def predict(model,x,batch_size):
    model.eval()
    with torch.no_grad():return torch.cat([model(x[i:i+batch_size]) for i in range(0,len(x),batch_size)])


def train_arm(base,data,initial,arm,folder,event,protocol=PROTOCOL):
    folder=Path(folder);folder.mkdir();model=None
    try:
        model=build(base,data,initial,arm['trainQwenAdapters']);device=base.embed_tokens.weight.device
        tensor=lambda x:torch.as_tensor(x,dtype=torch.float32,device=device)
        tx,ty,tm,teacher=[tensor(data[k]) for k in ['trainX','trainY','trainMask','trainTeacher']]
        vx,vy,vm=[tensor(data[k]) for k in ['validationX','validationY','validationMask']]
        frozen={n:p._version for n,p in model.named_parameters() if not p.requires_grad}
        initial_added=added_state(model)
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=protocol['weightDecay'])
        score=lambda:float(masked_mse(predict(model,vx,protocol['batchSize']),vy,vm).cpu())
        initial_score=score();best_score=initial_score;best_epoch=0;best=added_state(model);stale=0;updates=0;trace=[]
        save_file(best,str(folder/'adapters.safetensors'));event('arm_started',arm=arm['id'],initialDevelopmentMse=initial_score,
                   teacherWeight=arm['teacherWeight'],qwenAdaptersTrainable=arm['trainQwenAdapters'])
        for epoch in range(1,protocol['maximumEpochs']+1):
            model.train();seen=[]
            for indices in batches(len(tx),epoch,protocol['seed'],protocol['batchSize']):
                ix=torch.as_tensor(indices,dtype=torch.long,device=device);optimizer.zero_grad(set_to_none=True)
                loss=objective(model(tx[ix]),ty[ix],tm[ix],teacher[ix],arm['teacherWeight'])
                if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite loss; no retry.')
                loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True)
                optimizer.step();updates+=1;seen.extend(indices.tolist())
            if sorted(seen)!=list(range(len(tx))):raise ValueError('Full-pass coverage verification failed.')
            value=score();train_score=float(masked_mse(predict(model,tx,protocol['batchSize']),ty,tm).cpu())
            row={'epoch':epoch,'updates':updates,'trainingConditionsSeen':len(seen),'trainingMeasuredMse':train_score,'developmentMse':value}
            trace.append(row);event('epoch',arm=arm['id'],**row)
            if value<best_score-protocol['minimumDelta']:
                best_score=value;best_epoch=epoch;best=added_state(model);stale=0;save_file(best,str(folder/'adapters.safetensors'))
            else:stale+=1
            if stale>=protocol['patienceEpochs']:break
        last=added_state(model);save_file(last,str(folder/'final-step-adapters.safetensors'))
        changed=[n for n in last if not torch.equal(initial_added[n],last[n])]
        if not all(p._version==frozen[n] for n,p in model.named_parameters() if not p.requires_grad):raise ValueError('Frozen parameter version changed.')
        adapter_changed=any('.lora_' in n for n in changed)
        if adapter_changed!=arm['trainQwenAdapters']:raise ValueError('Qwen adapter/control update verification failed.')
        # Loading selected added tensors is independent of requires_grad flags.
        with torch.no_grad():
            params=dict(model.named_parameters())
            for n,value in best.items():params[n].copy_(value.to(device))
        prediction=predict(model,vx,protocol['batchSize']).cpu().numpy()
        np.savez_compressed(folder/'development-predictions.npz',conditions=data['validationConditions'],genes=data['genes'],prediction=prediction)
        selected_changed=any('.lora_' in n and not torch.equal(initial_added[n],best[n]) for n in best)
        params=dict(model.named_parameters());trainable=sum(p.numel() for p in params.values() if p.requires_grad)
        result={'arm':arm,'epochsCompleted':len(trace),'updates':updates,'conditionPresentations':len(trace)*len(tx),
                'trainableParameters':trainable,'qwenAdapterTrainableParameters':sum(p.numel() for n,p in params.items() if '.lora_' in n and p.requires_grad),
                'initialDevelopmentMse':initial_score,'selectedDevelopmentMse':best_score,'selectedEpoch':best_epoch,
                'earlyStopped':len(trace)<protocol['maximumEpochs'],'qwenAdaptersUpdatedDuringTraining':adapter_changed,
                'selectedCheckpointQwenAdaptersChanged':selected_changed,'frozenParameterVersionsUnchanged':True,'changedTensorNames':changed,
                'trace':trace,'files':{p.name:sha(p) for p in folder.iterdir() if p.suffix in ['.safetensors','.npz']}}
        write(folder/'receipt.json',result);return result
    finally:
        unwrap(base);del model;gc.collect()


def verify_dependencies(plan):
    if plan.get('schema')!='fold.qwen-cell.curriculum-plan/1' or plan.get('protocol')!=PROTOCOL or plan.get('arms')!=ARMS:
        raise ValueError('This study requires the fixed, reviewed curriculum protocol.')
    manifest=verify_bundle(plan['data'])
    if manifest['dataSha256']!=plan['dataSha256']:raise ValueError('Unexpected training bundle.')
    if sha(plan['initialAdapters'])!=plan['initialAdaptersSha256']:raise ValueError('Warm-start weights changed.')
    if sha(plan['initialReceipt'])!=plan['initialReceiptSha256']:raise ValueError('Pilot receipt changed.')
    receipt=json.loads(Path(plan['initialReceipt']).read_text())
    if receipt['state']!='done' or receipt['selectedStep']!=20 or receipt['dataSha256']!=manifest['dataSha256']:
        raise ValueError('Unexpected initial pilot state.')
    if receipt['files']['adapters.safetensors']!=plan['initialAdaptersSha256']:raise ValueError('Initial checkpoint differs from the completed pilot.')
    if sha(plan['referenceComparison'])!=plan['referenceComparisonSha256']:raise ValueError('Reference comparison changed.')
    for name,digest in plan['sourceSha256'].items():
        if sha(Path(__file__).parent/name)!=digest:raise ValueError('Study source differs from the frozen plan: '+name)
    return manifest,receipt


def run(plan,folder,event):
    from transformers import Qwen2Model
    from qwen_cell_training import validate_checkpoint
    _,initial_receipt=verify_dependencies(plan);folder=Path(folder);metadata=json.loads(Path(plan['metadata']).read_text())
    checks=validate_checkpoint(plan['checkpoint'],metadata)
    if checks!=initial_receipt['checkpointFiles']:raise ValueError('Backbone differs from the verified pilot.')
    if not torch.backends.mps.is_available():raise ValueError('The local Apple GPU is unavailable; no fallback.')
    torch.set_num_threads(2)
    with np.load(Path(plan['data'])/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    if len(data['trainX'])!=77 or len(data['validationX'])!=26:raise ValueError('Unexpected development split.')
    initial=load_file(plan['initialAdapters'])
    base=Qwen2Model.from_pretrained(plan['checkpoint'],local_files_only=True,trust_remote_code=False,use_safetensors=True,dtype=torch.float16,attn_implementation='eager').to('mps')
    results=[]
    for arm in ARMS:results.append(train_arm(base,data,initial,arm,folder/arm['id'],event))
    # Reload every selected saved checkpoint into a freshly attached numerical
    # model and adapters. This verifies serialization without refitting anything.
    for result in results:
        arm=result['arm'];model=build(base,data,initial,True)
        load_trainable_state(model,load_file(str(folder/arm['id']/'adapters.safetensors')))
        x=torch.tensor(data['validationX'],dtype=torch.float32,device='mps')
        actual=predict(model,x,PROTOCOL['batchSize']).cpu().numpy()
        with np.load(folder/arm['id']/'development-predictions.npz',allow_pickle=False) as z:expected=z['prediction']
        np.testing.assert_allclose(actual,expected,rtol=1e-4,atol=1e-5)
        result['selectedWeightReloadPassed']=True;result['reloadMaxAbsDifference']=float(np.max(np.abs(actual-expected)))
        write(folder/arm['id']/'receipt.json',result);unwrap(base);del model;gc.collect()
    reference=json.loads(Path(plan['referenceComparison']).read_text())['scoresDevelopmentMse']
    winner=min(results,key=lambda r:r['selectedDevelopmentMse']);by={r['arm']['id']:r for r in results}
    output={'schema':'fold.qwen-cell.curriculum/1','state':'done','protocol':PROTOCOL,'arms':results,'selectedArm':winner['arm']['id'],
            'selectedDevelopmentMse':winner['selectedDevelopmentMse'],'referenceDevelopmentMse':reference,
            'teacherArmMinusMeasuredMse':by['teacher']['selectedDevelopmentMse']-by['measured']['selectedDevelopmentMse'],
            'trainQwenMinusFrozenControlMse':by['teacher']['selectedDevelopmentMse']-by['frozen_qwen']['selectedDevelopmentMse'],
            'beatsExistingRnaPrototypeOnDevelopment':winner['selectedDevelopmentMse']<reference['existing_rna_prototype'],
            'checkpointFiles':checks,'dataSha256':plan['dataSha256'],'initialAdaptersSha256':plan['initialAdaptersSha256'],
            'independentTestEvaluated':False,'legacyTestOutcomesAggregated':False,'cloudJobs':0,'automaticRetry':False,'automaticPromotion':False,
            'conclusion':'Reused development validation only. Controls test further adapter training and teacher loss from a shared already-adapted checkpoint; they do not establish the value of language pretraining, independent generalization or whole-cell capability.'}
    write(folder/'RESULTS.json',output)
    lines=['# Qwen training continuation — completed','','Lower RNA-response MSE is better. Same 26 reused development conditions; no independent-test claim.','',
           '| Version | Best development MSE | Selected epoch | Passes completed |','| --- | ---: | ---: | ---: |']
    for r in results:lines.append(f"| {r['arm']['label']} | {r['selectedDevelopmentMse']:.8f} | {r['selectedEpoch']} | {r['epochsCompleted']} |")
    lines+=['',f"Existing RNA predictor: **{reference['existing_rna_prototype']:.8f}**. Previous Qwen pilot: **{reference['qwen_selected']:.8f}**.",
            '',f"Lowest development error among these arms: **{winner['arm']['label']}**.",'',output['conclusion'],
            '', 'Every completed epoch presented all 77 training conditions once. Teacher predictions were used only for training conditions and were kept separate from measurements. Original Qwen base weights stayed frozen. All three selected saved checkpoints reproduce their stored development predictions. No default app predictor was replaced.']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n');event('comparison_finished',selectedArm=output['selectedArm'],developmentMse=output['selectedDevelopmentMse']);return output
