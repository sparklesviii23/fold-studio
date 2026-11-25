#!/usr/bin/env python3
"""Bounded offline RNA pilot. Source archive is acquired separately; no downloads here."""
import argparse
import gc
import hashlib
import json
import random
import sys
import tarfile
import time
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scientific'))
from qwen_rna_contract import accuracy, decode, digest, pairs, result


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def prepare(archive, destination):
    destination.mkdir(parents=True, exist_ok=False)
    rows, rejected = [], []
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if not member.name.endswith('.ct'):
                continue
            lines = source.extractfile(member).read().decode().splitlines()
            n = int(lines[0].split()[0])
            family = Path(member.name).name.split('_')[0]
            if not 24 <= n <= 128 or family not in ('5s', 'tRNA', 'srp'):
                continue
            fields = [line.split() for line in lines[1:] if line.strip()]
            sequence = ''.join(f[1].upper().replace('T', 'U') for f in fields)
            if len(fields) != n or len(sequence) != n or set(sequence)-set('ACGU'):
                continue
            links = [int(f[4])-1 for f in fields]
            good = all(j == -1 or 0 <= j < n and links[j] == i for i, j in enumerate(links))
            edges = [(i, j) for i, j in enumerate(links) if j > i]
            good = good and bool(edges) and all(j-i > 3 and sequence[i]+sequence[j] in {'AU','UA','GC','CG','GU','UG'} for i,j in edges)
            good = good and not any(i < k < j < l for i,j in edges for k,l in edges)
            if not good:
                rejected.append(member.name)
                continue
            structure = ['.']*n
            for i,j in edges:
                structure[i],structure[j] = '(',')'
            rows.append({'id': Path(member.name).stem, 'family': family, 'sequence': sequence,
                         'structure': ''.join(structure), 'sourceMember': member.name,
                         'sourceSha256': hashlib.sha256(source.extractfile(member).read()).hexdigest(),
                         'evidence': 'ArchiveII comparative/reference secondary-structure annotation; not a new measurement'})
    # Entire biological families are reserved. Screen sequence and structural near-duplicates
    # across families BEFORE selecting a small deterministic compute-bounded subset.
    groups = {'train': ('5s', 48), 'validation': ('tRNA', 16), 'test': ('srp', 24)}
    splits, seen, exclusions = {}, [], []
    for part,(family,limit) in groups.items():
        chosen=[]
        for row in sorted((x for x in rows if x['family']==family), key=lambda x:digest(x['id'])):
            if any(x['sequence']==row['sequence'] for x in chosen):
                continue
            near = False
            for prior in seen:
                a,b=prior['sequence'],row['sequence']
                if SequenceMatcher(None,a,b,autojunk=False).ratio() >= .8:
                    near=True;break
                if len(a)==len(b) and accuracy(prior['structure'],row['structure'])['f1'] >= .8:
                    near=True;break
            if near:
                exclusions.append(row['id']);continue
            chosen.append(row)
            if len(chosen)==limit:
                break
        if len(chosen)!=limit:
            raise ValueError('Not enough protected examples for '+part)
        splits[part]=chosen;seen.extend(chosen)
    manifest = {'schema':'fold.qwen-rna-split/1', 'source':'https://github.com/marcellszi/dl-rna/releases/download/Data/archiveII.tar.gz',
                'sourceSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'citation':'Szikszai et al., Bioinformatics 2022, doi:10.1093/bioinformatics/btac415; ArchiveII reference structures',
                'seed':20261115, 'frozenBeforeTraining':True, 'splitFamilies':groups,
                'selection':'SHA256 order; canonical nested pairs only; 24–128 nt; exact sequence deduplication',
                'crossSplitScreen': 'No sequence SequenceMatcher ratio >=0.8 or equal-length reference pair F1 >=0.8 across selected splits.',
                'excludedInvalidAnnotations':rejected,'excludedCrossSplitNearDuplicates':exclusions,
                'limits':'Small compute-bounded family-held-out pilot; not the full ArchiveII benchmark. Qwen pretraining contamination is unknown.',
                'splits':splits}
    manifest['sha256']=digest(manifest)
    write(destination/'split.json',manifest)
    print(json.dumps({'prepared':str(destination),'sha256':manifest['sha256'],'counts':{k:len(v) for k,v in splits.items()}}),flush=True)


def train(args):
    import numpy as np
    import torch
    from safetensors.torch import load_file, save_file
    from transformers import AutoTokenizer, Qwen2Model
    from qwen_rna_model import RNAModel, detach_adapters, marginals
    from torch.nn import functional as F
    folder=args.out;folder.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();torch.set_num_threads(8);torch.manual_seed(20261115)
    manifest=json.loads((args.data/'split.json').read_text())
    if manifest['sha256']!=digest({k:v for k,v in manifest.items() if k!='sha256'}):
        raise ValueError('Frozen split seal changed.')
    splits=manifest['splits'];device='mps' if torch.backends.mps.is_available() else 'cpu'
    def event(name,**values):
        value={'event':name,'seconds':round(time.monotonic()-start,2),**values}
        print(json.dumps(value),flush=True)
        with (folder/'events.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
    event('start',device=device,externalFoldingEngines=False,splitSha256=manifest['sha256'])
    traces={};selected={};models={};base=None;tokens=None;cache={}
    for arm in ('compact','qwen_frozen','qwen_adapter'):
        torch.manual_seed(20261115)
        if arm.startswith('qwen') and base is None:
            tokenizer=AutoTokenizer.from_pretrained(args.base,local_files_only=True,trust_remote_code=False)
            tokens={c:tokenizer.encode(c,add_special_tokens=False)[0] for c in 'ACGU'}
            if any(len(tokenizer.encode(c,add_special_tokens=False))!=1 for c in tokens):
                raise ValueError('One token per nucleotide required.')
            event('loading_local_qwen')
            base=Qwen2Model.from_pretrained(args.base,local_files_only=True,trust_remote_code=False,use_safetensors=True,
                                           dtype=torch.float16,attn_implementation='sdpa').to(device).eval()
            event('qwen_loaded',parameters=sum(p.numel() for p in base.parameters()),tokenIds=tokens)
        model=RNAModel(base if arm.startswith('qwen') else None,tokens,adapters=arm=='qwen_adapter').to(device)
        if arm=='qwen_frozen':
            with torch.no_grad():
                for row in splits['train']+splits['validation']:
                    cache[row['id']]=model.hidden(row['sequence']).detach().cpu()
            event('frozen_features_cached',examples=len(cache))
        initial={n:p.detach().cpu().clone() for n,p in model.named_parameters() if p.requires_grad}
        frozen_versions={n:p._version for n,p in model.named_parameters() if not p.requires_grad}
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.001 if arm=='compact' else .0003)
        best=-1.;history=[];arm_start=time.monotonic()
        def infer(rows):
            model.eval();values=[]
            with torch.no_grad():
                for row in rows:
                    c=cache.get(row['id']) if arm=='qwen_frozen' else None
                    logits=model(row['sequence'],c.to(device) if c is not None else None)
                    values.append(marginals(logits).float().cpu().numpy())
            return values
        for epoch in range(args.epochs+1):
            if epoch:
                model.train();losses=[];order=list(splits['train']);random.Random(20261115+epoch).shuffle(order)
                for step,row in enumerate(order):
                    if time.monotonic()-start>args.maximum_seconds:
                        raise TimeoutError('Bounded training budget reached; partial evidence retained, no automatic retry.')
                    seq=row['sequence'];target=list(range(len(seq)))
                    for i,j in pairs(row['structure']):target[i]=j;target[j]=i
                    c=cache.get(row['id']) if arm=='qwen_frozen' else None
                    optimizer.zero_grad(set_to_none=True)
                    logits=model(seq,c.to(device) if c is not None else None)
                    loss=F.cross_entropy(logits,torch.tensor(target,device=device))
                    if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite training loss.')
                    loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
                    optimizer.step();losses.append(float(loss.detach()))
                    if step%16==0:event('training',arm=arm,epoch=epoch,step=step,loss=losses[-1])
            probabilities=infer(splits['validation'])
            choices=[]
            for threshold in (.02,.05,.1,.15,.2,.3,.4):
                score=float(np.mean([accuracy(decode(p,threshold),r['structure'])['f1'] for p,r in zip(probabilities,splits['validation'])]))
                choices.append((score,threshold))
            score,threshold=max(choices,key=lambda x:x[0])
            history.append({'epoch':epoch,'validationF1':score,'threshold':threshold,'trainingLoss':float(np.mean(losses)) if epoch else None})
            if score>best:
                best=score;selected[arm]={'epoch':epoch,'validationF1':score,'threshold':threshold}
                save_file(model.added_state(),str(folder/(arm+'.safetensors')))
            event('validation',arm=arm,**history[-1])
        save_file(model.added_state(),str(folder/(arm+'-final.safetensors')))
        changed=[n for n,p in model.named_parameters() if p.requires_grad and not torch.equal(initial[n],p.detach().cpu())]
        preserved=all(p._version==frozen_versions[n] for n,p in model.named_parameters() if n in frozen_versions)
        if not preserved:raise ValueError('Frozen base parameter mutated.')
        traces[arm]={'history':history,'seconds':time.monotonic()-arm_start,'trainableParameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
                     'changedTensors':changed,'frozenWeightsUnchanged':preserved,'adaptersChanged':any('.lora_' in n for n in changed)}
        event('arm_finished',arm=arm,selected=selected[arm],receipt=traces[arm])
        if arm.startswith('qwen'):detach_adapters(base)
        del model,optimizer;gc.collect()
        if device=='mps':torch.mps.empty_cache()
    selection={'schema':'fold.qwen-rna-selection/1','splitSha256':manifest['sha256'],'selected':selected,'criterion':'Validation mean per-RNA exact pair F1; thresholds and epochs chosen without final-test scoring.'}
    write(folder/'selection.json',selection)
    event('selection_sealed',sha256=digest(selection))
    # Only now evaluate held-out outcomes. No further training/tuning below.
    benchmark={'schema':'fold.qwen-rna-benchmark/1','splitSha256':manifest['sha256'],'selectionSha256':digest(selection),'device':device,'arms':{},'training':traces}
    for arm in ('compact','qwen_frozen','qwen_adapter'):
        model=RNAModel(base if arm.startswith('qwen') else None,tokens,adapters=arm=='qwen_adapter').to(device).eval()
        model.restore(load_file(str(folder/(arm+'.safetensors'))))
        records=[];briers=[]
        with torch.no_grad():
            for row in splits['test']:
                logits=model(row['sequence']);matrix=marginals(logits).float().cpu().numpy()
                out=result(row['sequence'],matrix.tolist(),selected[arm]['threshold'],{'engine':arm,'externalEngines':[]},row['structure'])
                truth=np.zeros_like(matrix)
                for i,j in pairs(row['structure']):truth[i,j]=truth[j,i]=1
                mask=np.triu(np.ones_like(truth,dtype=bool),4)
                briers.append(float(((matrix-truth)[mask]**2).mean()))
                out['caseId']=row['id'];records.append(out)
            # Reload selected state and reproduce one complete numerical matrix.
            first=records[0];model.restore(load_file(str(folder/(arm+'.safetensors'))))
            again=marginals(model(first['sequence'])).float().cpu().numpy()
            expected=np.zeros_like(again)
            for i,j,p in first['basePairProbabilities']:expected[i-1,j-1]=expected[j-1,i-1]=p
            error=float(np.max(np.abs(again-expected)))
            if error>1e-6:raise ValueError('Checkpoint reload prediction differs.')
        write(folder/(arm+'-test-predictions.json'),records)
        benchmark['arms'][arm]={'meanF1':float(np.mean([r['comparison']['f1'] for r in records])),
                                'meanPairBrier':float(np.mean(briers)),'cases':len(records),'reloadMaxAbsError':error,
                                'worstCases':sorted([{'id':r['caseId'],**r['comparison']} for r in records],key=lambda r:r['f1'])[:5]}
        if arm.startswith('qwen'):detach_adapters(base)
        del model;gc.collect()
    config={'schema':'fold.qwen-rna-checkpoint/1','version':'0.1.0','baseCheckpoint':str(args.base.resolve()),
            'baseRevision':'488639f1ff808d1d3d0ba301aef8c11461451ec5','tokenIds':tokens,
            'splitSha256':manifest['sha256'],'selected':selected,'maximumLength':128,
            'weights':{a:{'file':a+'.safetensors','sha256':hashlib.sha256((folder/(a+'.safetensors')).read_bytes()).hexdigest()} for a in selected},
            'runtime':sys.executable,'device':device,'externalFoldingEngines':False,'promotion':'Research candidate only; no established-engine superiority or cell-default replacement.'}
    write(folder/'checkpoint.json',config);write(folder/'benchmark.json',benchmark)
    event('finished',benchmark={a:v['meanF1'] for a,v in benchmark['arms'].items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path);parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--base',type=Path);parser.add_argument('--out',type=Path)
    parser.add_argument('--epochs',type=int,default=3);parser.add_argument('--maximum-seconds',type=int,default=1500)
    args=parser.parse_args()
    if args.archive:prepare(args.archive,args.data)
    else:train(args)
