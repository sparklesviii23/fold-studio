"""Gene-labelled hybrid inputs; pinned C2S ranking and GEARS correlations.

Only existing calibration/training profiles define graph, masking and curricula.
Validation responses are labels for development scoring, never input text.
"""
import contextlib
import io
import json
from pathlib import Path
from collections import OrderedDict
from types import SimpleNamespace
import numpy as np
from qwen_cell_data import sha,write,verify_bundle,BASE_RUN
from cell2sentence_rank import generate_sentences
from gears_correlation import np_pearson_cor

TOKENS=96


def rank_sentences(profiles,genes,top=8):
    values=np.maximum(np.asarray(profiles),0)
    state=np.random.get_state()
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            rows=generate_sentences(SimpleNamespace(X=values,var=genes,obs=range(len(values))),OrderedDict((str(g),0) for g in genes),random_state=20261106)
    finally:np.random.set_state(state)
    return [' '.join(s.split()[:top]) for s in rows]


def graph(profiles,neighbors=4):
    with np.errstate(divide='ignore',invalid='ignore'):cor=np_pearson_cor(profiles,profiles)
    cor=np.nan_to_num(cor,nan=0,posinf=0,neginf=0);np.fill_diagonal(cor,-1)
    take=np.argsort(-cor,axis=1,kind='stable')[:,:neighbors]
    values=np.maximum(np.take_along_axis(cor,take,axis=1),0)
    indices=np.concatenate([np.arange(len(cor))[:,None],take],axis=1)
    weights=np.concatenate([np.ones((len(cor),1)),values],axis=1);weights/=weights.sum(1,keepdims=True)
    return indices.astype(np.int64),weights.astype(np.float32)


def encode(tokenizer,texts):
    r=tokenizer(texts,padding='max_length',truncation=True,max_length=TOKENS,return_tensors='np',add_special_tokens=False)
    return np.asarray(r['input_ids'],dtype=np.int64),np.asarray(r['attention_mask'],dtype=np.int64)


def pair_texts(labels,model,neighbors):
    genes=model['genes'].astype(str);single=model['singleGenes'].astype(str);ix={g:i for i,g in enumerate(single)};gi={g:i for i,g in enumerate(genes)}
    ranked=rank_sentences(model['baseline'][None,:]+model['singleEffects'],genes,top=5)
    baseline=rank_sentences(model['baseline'][None,:],genes,top=6)[0];texts=[]
    for label in labels:
        pair=sorted(str(label).split('+'));near=sorted({str(genes[j]) for g in pair for j in neighbors[gi[g],1:3]})
        texts.append('Human K562 CRISPR activation '+ ' '.join(pair)+'. Baseline genes: '+baseline+
                     '. Single response A: '+ranked[ix[pair[0]]]+'. Single response B: '+ranked[ix[pair[1]]]+'. Correlated genes: '+' '.join(near)+'. Predict RNA change.')
    return texts


def foundation(data,model,neighbors,tokenizer,steps=16):
    genes=model['genes'].astype(str);rng=np.random.default_rng(20261106)
    # Known single-response calibration and training pairs only. No validation outcome.
    effects=np.concatenate([model['singleEffects'],data['trainY']]);profiles=model['baseline'][None,:]+effects
    rows=rng.choice(len(profiles),size=steps,replace=False);masks=rng.random((steps,len(genes)))<.2
    masked=profiles[rows].copy();masked[masks]=0
    texts=['Human K562 masked cell genes: '+s+'. Reconstruct hidden RNA.' for s in rank_sentences(masked,genes,top=16)]
    ids,attn=encode(tokenizer,texts)
    numeric=(np.where(masks,0,effects[rows])@model['encoder']).astype(np.float32)
    numeric=np.concatenate([numeric,np.zeros((steps,data['trainX'].shape[1]-numeric.shape[1]),np.float32)],axis=1)
    singles=rng.choice(len(model['singleGenes']),size=steps,replace=False)
    base=rank_sentences(model['baseline'][None,:],genes,top=10)[0]
    single_text=['Human K562 CRISPR activation '+str(model['singleGenes'][i])+'. Baseline genes: '+base+'. Predict single activation RNA.' for i in singles]
    si,sa=encode(tokenizer,single_text)
    return {'maskedX':numeric,'maskedIds':ids,'maskedAttention':attn,'maskedY':effects[rows].astype(np.float32),'maskedMask':masks,
            'singleX':np.zeros((steps,data['trainX'].shape[1]),np.float32),'singleIds':si,'singleAttention':sa,
            'singleY':model['singleEffects'][singles].astype(np.float32),'singleMask':np.ones((steps,len(genes)),bool)}


def prepare(root,data_folder,checkpoint,out):
    from transformers import AutoTokenizer
    root=Path(root);out=Path(out)
    if out.exists():raise ValueError('Existing biological bundle is preserved.')
    original=verify_bundle(data_folder)
    with np.load(Path(data_folder)/'data.npz',allow_pickle=False) as z:data={k:z[k] for k in z.files}
    base=root/'gpu_tasks'/BASE_RUN;rec=json.loads((base/'task.json').read_text());model_path=base/'outputs/MODEL.npz'
    if sha(model_path)!=next(x['sha256'] for x in rec['outputs'] if x['path']=='MODEL.npz'):raise ValueError('Internal RNA expert integrity failed.')
    with np.load(model_path,allow_pickle=False) as z:model={k:z[k] for k in z.files}
    if not np.array_equal(model['genes'],data['genes']):raise ValueError('RNA expert gene order differs.')
    neighbors,weights=graph(np.concatenate([model['singleEffects'],data['trainY']]))
    tokenizer=AutoTokenizer.from_pretrained(str(checkpoint),local_files_only=True,trust_remote_code=False)
    tokenizer.padding_side='left'
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    output={**data,**{'expert_'+k:v for k,v in model.items()},'graphNeighbors':neighbors,'graphWeights':weights}
    text_rows={}
    single_index={str(g):i for i,g in enumerate(model['singleGenes'])}
    for split in ['train','validation']:
        labels=data[split+'Conditions'].tolist();texts=pair_texts(labels,model,neighbors);text_rows[split]=texts
        ids,attention=encode(tokenizer,texts);output[split+'Ids']=ids;output[split+'Attention']=attention
        output[split+'PairIndices']=np.array([[single_index[g] for g in sorted(p.split('+'))] for p in labels],np.int64)
    output.update(foundation(data,model,neighbors,tokenizer))
    residual=data['trainY']-data['trainTeacher'];output['correctionScale']=np.maximum(np.std(residual,axis=0),.01).astype(np.float32)
    output['auxiliaryScale']=np.maximum(np.std(np.concatenate([data['trainY'],model['singleEffects']]),axis=0),.01).astype(np.float32)
    out.mkdir(parents=True);np.savez_compressed(out/'data.npz',**output);write(out/'INPUT_TEXT_EXAMPLES.json',{k:v[:3] for k,v in text_rows.items()})
    manifest={'schema':'fold.qwen-cell.hybrid-data/1','dataSha256':sha(out/'data.npz'),'parentDataSha256':original['dataSha256'],
              'internalExpertSha256':sha(model_path),'trainConditions':77,'developmentConditions':26,'genes':len(data['genes']),
              'output':'One numerical channel per measured gene; no fixed rank-12 output basis.',
              'graph':'GEARS correlation helper; top four positive co-expression neighbors + self from known single calibrations and training-pair response profiles only. Association, not causal edges.',
              'language':'Unchanged C2S ranking helper applied to existing condition-mean profiles, with Qwen gene-labelled prompts; not a reproduction of the full C2S or GEARS model.',
              'maximumTextTokens':TOKENS,'foundationExamples':{'maskedTrainingProfiles':16,'singleCalibrations':16},
              'validationOutcomeUsedAsInput':False,'legacyTestOutcomesIncluded':False,'sourceCodeSha256':sha(__file__)}
    write(out/'manifest.json',manifest);return manifest
