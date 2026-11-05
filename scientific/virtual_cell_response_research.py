"""Retrospective response diagnostics and training-only statistical comparisons.

Keeps the original 72 cases and scores intact. Standard errors are diagnostic
approximations, not raw control replicates or donor-aware biological validation.
"""
import json
from pathlib import Path
import time
import re

import numpy as np
from scipy.special import ndtr

import virtual_cell_benchmarks as B
import virtual_cell_drugs as D


def bh_count(z, alpha=.05):
    p=2*ndtr(-np.abs(z[np.isfinite(z)])); p.sort()
    return int(np.max(np.where(p<=alpha*np.arange(1,len(p)+1)/max(1,len(p)),np.arange(1,len(p)+1),0),initial=0))


def diagnose(root, run):
    old=B.load(root,run); A=D.atlas(root)
    with np.load(Path(root).joinpath(*B.FOLDER,run,'predictions.npz'),allow_pickle=False) as z:
        if list(z['genes'])!=A.genes: raise ValueError('Gene feature order changed.')
        rows=[]
        for r in old['results']['test']:
            prefix=r['artifactPrefix']; mask=z[prefix+'_mask']; obs=z[prefix+'_observed']; pred=z[prefix+'_drug_dose_mean']
            raw=np.asarray(A.lfc[r['targetRows']],float); se=np.asarray(A.se[r['targetRows']],float)
            if not np.array_equal(B._mean(raw),obs,equal_nan=True): raise ValueError('Target observations changed.')
            valid=np.isfinite(raw)&np.isfinite(se)&(se>0)
            zs=np.full_like(raw,np.nan); zs[valid]=raw[valid]/se[valid]
            earlier=[i for i,c in enumerate(A.conditions) if c['cellosaurus']==r['cellosaurus'] and c['drug'].strip().lower()==r['drug'] and float(c['concentration'])==r['concentration'] and 1<=int(c['plate'])<=10]
            same_line=B._mean(np.asarray(A.lfc[earlier],float)) if earlier else None
            rr=None
            selected_rr=None; discovery_genes=0
            if same_line is not None:
                ok=mask&np.isfinite(same_line)
                if ok.sum()>100 and np.ptp(same_line[ok]) and np.ptp(obs[ok]): rr=float(np.corrcoef(same_line[ok],obs[ok])[0,1])
                earlier_lfc=np.asarray(A.lfc[earlier],float); earlier_se=np.asarray(A.se[earlier],float)
                ev=np.isfinite(earlier_lfc)&np.isfinite(earlier_se)&(earlier_se>0)
                ez=np.full_like(earlier_lfc,np.nan); ez[ev]=earlier_lfc[ev]/earlier_se[ev]
                discovery=B._mean(np.abs(ez))>4; discovery &= ok; discovery_genes=int(discovery.sum())
                if discovery_genes>=10 and np.ptp(same_line[discovery]) and np.ptp(obs[discovery]): selected_rr=float(np.corrcoef(same_line[discovery],obs[discovery])[0,1])
            y=obs[mask]; p=pred[mask]
            rows.append({**{k:r[k] for k in ('cellosaurus','cellLine','drug','concentration','unit','targetRows','targetPlates')},
                         'treatedCells':[A.conditions[i]['cellsTreated'] for i in r['targetRows']], 'controlCells':[A.conditions[i]['cellsControl'] for i in r['targetRows']],
                         'meanAbsoluteEffect':float(np.abs(y).mean()),'fractionAbsLfcAtLeast1':float((np.abs(y)>=1).mean()),
                         'waldAbsZ4Genes':[int(np.sum(np.abs(x[np.isfinite(x)])>4)) for x in zs],
                         'approximateWaldBh05Genes':[bh_count(x) for x in zs],
                         'medianStandardError':float(np.nanmedian(np.where(valid,se,np.nan))),
                         'sameLineOtherPlateRows':earlier,'sameLineOtherPlateEffectPearson':rr,
                         'otherPlateSelectedGenes':discovery_genes,'otherPlateSelectedEffectPearson':selected_rr,
                         'donorPredictionEnergy':float(np.square(p).mean()),'twicePredictionTruthProduct':float(2*np.mean(p*y)),
                         'donorMseDifferenceVsControl':r['metrics']['drug_dose_mean']['mse']-r['metrics']['unchanged']['mse'],
                         'metrics':r['metrics']})
    usable=[r['sameLineOtherPlateEffectPearson'] for r in rows if r['sameLineOtherPlateEffectPearson'] is not None]
    selected=[r['otherPlateSelectedEffectPearson'] for r in rows if r['otherPlateSelectedEffectPearson'] is not None]
    out={'schema':'fold.virtualcell.response-diagnostics/1','sourceRun':run,'conditions':rows,
         'summary':{'n':len(rows),'donorBeatsControlCases':sum(r['donorMseDifferenceVsControl']<0 for r in rows),
                    'lowWaldSignalCases':sum(max(r['waldAbsZ4Genes'])<30 for r in rows),
                    'sameLineAcrossPlatePairs':len(usable),'sameLineAcrossPlateMeanPearson':float(np.mean(usable)) if usable else None,
                    'otherPlateSelectedPairs':len(selected),'otherPlateSelectedMeanPearson':float(np.mean(selected)) if selected else None,
                    'donorMeanPredictionEnergy':float(np.mean([r['donorPredictionEnergy'] for r in rows])),
                    'donorMeanTwicePredictionTruthProduct':float(np.mean([r['twicePredictionTruthProduct'] for r in rows]))},
         'classification':{'implementation':'Exact reproduction and matching gene/feature order checks passed; no demonstrated indexing or numerical bug.',
                           'datasetLimitation':'Only pseudobulk DESeq2 log2FC/SE and cell counts are present; raw control-to-control and within-condition per-cell variation cannot be recovered.',
                           'distributionShift':'Entire cell identities and plates differ; same-line other-plate agreement is a diagnostic, not a permissible model input.',
                           'modelLimitation':'Mean-squared error is worse when prediction energy exceeds twice its alignment with measured effects. This identity does not prove whether the missing alignment is biological or technical.',
                           'weakBiologicalSignal':'Wald signal counts describe estimated signal relative to reported SE; weak biology and technical noise cannot be conclusively separated.',
                           'evaluationIssue':'All-gene MSE and covered-gene correlations measure different aspects. All metrics and the unchanged baseline are retained.',
                           'unresolved':'Original well/specimen identifiers, duration, covariance and raw controls are absent; exact causal attribution of errors is unresolved.'},
         'standardErrorSha256':B.file_hash(Path(root)/'virtualcell/data/tahoe100m/se.f16'),
         'limitations':['Wald/BH counts are recomputed approximations from float16 LFC/SE, not published adjusted P values.',
                        'Cell counts are not independent biological replicate counts.', 'Same-line replicate rows are used only to diagnose reference reproducibility, never to fit a held-out-line predictor.']}
    out['sha256']=B._hash(out); return out


def save_diagnostics(root,report):
    if not re.fullmatch('[a-f0-9]{32}',str(report.get('sourceRun'))): raise ValueError('Invalid source run.')
    if B._hash({k:v for k,v in report.items() if k!='sha256'})!=report.get('sha256'): raise ValueError('Diagnostic checksum mismatch.')
    folder=Path(root)/'virtualcell/response-diagnostics'/report['sourceRun']; folder.mkdir(parents=True,exist_ok=True)
    temp=folder/'report.partial'; temp.write_text(json.dumps(report,indent=1,allow_nan=False)); temp.replace(folder/'report.json')


def diagnostics(root):
    reports=[]
    for path in sorted((Path(root)/'virtualcell/response-diagnostics').glob('*/report.json')):
        report=json.loads(path.read_text()); digest=report.pop('sha256',None)
        if report.get('sourceRun')!=path.parent.name or B._hash(report)!=digest: raise ValueError('Diagnostic checksum mismatch.')
        B.load(root,report['sourceRun'])
        reports.append({**report,'sha256':digest})
    return reports


PROTOCOL='tahoe-response-comparison/2'
NEW_LABELS={'shrunken_donor':'Validation-shrunk matched donor mean','nearest3':'Three nearest untreated RNA contexts',
            'ridge_context':'Ridge regression on untreated RNA PCA','low_rank':'Rank-4 response ridge regression','rbf_context':'Nonlinear RBF kernel ridge on untreated RNA PCA'}


def transfer_fit(x,y,query,spec):
    """Fit each gene only on observed training donors; no outcome imputation."""
    output=np.full((len(query),y.shape[1]),np.nan); finite=np.isfinite(y)
    _,groups=np.unique(np.packbits(finite.T,axis=1),axis=0,return_inverse=True)
    for group in range(int(groups.max())+1):
        columns=np.flatnonzero(groups==group); rows=finite[:,columns[0]]
        if not rows.any():continue
        yy=y[rows][:,columns];mu=yy.mean(axis=0);centered=yy-mu
        if rows.sum()==1:output[:,columns]=mu;continue
        xx=x[rows,:spec.get('dimensions',8)];qq=query[:,:spec.get('dimensions',8)]
        if spec['family']=='low_rank':
            eigenvalues,eigenvectors=np.linalg.eigh(centered@centered.T)
            basis=eigenvectors[:,np.argsort(eigenvalues)[-min(4,len(xx)-1,len(columns)):]]
            centered=basis@(basis.T@centered)
        if spec['family']=='rbf_context':
            distances=np.square(xx[:,None,:]-xx[None,:,:]).mean(axis=2); positive=distances[distances>0]
            bandwidth=(float(np.median(positive)) if len(positive) else 1.)*spec['bandwidth']
            kernel=np.exp(-distances/max(bandwidth,1e-12));cross=np.exp(-np.square(qq[:,None,:]-xx[None,:,:]).mean(axis=2)/max(bandwidth,1e-12))
        else:kernel=xx@xx.T/xx.shape[1];cross=qq@xx.T/xx.shape[1]
        # An unpenalised intercept, with training-only centring of both kernels.
        kmean=kernel.mean(axis=0);grand=float(kernel.mean())
        k=kernel-kmean[None,:]-kernel.mean(axis=1)[:,None]+grand
        q=cross-kmean[None,:]-cross.mean(axis=1)[:,None]+grand
        coefficients=np.linalg.solve(k+spec['alpha']*np.eye(len(xx)),centered)
        output[:,columns]=mu+q@coefficients
    return output


def additional_plan(root,old,rows,donors,count=20):
    """Freeze new condition identities using metadata before reading outcomes."""
    excluded={tuple(x) for values in old['selection']['keys'].values() for x in values}
    candidates=[]
    for key,byline in donors.items():
        if key in excluded or len(byline)<10:continue
        if all(any((line,*key,plate) in rows for plate in (13,14)) for line in old['split']['test']):candidates.append(key)
    keys=sorted(candidates,key=lambda k:B._hash([PROTOCOL,29,list(k)]))[:count]
    if len(keys)!=count:raise ValueError('Insufficient metadata-only additional conditions.')
    plan={'schema':'fold.response.additional-plan/1','protocol':PROTOCOL,'sourceRun':old['id'],'sourceSha256':old['sha256'],'keys':[list(k) for k in keys],
          'lines':old['split']['test'],'plates':[13,14],'seed':29,'rule':'Hash ordering, at least ten training donors, metadata coverage on all test lines; excludes all original validation/test keys.',
          'limitation':'New conditions on previously used test lines and plates, not an independent study or untouched biological contexts.'}
    plan['sha256']=B._hash(plan);folder=Path(root)/'virtualcell/response-plans';folder.mkdir(parents=True,exist_ok=True);path=folder/(old['id']+'.json')
    if path.exists():
        if json.loads(path.read_text())!=plan:raise ValueError('Frozen additional-condition plan changed.')
    else:
        with path.open('x') as f:json.dump(plan,f,indent=1)
    return plan


def evaluate(root,source_run):
    started=time.monotonic();old=B.load(root,source_run);A=D.atlas(root)
    if A is None or not A.complete:raise ValueError('Completed Tahoe atlas required.')
    # Verify all original input bytes; preservation of split/outcome identity is mandatory.
    for source in old['inputs']:
        if B.file_hash(Path(root)/source['path'])!=source['sha256']:raise ValueError('Source benchmark input changed: '+source['path'])
    rows=B.group_rows(A.conditions);train=set(old['split']['train']);donor_rows={}
    for (line,drug,dose,plate),index in rows.items():
        if line in train and 1<=plate<=10:donor_rows.setdefault((drug,dose),{}).setdefault(line,[]).append(index)
    plan=additional_plan(root,old,rows,donor_rows)
    print('[fold] additional-condition identities frozen '+plan['sha256'],flush=True)
    with np.load(Path(root).joinpath(*B.FOLDER,source_run,'predictions.npz'),allow_pickle=False) as z:original={key:z[key] for key in z.files}
    if list(original['genes'])!=A.genes:raise ValueError('Gene order mismatch.')
    neighbours,nn=B._neighbours(root,A,old['split'])
    if nn!=old['nearestContextFit']:raise ValueError('Untreated feature fit changed.')
    meta,raw=B._contexts(root,None);lines=sorted(old['split']['train']+old['split']['validation']+old['split']['test']);line_index={line:i for i,line in enumerate(lines)}
    features=[meta['genes'].index(g) for g in nn['features']];indices=[meta['models'].index(A.lines[line]['depmap']) for line in lines]
    x=(np.asarray(raw[indices][:,features],float)-np.array(nn['center']))/np.array(nn['scale'])
    ti=[line_index[line] for line in old['split']['train']];u,s,vt=np.linalg.svd(x[ti],full_matrices=False)
    components=vt[:16];scale=np.maximum(s[:16]/np.sqrt(len(ti)-1),1e-12);scores=x@components.T/scale
    cache={}
    def donors(key):
        if key not in cache:
            names=sorted(donor_rows[key]);used=sorted(i for rs in donor_rows[key].values() for i in rs)
            if any(A.conditions[i]['cellosaurus'] not in train or not 1<=int(A.conditions[i]['plate'])<=10 for i in used):raise ValueError('Donor leakage.')
            cache[key]=(names,np.vstack([B._mean(np.asarray(A.lfc[donor_rows[key][line]],float)) for line in names]),used)
        return cache[key]
    specs=[{'family':'ridge_context','dimensions':dim,'alpha':alpha} for dim in (8,16) for alpha in (.01,.1,1.,10.,100.)]
    specs +=[{'family':'low_rank','dimensions':8,'alpha':alpha} for alpha in (.01,.1,1.,10.,100.)]
    specs +=[{'family':'rbf_context','dimensions':8,'alpha':alpha,'bandwidth':width} for width in (.25,1.,4.) for alpha in (.01,.1,1.,10.,100.)]
    validation=old['results']['validation'];validation_keys=sorted({(r['drug'],r['concentration']) for r in validation});totals={B._hash(spec):[] for spec in specs}
    for key in validation_keys:
        names,y,_=donors(key);cases=[r for r in validation if (r['drug'],r['concentration'])==key];query=scores[[line_index[r['cellosaurus']] for r in cases]];xx=scores[[line_index[line] for line in names]]
        for spec in specs:
            pred=transfer_fit(xx,y,query,spec)
            for r,prediction in zip(cases,pred):
                mask=original[r['artifactPrefix']+'_mask'];truth=original[r['artifactPrefix']+'_observed']
                if not np.isfinite(prediction[mask]).all():raise ValueError('Candidate lacks original eligible genes.')
                totals[B._hash(spec)].append(float(np.square(prediction[mask]-truth[mask]).mean()))
        print('[fold] validation candidates checked '+str(key),flush=True)
    tuned={family:min([spec for spec in specs if spec['family']==family],key=lambda spec:np.mean(totals[B._hash(spec)])) for family in ('ridge_context','low_rank','rbf_context')}
    shrink_scores={amount:float(np.mean([np.square(amount*original[r['artifactPrefix']+'_drug_dose_mean'][original[r['artifactPrefix']+'_mask']]-original[r['artifactPrefix']+'_observed'][original[r['artifactPrefix']+'_mask']]).mean() for r in validation])) for amount in (0.,.1,.25,.5,.75,1.)}
    shrink=min(shrink_scores,key=shrink_scores.get)
    print('[fold] validation-only parameters frozen '+json.dumps({'shrink':shrink,'models':tuned}),flush=True)
    cases_by_mode={'validation':validation,'test':old['results']['test'],'additional':[]}
    for line in old['split']['test']:
        for drug,dose in plan['keys']:
            target=sorted(rows[(line,drug,dose,p)] for p in (13,14) if (line,drug,dose,p) in rows)
            names,y,used=donors((drug,dose));nearest=next(n for n in neighbours[line] if n in names)
            cases_by_mode['additional'].append({'cellosaurus':line,'cellLine':A.lines[line]['name'],'drug':drug,'concentration':dose,'unit':'uM','targetRows':target,'targetPlates':sorted({A.conditions[i]['plate'] for i in target}),
                                               'donorRows':used,'donorLines':names,'nearestDonor':nearest,'artifactPrefix':'additional_'+str(len(cases_by_mode['additional']))})
    labels={**B.MODEL_LABELS,**NEW_LABELS};artifacts={'genes':original['genes'],'training_mean':original['training_mean']};results={};used_training=set(old['trainingRows'])
    for mode,cases in cases_by_mode.items():
        results[mode]=[]
        for key in sorted({(r['drug'],r['concentration']) for r in cases}):
            names,y,used=donors(key);used_training.update(used);matched=B._mean(y);chosen=[r for r in cases if (r['drug'],r['concentration'])==key]
            query=scores[[line_index[r['cellosaurus']] for r in chosen]];xx=scores[[line_index[line] for line in names]]
            fits={family:transfer_fit(xx,y,query,spec) for family,spec in tuned.items()}
            for ri,r in enumerate(chosen):
                prefix=r['artifactPrefix']
                if mode!='additional':truth=original[prefix+'_observed'];predicted={m:original[prefix+'_'+m] for m in B.MODELS}
                else:
                    truth=B._mean(np.asarray(A.lfc[r['targetRows']],float));predicted={'unchanged':np.zeros(len(A.genes)),'training_mean':original['training_mean'],'drug_dose_mean':matched,'nearest_context':y[names.index(r['nearestDonor'])]}
                nearest=[n for n in neighbours[r['cellosaurus']] if n in names][:3]
                predicted.update(shrunken_donor=shrink*matched,nearest3=B._mean(y[[names.index(n) for n in nearest]]),**{family:values[ri] for family,values in fits.items()})
                metrics,mask=B.metrics(truth,predicted)
                if mode!='additional' and not np.array_equal(mask,original[prefix+'_mask']):raise ValueError('Primary eligible-gene mask changed.')
                if set(r['targetRows'])&set(used):raise ValueError('Target/training overlap.')
                for model,prediction in predicted.items():
                    if mode!='additional' and model in B.MODELS and metrics[model]!=r['metrics'][model]:raise ValueError('Original predictor score changed.')
                    pp=prediction[mask];tt=truth[mask];centroid=original['training_mean'][mask];aa=pp-centroid;bb=tt-centroid
                    metrics[model]['centroidResidualPearson']=float(np.corrcoef(aa,bb)[0,1]) if np.ptp(aa)>0 and np.ptp(bb)>0 else None
                    strong=np.abs(tt)>=1;metrics[model]['strongEffectSignAgreement']=float(np.mean(np.sign(pp[strong])==np.sign(tt[strong]))) if strong.any() else None
                    metrics[model]['top100EffectRecall']=len(set(np.argsort(-np.abs(pp))[:100])&set(np.argsort(-np.abs(tt))[:100]))/100 if np.ptp(np.abs(pp))>0 else None
                    artifacts[prefix+'_'+model]=prediction
                artifacts[prefix+'_observed']=truth;artifacts[prefix+'_mask']=mask;results[mode].append({**r,'metrics':metrics})
            print('[fold] scored '+mode+' '+str(key),flush=True)
        # Preserve the exact original condition order for reproducibility.
        order={r['artifactPrefix']:i for i,r in enumerate(cases)};results[mode].sort(key=lambda r:order[r['artifactPrefix']])
    metric_names=('mae','mse','pearson','centroidResidualPearson','strongEffectSignAgreement','top100EffectRecall')
    summary={mode:{model:{metric:B.crossed_interval(rs,model,metric,17) for metric in metric_names} for model in labels} for mode,rs in results.items()}
    contrasts={mode:{model:B.crossed_interval(rs,model,'mse',17,baseline='unchanged') for model in labels if model!='unchanged'} for mode,rs in results.items() if mode!='validation'}
    selected=min(labels,key=lambda m:summary['validation'][m]['mse']['mean'])
    report={k:v for k,v in old.items() if k not in ('id','created','sha256','artifacts','complete')}
    report.update(protocol=PROTOCOL,sourceBenchmarkRun=source_run,sourceBenchmarkSha256=old['sha256'],models=labels,results=results,summary=summary,trainingRows=sorted(used_training),
                  testMseDifferenceVsTrainingMean={model:B.crossed_interval(results['test'],model,'mse',17,baseline='training_mean') for model in labels if model!='training_mean'},
                  mseDifferenceVsUnchanged=contrasts,additionalConditionPlan=plan,
                  tuning={'selectedOnValidation':selected,'shrink':shrink,'specifications':tuned,'validationGridScores':[{'spec':spec,'mse':float(np.mean(totals[B._hash(spec)]))} for spec in specs],
                          'shrinkValidationScores':shrink_scores,'featureFit':'Train-only 256-gene standardisation, train-only PCA, whitened scores; each matched-drug model fits training lines/plates only.',
                          'pcaComponents':components.tolist(),'pcaScale':scale.tolist(),'missingness':'Per-gene finite-donor subsets; no missing response is imputed. A single observed donor gives the intercept only.'},
                  modelRegistry={model:{'version':PROTOCOL,'status':'benchmarked','family':'nonlinear statistical predictor' if model=='rbf_context' else 'statistical baseline',
                                        'trainingDomain':'Tahoe matched drug/dose, 29 training lines, plates 1–10','input':'untreated DepMap 24Q4 RNA plus drug/dose identity; training donor responses',
                                        'output':'pseudobulk DESeq2 log2 fold change','uncertainty':'Crossed line/compound bootstrap; no calibrated gene-level intervals'} for model in labels},
                  promotion={'recommendedDefault':False,'reason':'Exploratory comparisons; additional conditions reuse test lines/plates. No independent-study or parental-HepG2 prediction validation.'},
                  limitations=old['limitations']+['The original test outcomes were examined in Stage 1; tuned comparisons on the original 72 are exploratory retesting.',
                     'Additional condition identities were frozen before new fitting/scoring, but reuse the same nine lines and two plates. This is not independent-study validation.',
                     'Centroid-residual correlation subtracts the training-only generic response. It is a custom diagnostic, not exact Systema or raw-count Virtual Cell Challenge scoring.',
                     'Strong-effect sign and top-100 recall are secondary outcome-defined summaries; they do not replace primary all-gene MSE.',
                     'Kernel ridge is a nonlinear statistical method, not a pretrained foundation model. GEARS/CPA/scGPT were not executed on incompatible pseudobulk LFC inputs.'],
                  software={'implementationSha256':B.file_hash(__file__),'numpy':np.__version__},seconds=round(time.monotonic()-started,3))
    return report,artifacts
