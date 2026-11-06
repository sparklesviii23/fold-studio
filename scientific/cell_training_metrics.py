"""Masked biological metrics, honest constant-vector handling and group intervals."""
import numpy as np


def cosine(a,b):
    d=float(np.linalg.norm(a)*np.linalg.norm(b));return None if d<1e-15 else float(np.dot(a,b)/d)


def metrics(prediction,observed,mask,groups=None,top=100):
    p,y,m=np.asarray(prediction,float),np.asarray(observed,float),np.asarray(mask,bool)
    if p.shape!=y.shape or m.shape!=y.shape or p.ndim!=2 or not np.isfinite(p).all() or not np.isfinite(y[m]).all() or np.any(m.sum(1)==0):raise ValueError('Invalid response evaluation arrays.')
    rows=[]
    for a,b,ok in zip(p,y,m):
        a,b=a[ok],b[ok];n=min(top,len(a));ix=np.argsort(-np.abs(b),kind='stable')[:n];pi=np.argsort(-np.abs(a),kind='stable')[:n]
        changed=np.abs(b[ix])>1e-8
        # Top-effect metrics use the measured outcome only during scoring,
        # never for inputs, training feature selection or held-out fitting.
        rows.append({'mse':float(np.mean((a-b)**2)),'mae':float(np.mean(np.abs(a-b))),
                     'effectCosine':cosine(a,b),'centeredCorrelation':cosine(a-a.mean(),b-b.mean()),
                     'topEffectMse':float(np.mean((a[ix]-b[ix])**2)),
                     'topEffectDirectionAccuracy':float(np.mean(np.sign(a[ix][changed])==np.sign(b[ix][changed]))) if changed.any() else None,
                     'topEffectOverlap':float(len(set(ix)&set(pi))/n) if np.ptp(np.abs(a))>1e-12 else None})
    # Correct signature discrimination within this evaluation candidate set.
    distances=np.array([[np.mean((a[ok]-b[ok])**2) for b,ok in zip(y,m)] for a in p])
    ranks=[1+int(np.sum(distances[i]<distances[i,i]-1e-12))+(int(np.sum(np.isclose(distances[i],distances[i,i],atol=1e-12,rtol=0)))-1)/2 for i in range(len(p))]
    return {'conditions':len(p),'groups':len(set(groups)) if groups is not None else len(p),
            'mean':{k:(float(np.mean(v)) if (v:=[r[k] for r in rows if r[k] is not None]) else None) for k in rows[0]},
            'signatureTop1':float(np.mean([r==1 and np.sum(np.isclose(distances[i],distances[i,i],atol=1e-12,rtol=0))==1 for i,r in enumerate(ranks)])),
            'signatureMeanReciprocalRank':float(np.mean([1/r for r in ranks])),
            'signatureCandidates':len(p),'perCondition':rows,
            'note':'Top-effect genes are selected from scored outcomes; this is descriptive effect recovery, not a statistical differential-expression call.'}


def paired_group_interval(candidate,baseline,groups,seed=17,draws=1000):
    a,b=np.asarray(candidate,float),np.asarray(baseline,float);groups=np.asarray(groups).astype(str)
    names=sorted(set(groups));differences=np.array([(a[groups==g]-b[groups==g]).mean() for g in names])
    if not len(names) or not np.isfinite(differences).all():raise ValueError('Invalid grouped comparison.')
    if len(names)<2:return {'meanDifference':float(differences.mean()),'ci95':None,'groups':len(names)}
    rng=np.random.default_rng(seed);values=differences[rng.integers(len(names),size=(draws,len(names)))].mean(1)
    return {'meanDifference':float(differences.mean()),'ci95':np.quantile(values,[.025,.975]).tolist(),'groups':len(names),'method':'Paired bootstrap over whole intervention identities; descriptive within-dataset interval.'}


def fit_baselines(x,y,mask,validation_x,validation_y,validation_mask):
    """Ridge regularization selected on validation; all transforms fit training only."""
    x,y,mask=np.asarray(x,float),np.asarray(y,float),np.asarray(mask,bool)
    center=x.mean(0);scale=np.maximum(x.std(0),.05);z=(x-center)/scale
    mean=np.sum(np.where(mask,y,0),axis=0)/np.maximum(mask.sum(0),1);target=np.where(mask,y-mean,0)
    u,s,vt=np.linalg.svd(z,full_matrices=False);uy=u.T@target;trials=[];best=None
    for penalty in [1.,10.,100.,1000.]:
        weights=vt.T@((s/(s*s+penalty))[:,None]*uy);pred=((validation_x-center)/scale)@weights+mean
        score=float(np.mean(np.sum((pred-validation_y)**2*validation_mask,axis=1)/validation_mask.sum(1)));trials.append({'penalty':penalty,'validationMse':score})
        if best is None or score<best['score']:best={'score':score,'weights':weights,'penalty':penalty}
    return {'center':center,'scale':scale,'mean':mean,'weights':best['weights'],'penalty':best['penalty'],'trials':trials,'missingTrainingTargets':'imputed to training-only per-gene mean before fitting residual ridge'}


def baseline_predictions(fit,x):
    return {'unchanged':np.zeros((len(x),len(fit['mean']))),'training_mean':np.broadcast_to(fit['mean'],(len(x),len(fit['mean']))).copy(),
            'ridge':((x-fit['center'])/fit['scale'])@fit['weights']+fit['mean']}
