#!/usr/bin/env python3
"""Train an inverse head. Preserve the Qwen backbone and all prior checkpoints."""
import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from rna_design_core import atomic,digest


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--base',required=True);p.add_argument('--maximum-seconds',type=float,default=300);a=p.parse_args()
    if a.out.exists():
        raise ValueError('Output must be new. Prior checkpoints must remain available.')
    a.out.mkdir(parents=True)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    import torch
    from torch.nn import functional as F
    from safetensors.torch import save_file
    from rna_design_qwen import load_backbone,features,head
    protocol=json.loads((a.data/'protocol.json').read_text());labels=json.loads((a.data/'labels.json').read_text())
    if labels['protocolSha256'] != protocol['sha256'] or protocol['sha256'] != digest({k:v for k,v in protocol.items() if k!='sha256'}):
        raise ValueError('Training protocol integrity check failed.')
    config=protocol['training']; seed=config['seed'];random.seed(seed);torch.manual_seed(seed)
    receipt=Path(__file__).resolve().parents[1]/'scientific/qwen_rna_install.json'
    import workspace
    prior_path=Path(workspace.expand(json.loads(receipt.read_text())['checkpoint']))
    prior=json.loads(prior_path.read_text())
    if Path(prior['baseCheckpoint']).resolve()!=Path(a.base).resolve():
        raise ValueError('Use the preserved, qualified Qwen base for this pilot.')
    for entry in prior['baseFiles']:
        with (Path(a.base)/entry['file']).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:
                raise ValueError('Preserved Qwen base checksum changed: '+entry['file'])
    start=time.monotonic()
    model,tokens,device=load_backbone(a.base)
    before={n:p._version for n,p in model.named_parameters()}
    cache={}
    for row in labels['labels']:
        if row['target'] not in cache:
            cache[row['target']]=features(model,tokens,row['target'],device)
    feature_seconds=time.monotonic()-start
    width=next(iter(cache.values())).shape[-1]
    inverse=head(width).to(device)
    save_file({k:v.detach().cpu().contiguous() for k,v in inverse.state_dict().items()},str(a.out/'initial.safetensors'))
    optimizer=torch.optim.AdamW(inverse.parameters(),lr=config['headLearningRate'])
    records=[];best=float('inf');best_epoch=None
    training=[r for r in labels['labels'] if r['split']=='train']
    validation=[r for r in labels['labels'] if r['split']=='validation' and r['qualifies']]
    if not any(r['qualifies'] for r in training) or not validation:
        raise ValueError('Both training and validation need solver successes.')
    for epoch in range(config['epochs']):
        if time.monotonic()-start>a.maximum_seconds:
            break
        rng=random.Random(seed+epoch);rng.shuffle(training);losses=[]
        inverse.train()
        for row in training:
            logits=inverse(cache[row['target']]);ids=torch.tensor(['ACGU'.index(c) for c in row['sequence']],device=device)
            if row['qualifies']:
                loss=F.cross_entropy(logits,ids)
            else:
                chosen=logits.softmax(-1).gather(-1,ids[:,None]).squeeze(-1)
                loss=-(1-chosen).clamp(min=1e-6).log().mean()*.1*(1-row['pairF1'])
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(inverse.parameters(),1.);optimizer.step();losses.append(float(loss.detach().cpu()))
        inverse.eval()
        with torch.no_grad():
            val=statistics_mean([float(F.cross_entropy(inverse(cache[r['target']]),torch.tensor(['ACGU'.index(c) for c in r['sequence']],device=device)).cpu()) for r in validation])
        if val<best:
            best,best_epoch=val,epoch+1
            save_file({k:v.detach().cpu().contiguous() for k,v in inverse.state_dict().items()},str(a.out/'selected.safetensors'))
        event={'epoch':epoch+1,'trainLoss':statistics_mean(losses),'validationPositiveBaseCE':val,'elapsedSeconds':time.monotonic()-start}
        records.append(event);print(json.dumps(event),flush=True)
    save_file({k:v.detach().cpu().contiguous() for k,v in inverse.state_dict().items()},str(a.out/'final.safetensors'))
    if before != {n:p._version for n,p in model.named_parameters()}:
        raise ValueError('Frozen Qwen parameters changed.')
    weights=a.out/'selected.safetensors'
    checkpoint={'schema':'fold.rna-design-qwen/1','version':'qwen-inverse-head/0.1.0','baseCheckpoint':str(Path(a.base).resolve()),
                'baseRevision':prior['baseRevision'], 'baseFiles':prior['baseFiles'],
                'priorCheckpointReceipt':str(prior_path),'priorCheckpointSha256':hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                'featureWidth':width,'tokenIds':tokens,
                'weights':{'file':weights.name,'sha256':hashlib.sha256(weights.read_bytes()).hexdigest()},
                'protocolSha256':protocol['sha256'],'labelsSha256':labels['sha256'],'training':config,'selectedEpoch':best_epoch,
                'trainableParameters':sum(p.numel() for p in inverse.parameters()),'frozenBackboneUnchanged':True,
                'trained':'Inverse sequence head on frozen Qwen target features. No Qwen backbone or prior folding head was changed.',
                'labelCounts':{split:{'success':sum(r['split']==split and r['qualifies'] for r in labels['labels']), 'nearMissOrFailure':sum(r['split']==split and not r['qualifies'] for r in labels['labels'])} for split in ('train','validation')},
                'evidence':'Solver labels only. No measurement labels. Failed labels use a small unlikelihood loss; successes use base cross-entropy.',
                'startupAndFeatureSeconds':feature_seconds,'totalSeconds':time.monotonic()-start,'device':device,
                'torch':torch.__version__,'transformers':__import__('transformers').__version__,'epochs':records,
                'command':sys.argv,'seed':seed}
    checkpoint['sha256']=digest(checkpoint);atomic(a.out/'checkpoint.json',checkpoint)


def statistics_mean(values):
    return sum(values)/len(values)


if __name__=='__main__': main()
