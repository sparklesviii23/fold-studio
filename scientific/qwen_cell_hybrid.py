"""Frozen numerical RNA expert INSIDE a gene-aware Qwen neural model.

Expandable full per-gene output channels; no external predictor call or fixed PCA
decoder. A zero correction preserves the original RNA expert at initialization.
"""
import numpy as np
import torch
from torch import nn
from qwen_cell_model import LoRALinear


class RNAExpert(nn.Module):
    context='human K562 SunTag paired CRISPRa'
    unit='mean log1p(counts per 10000) response'
    def __init__(self,arrays):
        super().__init__();self.genes=tuple(str(g) for g in arrays['genes']);self.symbols=tuple(str(g) for g in arrays['singleGenes'])
        for name,value in arrays.items():
            if np.asarray(value).dtype.kind in 'fiu':self.register_buffer(name,torch.tensor(np.asarray(value),dtype=torch.float32))
    def forward(self,pairs):
        left=self.singleEffects[pairs[:,0]];right=self.singleEffects[pairs[:,1]];a=left@self.encoder;b=right@self.encoder
        features=(torch.cat([a+b,torch.abs(a-b),a*b],dim=1)-self.featureCenter)/self.featureScale
        codes=torch.tanh(features@self.w1+self.b1)@self.w2+self.b2
        return self.alpha*(left+right)+(codes*self.codeScale)@self.decoder.T+self.residualCenter


class ExpertBank(nn.Module):
    def __init__(self,expert):
        super().__init__();self.models=nn.ModuleDict({'rna':expert});self.genes=expert.genes;self.context=expert.context;self.unit=expert.unit
    def register(self,name,expert):
        if name in self.models or expert.genes!=self.genes or expert.context!=self.context or expert.unit!=self.unit:
            raise ValueError('Additional expert needs a unique name and matching genes, biological context and units.')
        self.models[name]=expert
    def forward(self,pairs,weights=None):
        if weights is None:return self.models['rna'](pairs)
        if not weights or set(weights)-set(self.models) or any(not np.isfinite(v) or v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-6:
            raise ValueError('Expert fusion requires explicit nonnegative weights summing to one.')
        return sum(float(v)*self.models[name](pairs) for name,v in weights.items())


class GeneReadout(nn.Module):
    def __init__(self,hidden,genes,neighbors,weights,gene_features,scale):
        super().__init__();self.channels=len(genes)
        self.full=nn.Linear(hidden,self.channels);nn.init.zeros_(self.full.weight);nn.init.zeros_(self.full.bias)
        self.graph_query=nn.Linear(hidden,gene_features.shape[1],bias=False);nn.init.zeros_(self.graph_query.weight)
        self.gene_features=nn.Parameter(torch.as_tensor(gene_features,dtype=torch.float32).clone())
        self.register_buffer('neighbors',torch.as_tensor(neighbors,dtype=torch.long));self.register_buffer('weights',torch.as_tensor(weights,dtype=torch.float32))
        self.register_buffer('scale',torch.as_tensor(scale,dtype=torch.float32))
    def forward(self,hidden):
        graph=(self.gene_features[self.neighbors]*self.weights[...,None]).sum(1)
        return (self.full(hidden)+self.graph_query(hidden)@graph.T)*self.scale


class HybridCellModel(nn.Module):
    def __init__(self,base,data,mode='qwen'):
        super().__init__()
        if mode not in ['qwen','small']:raise ValueError('Unknown hybrid mode.')
        arrays={k[7:]:v for k,v in data.items() if k.startswith('expert_')};self.experts=ExpertBank(RNAExpert(arrays));self.mode=mode;hidden=base.config.hidden_size
        self.backbone=base
        for p in base.parameters():p.requires_grad_(False)
        if mode=='qwen':
            for layer in base.layers[-2:]:
                for name in ['q_proj','v_proj']:setattr(layer.self_attn,name,LoRALinear(getattr(layer.self_attn,name),8))
            self.numeric=nn.Linear(data['trainX'].shape[1],4*hidden);self.query=nn.Parameter(torch.zeros(1,1,hidden));readout_hidden=hidden
        else:self.small=nn.Sequential(nn.Linear(data['trainX'].shape[1]+hidden,64),nn.Tanh());readout_hidden=64
        gene_features=arrays['encoder'].astype(np.float32)
        self.readout=GeneReadout(readout_hidden,arrays['genes'],data['graphNeighbors'],data['graphWeights'],gene_features,data['correctionScale'])
        self.auxiliary=nn.Linear(readout_hidden,len(arrays['genes']));nn.init.normal_(self.auxiliary.weight,std=.0001);nn.init.zeros_(self.auxiliary.bias)
        self.register_buffer('auxiliary_scale',torch.tensor(data['auxiliaryScale'],dtype=torch.float32))
    def hidden(self,x,ids,attention):
        embeddings=self.backbone.embed_tokens(ids)
        if self.mode=='small':
            pooled=(embeddings.float()*attention[...,None]).sum(1)/attention.sum(1,keepdim=True).clamp(min=1)
            return self.small(torch.cat([x.float(),pooled],dim=1))
        prefix=self.numeric(x.float()).reshape(-1,4,self.backbone.config.hidden_size)
        values=torch.cat([prefix.to(embeddings.dtype),embeddings,self.query.expand(len(x),-1,-1).to(embeddings.dtype)],dim=1)
        mask=torch.cat([torch.ones((len(x),4),device=x.device,dtype=torch.long),attention,torch.ones((len(x),1),device=x.device,dtype=torch.long)],dim=1)
        positions=(mask.cumsum(1)-1).clamp(min=0)
        return self.backbone(inputs_embeds=values,attention_mask=mask,position_ids=positions,use_cache=False,return_dict=True).last_hidden_state[:,-1].float()
    def forward(self,x,ids,attention,pairs):return self.experts(pairs)+self.readout(self.hidden(x,ids,attention))
    def pretrain(self,x,ids,attention):return self.auxiliary(self.hidden(x,ids,attention))*self.auxiliary_scale
    def freeze_qwen(self):
        for p in self.backbone.parameters():p.requires_grad_(False)
    def freeze_auxiliary(self):
        for p in self.auxiliary.parameters():p.requires_grad_(False)
    def freeze_readout(self):
        for p in self.readout.parameters():p.requires_grad_(False)
    def added_state(self):
        return {n:p.detach().cpu().clone().contiguous() for n,p in self.state_dict().items() if not n.startswith('backbone.') or '.lora_' in n}
    def restore(self,state):
        params=self.state_dict();expected=set(self.added_state())
        if set(state)!=expected:raise ValueError('Hybrid checkpoint architecture differs.')
        for n,value in state.items():
            if value.shape!=params[n].shape or not bool(torch.isfinite(value).all()):raise ValueError('Invalid hybrid tensor: '+n)
        with torch.no_grad():
            for n,value in state.items():params[n].copy_(value.to(params[n].device))


def detach_adapters(base):
    for layer in base.layers:
        for name in ['q_proj','v_proj']:
            module=getattr(layer.self_attn,name)
            if isinstance(module,LoRALinear):setattr(layer.self_attn,name,module.base)
