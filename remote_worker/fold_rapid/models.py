"""Explicit, checksum-verified model acquisition. Never used by job submission."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from .contracts import canonical
from .install import update_config
CATALOG=json.loads(pathlib.Path(__file__).with_name('model-catalog.json').read_text())

def fetch(url,path,expected=None):
    path=pathlib.Path(path);pending=path.with_suffix(path.suffix+'.incoming')
    if path.is_file() and expected and file_sha(path)==expected:return path
    if not url.startswith('https://'):raise ValueError('Only reviewed HTTPS checkpoint sources are permitted.')
    try:
        with urllib.request.urlopen(url,timeout=60) as response,pending.open('wb') as out:
            while block:=response.read(4*1024**2):
                if out.tell()+len(block)>8*1024**3 or shutil.disk_usage(path.parent).free<2*1024**3:raise ValueError('Checkpoint transfer exceeded its per-file limit or free-storage reserve.')
                out.write(block)
        if expected and file_sha(pending)!=expected:raise ValueError('Downloaded checkpoint checksum mismatch.')
        os.replace(pending,path)
    finally:pending.unlink(missing_ok=True)
    return path

def file_sha(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        while block:=f.read(4*1024**2):h.update(block)
    return h.hexdigest()

def install_esm(cache,fast,register):
    receipt=[]
    catalogs=CATALOG['esmfold2-fast'] if fast else CATALOG['esmfold2']
    for repo,data in catalogs.items():
        snapshot=cache/'huggingface'/'hub'/('models--'+repo.replace('/','--'))/'snapshots'/data['revision'];snapshot.mkdir(parents=True,exist_ok=True)
        for name,item in data['files'].items():
            path=snapshot/name
            if snapshot.resolve() not in path.resolve().parents:raise ValueError('Invalid model artifact path.')
            path.parent.mkdir(parents=True,exist_ok=True)
            fetch('https://huggingface.co/'+repo+'/resolve/'+data['revision']+'/'+name,path,item['sha256'])
            receipt.append({'path':str(path),'sha256':item['sha256'],'repository':repo,'revision':data['revision']})
    if fast:
        repo='biohub/ESMFold2';data=CATALOG['esmfold2'][repo];item=data['files']['ccd.pkl'];folder=cache/'ccd';folder.mkdir(exist_ok=True)
        path=fetch('https://huggingface.co/'+repo+'/resolve/'+data['revision']+'/ccd.pkl',folder/'ccd.pkl',item['sha256'])
        receipt.append({'path':str(path),'sha256':item['sha256'],'repository':repo,'revision':data['revision']})
    name='esmfold2-fast-bundle' if fast else 'esmfold2-bundle';path=cache/(name+'-receipt.json');path.write_text(canonical(receipt));register(name,path,file_sha(path))

def install(root,engine,approved):
    if approved is not True:raise ValueError('Approve the model archive download and its storage requirement first.')
    root=pathlib.Path(root);cache=root/'models';cache.mkdir(exist_ok=True)
    needed=50 if engine=='boltzgen' else 30 if engine in ('esmfold2','esmfold2_fast') else 1 if engine=='solublempnn' else 16
    if shutil.disk_usage(root).free<needed*1024**3:raise ValueError(f'At least {needed} GiB free storage is required before this model bundle installation.')
    def register(name,path,sha):update_config(root,'models',name,{'path':str(path),'sha256':sha})
    if engine in ('esmfold2','esmfold2_fast'):
        install_esm(cache,engine=='esmfold2_fast',register)
    elif engine=='solublempnn':
        folder=cache/'proteinmpnn';folder.mkdir(exist_ok=True);item=CATALOG['solublempnn'];path=fetch(item['source'],folder/'solublempnn_v_48_020.pt',item['sha256']);register('solublempnn',path,item['sha256'])
    elif engine=='bindcraft2':
        af=CATALOG['alphafold'];folder=cache/'alphafold';folder.mkdir(exist_ok=True)
        archive=fetch(af['source'],cache/'alphafold-official.tar')
        with tarfile.open(archive,'r:') as tar:
            for name,expected in af['models'].items():
                filename='params_'+name+'.npz';members=[m for m in tar.getmembers() if pathlib.PurePosixPath(m.name).name==filename and m.isfile()]
                if len(members)!=1:raise ValueError('Ambiguous/missing official AlphaFold archive member: '+name)
                path=folder/filename;temp=folder/(filename+'.incoming')
                with tar.extractfile(members[0]) as src,temp.open('wb') as dst:shutil.copyfileobj(src,dst,4*1024**2)
                if file_sha(temp)!=expected:temp.unlink();raise ValueError('AlphaFold member hash differs from the recorded official archive baseline.')
                os.replace(temp,path);register(name,path,expected)
        archive.unlink()
        for variant,item in CATALOG['mpnn'].items():
            folder=cache/'proteinmpnn'/('weights_'+variant);folder.mkdir(parents=True,exist_ok=True)
            path=fetch(item['source'],folder/'v_48_020.npz',item['sha256']);register('mpnn-'+variant,path,item['sha256'])
    elif engine=='boltzgen':
        data=CATALOG['boltzgen/boltzgen-1'];folder=cache/'boltzgen';folder.mkdir(exist_ok=True)
        for name,filename in {'design-diverse':'boltzgen1_diverse.ckpt','design-adherence':'boltzgen1_adherence.ckpt','folding':'boltz2_conf_final.ckpt'}.items():
            item=data['files'][filename];path=fetch('https://huggingface.co/boltzgen/boltzgen-1/resolve/'+data['revision']+'/'+filename,folder/filename,item['sha256']);register(name,path,item['sha256'])
        item=CATALOG['solublempnn'];path=fetch(item['source'],folder/'solublempnn_v_48_020.pt',item['sha256']);register('solublempnn',path,item['sha256'])
        data=CATALOG['boltzgen/inference-data'];item=data['files']['mols.zip'];path=fetch('https://huggingface.co/datasets/boltzgen/inference-data/resolve/'+data['revision']+'/mols.zip',folder/'mols.zip',item['sha256']);register('moldir',path,item['sha256'])
        extracted=folder/'molecules';extracted.mkdir(exist_ok=True)
        with zipfile.ZipFile(path) as z:
            if sum(v.file_size for v in z.infolist())>12*1024**3:raise ValueError('Molecule archive expansion exceeds the approved size.')
            for member in z.infolist():
                dest=extracted/member.filename
                if extracted.resolve() not in dest.resolve().parents or member.external_attr>>16 & 0o170000==0o120000:raise ValueError('Unsafe molecule archive member.')
            z.extractall(extracted)
        from .registry import config
        runtime=config(root).get('runtimes',{}).get('boltzgen')
        if runtime is None:raise ValueError('Install the isolated BoltzGen runtime before models.')
        runtime['moldir']=str(extracted/'mols' if (extracted/'mols').is_dir() else extracted);update_config(root,'runtimes','boltzgen',runtime)
        receipt=[]
        for repo,data in CATALOG['esmfold2'].items():
            if data.get('error'):raise ValueError('ESMFold2 checkpoint metadata is unavailable: '+repo)
            snapshot=cache/'huggingface'/'hub'/('models--'+repo.replace('/','--'))/'snapshots'/data['revision']
            snapshot.mkdir(parents=True,exist_ok=True)
            for name,item in data['files'].items():
                path=snapshot/name
                if snapshot.resolve() not in path.resolve().parents:raise ValueError('Invalid pinned ESM artifact path.')
                path.parent.mkdir(parents=True,exist_ok=True)
                fetch('https://huggingface.co/'+repo+'/resolve/'+data['revision']+'/'+name,path,item['sha256'])
                receipt.append({'path':str(path),'sha256':item['sha256'],'repository':repo,'revision':data['revision']})
        path=cache/'esmfold2-receipt.json';path.write_text(canonical(receipt));register('esmfold2-bundle',path,file_sha(path))
    else:raise ValueError('Unknown model bundle.')
    return {'state':'installed','engine':engine,'cudaQualified':False}

def background(root,engine):
    root=pathlib.Path(root);path=root/('models-'+engine+'.json')
    old=json.loads(path.read_text()) if path.is_file() else {}
    if old.get('state')=='running':
        try:os.kill(old['pid'],0);return old
        except ProcessLookupError:pass
    with (root/('models-'+engine+'.log')).open('ab') as log:
        p=subprocess.Popen([sys.executable,'-m','fold_rapid.models','--root',str(root),'--engine',engine,'--approve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    value={'state':'running','engine':engine,'pid':p.pid};path.write_text(canonical(value));return value

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--engine',required=True,choices=['bindcraft2','boltzgen','esmfold2','esmfold2_fast','solublempnn']);p.add_argument('--approve',action='store_true');a=p.parse_args()
    try:value=install(a.root,a.engine,a.approve)
    except Exception as e:value={'state':'failed','error':str(e)}
    (pathlib.Path(a.root)/('models-'+a.engine+'.json')).write_text(canonical(value));print(canonical(value))
    if value['state']=='failed':raise SystemExit(1)

if __name__=='__main__':main()
