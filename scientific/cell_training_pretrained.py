"""Real local-only Cell2Sentence encoder and explicit model acquisition review."""
import hashlib,json
from pathlib import Path

MODEL='vandijklab/C2S-Pythia-410m-diverse-single-and-multi-cell-tasks'
ATTRIBUTION='Cell2Sentence, van Dijk Lab; pretrained weights CC BY 4.0. https://huggingface.co/'+MODEL


def metadata():
    import urllib.request
    url='https://huggingface.co/api/models/'+MODEL+'?blobs=true'
    with urllib.request.urlopen(url,timeout=30) as response:info=json.load(response)
    names={'config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','README.md'}
    files=[{'name':r['rfilename'],'bytes':r['size'],'sha256':r.get('lfs',{}).get('sha256'),'gitBlob':r.get('blobId')} for r in info['siblings'] if r['rfilename'] in names]
    if not any(r['name']=='model.safetensors' and r['sha256'] for r in files):raise ValueError('Official safe checkpoint metadata is incomplete.')
    return {'schema':'fold.cell-encoder-download/1','model':MODEL,'revision':info['sha'],'files':files,'totalBytes':sum(r['bytes'] for r in files),
            'license':info.get('cardData',{}).get('license'),'attribution':ATTRIBUTION,'downloaded':False,'approvalRequired':True}


def download(review,destination,approved=False,event=lambda *a,**kw:None):
    import urllib.request
    from cell_training_entry import digest as sha
    if approved is not True:raise ValueError('Explicit approval is required for this new pretrained checkpoint download.')
    if review.get('model')!=MODEL or review.get('schema')!='fold.cell-encoder-download/1':raise ValueError('Official reviewed Cell2Sentence assets required.')
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    claim=dest/'DOWNLOAD_ATTEMPT.json'
    with claim.open('x') as f:json.dump({'revision':review['revision'],'approved':True,'automaticRetry':False},f)
    for row in review['files']:
        target=dest/row['name'];part=dest/(row['name']+'.partial')
        if target.exists():raise ValueError('Existing model assets are preserved; verify them separately.')
        url='https://huggingface.co/'+MODEL+'/resolve/'+review['revision']+'/'+row['name']
        event('encoder_download',file=row['name'],bytes=row['bytes'])
        with urllib.request.urlopen(url,timeout=600) as response,part.open('wb') as f:
            for block in iter(lambda:response.read(8<<20),b''):f.write(block)
        if part.stat().st_size!=row['bytes'] or row.get('sha256') and sha(part)!=row['sha256']:raise ValueError('Downloaded asset failed its official integrity check.')
        if not row.get('sha256') and (not row.get('gitBlob') or hashlib.sha1(b'blob '+str(part.stat().st_size).encode()+b'\0'+part.read_bytes()).hexdigest()!=row['gitBlob']):raise ValueError('Downloaded encoder source file differs from its pinned revision.')
        part.replace(target)
    (dest/'MODEL_RECEIPT.json').write_text(json.dumps({**review,'downloaded':True,'approvalRequired':False,'localFiles':{r['name']:sha(dest/r['name']) for r in review['files']}},indent=2)+'\n')


def encode_local(checkpoint,sentences,device='cpu',batch=8,loader=None,event=lambda *a,**kw:None):
    """Measured-input embeddings only; complete sequences; never network fallback."""
    import torch
    import numpy as np
    from transformers import AutoModel,AutoTokenizer
    path=Path(checkpoint)
    if loader:
        tokenizer,model=loader()
    else:
        if not (path/'MODEL_RECEIPT.json').is_file():raise ValueError('Install the explicitly approved, verified biology encoder first.')
        receipt=json.loads((path/'MODEL_RECEIPT.json').read_text())
        from qwen_cell_data import sha
        if receipt['model']!=MODEL or not receipt['downloaded']:raise ValueError('Unknown pretrained encoder.')
        for name,digest in receipt['localFiles'].items():
            if sha(path/name)!=digest:raise ValueError('Pretrained encoder asset changed: '+name)
        tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
        model=AutoModel.from_pretrained(path,local_files_only=True,trust_remote_code=False,use_safetensors=True,
                                        dtype=torch.bfloat16 if device=='cuda' else torch.float32,attn_implementation='sdpa')
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    model=model.to(device).eval();cap=int(model.config.max_position_embeddings);values=[]
    # Input-only deduplication avoids re-encoding the same baseline for every drug.
    unique=list(dict.fromkeys(sentences));mapping={s:i for i,s in enumerate(unique)}
    rng=np.random.default_rng(17);projection=rng.choice([-1.,1.],size=(model.config.hidden_size,128)).astype(np.float32)/np.sqrt(model.config.hidden_size)
    for start in range(0,len(unique),batch):
        texts=unique[start:start+batch];raw=tokenizer(texts,padding=False,truncation=False,add_special_tokens=False)['input_ids']
        if any(not r or len(r)>cap for r in raw):raise ValueError('Complete biology-encoder context exceeds its trained position budget.')
        encoded=tokenizer(texts,padding=True,truncation=False,add_special_tokens=False,return_tensors='pt');encoded={k:v.to(device) for k,v in encoded.items()}
        with torch.no_grad():
            hidden=model(**encoded,use_cache=False,return_dict=True).last_hidden_state.float();mask=encoded['attention_mask'][...,None]
            pooled=(hidden*mask).sum(1)/mask.sum(1);values.append(pooled.cpu().numpy()@projection)
        if start%128==0 or start+batch>=len(unique):event('biology_encoder',completed=min(start+batch,len(unique)),uniqueProfiles=len(unique))
    matrix=np.concatenate(values);return matrix[[mapping[s] for s in sentences]].astype(np.float32)
