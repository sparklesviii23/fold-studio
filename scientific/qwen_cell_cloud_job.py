"""Prepare and stage a sealed cloud experiment using the existing Modal account.

Preparation is local. stage_and_launch is called only after explicit approval.
Its caller records an attempt before staging and never retries a paid launch.
"""
import hashlib,json,time,zipfile
from pathlib import Path,PurePosixPath
from qwen_cell_cloud_recipe import RECIPE,RECIPE_ID,REVISION

SOURCES=('qwen_cell_cloud_entry.py','qwen_cell_cloud_training.py','qwen_cell_hybrid.py',
         'qwen_cell_hybrid_training.py','qwen_cell_model.py','qwen_cell_data.py')
CHECKPOINT={
 'config.json':(661,'8f85440a3222d18772e964b1ef0b4b1574a1c5e6260c99aa23fcddd05c28b8ae'),
 'model-00001-of-00002.safetensors':(4957560304,'5b684409377e037e5ed75d680a070126e841dab17e8cb9a818868deadf01ab39'),
 'model-00002-of-00002.safetensors':(1214366696,'8bc5227aae6174eaf0b589fd4fbeb0de046a1fc951a67f2d2538acad811e1068'),
 'model.safetensors.index.json':(35581,'7b85f79fd7612df2e5d7f03d7f92d65c8967f790a331146ca7f45658823060d3'),
}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def verify_answer_free(path):
    with zipfile.ZipFile(path) as z:
        if any('test' in Path(n).stem.lower() and Path(n).stem.endswith('Y') for n in z.namelist()):raise ValueError('Test answers must stay local.')


def prepare(repo,data,checkpoint,warm,out):
    repo,data,checkpoint,warm,out=map(Path,[repo,data,checkpoint,warm,out])
    if out.exists():raise ValueError('An existing preparation is preserved; choose a fresh destination.')
    meta=json.loads((data/'manifest.json').read_text())
    if meta['schema']!='fold.qwen-cell.expanded-data/1' or not meta['noTruncation'] or meta['testAnswersUploaded']:
        raise ValueError('Complete protected biological data is required.')
    if digest(data/'data.npz')!=meta['dataSha256']:raise ValueError('Data changed.')
    verify_answer_free(data/'data.npz')
    for name,(size,sha) in CHECKPOINT.items():
        p=checkpoint/name
        if p.stat().st_size!=size or digest(p)!=sha:raise ValueError('Official checkpoint changed: '+name)
    out.mkdir(parents=True);code=out/'code';code.mkdir();files=[];assets=[]
    def add(path,name):
        row={'path':name,'bytes':path.stat().st_size,'sha256':digest(path)};files.append(row);assets.append({**row,'local':str(path.resolve())})
    for name in SOURCES:
        p=code/name;p.write_bytes((repo/'scientific'/name).read_bytes());add(p,'code/'+name)
    for name in ['data.npz','manifest.json']:add(data/name,name)
    add(warm,'warm.safetensors')
    for name in [*CHECKPOINT,'LICENSE']:add(checkpoint/name,'checkpoint/'+name)
    manifest={'schema':'fold.qwen-cell.cloud-assets/1','checkpointRevision':REVISION,'dataSha256':meta['dataSha256'],'files':files}
    write(out/'ASSET_MANIFEST.json',manifest);manifest_sha=digest(out/'ASSET_MANIFEST.json')
    request={'studyKey':manifest_sha,'manifestSha256':manifest_sha}
    plan={'schema':'fold.qwen-cell.cloud-plan/1','recipe':RECIPE_ID,'recipeSha256':hashlib.sha256(json.dumps(RECIPE,sort_keys=True).encode()).hexdigest(),
          'request':request,'assets':assets,'manifest':str((out/'ASSET_MANIFEST.json').resolve()),'manifestSha256':manifest_sha,
          'uploadBytes':sum(f['bytes'] for f in assets),'gpu':'A100-80GB','timeout':2700,'seeds':[20261106,20261107,20261108],
          'estimatedUsd':[4,7],'estimateIsDollarCap':False,'automaticRetry':False,'testAnswersUploaded':False,'preparedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    write(out/'PLAN.json',plan);return plan


def verify_plan(plan):
    if plan.get('schema')!='fold.qwen-cell.cloud-plan/1' or plan.get('recipe')!=RECIPE_ID or plan.get('automaticRetry') is not False:
        raise ValueError('A sealed reviewed cloud plan is required.')
    if plan.get('gpu')!='A100-80GB' or plan.get('timeout')!=2700 or plan.get('seeds')!=[20261106,20261107,20261108]:raise ValueError('Unexpected study budget.')
    if plan['recipeSha256']!=hashlib.sha256(json.dumps(RECIPE,sort_keys=True).encode()).hexdigest():raise ValueError('Recipe changed.')
    if digest(plan['manifest'])!=plan['manifestSha256'] or plan['request']!={'studyKey':plan['manifestSha256'],'manifestSha256':plan['manifestSha256']}:raise ValueError('Manifest changed.')
    expected=json.loads(Path(plan['manifest']).read_text())
    if expected.get('schema')!='fold.qwen-cell.cloud-assets/1' or expected.get('checkpointRevision')!=REVISION:raise ValueError('Checkpoint manifest differs.')
    rows=[{k:a[k] for k in ['path','bytes','sha256']} for a in plan['assets']]
    if rows!=expected['files']:raise ValueError('Upload assets differ from the sealed manifest.')
    allowed={'data.npz','manifest.json','warm.safetensors',*('code/'+s for s in SOURCES),*('checkpoint/'+s for s in [*CHECKPOINT,'LICENSE'])}
    if len(rows)!=len(allowed) or {r['path'] for r in rows}!=allowed:raise ValueError('Only explicit public training assets may be uploaded.')
    for a in plan['assets']:
        p=PurePosixPath(a['path'])
        if p.is_absolute() or '..' in p.parts or str(p)!=a['path']:raise ValueError('Unsafe asset path.')
        path=Path(a['local'])
        if not path.is_file() or path.stat().st_size!=a['bytes'] or digest(path)!=a['sha256']:raise ValueError('Local asset changed: '+a['path'])
        if a['path']=='data.npz':verify_answer_free(path)
    return expected


def remote_assets(plan):
    study='qwen-cell-studies/'+plan['request']['studyKey']
    result=[]
    for a in plan['assets']:
        target=('models/qwen-cell/'+REVISION+'/'+a['path'][11:]) if a['path'].startswith('checkpoint/') else study+'/'+a['path']
        result.append({**a,'remote':target})
    result.append({'local':plan['manifest'],'remote':study+'/ASSET_MANIFEST.json','bytes':Path(plan['manifest']).stat().st_size,'sha256':plan['manifestSha256']})
    return result


def stage_and_launch(plan,volume,launch,cancelled,event,verifier=None,asset_provider=None):
    """Injected SDK boundary makes upload-before-allocation independently testable."""
    (verifier or verify_plan)(plan)
    def check():
        if cancelled():raise InterruptedError('Stopped before GPU launch; no retry.')
    check();assets=(asset_provider or remote_assets)(plan)
    # Batch uploads commit on successful exit; one explicit batch, no paid retry.
    # Existing content-addressed checkpoint blobs are deduplicated by Modal.
    event('Uploading verified inputs before GPU allocation',bytes=sum(a['bytes'] for a in assets))
    with volume.batch_upload(force=True) as batch:
        for a in assets:check();batch.put_file(a['local'],'/'+a['remote'])
    check()
    for prefix in sorted({a['remote'].rsplit('/',1)[0] for a in assets}):
        listed={str(e.path).lstrip('/'):e.size for e in volume.listdir(prefix,recursive=True)}
        for a in assets:
            if a['remote'].startswith(prefix+'/') and listed.get(a['remote'])!=a['bytes']:raise ValueError('Remote staging incomplete: '+a['remote'])
    check();event('All cloud inputs committed; allocating one approved GPU',files=len(assets))
    result=launch()
    return result
