"""Qwen *is* the response predictor: numerical prefix → Qwen → numerical head.

The original Qwen parameters are frozen. LoRA A/B weights inside selected Qwen
attention layers, an input projection, query and output head are trained jointly.
No language-model prose or external scientific predictor computes the output.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F


class LoRALinear(nn.Module):
    def __init__(self,base,rank=8):
        super().__init__()
        if not isinstance(base,nn.Linear) or not 1<=rank<=64:raise ValueError('Expected a linear projection and rank 1–64.')
        self.base=base;self.rank=rank;self.scale=1.0
        for p in base.parameters():p.requires_grad_(False)
        self.lora_a=nn.Parameter(torch.empty(rank,base.in_features,device=base.weight.device,dtype=torch.float32))
        self.lora_b=nn.Parameter(torch.zeros(base.out_features,rank,device=base.weight.device,dtype=torch.float32))
        nn.init.kaiming_uniform_(self.lora_a,a=math.sqrt(5))

    def forward(self,x):
        y=self.base(x)
        return y+(F.linear(F.linear(x.float(),self.lora_a),self.lora_b)*self.scale).to(y.dtype)


class QwenCellPredictor(nn.Module):
    def __init__(self,qwen,input_features,decoder,target_center,target_scale,rank=8,layers=2,prefix_tokens=4):
        super().__init__()
        if qwen.config.model_type!='qwen2':raise ValueError('This initial implementation supports Qwen2/Qwen2.5 architecture only.')
        if not 1<=layers<=len(qwen.layers):raise ValueError('Invalid number of adapted Qwen layers.')
        self.qwen=qwen;self.prefix_tokens=prefix_tokens;self.hidden=qwen.config.hidden_size
        for p in qwen.parameters():p.requires_grad_(False)
        self.adapted=[]
        for i in range(len(qwen.layers)-layers,len(qwen.layers)):
            for name in ['q_proj','v_proj']:
                attention=qwen.layers[i].self_attn;setattr(attention,name,LoRALinear(getattr(attention,name),rank))
                self.adapted.append(f'qwen.layers.{i}.self_attn.{name}')
        self.input_projection=nn.Linear(input_features,prefix_tokens*self.hidden)
        self.query=nn.Parameter(torch.zeros(1,1,self.hidden))
        self.readout=nn.Linear(self.hidden,len(target_scale))
        nn.init.normal_(self.readout.weight,std=.002);nn.init.zeros_(self.readout.bias)
        self.register_buffer('decoder',torch.as_tensor(decoder,dtype=torch.float32).clone())
        self.register_buffer('target_center',torch.as_tensor(target_center,dtype=torch.float32).clone())
        self.register_buffer('target_scale',torch.as_tensor(target_scale,dtype=torch.float32).clone())

    def forward(self,features):
        prefix=self.input_projection(features.float()).reshape(-1,self.prefix_tokens,self.hidden)
        prefix=torch.cat([prefix,self.query.expand(len(features),-1,-1)],dim=1)
        dtype=self.qwen.embed_tokens.weight.dtype
        hidden=self.qwen(inputs_embeds=prefix.to(dtype),use_cache=False,return_dict=True).last_hidden_state[:,-1].float()
        codes=self.readout(hidden)
        return self.target_center+(codes*self.target_scale)@self.decoder.T

    def parameter_report(self):
        values=dict(self.named_parameters());train={n:p.numel() for n,p in values.items() if p.requires_grad}
        return {'baseQwenParameters':sum(p.numel() for n,p in values.items() if n.startswith('qwen.') and '.lora_' not in n),
                'frozenBaseParameters':sum(p.numel() for p in values.values() if not p.requires_grad),
                'trainableParameters':sum(train.values()),'qwenAdapterParameters':sum(v for n,v in train.items() if '.lora_' in n),
                'trainableByName':train,'adaptedModules':self.adapted,
                'baseQwenWeightsTrainable':False,'qwenAdaptersTrainable':True,
                'architectureExpansion':'LoRA adapters inside Qwen plus numerical input/output layers; base width/depth is unchanged.'}


def masked_mse(pred,target,mask):
    if pred.shape!=target.shape or pred.shape!=mask.shape or not bool(torch.all(mask.sum(-1)>0)):
        raise ValueError('Invalid prediction, target or evaluation mask.')
    return (((pred-target)**2*mask).sum(-1)/mask.sum(-1)).mean()


def objective(pred,target,mask,teacher=None,teacher_weight=0.):
    if not 0<=teacher_weight<=.5:raise ValueError('Teacher loss weight must be between 0 and 0.5.')
    measured=masked_mse(pred,target,mask)
    if teacher_weight and teacher is None:raise ValueError('Teacher predictions were not supplied.')
    return measured+teacher_weight*masked_mse(pred,teacher,mask) if teacher_weight else measured


def trainable_state(model):
    return {name:p.detach().cpu().contiguous() for name,p in model.named_parameters() if p.requires_grad}


def load_trainable_state(model,state):
    params={n:p for n,p in model.named_parameters() if p.requires_grad}
    if set(params)!=set(state):raise ValueError('Adapter architecture differs from this model.')
    for name,p in params.items():
        if p.shape!=state[name].shape or not bool(torch.isfinite(state[name]).all()):raise ValueError('Invalid adapter tensor: '+name)
    with torch.no_grad():
        for name,p in params.items():p.copy_(state[name].to(p.device))
