"""Sealed grounded-study upload plan, optionally awaiting an approved encoder."""
import hashlib,json,shutil,re
from pathlib import Path
import qwen_cell_cloud_job as OLD
from cell_training_recipe import RECIPE,RECIPE_ID,PROTOCOL
from qwen_cell_cloud_recipe import REVISION
from cell_training_pretrained import MODEL

SOURCES=('cell_training_entry.py','cell_training_engine.py','cell_training_metrics.py','cell_training_pretrained.py','cell_training_recipe.py',
         'qwen_cell_cloud_recipe.py','qwen_cell_hybrid.py','qwen_cell_model.py','qwen_cell_data.py')
digest=OLD.digest;write=OLD.write


def git_blob(path):
    p=Path(path);return hashlib.sha1(b'blob '+str(p.stat().st_size).encode()+b'\0'+p.read_bytes()).hexdigest()


def prepare(repo,experiment,checkpoint,biology,review,out):
    repo,experiment,checkpoint,biology,out=map(Path,[repo,experiment,checkpoint,biology,out]);review=json.loads(Path(review).read_text())
    meta=json.loads((experiment/'cloud-inputs/manifest.json').read_text())
    if meta['schema']!='fold.cell-training-data/2' or meta['testAnswersUploaded'] or digest(experiment/'cloud-inputs/data.npz')!=meta['dataSha256']:raise ValueError('Verified grounded data required.')
    if out.exists():raise ValueError('Prepared plans are immutable; choose a new destination.')
    if review.get('schema')!='fold.cell-encoder-download/1' or review.get('license')!='cc-by-4.0' or review.get('model')!=MODEL:raise ValueError('Reviewed official biology checkpoint required.')
    out.mkdir(parents=True);(out/'code').mkdir();files=[];assets=[]
    def add(local,name,expected=None):
        row={'path':name,**(expected or {'bytes':local.stat().st_size,'sha256':digest(local)})};files.append(row);assets.append({**row,'local':str(local.resolve())})
    for name in SOURCES:
        p=out/'code'/name;shutil.copy2(repo/'scientific'/name,p);add(p,'code/'+name)
    for name in ['data.npz','manifest.json']:add(experiment/'cloud-inputs'/name,name)
    for name,(size,h) in OLD.CHECKPOINT.items():
        p=checkpoint/name
        if p.stat().st_size!=size or digest(p)!=h:raise ValueError('Existing official Qwen checkpoint changed.')
        add(p,'checkpoint/'+name)
    add(checkpoint/'LICENSE','checkpoint/LICENSE')
    for r in review['files']:add(biology/r['name'],'biology/'+r['name'],{'bytes':r['bytes'],'sha256':r.get('sha256'),'gitBlob':r.get('gitBlob')})
    manifest={'schema':'fold.cell-training-assets/2','checkpointRevision':REVISION,'biologyRevision':review['revision'],'biologyModel':review['model'],'files':files,'protocol':PROTOCOL}
    write(out/'ASSET_MANIFEST.json',manifest);h=digest(out/'ASSET_MANIFEST.json');write(out/'ENCODER_REVIEW.json',review)
    plan={'schema':'fold.cell-training-plan/2','recipe':RECIPE_ID,'recipeSha256':hashlib.sha256(json.dumps(RECIPE,sort_keys=True).encode()).hexdigest(),
          'manifest':str((out/'ASSET_MANIFEST.json').resolve()),'manifestSha256':h,'request':{'studyKey':h,'manifestSha256':h},'assets':assets,
          'gpu':'A100-80GB','timeout':5400,'protocol':PROTOCOL,'estimatedUsd':[8,15],'estimateIsDollarCap':False,'automaticRetry':False,
          'uploadBytes':sum(r['bytes'] for r in assets),'biologyPath':str(biology.resolve()),'encoderReview':str((out/'ENCODER_REVIEW.json').resolve()),
          'encoderReviewSha256':digest(out/'ENCODER_REVIEW.json'),'experiment':str(experiment.resolve()),
          'label':'10,000 cells · chemical & pathway evidence · five controlled variants · separate task validation'}
    write(out/'PLAN.json',plan);verify_plan(plan,allow_missing_biology=True);return plan


def verify_plan(plan,allow_missing_biology=False):
    if plan.get('schema')!='fold.cell-training-plan/2' or plan.get('protocol')!=PROTOCOL or plan.get('gpu')!='A100-80GB' or plan.get('timeout')!=5400 or plan.get('automaticRetry') is not False:raise ValueError('Fixed reviewed grounded study required.')
    if plan.get('recipe')!=RECIPE_ID or plan['recipeSha256']!=hashlib.sha256(json.dumps(RECIPE,sort_keys=True).encode()).hexdigest():raise ValueError('Grounded recipe changed.')
    if digest(plan['manifest'])!=plan['manifestSha256'] or plan['request']!={'studyKey':plan['manifestSha256'],'manifestSha256':plan['manifestSha256']}:raise ValueError('Grounded manifest changed.')
    if digest(plan['encoderReview'])!=plan['encoderReviewSha256']:raise ValueError('Encoder review changed.')
    meta=json.loads(Path(plan['manifest']).read_text());allowed={'data.npz','manifest.json',*('code/'+s for s in SOURCES),*('checkpoint/'+s for s in [*OLD.CHECKPOINT,'LICENSE'])}
    review=json.loads(Path(plan['encoderReview']).read_text())
    expected_names={'README.md','config.json','model.safetensors','special_tokens_map.json','tokenizer.json','tokenizer_config.json'}
    if review.get('model')!=MODEL or not re.fullmatch('[a-f0-9]{40}',review.get('revision','')) or {r['name'] for r in review['files']}!=expected_names:raise ValueError('Unexpected encoder identity or assets.')
    allowed|={'biology/'+r['name'] for r in review['files']}
    rows=[{k:v for k,v in a.items() if k!='local'} for a in plan['assets']]
    if rows!=meta['files'] or len(rows)!=len(allowed) or {r['path'] for r in rows}!=allowed:raise ValueError('Unreviewed assets or test answers in the upload list.')
    for a in plan['assets']:
        p=Path(a['local'])
        if allow_missing_biology and a['path'].startswith('biology/') and not p.exists():continue
        if not p.is_file() or p.stat().st_size!=a['bytes']:raise ValueError('Missing or changed input: '+a['path'])
        if a.get('sha256'):
            if digest(p)!=a['sha256']:raise ValueError('Input SHA changed: '+a['path'])
        elif not a.get('gitBlob') or git_blob(p)!=a['gitBlob']:raise ValueError('Pinned encoder source asset changed: '+a['path'])
        if a['path']=='data.npz':OLD.verify_answer_free(p)
    return meta


def remote_assets(plan):
    revision=json.loads(Path(plan['manifest']).read_text())['biologyRevision'];study='qwen-cell-studies/'+plan['request']['studyKey'];result=[]
    for a in plan['assets']:
        target=('models/qwen-cell/'+REVISION+'/'+a['path'][11:]) if a['path'].startswith('checkpoint/') else ('models/cell-encoder/'+revision+'/'+a['path'][8:]) if a['path'].startswith('biology/') else study+'/'+a['path']
        result.append({**a,'remote':target})
    result.append({'local':plan['manifest'],'remote':study+'/ASSET_MANIFEST.json','bytes':Path(plan['manifest']).stat().st_size,'sha256':plan['manifestSha256']});return result


def download_encoder(plan,approved,event):
    verify_plan(plan,allow_missing_biology=True)
    if all(Path(a['local']).exists() for a in plan['assets'] if a['path'].startswith('biology/')):return
    if not approved:raise ValueError('Explicit approval for the 1.62 GB Cell2Sentence checkpoint is required before download.')
    from cell_training_pretrained import download
    download(json.loads(Path(plan['encoderReview']).read_text()),plan['biologyPath'],approved=True,event=event)


def stage_and_launch(plan,volume,launch,cancelled,event):
    return OLD.stage_and_launch(plan,volume,launch,cancelled,event,verifier=verify_plan,asset_provider=remote_assets)
