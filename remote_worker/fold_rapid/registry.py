"""Source-pinned capabilities. Configuration never implies CUDA qualification."""
import json
import pathlib
import subprocess
from .contracts import digest

BC_PIN='c0ee638d11bc010817c2c97ee58ed5c323e664e2'
BG_PIN='a07fea1153111ef453aaea7a15697ee05de9291f'
ENGINES={
 'bindcraft2':{'repository':'https://github.com/PacesaLab/BindCraft2','revision':BC_PIN,'license':'BindCraft2 Source-Available (Hosting-Restricted); retain LICENSE','operations':['design'],'modalities':['peptide','binder'],'runtime':'bindcraft2','models':['model_1_multimer_v3','model_2_multimer_v3','model_3_multimer_v3','model_4_multimer_v3','model_5_multimer_v3','model_1_ptm','model_2_ptm','mpnn-neutral','mpnn-negative','mpnn-positive'],'representation':'PDB/mmCIF target + original settings; native CIF/CSV output','memory':'Workload dependent; real CUDA peak not measured'},
 'boltzgen':{'repository':'https://github.com/HannesStark/boltzgen','revision':BG_PIN,'license':'MIT','operations':['design'],'modalities':['peptide','binder'],'runtime':'boltzgen','models':['design-diverse','design-adherence','solublempnn','folding','moldir','esmfold2-bundle'],'representation':'Official YAML entities, peptide-anything / protein-anything pipeline; native mmCIF and metrics','memory':'Workload dependent; real CUDA peak not measured'},
 'proteinmpnn':{'repository':'https://github.com/PacesaLab/BindCraft2','revision':BC_PIN,'license':'Bundled upstream ProteinMPNN; retain notices','operations':['redesign'],'modalities':['peptide','binder'],'runtime':'bindcraft2','models':['mpnn-neutral'],'representation':'Fixed coordinates, explicit redesign chains; FASTA + metrics','memory':'Workload dependent; CUDA not measured'},
 'af2_multimer':{'repository':'https://github.com/PacesaLab/BindCraft2','revision':BC_PIN,'license':'Upstream AlphaFold notices and checkpoint terms apply','operations':['evaluate'],'modalities':['peptide','binder'],'runtime':'bindcraft2','models':['model_2_multimer_v3','model_4_multimer_v3'],'representation':'Explicit target and binder chain coordinates; original held-out 2/4 predictions','memory':'Workload dependent; CUDA not measured'},
 'structure_screen':{'repository':'local Fold Studio','revision':'0.2.0','license':'Project source terms','operations':['screen'],'modalities':['peptide','binder'],'runtime':'core','models':[],'representation':'Observed PDB/mmCIF sequences/residue mapping; no model prediction','memory':'Bounded 2 MB input; CPU geometry/sequence checks'}
}

def config(root):
    path=pathlib.Path(root)/'config.json'
    value=json.loads(path.read_text()) if path.is_file() else {}
    return value

def checkpoint_records(root, engine):
    values=config(root).get('models',{});records=[]
    for name in ENGINES[engine]['models']:
        item=values.get(name,{})
        path=pathlib.Path(item.get('path','/nonexistent'))
        present=path.is_file() and not path.is_symlink() and path.stat().st_size>0
        valid=present and isinstance(item.get('sha256'),str) and len(item['sha256'])==64
        records.append({'id':name,'present':present,'hashRegistered':valid,'sha256':item.get('sha256'),'path':str(path) if present else None})
    return records

def inventory(root):
    cfg=config(root);rows=[]
    for id,description in ENGINES.items():
        runtime=cfg.get('runtimes',{}).get(description['runtime'],{})
        installed=description['runtime']=='core' or (pathlib.Path(runtime.get('python','/nonexistent')).is_file() and pathlib.Path(runtime.get('source','/nonexistent')).is_dir())
        checkpoints=checkpoint_records(root,id)
        rows.append({'id':id,**description,'installed':installed,'models':checkpoints,'executionAvailable':installed and all(v['hashRegistered'] for v in checkpoints),'cudaExecutionTested':False,'scientificReferenceValidated':False,'status':'cpu_analysis_available' if id=='structure_screen' else 'hardware_qualification_required' if installed else 'not_installed'})
    return {'engines':rows,'scientificCUDAQualified':False,'qualificationReason':'No NVIDIA reference campaign has been certified by this release.'}

def verified_runtime(root,engine):
    description=ENGINES[engine];cfg=config(root)
    runtime=cfg.get('runtimes',{}).get(description['runtime'],{})
    python=pathlib.Path(runtime.get('python','/nonexistent'));source=pathlib.Path(runtime.get('source','/nonexistent'))
    if not python.is_file() or not source.is_dir():raise ValueError('Install the isolated '+description['runtime']+' runtime first.')
    pin=source/'rapid-source.json'
    if not pin.is_file() or json.loads(pin.read_text()).get('revision')!=description['revision']:raise ValueError('Scientific source revision is not the pinned release.')
    index=source/'rapid-files.json'
    if not index.is_file():raise ValueError('Scientific source integrity manifest is missing.')
    for name,expected in json.loads(index.read_text()).items():
        path=source/name
        if path.is_symlink() or source.resolve() not in path.resolve().parents or not path.is_file() or digest(path.read_bytes())!=expected:
            raise ValueError('Scientific source integrity mismatch: '+name)
    models={}
    for record in checkpoint_records(root,engine):
        if not record['hashRegistered']:raise ValueError('Approved checkpoint missing: '+record['id'])
        path=pathlib.Path(record['path']);h=__import__('hashlib').sha256()
        with path.open('rb') as f:
            while block:=f.read(4*1024**2):h.update(block)
        if h.hexdigest()!=record['sha256']:raise ValueError('Checkpoint checksum mismatch: '+record['id'])
        if record['id']=='esmfold2-bundle':
            from .models import file_sha
            for artifact in json.loads(path.read_text()):
                if file_sha(artifact['path'])!=artifact['sha256']:raise ValueError('ESMFold2 cached checkpoint checksum mismatch.')
        models[record['id']]=record
    return runtime,models
