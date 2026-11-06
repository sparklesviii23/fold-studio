"""Bounded local CRISPRa pair-response prototype, with a frozen condition holdout.

Requires the existing singlecell runtime (NumPy/SciPy/h5py). Never downloads,
submits compute, edits a source dataset or promotes a predictor into Virtual Cell.
Training reads no held-out pair response means. Predictions and weights are sealed
before test aggregation. A previously benchmarked public dataset is retrospective.
"""
import csv
import hashlib
import json
import platform
import time
from pathlib import Path

import h5py
import numpy as np

SCHEMA = 'fold.k562.pair-prototype/1'
SOURCE_SHA = 'efde6f5301fe256725dce1d980f37bd96a13481a9a16135515897368e631affc'
SOURCE_MD5 = 'c870e6967d91c017d9da827bab183cd6'
PROTOCOL = {
    'seed': 20261106, 'minimumCells': 20, 'variableGenes': 2048,
    'validationFraction': .2, 'testFraction': .2,
    'inputRank': 16, 'residualRank': 12, 'hidden': 16,
    'weightDecay': [.01, .1], 'epochs': 600, 'learningRate': .003,
    'checkpointEvery': 10, 'patienceCheckpoints': 12,
    'primaryMetric': 'mean condition MSE of RNA change, excluding both intervention targets',
    'selection': 'Lowest validation primary MSE; test outcomes never choose models or epochs.',
    'baselines': ['unchanged', 'training_pair_mean', 'additive', 'scaled_additive'],
    'bootstrapReplicates': 3000,
}


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def column(group, name):
    item = group[name]
    if isinstance(item, h5py.Group):
        codes = item['codes'][...]
        if (codes < 0).any():
            raise ValueError('Missing categorical metadata: ' + name)
        return np.asarray(item['categories'].asstr()[...][codes],dtype=str)
    return np.asarray(item.asstr()[...],dtype=str) if item.dtype.kind in 'OSU' else item[...]


def parts(label):
    return tuple(sorted(g for g in str(label).replace('+', '_').split('_') if g and g != 'control'))


def condition(label):
    genes = parts(label)
    return '+'.join(genes) if genes else 'control'


def metadata(path):
    with h5py.File(path, 'r') as f:
        obs = f['obs']
        result = {'labels': np.array([condition(x) for x in column(obs, 'perturbation')]),
                  'cellIds': column(obs, '_index'), 'genes': column(f['var'], '_index'),
                  'ensembl': column(f['var'], 'ensemble_id'), 'batch': column(obs, 'gemgroup').astype(str),
                  'librarySize': column(obs, 'ncounts').astype(float),
                  'cellLine': column(obs, 'cell_line'), 'organism': column(obs, 'organism')}
        result['shape'] = [int(x) for x in f['X'].attrs['shape']]
        result['encoding'] = f['X'].attrs['encoding-type']
    return result


def split_metadata(meta, protocol=PROTOCOL):
    if len(set(meta['cellIds'])) != len(meta['cellIds']) or len(set(meta['genes'])) != len(meta['genes']):
        raise ValueError('Cell or gene identifiers are not unique.')
    if set(meta['cellLine']) != {'K562'} or set(meta['organism']) != {'human'}:
        raise ValueError('This prototype only supports the recorded human K562 screen.')
    if meta['encoding'] != 'csc_matrix':
        raise ValueError('Expected the pinned raw-count CSC source.')
    labels, counts = np.unique(meta['labels'], return_counts=True)
    counts = dict(zip(labels, counts.astype(int)))
    genes = set(meta['genes'])
    singles = sorted(p for p, n in counts.items() if p != 'control' and len(p.split('+')) == 1
                     and p in genes and n >= protocol['minimumCells'])
    pairs = sorted(p for p, n in counts.items() if len(p.split('+')) == 2
                   and len(set(p.split('+'))) == 2 and set(p.split('+')) <= set(singles)
                   and n >= protocol['minimumCells'])
    order = sorted(pairs, key=lambda p: fingerprint([protocol['seed'], p]))
    nv = round(len(order) * protocol['validationFraction'])
    nt = round(len(order) * protocol['testFraction'])
    if min(nv, nt) < 10 or len(order) - nv - nt < 30:
        raise ValueError('Insufficient condition groups for the prespecified small prototype.')
    split = {'train': order[:len(order)-nv-nt], 'validation': order[len(order)-nv-nt:len(order)-nt],
             'test': order[len(order)-nt:]}
    role = {p: key for key, values in split.items() for p in values}
    role.update({p: 'single_calibration' for p in singles}); role['control'] = 'control_calibration'
    batches = sorted(set(meta['batch']))
    controls = {b: int(np.sum((meta['batch'] == b) & (meta['labels'] == 'control'))) for b in batches}
    if not all(n >= 20 for n in controls.values()):
        raise ValueError('Every loading group needs at least 20 matched control cells.')
    excluded = {str(p): 'Too few cells, unresolved target, self-pair or missing single-response calibration.'
                for p in labels if p not in role}
    return {'schema': SCHEMA, 'protocol': protocol, 'context': 'K562 SunTag CRISPRa; CVCL_0004 lineage',
            'split': split, 'singleCalibration': singles, 'counts': {str(k): int(v) for k,v in counts.items()},
            'roles': role, 'excluded': excluded, 'controlsByLoadingGroup': controls,
            'cellAssignmentSha256': fingerprint([[str(i), role.get(p, 'excluded')] for i,p in zip(meta['cellIds'],meta['labels'])]),
            'holdoutUnit': 'Whole canonical gene-pair condition; all its cells and guide orders stay together.',
            'interpretation': 'Newly frozen for this prototype. This public screen was used by prior Fold Studio benchmarks; this is retrospective, not independent-study validation.',
            'generalization': 'Unseen combinations of genes whose single-activation RNA responses are already measured. No unseen-gene, drug, knockout, temporal or other-cell validation.'}


def freeze(source, folder, protocol=PROTOCOL, verify_pinned=True):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    if (folder/'SPLIT_MANIFEST.json').exists():
        raise ValueError('A protocol is already frozen here; keep the previous run intact.')
    source = Path(source)
    sha = digest(source); md5 = digest(source, 'md5')
    if verify_pinned and (sha != SOURCE_SHA or md5 != SOURCE_MD5):
        raise ValueError('The existing source differs from the pinned original file.')
    meta = metadata(source); plan = split_metadata(meta, protocol)
    plan['source'] = {'path': str(source.resolve()), 'bytes': source.stat().st_size, 'sha256': sha, 'md5': md5,
                      'url': 'https://zenodo.org/records/7041849',
                      'citation': 'Norman et al. Science 2019, DOI 10.1126/science.aax4438; scPerturb harmonization.',
                      'licence': 'CC BY 4.0 (existing verified dataset manifest)'}
    plan['created'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    plan['sha256'] = fingerprint(plan)
    write(folder/'SPLIT_MANIFEST.json', plan)
    print('[fold] frozen groups: ' + str({k:len(v) for k,v in plan['split'].items()}), flush=True)
    return plan


def verify_plan(plan, source):
    raw = {k:v for k,v in plan.items() if k != 'sha256'}
    if fingerprint(raw) != plan['sha256'] or digest(source) != plan['source']['sha256']:
        raise ValueError('Frozen manifest or source integrity failed.')


def blocks(f, width=256):
    """Stream raw CSC columns, using bounded memory rather than densifying cells × genes."""
    x = f['X']; pointers = x['indptr'][...]
    for start in range(0, len(pointers)-1, width):
        end = min(start+width, len(pointers)-1); lo, hi = int(pointers[start]), int(pointers[end])
        rows = x['indices'][lo:hi]; values = x['data'][lo:hi]
        cols = np.repeat(np.arange(end-start), np.diff(pointers[start:end+1]))
        yield start, end, rows, cols, values


def training_variance(rows, cols, values, library, train, width):
    keep = train[rows]
    v = np.log1p(values[keep].astype(float) * (1e4/library[rows[keep]]))
    mu = np.bincount(cols[keep], weights=v, minlength=width)/int(train.sum())
    return np.maximum(np.bincount(cols[keep], weights=v*v, minlength=width)/int(train.sum())-mu*mu, 0)


def select_genes(source, meta, plan, folder):
    if not np.isfinite(meta['librarySize']).all() or (meta['librarySize'] <= 0).any():
        raise ValueError('Invalid per-cell library sizes.')
    allowed = set(plan['split']['train'] + plan['singleCalibration'] + ['control'])
    train = np.isin(meta['labels'], list(allowed)); variance = np.zeros(len(meta['genes']))
    totals = np.zeros(len(meta['labels']), dtype=float); nonzero = 0
    with h5py.File(source, 'r') as f:
        for start,end,rows,cols,v in blocks(f):
            if start % 8192 == 0:
                print(f'[fold] checking raw-count columns {start}/{len(variance)}; fitting statistics use training cells only', flush=True)
            if not np.isfinite(v).all() or (v < 0).any() or np.any(v != np.rint(v)):
                raise ValueError('The source matrix must contain finite nonnegative integer raw counts.')
            totals += np.bincount(rows, weights=v, minlength=len(totals)); nonzero += len(v)
            variance[start:end] = training_variance(rows,cols,v,meta['librarySize'],train,end-start)
    if not np.allclose(totals, meta['librarySize'], rtol=0, atol=.5):
        raise ValueError('Recorded library sizes differ from raw-count sums.')
    order = np.lexsort((meta['genes'], -variance))[:plan['protocol']['variableGenes']]
    target = np.flatnonzero(np.isin(meta['genes'], plan['singleCalibration']))
    selected = np.array(sorted(set(order) | set(target)), dtype=int)
    audit = {'schema': SCHEMA, 'sourceSha256': plan['source']['sha256'], 'shape': meta['shape'],
             'nonzeroStoredValues': nonzero, 'uniqueCellIds': True, 'uniqueGeneIds': True,
             'rawCountAndLibrarySizeChecksPassed': True, 'splitDisjoint': True,
             'selectedGenes': len(selected), 'featureSelectionCells': int(train.sum()),
             'featureSelection': 'Variance using training pair, single-calibration and control cells only, plus known target IDs. Validation/test response values never choose genes.',
             'controlMatching': 'Subtract mean control log-normalized RNA within each gemgroup before pooling condition cells.',
             'loadingGroups': plan['controlsByLoadingGroup'],
             'replicationLimit': 'gemgroup denotes loading groups, not demonstrated independent biological experiments.',
             'normalization': 'Per cell: log1p(raw counts × 10000 / raw library size). RNA change is a difference of these means, not a log2 fold change.',
             'selectedGeneIdsSha256': fingerprint(meta['genes'][selected].tolist())}
    write(Path(folder)/'DATA_AUDIT.json', audit)
    print('[fold] raw counts checked; selected '+str(len(selected))+' genes from training cells', flush=True)
    return selected, audit


def aggregate(source, meta, selected, requested):
    """Aggregate only requested conditions. Test is requested only after prediction sealing."""
    labels = list(requested); gi = {p:i for i,p in enumerate(labels)}
    group = np.array([gi.get(p, -1) for p in meta['labels']]); batches = sorted(set(meta['batch']))
    bi = np.array([batches.index(b) for b in meta['batch']]); control = meta['labels'] == 'control'
    counts = np.bincount(group[group>=0], minlength=len(labels)).astype(float)
    nc = np.bincount(bi[control], minlength=len(batches)).astype(float)
    mixtures = np.zeros((len(labels),len(batches)))
    np.add.at(mixtures,(group[group>=0],bi[group>=0]),1)
    mixtures /= counts[:,None]
    effects = np.empty((len(labels),len(selected))); baseline = np.empty(len(selected))
    with h5py.File(source, 'r') as f:
        x=f['X']; ptr=x['indptr'][...]
        for out,j in enumerate(selected):
            lo,hi=int(ptr[j]),int(ptr[j+1]); rows=x['indices'][lo:hi]
            v=np.log1p(x['data'][lo:hi].astype(float)*(1e4/meta['librarySize'][rows]))
            c=control[rows]; cm=np.bincount(bi[rows[c]],weights=v[c],minlength=len(batches))/nc
            keep=group[rows]>=0
            means=np.bincount(group[rows[keep]],weights=v[keep],minlength=len(labels))/counts
            effects[:,out]=means-mixtures@cm
            baseline[out]=float(cm@nc/nc.sum())
    if not np.isfinite(effects).all():raise ValueError('Nonfinite condition means.')
    return effects, baseline


def target_mask(labels, genes):
    return np.array([[g not in label.split('+') for g in genes] for label in labels])


def mse_rows(pred, observed, mask):
    return np.sum((pred-observed)**2*mask,axis=1)/mask.sum(1)


def scale_fit(additive, observed, mask):
    return float(np.clip(np.sum(additive*observed*mask)/max(np.sum(additive*additive*mask),1e-12),0,2))


def basis(matrix, rank):
    # Rank selected before test outcomes. No PCA on validation/test responses.
    _,_,vt=np.linalg.svd(matrix,full_matrices=False)
    return vt[:min(rank,len(vt))].T


def symmetric_features(a,b):
    return np.concatenate([a+b,np.abs(a-b),a*b],axis=1)


def initialize(inputs, hidden, outputs, seed):
    rng=np.random.default_rng(seed)
    return {'w1':rng.normal(0,1/np.sqrt(inputs),(inputs,hidden)), 'b1':np.zeros(hidden),
            'w2':rng.normal(0,.02/np.sqrt(hidden),(hidden,outputs)), 'b2':np.zeros(outputs)}


def forward(x,params):
    return np.tanh(x@params['w1']+params['b1'])@params['w2']+params['b2']


def loss_gradient(x,y,p,decay):
    hidden=np.tanh(x@p['w1']+p['b1']);pred=hidden@p['w2']+p['b2'];d=2*(pred-y)/pred.size
    dh=(d@p['w2'].T)*(1-hidden**2)
    grad={'w2':hidden.T@d+decay*p['w2'],'b2':d.sum(0),
          'w1':x.T@dh+decay*p['w1'],'b1':dh.sum(0)}
    loss=float(np.mean((pred-y)**2)+decay*.5*(np.sum(p['w1']**2)+np.sum(p['w2']**2)))
    return loss,grad


def train_mlp(x,y,validation,protocol,decay):
    p=initialize(x.shape[1],protocol['hidden'],y.shape[1],protocol['seed'])
    m={k:np.zeros_like(v) for k,v in p.items()};v={k:np.zeros_like(z) for k,z in p.items()}
    best=None;best_score=float('inf');stale=0;trace=[]
    for epoch in range(1,protocol['epochs']+1):
        loss,g=loss_gradient(x,y,p,decay)
        for key in p:
            m[key]=.9*m[key]+.1*g[key];v[key]=.999*v[key]+.001*g[key]**2
            p[key]-=protocol['learningRate']*(m[key]/(1-.9**epoch))/(np.sqrt(v[key]/(1-.999**epoch))+1e-8)
        if epoch%protocol['checkpointEvery']==0:
            score=float(validation(p));trace.append({'weightDecay':decay,'epoch':epoch,'trainingObjective':loss,'validationMse':score})
            if score < best_score:
                best_score=score;best={k:z.copy() for k,z in p.items()};stale=0
            else:stale+=1
            if stale>=protocol['patienceCheckpoints']:break
    return best,best_score,trace


def train(source,folder,plan,meta,selected):
    folder=Path(folder); protocol=plan['protocol']; verify_plan(plan,source)
    if (folder/'TRAINING_LOCK.json').exists():raise ValueError('Predictions are already sealed; no fitting after test evaluation.')
    singles=plan['singleCalibration'];train_labels=plan['split']['train'];val_labels=plan['split']['validation'];test_labels=plan['split']['test']
    allowed=singles+train_labels+val_labels
    assert not(set(allowed)&set(test_labels))
    observed,baseline=aggregate(source,meta,selected,allowed)
    single=observed[:len(singles)];idx={g:i for i,g in enumerate(singles)}
    genes=meta['genes'][selected];ys=observed[len(singles):];n=len(train_labels);y=ys[:n];val=ys[n:]
    all_labels=train_labels+val_labels+test_labels
    a=np.array([single[idx[p.split('+')[0]]] for p in all_labels]);b=np.array([single[idx[p.split('+')[1]]] for p in all_labels]);add=a+b
    train_mask=target_mask(train_labels,genes);val_mask=target_mask(val_labels,genes)
    alpha=scale_fit(add[:n],y,train_mask); mean=y.mean(0)
    encoder=basis(single,protocol['inputRank']); raw=symmetric_features(a@encoder,b@encoder)
    center=raw[:n].mean(0);spread=np.maximum(raw[:n].std(0),1e-4);features=(raw-center)/spread
    residual=y-alpha*add[:n];residual_center=residual.mean(0);decoder=basis(residual-residual_center,protocol['residualRank'])
    codes=(residual-residual_center)@decoder;code_scale=np.maximum(codes.std(0),1e-4);codes/=code_scale
    def decode(f,p):return (forward(f,p)*code_scale)@decoder.T+residual_center
    trials=[];best=None;best_score=float('inf');trace=[]
    for decay in protocol['weightDecay']:
        validate=lambda p: mse_rows(alpha*add[n:n+len(val_labels)]+decode(features[n:n+len(val_labels)],p),val,val_mask).mean()
        params,score,rows=train_mlp(features[:n],codes,validate,protocol,decay);trace+=rows
        trials.append({'weightDecay':decay,'validationMse':score,'checkpoints':len(rows)})
        if score<best_score:best_score=score;best=params;chosen_decay=decay
    predictions={'unchanged':np.zeros_like(add),'training_pair_mean':np.broadcast_to(mean,add.shape).copy(),
                 'additive':add,'scaled_additive':alpha*add,
                 'residual_mlp':alpha*add+decode(features,best)}
    val_scores={key:float(mse_rows(p[n:n+len(val_labels)],val,val_mask).mean()) for key,p in predictions.items()}
    baseline_winner=min(protocol['baselines'],key=val_scores.get);winner=min(val_scores,key=val_scores.get)
    model=folder/'MODEL.npz'
    np.savez_compressed(model,genes=genes,ensembl=meta['ensembl'][selected],singleGenes=np.array(singles),singleEffects=single,
                        baseline=baseline,encoder=encoder,featureCenter=center,featureScale=spread,decoder=decoder,
                        residualCenter=residual_center,codeScale=code_scale,alpha=np.array(alpha),trainingPairMean=mean,**best)
    prediction_file=folder/'SEALED_TEST_PREDICTIONS.npz'
    np.savez_compressed(prediction_file,conditions=np.array(test_labels),genes=genes,
                        **{k:p[-len(test_labels):] for k,p in predictions.items()})
    with (folder/'TRAINING_TRACE.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(trace[0]));w.writeheader();w.writerows(trace)
    lock={'schema':SCHEMA,'manifestSha256':plan['sha256'],'modelSha256':digest(model),'predictionSha256':digest(prediction_file),
          'selectedGenesSha256':fingerprint(genes.tolist()),'testTargetsAggregated':False,
          'baselineSelectedOnValidation':baseline_winner,'modelSelectedOnValidation':winner,'validationMse':val_scores,
          'prototypeWeightDecay':chosen_decay,'trials':trials,'additiveScaleTrainedOnly':alpha,
          'model':'Small symmetric residual MLP; 16-dimensional single-response encoder, 12-dimensional learned residual decoder, one tanh hidden layer. Dimensions may truncate if rank is lower.',
          'parameters':sum(p.size for p in best.values()),'software':{'python':platform.python_version(),'numpy':np.__version__,'h5py':h5py.__version__},
          'codeSha256':digest(__file__),'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    write(folder/'TRAINING_LOCK.json',lock)
    print('[fold] training complete; predictions sealed before test aggregation; validation selected '+winner,flush=True)
    return lock


def predict(model,conditions):
    """Portable inference from measured component singles; no pair outcomes are read."""
    with np.load(model,allow_pickle=False) as z:
        arrays={k:z[k] for k in z.files}
    idx={str(g):i for i,g in enumerate(arrays['singleGenes'])};canonical=[condition(c) for c in conditions]
    if any(len(p.split('+'))!=2 or len(set(p.split('+')))!=2 or not set(p.split('+'))<=set(idx) for p in canonical):
        raise ValueError('Requires two distinct genes with measured single-activation calibration in this K562 screen.')
    a=np.array([arrays['singleEffects'][idx[p.split('+')[0]]] for p in canonical]);b=np.array([arrays['singleEffects'][idx[p.split('+')[1]]] for p in canonical])
    x=(symmetric_features(a@arrays['encoder'],b@arrays['encoder'])-arrays['featureCenter'])/arrays['featureScale']
    return float(arrays['alpha'])*(a+b)+(forward(x,arrays)*arrays['codeScale'])@arrays['decoder'].T+arrays['residualCenter']


def metrics(pred,truth,mask):
    rows=[]
    for p,y,k in zip(pred,truth,mask):
        p,y=p[k],y[k];a,b=p-p.mean(),y-y.mean();den=np.linalg.norm(a)*np.linalg.norm(b)
        top=np.argsort(-np.abs(y),kind='stable')[:50]
        rows.append({'mse':float(np.mean((p-y)**2)),'mae':float(np.mean(np.abs(p-y))),
                     'pearson':float(a@b/den) if den>1e-12 else None,
                     'top50Mse':float(np.mean((p[top]-y[top])**2))})
    return rows


def interval(values,labels,reps,seed):
    """Endpoint-aware Poisson bootstrap of the observed pair graph; conditional on this study."""
    genes=sorted({g for p in labels for g in p.split('+')});gi={g:i for i,g in enumerate(genes)}
    ends=np.array([[gi[g] for g in p.split('+')] for p in labels]);rng=np.random.default_rng(seed)
    w=rng.poisson(1,size=(reps,len(genes)));w=w[:,ends[:,0]]*w[:,ends[:,1]];keep=w.sum(1)>0;w=w[keep]
    draws=(w@np.asarray(values))/w.sum(1)
    return {'mean':float(np.mean(values)),'ci95':np.quantile(draws,[.025,.975]).tolist(),'replicates':int(len(draws)),
            'method':'Shared-target endpoint-weighted Poisson bootstrap of held-out gene pairs. Conditional on this screen; not predictive intervals or independent-study uncertainty.'}


def evaluate(source,folder,plan,meta,selected):
    folder=Path(folder); lock=json.loads((folder/'TRAINING_LOCK.json').read_text());verify_plan(plan,source)
    if (folder/'EVALUATION.json').exists():raise ValueError('Test evaluation is already saved; no automatic test reopening or model retry.')
    if digest(folder/'MODEL.npz')!=lock['modelSha256'] or digest(folder/'SEALED_TEST_PREDICTIONS.npz')!=lock['predictionSha256']:
        raise ValueError('Sealed model or predictions changed before evaluation.')
    with np.load(folder/'SEALED_TEST_PREDICTIONS.npz',allow_pickle=False) as z:sealed={k:z[k] for k in z.files}
    labels=sealed.pop('conditions').tolist();genes=sealed.pop('genes')
    if labels!=plan['split']['test'] or fingerprint(genes.tolist())!=lock['selectedGenesSha256']:
        raise ValueError('Test identity differs from the frozen manifest.')
    reproduced=predict(folder/'MODEL.npz',labels)
    np.testing.assert_allclose(reproduced,sealed['residual_mlp'],rtol=1e-10,atol=1e-12)
    # First and only held-out expression aggregation happens after prediction sealing.
    truth,_=aggregate(source,meta,selected,labels);mask=target_mask(labels,genes)
    per={k:metrics(p,truth,mask) for k,p in sealed.items()}
    summary={k:{metric:float(np.mean([r[metric] for r in rows if r[metric] is not None])) if any(r[metric] is not None for r in rows) else None
                for metric in ('mse','mae','pearson','top50Mse')} for k,rows in per.items()}
    baseline=lock['baselineSelectedOnValidation'];target=np.array([r['mse'] for r in per[baseline]])
    comparisons={k:interval(np.array([r['mse'] for r in rows])-target,labels,plan['protocol']['bootstrapReplicates'],plan['protocol']['seed']+8) for k,rows in per.items() if k!=baseline}
    ci=comparisons['residual_mlp'];gained=ci['mean']<0 and ci['ci95'][1]<0
    report={'schema':SCHEMA,'context':plan['context'],'source':plan['source'],'split':{k:len(v) for k,v in plan['split'].items()},
            'manifestSha256':plan['sha256'],'trainingLock':lock,'geneCount':len(genes),'testConditions':labels,
            'summary':summary,'pairedMseDifferenceVsValidationBaseline':comparisons,'perCondition':per,
            'primaryScoring':'Equal weight per held-out pair; exclude its two target genes; compare differences of matched-control log1p CPM means.',
            'portablePredictionReproductionPassed':True,
            'conclusion':('The prototype improves the primary error versus the validation-selected baseline within this retrospective holdout, with an endpoint-weighted interval below zero.' if gained else 'The prototype has not demonstrated a reliable primary-error improvement over the validation-selected simple baseline.'),
            'promotion':'Research prototype only; no automatic replacement of Virtual Cell predictions.',
            'limitations':[plan['interpretation'],plan['generalization'],'Only 26 held-out pairs if the expected 129 eligible conditions are present; intervals can be unstable.',
                           'Pair outcomes share target genes. Endpoint bootstrap is a dependence sensitivity estimate, not independent-study replication.',
                           'Measured single-activation responses are required as inputs; this is not prediction from gene identity alone.',
                           'No sequential, temporal, protein, morphology, drug, knockout, other-cell or whole-cell simulation validation.'],
            'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    np.savez_compressed(folder/'TEST_OBSERVATIONS.npz',conditions=np.array(labels),genes=genes,observed=truth,scoreMask=mask)
    write(folder/'EVALUATION.json',report)
    with (folder/'METRICS.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['model','mse','mae','pearson','top50Mse']);w.writeheader();w.writerows({'model':k,**v} for k,v in summary.items())
    print('[fold] held-out evaluation saved; '+report['conclusion'],flush=True)
    return report


def render_report(folder, report, audit):
    folder=Path(folder);lock=report['trainingLock'];base=lock['baselineSelectedOnValidation']
    names={'unchanged':'Unchanged control','training_pair_mean':'Training-pair mean','additive':'Measured-single additive',
           'scaled_additive':'Training-fitted additive scale','residual_mlp':'Small residual neural prototype'}
    lines=['# K-562 genetic-response prototype','',report['conclusion'],'',
           '**Scope:** paired CRISPR activation in the Norman 2019 K-562 screen, with measured single-activation RNA responses available as calibration.',
           '**Evaluation status:** newly frozen holdout for this prototype; retrospective reuse of a public screen already benchmarked in Fold Studio. Independent-study accuracy remains untested.','',
           '## What ran','',f"The existing {audit['shape'][0]:,}-cell raw-count file was reused and its published MD5 and retained SHA-256 verified. {report['split']['train']} pair conditions trained the interaction model, {report['split']['validation']} selected its settings, and {report['split']['test']} were reserved for one final evaluation. All cells belonging to a pair stayed together.",
           f"Training-only variation selected the RNA panel ({report['geneCount']} genes, including the known intervention targets). Each cell was normalized to 10,000 counts and log1p transformed. Responses subtract matched control means within each of eight loading groups. The two activated target genes are excluded from each condition's primary score.",
           f"The neural prototype has {lock['parameters']:,} trainable parameters. Its encoder uses measured single-response profiles; its learned residual decoder and nonlinear hidden layer model departures from a training-fitted additive response. Two prespecified regularization settings were tried, with validation-only checkpoint selection. Test predictions and weights were sealed before test response means were aggregated.",'',
           '## Held-out results','', '| Method | Mean squared error ↓ | Mean absolute error ↓ | Mean response Pearson ↑ | Top-50 response MSE ↓ |','|---|---:|---:|---:|---:|']
    for key,values in report['summary'].items():
        corr='undefined' if values['pearson'] is None else f"{values['pearson']:.3f}"
        lines.append(f"| {names[key]} | {values['mse']:.6f} | {values['mae']:.6f} | {corr} | {values['top50Mse']:.6f} |")
    comparison=report['pairedMseDifferenceVsValidationBaseline']['residual_mlp']
    lines+=['',f"The simple baseline chosen on validation data was **{names[base]}**. Neural prototype minus that baseline: **{comparison['mean']:+.6f} MSE**, endpoint-weighted 95% bootstrap interval **[{comparison['ci95'][0]:+.6f}, {comparison['ci95'][1]:+.6f}]**. Negative differences favour the prototype. Shared-target resampling is a sensitivity estimate conditional on this screen; it does not establish independent replication.",
            '','## What was saved','',
            '- `MODEL.npz`: fitted weights, RNA encoder/decoder, preprocessing and measured single-response calibrations; arrays load without pickle.',
            '- `SPLIT_MANIFEST.json`, `DATA_AUDIT.json`, `TRAINING_LOCK.json`: frozen protocol, checks and pre-evaluation hashes.',
            '- `SEALED_TEST_PREDICTIONS.npz`, `TEST_OBSERVATIONS.npz`, `EVALUATION.json`, `METRICS.csv`, `TRAINING_TRACE.csv`: predictions, measured comparison and complete outcomes.',
            '- `predict.py`: NumPy-only inference for supported gene pairs, independent of the original raw dataset.',
            '','## Scientific limits','']+[f'- {x}' for x in report['limitations']]
    lines+=['- Loading groups are not proven independent biological replicates.','- Model disagreement or a benchmark interval is not calibrated uncertainty for a future individual prediction.',
            '- This task predicts mean RNA response for simultaneous paired activation. No persistent learned whole-cell state or sequential intervention engine was established.',
            '- Existing Virtual Cell predictions were not replaced automatically.','',
            '## Sources','',
            'Dataset and checksum: [scPerturb record 7041849](https://zenodo.org/records/7041849). Original experiment: [Norman et al., Science 2019](https://pubmed.ncbi.nlm.nih.gov/31395745/).',
            '',f"Source SHA-256: `{report['source']['sha256']}`. Frozen manifest SHA-256: `{report['manifestSha256']}`. Portable weight-based predictions reproduced the sealed neural predictions."]
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    keys=list(report['summary']);vals=[report['summary'][k]['mse'] for k in keys]
    axes[0].barh(range(len(keys)),vals,color=['#aab2c5','#aab2c5','#89b5cf','#73b89a','#a392d2'])
    axes[0].set_yticks(range(len(keys)),[names[k] for k in keys]);axes[0].invert_yaxis();axes[0].set_xlabel('Held-out mean squared RNA-response error (lower is better)')
    d=np.array([r['mse'] for r in report['perCondition']['residual_mlp']])-np.array([r['mse'] for r in report['perCondition'][base]])
    axes[1].scatter(range(1,len(d)+1),d,color='#a392d2');axes[1].axhline(0,color='#738096',lw=1)
    axes[1].set_xlabel('Frozen held-out pair index');axes[1].set_ylabel('Neural minus validation-selected baseline MSE')
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.suptitle(f"K-562 paired activation · {len(d)} held-out conditions\nRetrospective single-study test; measured component responses supplied",fontsize=12)
    fig.savefig(folder/'RESULTS.png',dpi=170);plt.close(fig)
