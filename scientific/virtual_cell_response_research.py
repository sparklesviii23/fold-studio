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
