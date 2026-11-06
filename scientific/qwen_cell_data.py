"""Development-only biological supervision for a direct Qwen cell predictor.

No model downloads, source edits, test-outcome aggregation or promotion. Fixed
K562 background and measured single responses are required at inference.
"""
import json
from pathlib import Path
import hashlib
import numpy as np

BASE_RUN = 'ab4d920cc9714f9e8933b4aa150eef49'
SOURCE_SHA = 'efde6f5301fe256725dce1d980f37bd96a13481a9a16135515897368e631affc'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def verify_bundle(folder):
    folder=Path(folder);manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('schema')!='fold.qwen-cell.data/1' or manifest.get('legacyTestOutcomesIncluded') is not False:
        raise ValueError('Unsupported or unprotected training bundle.')
    if sha(folder/'data.npz')!=manifest['dataSha256']:raise ValueError('Training bundle integrity failed.')
    return manifest


def allowed_aggregate(aggregate,source,meta,columns,requested,blocked):
    if set(requested)&set(blocked):raise ValueError('Legacy test outcomes are excluded from Qwen development.')
    return aggregate(source,meta,columns,requested)


def assemble(plan,model,observed,teacher):
    """Fit every new numerical transform using training pairs only."""
    import k562_prototype as K
    train=plan['split']['train'];validation=plan['split']['validation'];labels=train+validation;n=len(train)
    if set(labels)&set(plan['split']['test']):raise ValueError('Condition split overlap.')
    ix={str(g):i for i,g in enumerate(model['singleGenes'])}
    a=np.array([model['singleEffects'][ix[p.split('+')[0]]] for p in labels])
    b=np.array([model['singleEffects'][ix[p.split('+')[1]]] for p in labels])
    raw=K.symmetric_features(a@model['encoder'],b@model['encoder'])
    center=raw[:n].mean(0);spread=np.maximum(raw[:n].std(0),1e-4);features=(raw-center)/spread
    target_center=observed[:n].mean(0);decoder=K.basis(observed[:n]-target_center,12)
    scale=np.maximum(((observed[:n]-target_center)@decoder).std(0),1e-4)
    mask=K.target_mask(labels,model['genes'])
    alpha=K.scale_fit((a+b)[:n],observed[:n],mask[:n])
    arrays={'trainX':features[:n],'validationX':features[n:],'trainY':observed[:n],'validationY':observed[n:],
            'trainMask':mask[:n],'validationMask':mask[n:],'trainTeacher':teacher,
            'validationAdditive':(a+b)[n:],'validationScaledAdditive':alpha*(a+b)[n:],
            'inputCenter':center,'inputScale':spread,'decoder':decoder,'targetCenter':target_center,'targetScale':scale,
            'genes':model['genes'],'singleGenes':model['singleGenes'],'singleEffects':model['singleEffects'],
            'singleEncoder':model['encoder'],'baseline':model['baseline'],
            'trainConditions':np.array(train),'validationConditions':np.array(validation)}
    return {k:v.astype(np.float32) if v.dtype.kind=='f' else v for k,v in arrays.items()}


def prepare(root,out):
    import k562_prototype as K
    root=Path(root);out=Path(out)
    if out.exists():raise ValueError('Choose a new output folder; existing training evidence is preserved.')
    base=root/'gpu_tasks'/BASE_RUN;record=json.loads((base/'task.json').read_text());base=base/'outputs'
    for name in ['MODEL.npz','SPLIT_MANIFEST.json','TRAINING_LOCK.json']:
        entry=next((x for x in record.get('outputs',[]) if x['path']==name),None)
        if record.get('state')!='done' or not entry or sha(base/name)!=entry['sha256']:
            raise ValueError('Verified RNA reference integrity failed: '+name)
    plan=json.loads((base/'SPLIT_MANIFEST.json').read_text());source=root/'oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad'
    if plan['source']['sha256']!=SOURCE_SHA:raise ValueError('Unexpected biological source.')
    K.verify_plan(plan,source);meta=K.metadata(source)
    with np.load(base/'MODEL.npz',allow_pickle=False) as z:model={k:z[k] for k in z.files}
    gi={str(g):i for i,g in enumerate(meta['genes'])};columns=np.array([gi[str(g)] for g in model['genes']])
    labels=plan['split']['train']+plan['split']['validation']
    # The aggregator selects only these conditions and matched controls. Test
    # metadata may be inspected to exclude it; test response values are not aggregated.
    observed,_=allowed_aggregate(K.aggregate,source,meta,columns,labels,plan['split']['test'])
    teacher=K.predict(base/'MODEL.npz',plan['split']['train'])
    arrays=assemble(plan,model,observed,teacher)
    if sha(source)!=SOURCE_SHA:raise ValueError('Biological source changed during preparation.')
    out.mkdir(parents=True);np.savez_compressed(out/'data.npz',**arrays)
    manifest={'schema':'fold.qwen-cell.data/1','sourceSha256':SOURCE_SHA,'referenceModelSha256':sha(base/'MODEL.npz'),
              'splitManifestSha256':sha(base/'SPLIT_MANIFEST.json'),'dataSha256':sha(out/'data.npz'),
              'trainConditions':len(plan['split']['train']),'validationConditions':len(plan['split']['validation']),
              'legacyTestConditionsExcluded':len(plan['split']['test']),'legacyTestOutcomesIncluded':False,
              'inputFeatures':int(arrays['trainX'].shape[1]),'readoutGenes':len(model['genes']),'outputCodeDimensions':arrays['decoder'].shape[1],
              'input':'Symmetric features of measured single-activation RNA effects in a fixed K562 background; no pair outcome is an input.',
              'output':'Direct mean RNA-response prediction through Qwen and its numerical head; no additive or separate predictor bypass.',
              'unit':'difference of mean log1p(counts per 10000), loading-group-matched controls',
              'transforms':'Gene panel and single-response encoder reused from the frozen prototype. New input scaling and output basis/center/scale fit on the 77 training pairs only.',
              'teacher':'Frozen 988-parameter RNA model predictions, training conditions only; synthetic auxiliary targets, not measurements. Default teacher-loss weight zero.',
              'primaryMetric':'Mean per-condition MSE excluding the two directly activated genes.',
              'validationStatus':'Reused development validation; previously benchmarked public screen; no new independent generalization claim.',
              'limitations':['Requires measured single responses.','No unseen-gene, drug, knockout, temporal, other-cell or whole-cell claim.'],
              'codeSha256':sha(__file__)}
    write(out/'manifest.json',manifest);return manifest
