"""Grounded Qwen cell engine and controlled numerical/biology ablations."""
import gc,json,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import load_file,save_file
from qwen_cell_hybrid import RNAExpert,detach_adapters
from qwen_cell_model import LoRALinear
from qwen_cell_data import sha,write
from cell_training_metrics import metrics,fit_baselines,baseline_predictions
from cell_training_recipe import PROTOCOL

TASKS=('pair','inhibition','drug')


class CellEngine(nn.Module):
    def __init__(self,base,data,arm,protocol=PROTOCOL):
        super().__init__();self.arm=arm;self.use_biology=arm in ['biology_numeric','qwen_biology'];self.is_qwen=arm.startswith('qwen')
        arrays={k[7:]:v for k,v in data.items() if k.startswith('expert_')};self.expert=RNAExpert(arrays);self.genes=tuple(arrays['genes'].astype(str));g=len(self.genes)
        self.register_buffer('feature_center',torch.tensor(data['featureCenter'],dtype=torch.float32));self.register_buffer('feature_scale',torch.tensor(data['featureScale'],dtype=torch.float32))
        self.register_buffer('baseline_center',torch.tensor(data['baselineCenter'],dtype=torch.float32));self.register_buffer('baseline_scale',torch.tensor(data['baselineScale'],dtype=torch.float32))
        self.starting_cell=nn.Sequential(nn.Linear(2*g,128),nn.LayerNorm(128),nn.GELU())
        bio=np.concatenate([data[t+'_train_Bio'][:1024] for t in [*TASKS,'state']]);self.register_buffer('bio_center',torch.tensor(bio.mean(0),dtype=torch.float32));self.register_buffer('bio_scale',torch.tensor(np.maximum(bio.std(0),.1),dtype=torch.float32))
        width=len(self.feature_center)+256
        if self.is_qwen:
            self.backbone=base;hidden=base.config.hidden_size
            for p in base.parameters():p.requires_grad_(False)
            for layer in base.layers[-min(protocol['adapterLayers'],len(base.layers)):]:
                for name in ['q_proj','v_proj']:setattr(layer.self_attn,name,LoRALinear(getattr(layer.self_attn,name),protocol['adapterRank']))
            self.numeric=nn.Linear(width,4*hidden);self.query=nn.Parameter(torch.zeros(1,1,hidden))
        else:hidden=256;self.numeric=nn.Sequential(nn.Linear(width,hidden),nn.GELU(),nn.Linear(hidden,hidden),nn.GELU())
        self.heads=nn.ModuleDict({task:nn.Linear(hidden,g) for task in [*TASKS,'state','activation']})
        for head in self.heads.values():nn.init.zeros_(head.weight);nn.init.zeros_(head.bias)
        for task in self.heads:
            self.register_buffer(task+'_mean',torch.tensor(data[task+'_Mean'],dtype=torch.float32));self.register_buffer(task+'_scale',torch.tensor(data[task+'_Scale'],dtype=torch.float32))
        if arm=='qwen_frozen':self.freeze_adapters()
    def freeze_adapters(self):
        if self.is_qwen:
            for p in self.backbone.parameters():p.requires_grad_(False)
    def hidden(self,x,ids,attention,bio,baseline,baseline_mask):
        observed=(x-self.feature_center)/self.feature_scale;embedded=(bio-self.bio_center)/self.bio_scale if self.use_biology else torch.zeros_like(bio)
        cell=self.starting_cell(torch.cat([((baseline-self.baseline_center)/self.baseline_scale)*baseline_mask,baseline_mask],1))
        features=torch.cat([observed,embedded,cell],dim=1)
        if not self.is_qwen:return self.numeric(features)
        text=self.backbone.embed_tokens(ids);prefix=self.numeric(features).reshape(-1,4,text.shape[-1]).to(text.dtype)
        values=torch.cat([prefix,text,self.query.expand(len(x),-1,-1).to(text.dtype)],dim=1)
        am=torch.cat([torch.ones((len(x),4),device=x.device,dtype=torch.long),attention,torch.ones((len(x),1),device=x.device,dtype=torch.long)],1)
        return self.backbone(inputs_embeds=values,attention_mask=am,position_ids=(am.cumsum(1)-1).clamp(min=0),use_cache=False,return_dict=True).last_hidden_state[:,-1].float()
    def forward(self,task,x,ids,attention,bio,baseline,baseline_mask,pairs=None):
        reference=self.expert(pairs) if task=='pair' else (torch.zeros_like(getattr(self,task+'_mean')) if task=='state' else getattr(self,task+'_mean'))
        return reference+self.heads[task](self.hidden(x,ids,attention,bio,baseline,baseline_mask))*getattr(self,task+'_scale')
    def added_state(self,task=None):
        def include(name):
            if name.startswith('backbone.') and '.lora_' not in name:return False
            if task and name.startswith('heads.') and not name.startswith('heads.'+task+'.'):return False
            return True
        return {n:v.detach().cpu().clone().contiguous() for n,v in self.state_dict().items() if include(n)}
    def restore(self,state,task=None):
        target=self.state_dict();expected=set(self.added_state(task))
        if set(state)!=expected:raise ValueError('Engine checkpoint architecture differs.')
        with torch.no_grad():
            for n,value in state.items():
                if value.shape!=target[n].shape or not bool(torch.isfinite(value).all()):raise ValueError('Invalid engine tensor: '+n)
                target[n].copy_(value.to(target[n].device))


def batch(data,prefix,indices,device):
    keys=[('X',torch.float32),('Ids',torch.long),('Attention',torch.long),('Bio',torch.float32),('Baseline',torch.float32),('BaselineMask',torch.float32)]
    result=[torch.as_tensor(data[prefix+'_'+key][indices],device=device,dtype=dtype) for key,dtype in keys]
    result.append(torch.as_tensor(data[prefix+'_Pairs'][indices],device=device,dtype=torch.long) if prefix+'_Pairs' in data else None)
    return result


def predict(model,data,task,part,batch_size=16):
    prefix=task+'_'+part;device=next(model.parameters()).device;values=[];model.eval()
    with torch.no_grad():
        for i in range(0,len(data[prefix+'_X']),batch_size):values.append(model(task,*batch(data,prefix,slice(i,i+batch_size),device)).cpu().numpy())
    return np.concatenate(values)


def baseline_features(data,prefix):return np.concatenate([data[prefix+'_X'],data[prefix+'_Bio'],data[prefix+'_Baseline'],data[prefix+'_BaselineMask'].astype(np.float32)],1)


def objective(model,data,task,rows,device):
    prefix=task+'_train';prediction=model(task,*batch(data,prefix,rows,device));y=torch.as_tensor(data[prefix+'_Y'][rows],device=device,dtype=torch.float32);mask=torch.as_tensor(data[prefix+'_Mask'][rows],device=device,dtype=torch.float32)
    scale=getattr(model,task+'_scale');reference=model.expert(torch.as_tensor(data[prefix+'_Pairs'][rows],device=device,dtype=torch.long)) if task=='pair' else getattr(model,task+'_mean')
    weights=1+torch.clamp(torch.abs((y-reference)/scale),max=3.)
    if prefix+'_Reliability' in data:weights=weights*torch.as_tensor(data[prefix+'_Reliability'][rows],device=device,dtype=torch.float32)
    return ((((prediction-y)/scale).square()*mask*weights).sum(1)/(mask*weights).sum(1).clamp(min=1)).mean()


def fit_foundation(model,data,event,protocol):
    device=next(model.parameters()).device
    for task in TASKS:
        for p in model.heads[task].parameters():p.requires_grad_(False)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=protocol['numericLearningRate'] if not model.is_qwen else protocol['learningRate'])
    for epoch in range(protocol['foundationPasses']):
        for task in ['state','activation']:
            order=np.random.default_rng(np.random.SeedSequence([protocol['seed'],epoch,0 if task=='state' else 1])).permutation(len(data[task+'_train_X']))
            for i in range(0,len(order),protocol['batchSize']):
                model.train();optimizer.zero_grad(set_to_none=True);loss=objective(model,data,task,order[i:i+protocol['batchSize']],device)
                if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite foundation objective; no retry.')
                loss.backward();nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True);optimizer.step()
                if i%512==0 or i+protocol['batchSize']>=len(order):event('foundation',arm=model.arm,task=task,epoch=epoch+1,examples=min(i+protocol['batchSize'],len(order)),totalExamples=len(order),objective=float(loss.detach().cpu()))
    for task in TASKS:
        for p in model.heads[task].parameters():p.requires_grad_(True)
    for task in ['state','activation']:
        for p in model.heads[task].parameters():p.requires_grad_(False)


def fit_tasks(model,data,folder,event,protocol):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);device=next(model.parameters()).device
    for t in ['state','activation']:
        for p in model.heads[t].parameters():p.requires_grad_(False)
    frozen={n:p._version for n,p in model.named_parameters() if not p.requires_grad};before=model.added_state();scores={};trace=[]
    for task in TASKS:
        report=metrics(predict(model,data,task,'validation',protocol['batchSize']),data[task+'_validation_Y'],data[task+'_validation_Mask'])
        scores[task]={'mse':report['mean']['mse'],'epoch':0,'stale':0,'active':True};save_file(model.added_state(task),str(folder/(task+'.safetensors')))
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=protocol['learningRate'] if model.is_qwen else protocol['numericLearningRate'],weight_decay=.01)
    for epoch in range(1,protocol['maximumEpochs']+1):
        orders={t:np.random.default_rng(np.random.SeedSequence([protocol['seed'],epoch,j])).permutation(len(data[t+'_train_X'])) for j,t in enumerate(TASKS) if scores[t]['active']}
        if not orders:break
        batches={t:[rows[i:i+protocol['batchSize']] for i in range(0,len(rows),protocol['batchSize'])] for t,rows in orders.items()};largest=max(map(len,batches.values()));seen={t:[] for t in batches}
        for i in range(largest):
            model.train();optimizer.zero_grad(set_to_none=True);terms=[]
            for task,rows in batches.items():
                if i>=len(rows):continue
                terms.append(objective(model,data,task,rows[i],device)*(largest/len(rows)));seen[task].extend(rows[i].tolist())
            loss=sum(terms)/len(TASKS)
            if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite response objective; no retry.')
            loss.backward();nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True);optimizer.step()
        for task,order in orders.items():
            if sorted(seen[task])!=list(range(len(order))):raise ValueError('A task epoch omitted or repeated a training condition.')
            prediction=predict(model,data,task,'validation',protocol['batchSize']);score=metrics(prediction,data[task+'_validation_Y'],data[task+'_validation_Mask'])['mean']['mse']
            row={'arm':model.arm,'task':task,'epoch':epoch,'conditionsSeen':len(order),'validationMse':score};trace.append(row);event('response_epoch',**row)
            if score<scores[task]['mse']-protocol['minimumDelta']:
                scores[task].update(mse=score,epoch=epoch,stale=0);save_file(model.added_state(task),str(folder/(task+'.safetensors')))
            else:scores[task]['stale']+=1
            if scores[task]['stale']>=protocol['patience']:
                scores[task]['active']=False
                for p in model.heads[task].parameters():p.requires_grad_(False)
        if any(p._version!=frozen[n] for n,p in model.named_parameters() if n in frozen):raise ValueError('A frozen engine parameter changed.')
    adapter_changed=any('.lora_' in n and not torch.equal(v,before[n]) for n,v in model.added_state().items())
    if model.arm=='qwen_frozen' and adapter_changed:raise ValueError('The fixed-Qwen control changed adapters.')
    selected={}
    for task in TASKS:
        model.restore(load_file(str(folder/(task+'.safetensors'))),task);first=predict(model,data,task,'validation',protocol['batchSize']);model.restore(load_file(str(folder/(task+'.safetensors'))),task)
        np.testing.assert_allclose(first,predict(model,data,task,'validation',protocol['batchSize']),rtol=1e-4,atol=1e-5)
        selected[task]={**scores[task],'report':metrics(first,data[task+'_validation_Y'],data[task+'_validation_Mask'],data[task+'_validation_Group']),'weightReloadPassed':True}
    return {'arm':model.arm,'tasks':selected,'trace':trace,'frozenParametersPreserved':True,'adaptersChangedDuringResponseTraining':adapter_changed,
            'foundationPretrainedBiology':model.use_biology,'numericParameterCount':sum(p.numel() for n,p in model.named_parameters() if not n.startswith('backbone.'))}


def run(inputs,out,archive,event,device='cuda',loader=None,encoder_loader=None,protocol=PROTOCOL):
    from transformers import Qwen2Model
    from cell_training_pretrained import encode_local,ATTRIBUTION
    inputs,out,archive=map(Path,[inputs,out,archive]);out.mkdir(parents=True,exist_ok=True);archive.mkdir(parents=True,exist_ok=True)
    meta=json.loads((inputs/'manifest.json').read_text())
    if meta.get('schema')!='fold.cell-training-data/2' or sha(inputs/'data.npz')!=meta['dataSha256'] or meta['testAnswersUploaded'] or not meta['noTruncation']:raise ValueError('Reviewed, protected training data required.')
    with np.load(inputs/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    if any('test' in n and n.endswith('_Y') for n in data):raise ValueError('Final answers must stay local.')
    if device!='cuda' and loader is None:raise ValueError('Only injected tiny fixtures may run this study on CPU.')
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('Approved CUDA device unavailable; no fallback.')
    if loader is None:
        for prefix,n in [('state_train',10000),('pair_train',77),('pair_validation',26),('activation_train',102),('inhibition_train',512),('inhibition_validation',64),('inhibition_test',64),('drug_train',1152),('drug_validation',144),('drug_test',144)]:
            if len(data[prefix+'_X'])!=n:raise ValueError('Unexpected protected training split: '+prefix)
        if len(data['genes'])!=2132 or not meta['freshFinalInterventionGroups']:raise ValueError('Protected gene panel and fresh groups required.')
    torch.manual_seed(protocol['seed']);torch.set_num_threads(8)
    if device=='cuda':torch.backends.cuda.matmul.allow_tf32=False
    prefixes=sorted({k[:-2] for k in data if k.endswith('_X')});texts=[];slices={}
    for prefix in prefixes:slices[prefix]=slice(len(texts),len(texts)+len(data[prefix+'_BioText']));texts.extend(data[prefix+'_BioText'].tolist())
    bio=encode_local(inputs/'biology',texts,device=device,batch=protocol['batchSize'],loader=encoder_loader,event=event)
    for prefix in prefixes:data[prefix+'_Bio']=bio[slices[prefix]]
    np.savez_compressed(archive/'biology-input-embeddings.npz',**{p:data[p+'_Bio'] for p in prefixes});event('biology_embeddings_ready',profiles=len(texts),dimension=128,attribution=ATTRIBUTION)
    baseline_fits={};baselines={};candidates={task:{} for task in TASKS};selected={task:None for task in TASKS}
    for task in TASKS:
        # Baselines get the same available numeric and biology features.
        x=baseline_features(data,task+'_train');vx=baseline_features(data,task+'_validation')
        fit=fit_baselines(x,data[task+'_train_Y'],data[task+'_train_Mask'],vx,data[task+'_validation_Y'],data[task+'_validation_Mask']);baseline_fits[task]=fit
        baselines[task]={name:metrics(pred,data[task+'_validation_Y'],data[task+'_validation_Mask'],data[task+'_validation_Group']) for name,pred in baseline_predictions(fit,vx).items()}
        if task=='pair':
            expert=RNAExpert({k[7:]:v for k,v in data.items() if k.startswith('expert_')});pred=expert(torch.tensor(data[task+'_validation_Pairs'])).numpy()
            baselines[task]['internal_rna']=metrics(pred,data[task+'_validation_Y'],data[task+'_validation_Mask'])
        event('baselines_ready',task=task,ridgePenalty=fit['penalty'])
    base=loader() if loader else Qwen2Model.from_pretrained(inputs/'checkpoint',local_files_only=True,trust_remote_code=False,use_safetensors=True,dtype=torch.bfloat16,attn_implementation='sdpa')
    base=base.to(device)
    if protocol.get('gradientCheckpointing'):base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    trials=[];foundation_states={}
    # Final-test predictions start only after every candidate checkpoint has
    # been selected on its own task's validation outcomes.
    for arm in protocol['arms']:
        torch.manual_seed(protocol['seed']);model=CellEngine(base if arm.startswith('qwen') else None,data,arm,protocol).to(device)
        foundation_key='qwen' if arm=='qwen_frozen' else arm
        if arm=='qwen_frozen':model.restore(foundation_states['qwen']);model.freeze_adapters()
        else:
            fit_foundation(model,data,event,protocol)
            if arm=='qwen':foundation_states['qwen']=model.added_state()
        folder=archive/arm;trial=fit_tasks(model,data,folder,event,protocol);trials.append(trial);write(folder/'receipt.json',trial)
        for task,values in trial['tasks'].items():
            candidates[task][arm]=values['report']
            if selected[task] is None or values['mse']<selected[task]['validationMse']:
                selected[task]={'arm':arm,'epoch':values['epoch'],'validationMse':values['mse']}
                save_file(load_file(str(folder/(task+'.safetensors'))),str(out/(task+'-selected.safetensors')))
        if model.is_qwen:detach_adapters(base)
        del model;gc.collect()
        if device=='cuda':torch.cuda.empty_cache()
    winners={task:min({**candidates[task],**baselines[task]},key=lambda name:({**candidates[task],**baselines[task]})[name]['mean']['mse']) for task in TASKS}
    write(out/'SELECTION.json',{'tasks':selected,'validationWinnersIncludingBaselines':winners,'dataSha256':meta['dataSha256'],'criterion':'Separate per-task validation MSE; final answers unavailable','completedBeforeFinalPredictions':True})
    final_outputs={};validation_outputs={}
    for arm in protocol['arms']:
        model=CellEngine(base if arm.startswith('qwen') else None,data,arm,protocol).to(device)
        for task in TASKS:
            model.restore(load_file(str(archive/arm/(task+'.safetensors'))),task)
            validation_outputs[task+'__'+arm]=predict(model,data,task,'validation',protocol['batchSize'])
            for part in ['test','context_test']:
                if task+'_'+part+'_X' in data:final_outputs[task+'_'+part+'__'+arm]=predict(model,data,task,part,protocol['batchSize'])
        if model.is_qwen:detach_adapters(base)
        del model;gc.collect()
    for task,fit in baseline_fits.items():
        for part in ['validation','test','context_test']:
            prefix=task+'_'+part
            if prefix+'_X' not in data:continue
            x=baseline_features(data,prefix)
            for name,pred in baseline_predictions(fit,x).items():(validation_outputs if part=='validation' else final_outputs)[prefix+'__'+name]=pred
        np.savez_compressed(archive/(task+'-ridge.npz'),**{k:fit[k] for k in ['center','scale','mean','weights']})
    write(out/'BASELINE_ARTIFACTS.json',{task:{'path':str(archive/(task+'-ridge.npz')),'sha256':sha(archive/(task+'-ridge.npz')),'penalty':fit['penalty'],'trials':fit['trials']} for task,fit in baseline_fits.items()})
    np.savez_compressed(out/'final-predictions.npz',**final_outputs);np.savez_compressed(out/'validation-predictions.npz',**validation_outputs)
    report={'schema':'fold.cell-training-study/2','state':'done','protocol':protocol,'dataSha256':meta['dataSha256'],'selectedPerTask':selected,
            'validation':candidates,'baselineValidation':baselines,'validationWinnersIncludingBaselines':winners,'trials':trials,'units':meta['units'],'bioEncoderAttribution':ATTRIBUTION,
            'freshFinalAnswersEvaluated':False,'testAnswersUploaded':False,'automaticPromotion':False,'automaticRetry':False,
            'predictionUncertaintyCalibration':'Not established; grouped evaluation intervals are not individual predictive intervals.',
            'interpretation':'One seed engineering/scientific pilot. Models selected per task on validation; test inputs predicted after selection; final answers stay local. No whole-cell or independent-study claim.'}
    write(out/'RESULTS.json',report);write(out/'DATA_MANIFEST.json',meta);event('study_finished',selected=selected);return report
