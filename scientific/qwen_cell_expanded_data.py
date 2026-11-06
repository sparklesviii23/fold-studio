"""Prepare complete-context cloud training from existing public local datasets.

2,000 distinct training-only cells; separate activation/inhibition/drug objectives.
New inhibition/drug test answers stay local, outside the cloud input directory.
"""
import json,math
from pathlib import Path
import numpy as np
import h5py
from qwen_cell_data import sha,write
from qwen_cell_biology import rank_sentences,pair_texts

SEED=20261106


def column(group,key):
    item=group[key]
    if isinstance(item,h5py.Group):
        codes=item['codes'][...]
        if (codes<0).any():raise ValueError('Missing category '+key)
        a=item['categories'][...][codes]
    else:a=item[...]
    return np.array([v.decode() if isinstance(v,bytes) else str(v) for v in a])


def split_groups(names,counts=(128,32,32),namespace='inhibition'):
    import hashlib
    order=sorted(set(str(x) for x in names),key=lambda n:hashlib.sha256(f'{SEED}:{namespace}:{n}'.encode()).hexdigest())
    if len(order)<sum(counts):raise ValueError('Insufficient distinct intervention groups.')
    a,b,c=counts;return {'train':order[:a],'validation':order[a:a+b],'test':order[a+b:a+b+c]}


def stratified_rows(labels,allowed,count,seed):
    rng=np.random.default_rng(seed);groups=[rng.permutation(np.flatnonzero(labels==g)).tolist() for g in sorted(set(allowed)) if np.any(labels==g)]
    chosen=[]
    while len(chosen)<count:
        before=len(chosen)
        for group in groups:
            if group and len(chosen)<count:chosen.append(group.pop())
        if len(chosen)==before:raise ValueError('Insufficient distinct training cells.')
    return np.array(sorted(chosen),dtype=np.int64)


def read_profiles(path,rows,genes,metadata):
    """Read only selected cells; normalize on the source's full measured gene set."""
    with h5py.File(path,'r') as f:
        v=f['var'];names=column(v,str(v.attrs['_index']));gi={g:i for i,g in enumerate(names)}
        cols=np.array([gi.get(str(g),-1) for g in genes]);measured=cols>=0;x=f['X'];rows=np.asarray(rows,dtype=np.int64)
        if isinstance(x,h5py.Dataset):
            full=np.asarray(x[rows,:],dtype=np.float32);totals=full.sum(1);raw=full[:,cols[measured]]
        else:
            # CSC source; select requested row values without loading the whole matrix.
            ptr=x['indptr'][...];mapping=np.full(len(metadata['labels']),-1,np.int64);mapping[rows]=np.arange(len(rows));raw=np.zeros((len(rows),int(measured.sum())),np.float32)
            for out,j in enumerate(cols[measured]):
                lo,hi=int(ptr[j]),int(ptr[j+1]);ri=x['indices'][lo:hi];select=mapping[ri];keep=select>=0
                raw[select[keep],out]=x['data'][lo:hi][keep]
            totals=np.asarray(metadata['librarySize'][rows],np.float32)
        if np.any(totals<=0) or not np.isfinite(raw).all() or (raw<0).any():raise ValueError('Invalid source cell counts.')
        values=np.zeros((len(rows),len(genes)),np.float32);values[:,measured]=np.log1p(raw*(1e4/totals[:,None]))
    return values,measured


def encode_complete(tokenizer,texts,limit=32763):
    # No truncation, including for future larger prompts. Exceeding the model's
    # actual position budget is an explicit preparation error before paid compute.
    encoded=tokenizer(texts,add_special_tokens=False,truncation=False,padding=False)['input_ids']
    lengths=np.array([len(x) for x in encoded],np.int64)
    if not len(lengths) or np.any(lengths<1) or lengths.max()>limit:raise ValueError('Complete biological input exceeds the model position budget.')
    width=int(math.ceil(int(lengths.max())/8)*8)
    if width>limit:width=int(lengths.max())
    pad=int(tokenizer.pad_token_id);ids=np.full((len(encoded),width),pad,np.int64);attention=np.zeros_like(ids)
    for i,tokens in enumerate(encoded):ids[i,-len(tokens):]=tokens;attention[i,-len(tokens):]=1
    return ids,attention,lengths


def prepare(root,parent,checkpoint,out):
    from transformers import AutoTokenizer
    import k562_prototype as K
    from virtual_cell_drugs import Atlas
    root=Path(root);parent=Path(parent);out=Path(out)
    if out.exists():raise ValueError('Existing expanded data is preserved; choose a new destination.')
    old_manifest=json.loads((parent/'manifest.json').read_text())
    if sha(parent/'data.npz')!=old_manifest['dataSha256']:raise ValueError('Parent biological data changed.')
    with np.load(parent/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    for key in list(data):
        if key.startswith('masked') or key in ['singleX','singleIds','singleAttention','singleY','singleMask']:del data[key]
    expert={k[7:]:v for k,v in data.items() if k.startswith('expert_')};genes=expert['genes'].astype(str);gi={g:i for i,g in enumerate(genes)}
    source_manifest=json.loads((root/'virtualcell/reference/k562/manifest.json').read_text())
    norman=root/'oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad';replogle=root/'virtualcell/data/replogle2022/ReplogleWeissman2022_K562_essential.h5ad'
    source_hash={}
    for name,path,expected in [('norman',norman,K.SOURCE_SHA),('replogle',replogle,source_manifest['inputs']['replogle2022']['sha256'])]:
        actual=sha(path)
        if actual!=expected:raise ValueError('Source integrity failed: '+name)
        source_hash[name]=actual
    nm=K.metadata(norman)
    with h5py.File(replogle,'r') as f:
        rm={'labels':column(f['obs'],'perturbation'),'ids':column(f['obs'],str(f['obs'].attrs['_index']))}
    with np.load(root/'virtualcell/reference/k562/pack.npz',allow_pickle=False) as z:reference={k:z[k] for k in ['genes','kdPerturbations','kdEffects','kdMeasured']}
    eligible=[str(g) for g in reference['kdPerturbations'] if str(g) in gi]
    kd_split=split_groups(eligible)
    allowed_norman=set(data['trainConditions'].tolist())|set(expert['singleGenes'].tolist())|{'control'}
    nr=stratified_rows(nm['labels'],allowed_norman,1000,SEED)
    rr=stratified_rows(rm['labels'],set(kd_split['train'])|{'control','non-targeting'},1000,SEED+1)
    assert set(nm['labels'][nr])<=allowed_norman and not(set(rm['labels'][rr])&set(kd_split['validation']+kd_split['test']))
    nv,nmeasured=read_profiles(norman,nr,genes,nm);rv,rmeasured=read_profiles(replogle,rr,genes,rm)
    controls=np.flatnonzero(np.isin(rm['labels'],['control','non-targeting']))
    if len(controls)<100:raise ValueError('Insufficient measured inhibition controls.')
    cr=np.random.default_rng(SEED).choice(controls,size=min(256,len(controls)),replace=False);cr.sort();cv,_=read_profiles(replogle,cr,genes,rm);rb=cv.mean(0)
    profiles=np.concatenate([nv,rv]);baselines=np.concatenate([np.broadcast_to(expert['baseline'],nv.shape),np.broadcast_to(rb,rv.shape)])
    measured=np.concatenate([np.broadcast_to(nmeasured,nv.shape),np.broadcast_to(rmeasured,rv.shape)])
    rng=np.random.default_rng(SEED);hide=(rng.random(profiles.shape)<.2)&measured
    if np.any(hide.sum(1)==0):raise ValueError('A masked profile has no measured targets.')
    masked=np.where(hide,0,profiles);effects=np.where(measured,profiles-baselines,0)
    texts=['Human K562 '+('CRISPRa activation' if i<1000 else 'CRISPRi inhibition')+' training cell; observed genes '+s+'; reconstruct hidden expression.' for i,s in enumerate(rank_sentences(masked,genes,top=64))]
    numeric=np.where(hide,0,effects)@expert['encoder'];data['stateX']=np.concatenate([numeric,np.zeros((2000,data['trainX'].shape[1]-numeric.shape[1]))],axis=1).astype(np.float32)
    data['stateY']=effects.astype(np.float32);data['stateMask']=hide
    ids=['norman:'+str(nm['cellIds'][i]) for i in nr]+['replogle:'+str(rm['ids'][i]) for i in rr]
    if len(set(ids))!=2000:raise ValueError('Cell identities are not distinct.')
    text_sets={'state':texts}
    for split in ['train','validation']:text_sets[split]=pair_texts(data[split+'Conditions'],expert,data['graphNeighbors'])
    # Known activation calibrations: all are already permitted reference inputs.
    base_text=rank_sentences(expert['baseline'][None,:],genes,top=16)[0]
    data['activationX']=np.stack([np.pad(expert['encoder'][gi[str(g)]],(0,data['trainX'].shape[1]-expert['encoder'].shape[1])) for g in expert['singleGenes']]).astype(np.float32)
    data['activationY']=expert['singleEffects'].astype(np.float32);data['activationMask']=np.ones_like(data['activationY'],bool)
    text_sets['activation']=['Human K562 CRISPRa activation '+str(g)+'; baseline genes '+base_text+'; predict mean log1p counts per 10000 RNA change.' for g in expert['singleGenes']]
    # Distinct inhibition condition groups, with missing genes and direct target masked.
    rgi={str(g):i for i,g in enumerate(reference['genes'])};rpi={str(g):i for i,g in enumerate(reference['kdPerturbations'])};columns=np.array([rgi.get(g,-1) for g in genes]);present=columns>=0
    rbase=rank_sentences(rb[None,:],genes,top=16)[0];sealed={};split_metadata={'inhibition':kd_split}
    for split,conditions in kd_split.items():
        prefix='inhibition'+split.title();y=np.zeros((len(conditions),len(genes)),np.float32);m=np.zeros_like(y,bool);x=[];ts=[]
        for i,g in enumerate(conditions):
            y[i,present]=reference['kdEffects'][columns[present],rpi[g]];m[i]=np.isfinite(y[i])&present;m[i,gi[g]]=False;y[i,~m[i]]=0
            x.append(np.pad(expert['encoder'][gi[g]],(0,data['trainX'].shape[1]-expert['encoder'].shape[1])))
            ts.append('Human K562 CRISPRi inhibition '+g+'; baseline genes '+rbase+'; predict mean log1p counts per 10000 RNA change versus CRISPRi controls.')
        data[prefix+'X']=np.asarray(x,np.float32);text_sets[prefix]=ts;data[prefix+'Mask']=m
        if split=='test':sealed[prefix+'Y']=y
        else:data[prefix+'Y']=y
    # Entire drug identity is held out across every cell line, dose and plate.
    atlas=Atlas(root/'virtualcell/data/tahoe100m')
    from collections import Counter
    dose_counts=Counter(k[1] for k in atlas.groups if k[2]>0)
    drug_names=[g for g,n in dose_counts.items() if n>=4 and g not in ['dmso','control']]
    source_hash['tahoeConditions']=sha(root/'virtualcell/data/tahoe100m/conditions.json')
    source_hash['tahoeGenes']=sha(root/'virtualcell/data/tahoe100m/genes.json')
    source_hash['tahoeResponses']=sha(root/'virtualcell/data/tahoe100m/lfc.f16')
    drug_split=split_groups(drug_names,(32,8,8),'drug');split_metadata['drug']=drug_split
    dg={g:i for i,g in enumerate(atlas.genes)};dc=np.array([dg.get(g,-1) for g in genes]);dp=dc>=0
    drug_conditions={}
    import hashlib
    for split,names in drug_split.items():
        rows=[]
        for drug in names:
            keys=sorted([k for k in atlas.groups if k[1]==drug and k[2]>0],key=lambda k:hashlib.sha256(str((SEED,k)).encode()).hexdigest())
            rows+=keys[:4]
        prefix='drug'+split.title();ys=[];ms=[];xs=[];ts=[];records=[]
        for key in rows:
            line,drug,dose=key;indices=atlas.groups[key];values=np.asarray(atlas.lfc[sorted(indices)][:,dc[dp]],np.float32)
            with np.errstate(invalid='ignore',divide='ignore'):
                n=np.isfinite(values).sum(0);mean=np.nansum(values,axis=0)/np.maximum(n,1)
            y=np.zeros(len(genes),np.float32);m=np.zeros(len(genes),bool);y[dp]=mean;m[dp]=n>0
            if m.sum()<len(genes)//2:raise ValueError('Insufficient measured drug readouts.')
            row=atlas.conditions[indices[0]];x=np.zeros(data['trainX'].shape[1],np.float32);x[0]=np.log10(dose)
            ys.append(y);ms.append(m);xs.append(x);records.append({**row,'replicatePlates':len(indices)})
            ts.append(f"Human {row['cellLine']} ({line}); drug exposure {row['drug']} concentration {dose:g} {row['unit']}; predict DESeq2 log2 fold change versus DMSO; time not specified in this table.")
        data[prefix+'X']=np.array(xs);data[prefix+'Mask']=np.array(ms);text_sets[prefix]=ts;drug_conditions[split]=records
        if split=='test':sealed[prefix+'Y']=np.array(ys)
        else:data[prefix+'Y']=np.array(ys)
    tokenizer=AutoTokenizer.from_pretrained(str(checkpoint),local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    limit=int(tokenizer.model_max_length)
    # model_max_length may be a tokenizer sentinel; the pinned model config is authoritative.
    limit=min(limit,int(json.loads((Path(checkpoint)/'config.json').read_text())['max_position_embeddings']))-5
    lengths={}
    for prefix,ts in text_sets.items():
        ids_array,attention,lens=encode_complete(tokenizer,ts,limit);data[prefix+'Ids']=ids_array;data[prefix+'Attention']=attention
        lengths[prefix]={'examples':len(ts),'maximumTokens':int(lens.max()),'paddedTokens':ids_array.shape[1],'truncated':0}
    for task,prefix in [('state','state'),('activation','activation'),('inhibition','inhibitionTrain'),('drug','drugTrain')]:
        y=data[prefix+'Y'];m=data[prefix+'Mask'];count=m.sum(0);mean=np.sum(y*m,0)/np.maximum(count,1);var=np.sum((y-mean)**2*m,0)/np.maximum(count,1)
        data[task+'Scale']=np.maximum(np.sqrt(var),.05).astype(np.float32)
    out.mkdir(parents=True);upload=out/'cloud-inputs';upload.mkdir();np.savez_compressed(upload/'data.npz',**data)
    np.savez_compressed(out/'LOCAL_SEALED_TEST_ANSWERS.npz',**sealed)
    write(out/'SPLIT_MANIFEST.json',{'groups':split_metadata,'drugConditions':drug_conditions,'cells':ids,'normanSourceConditions':nm['labels'][nr].tolist(),'replogleSourceConditions':rm['labels'][rr].tolist(),
                                  'sealedAnswersSha256':sha(out/'LOCAL_SEALED_TEST_ANSWERS.npz'),'cloudDataSha256':sha(upload/'data.npz'),
                                  'note':'Prospective separation within this training pipeline, on previously available public datasets; not an independent-study claim.'})
    write(upload/'manifest.json',{'schema':'fold.qwen-cell.expanded-data/1','dataSha256':sha(upload/'data.npz'),'parentSha256':old_manifest['dataSha256'],
          'sourceSha256':source_hash,'cells':2000,'distinctCells':2000,'normanCells':1000,'replogleCells':1000,'textLengths':lengths,
          'inhibitionGroups':{k:len(v) for k,v in kd_split.items()},'drugGroups':{k:len(v) for k,v in drug_split.items()},
          'testAnswersUploaded':False,'legacyNormanHeldoutCellsIncluded':False,'units':{'state':'single-cell log1p counts per 10000, source-control centered','activation':'Norman mean log1p counts per 10000 response','inhibition':'Replogle mean log1p counts per 10000 response','drug':'Tahoe DESeq2 log2 fold change'},
          'sourceCodeSha256':sha(__file__),'noTruncation':True})
    return json.loads((upload/'manifest.json').read_text())
