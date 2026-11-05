"""Prespecified genomic panel and locus-level evaluation, independent of inference.

Select on annotations/known RNA strata, never on candidate prediction scores.
Training/validation examples are a separate illustrative cohort. All reporting
keeps original ENCODE signal distinct from the authors' processed training targets.
"""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request
import re

import numpy as np
from scipy.stats import spearmanr

from virtual_cell_benchmarks import file_hash, _hash

TRACKS = [(6226, 'ENCFF065PJM', 'CVCL_0027', 'RNA:HepG2'),
          (1303, 'ENCFF136DBS', 'CVCL_0027', 'DNASE:HepG2'),
          (6122, 'ENCFF980ZHM', 'CVCL_0004', 'RNA:K562')]
SCHEMA = 'fold.borzoi.panel/1'


def plan(library, reference, n=100, seed=29, source_run='af2b5ce1548e4fac95abd2781049c7c9'):
    if not 10 <= n <= 200: raise ValueError('Panel size must be 10–200.')
    reference = Path(reference)
    with gzip.open(reference/'sequences_human.bed.gz', 'rt') as f:
        regions = [(c, int(s), int(e), fold) for c,s,e,fold in map(str.split, f)]
    dbpath = Path(library)/'virtualcell/data/encode_hepg2/transcripts.sqlite'
    db = sqlite3.connect(f'file:{dbpath}?mode=ro', uri=True)
    genes = {}
    for name, raw in db.execute('SELECT gene_name,data FROM tx ORDER BY gene_name'):
        t = json.loads(raw)
        if t['chrom'] not in {'chr'+str(i) for i in range(1,23)}: continue
        r = genes.setdefault(name, {'symbol': name, 'geneId': t['gene_id'], 'chromosome': t['chrom'], 'start': t['start']-1,
                                   'end': t['end'], 'strand': t['strand'], 'isoforms': 0, 'tpm': 0.})
        if r['chromosome'] != t['chrom']: continue
        r['start'] = min(r['start'], t['start']-1); r['end'] = max(r['end'], t['end']); r['isoforms'] += 1
        reps = list(t.get('rsem', {}).values())
        if reps: r['tpm'] += sum(x['TPM'] for x in reps)/len(reps)
    db.close()
    by_chrom = {}
    for reg in regions: by_chrom.setdefault(reg[0], []).append(reg)
    candidates = []
    for g in genes.values():
        compatible = [r for r in by_chrom.get(g['chromosome'], []) if r[1] <= (g['start']+g['end'])//2 < r[2]]
        if not compatible: continue
        compatible.sort(key=lambda r: (0 if r[1]<=g['start'] and g['end']<=r[2] else 1, _hash([seed,list(r)])))
        r = compatible[0]; item = {**g, 'length':g['end']-g['start'], 'region':list(r[:3]), 'fold':r[3],
                                  'inputStart':r[1]-163840, 'cohort':'heldout' if r[3]=='fold3' else 'illustrative'}
        if item['inputStart'] < 0: continue
        item['expressionStratum'] = 'low' if g['tpm']<1 else ('medium' if g['tpm']<30 else 'high')
        item['lengthStratum'] = 'short' if item['length']<10000 else ('medium' if item['length']<50000 else 'long')
        candidates.append(item)
    # Prespecified technical anchor uses the exact Stage 1 window.
    anchor = next(c for c in candidates if c['symbol']=='FABP1')
    anchor.update(region=['chr2',88023337,88219945], inputStart=87859497, fold='fold3', cohort='heldout')
    chosen = [anchor]; seen_genes = {'FABP1'}
    strata = sorted({(c['expressionStratum'],c['lengthStratum']) for c in candidates})
    queues = {s: sorted([c for c in candidates if c['cohort']=='heldout' and (c['expressionStratum'],c['lengthStratum'])==s], key=lambda c:_hash([seed,c['symbol'],c['region']])) for s in strata}
    def independent(c):
        return all(c['chromosome']!=d['chromosome'] or c['inputStart']+524288<=d['inputStart'] or d['inputStart']+524288<=c['inputStart'] for d in chosen)
    while len(chosen)<n:
        added = False
        for s in strata:
            while queues[s]:
                c = queues[s].pop(0)
                if c['symbol'] not in seen_genes and independent(c):
                    chosen.append(c); seen_genes.add(c['symbol']); added=True; break
            if len(chosen)==n: break
        if not added: raise ValueError('Insufficient independent annotation-matched test loci.')
    examples = [next(c for c in candidates if c['symbol']==g) for g in ('ALB','ANGPTL3','APOA1','GAPDH')]
    tracks = list(csv.DictReader((reference/'targets_human.txt').open(), delimiter='\t'))
    track_rows=[]
    for index,acc,rrid,description in TRACKS:
        row=tracks[index]
        if row['description'] != description or row['identifier'].rstrip('+-')!=acc: raise ValueError('Track metadata mismatch.')
        track_rows.append({'index':index,'accession':acc,'cellosaurus':rrid,'metadata':row})
    result={'schema':SCHEMA,'seed':seed,'loci':chosen+examples,'testLoci':n,'illustrativeLoci':len(examples),'tracks':track_rows,
            'selection':'Round-robin expression/length strata, SHA-256 ordering; nonoverlapping 524,288-bp test inputs; FABP1 prespecified anchor. Illustrative genes kept separate.',
            'overlap':'All reference assays are training-related; fold3 is genomic holdout, not independent-study validation.',
            'sources':{'annotationsSha256':file_hash(dbpath),'splitsSha256':file_hash(reference/'sequences_human.bed.gz'),'targetsSha256':file_hash(reference/'targets_human.txt')},
            'reproduction':{'inputs':{'chromosome':'chr2','start':87859497,'track':6226},'sequenceSha256':'a4e613b77ef4074c7034cca690eb23afefe8edeab18a114e6d46926d8937d580','rtol':1e-4,'atol':1e-6}}
    from virtual_cell_regulatory import get, _task, _artifact
    previous=get(library,source_run,'CVCL_0027')
    task,folder=_task(library,source_run)
    if not previous.get('supported') or task.get('inputs')!=result['reproduction']['inputs'] or previous['reference']['sequenceSha256']!=result['reproduction']['sequenceSha256']: raise ValueError('The exact Stage 1 reproduction source is required.')
    old_csv=_artifact(task,folder,'regulatory-track.csv',5_000_000)
    result['reproduction'].update(sourceRun=source_run,artifactSha256=hashlib.sha256(old_csv).hexdigest())
    result['sha256']=_hash(result); return result


def score(predicted, observed, minimum=20):
    predicted,observed=np.asarray(predicted),np.asarray(observed)
    if predicted.shape!=observed.shape: raise ValueError('Prediction/reference shape mismatch.')
    valid=np.isfinite(predicted)&np.isfinite(observed)
    if (np.asarray(predicted)[valid]<0).any() or (np.asarray(observed)[valid]<0).any(): raise ValueError('Negative coverage is incompatible with these assays.')
    if valid.sum()<minimum: return {'status':'insufficient_reference','n':int(valid.sum()),'pearson':None,'spearman':None}
    a,b=np.asarray(predicted[valid],float),np.asarray(observed[valid],float)
    if np.ptp(a)==0 or np.ptp(b)==0: return {'status':'constant_signal','n':len(a),'pearson':None,'spearman':None}
    # Correlations are associations across differing assay transforms, not count calibration.
    pearson=float(np.corrcoef(np.log1p(a),np.log1p(b))[0,1]); rank=float(spearmanr(a,b).statistic)
    if not np.isfinite(pearson) or not np.isfinite(rank): return {'status':'numerically_undefined','n':len(a),'pearson':None,'spearman':None}
    return {'status':'scored','n':len(a),'pearson':pearson,'spearman':rank}


def aggregate(rows, seed=29):
    good=[r for r in rows if r['status']=='scored']; rng=np.random.default_rng(seed)
    result={'attempted':len(rows),'scored':len(good),'failed':len(rows)-len(good)}
    for metric in ('pearson','spearman'):
        values=np.array([r[metric] for r in good],float)
        samples=[float(rng.choice(values,len(values),replace=True).mean()) for _ in range(2000)] if len(values)>=3 else []
        result[metric]={'mean':float(values.mean()) if len(values) else None,'ci95':np.quantile(samples,[.025,.975]).tolist() if samples else None}
    return result


def paired_comparison(rows,track,baseline,metric,seed=29):
    lookup={(r['symbol'],r['model']):r for r in rows if r['cohort']=='heldout' and r['track']==track and r['status']=='scored'}
    pairs=[(r,lookup[(symbol,baseline)]) for (symbol,model),r in lookup.items() if model=='ensemble' and (symbol,baseline) in lookup]
    delta=np.array([a[metric]-b[metric] for a,b in pairs]); rng=np.random.default_rng(seed)
    samples=[float(rng.choice(delta,len(delta),replace=True).mean()) for _ in range(2000)] if len(delta)>=3 else []
    return {'n':len(delta),'meanDifference':float(delta.mean()) if len(delta) else None,
            'ci95':np.quantile(samples,[.025,.975]).tolist() if samples else None,'direction':'positive favours ensemble','baseline':baseline}


def prepare_reference(panel,folder):
    import pyBigWig
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'reference.json'; arrays=folder/'observed.npz'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['panelSha256']!=panel['sha256'] or file_hash(arrays)!=old['arraySha256']: raise ValueError('Reference cache identity mismatch.')
        return old
    values={}; metadata=[]
    for track in panel['tracks']:
        acc=track['accession']; url=f'https://www.encodeproject.org/files/{acc}/?format=json'
        with urllib.request.urlopen(url,timeout=60) as response: raw=response.read(8_000_001)
        if len(raw)>8_000_000: raise ValueError('Metadata exceeds bound.')
        meta=json.loads(raw); (folder/f'{acc}.json').write_bytes(raw)
        if meta.get('assembly')!='GRCh38' or meta.get('accession')!=acc or meta.get('file_format')!='bigWig' or 'Cellosaurus:'+track['cellosaurus'] not in meta.get('biosample_ontology',{}).get('dbxrefs',[]): raise ValueError('ENCODE assay/context identity mismatch.')
        if track['metadata']['description'].startswith('RNA:') and meta.get('output_type')!='plus strand signal of unique reads': raise ValueError('RNA strand mismatch.')
        canonical=f'https://www.encodeproject.org/files/{acc}/@@download/{acc}.bigWig'
        request=urllib.request.Request(canonical,headers={'Range':'bytes=0-63'})
        with urllib.request.urlopen(request,timeout=90) as response: resolved=response.geturl(); response.read(64)
        bw=pyBigWig.open(resolved)
        try:
            for i,locus in enumerate(panel['loci']):
                raw_values=np.asarray(bw.values(*locus['region'],numpy=True),float).reshape(6144,32)
                valid=np.isfinite(raw_values).all(axis=1); signal=np.full(6144,np.nan)
                signal[valid]=(raw_values[valid].mean(axis=1) if track['metadata']['sum_stat']=='mean' else raw_values[valid].sum(axis=1))
                values[f'locus_{i}_track_{track["index"]}']=signal
                if i%25==0: print(f'[reference] {acc} {i+1}/{len(panel["loci"])}',flush=True)
        finally: bw.close()
        metadata.append({'index':track['index'],'accession':acc,'source':canonical,'assembly':meta['assembly'],'cellosaurus':track['cellosaurus'],
                         'outputType':meta['output_type'],'publishedMd5':meta['md5sum'],'metadataSha256':hashlib.sha256(raw).hexdigest(),
                         'unit':('mean' if track['metadata']['sum_stat']=='mean' else 'sum')+' of original ENCODE '+meta['output_type']+' over 32 fully covered bases',
                         'integrity':'Remote byte-range extraction; full bigWig MD5 not independently verified.'})
    np.savez_compressed(arrays,**values)
    result={'schema':'fold.borzoi.panel-reference/1','panelSha256':panel['sha256'],'tracks':metadata,'arraySha256':file_hash(arrays),
            'missingness':'Uncovered bins are NaN, never replaced with zero.','transforms':'Original ENCODE signal, not author-processed .w5 target; count-scale errors are not supported.'}
    manifest.write_text(json.dumps(result,indent=1)); return result


def evaluate(root,run,reference):
    from virtual_cell_regulatory import _artifact
    if not re.fullmatch('[a-f0-9]{32}',str(run)): raise ValueError('Invalid job id.')
    job=Path(root)/'gpu_tasks'/run; task=json.loads((job/'task.json').read_text())
    if task.get('id')!=run or task.get('recipe')!='bio_borzoi_panel' or task.get('state')!='done' or task.get('fetchError'): raise ValueError('A completed retrieved panel job is required.')
    panel=json.loads(_artifact(task,job,'panel.json',200000)); receipt=json.loads(_artifact(task,job,'panel-inference.json',2000000))
    body={k:v for k,v in panel.items() if k!='sha256'}
    if _hash(body)!=panel['sha256'] or receipt['panelSha256']!=panel['sha256'] or receipt.get('reproductionPassed') is not True: raise ValueError('Panel/reproduction identity failed.')
    sources=[]
    for name in ['predictions-f0.npz','predictions-f1.npz']:
        _artifact(task,job,name,100*1024**2)
        sources.append({'path':name,'sha256':file_hash(job/'outputs'/name)})
    ref=prepare_reference(panel,reference); reference=Path(reference)
    rows=[]; gene_results=[]
    with np.load(job/'outputs/predictions-f0.npz',allow_pickle=False) as f0, np.load(job/'outputs/predictions-f1.npz',allow_pickle=False) as f1, np.load(reference/'observed.npz',allow_pickle=False) as observed:
        for i,locus in enumerate(panel['loci']):
            a,b=f0[f'locus_{i}'],f1[f'locus_{i}']
            if a.shape!=(6144,len(panel['tracks'])) or b.shape!=a.shape or not np.isfinite(a).all() or not np.isfinite(b).all(): raise ValueError('Panel array shape or values invalid.')
            for ti,track in enumerate(panel['tracks']):
                obs=observed[f'locus_{i}_track_{track["index"]}']; models={'f0':a[:,ti].astype(float),'f1':b[:,ti].astype(float),'ensemble':(a[:,ti].astype(float)+b[:,ti].astype(float))/2}
                ms={key:score(pred,obs) for key,pred in models.items()}
                for key,metric in ms.items(): rows.append({**metric,'model':key,'symbol':locus['symbol'],'track':track['index'],'cohort':locus['cohort'],'expressionStratum':locus['expressionStratum'],'lengthStratum':locus['lengthStratum']})
                preview=[]
                for start in range(0,6144,16):
                    block=obs[start:start+16]; valid=np.isfinite(block)
                    preview.append({'start':locus['region'][1]+start*32,'end':locus['region'][1]+(start+16)*32,
                                    **{key:float(p[start:start+16].mean()) for key,p in models.items()},'observed':float(block[valid].mean()) if valid.any() else None})
                gene_results.append({'symbol':locus['symbol'],'geneId':locus['geneId'],'region':locus['region'],'fold':locus['fold'],'cohort':locus['cohort'],
                                     'fullGeneCovered':locus['region'][1]<=locus['start'] and locus['end']<=locus['region'][2],
                                     'cellosaurus':track['cellosaurus'],'trackIndex':track['index'],'trackDescription':track['metadata']['description'],
                                     'trackIdentifier':track['metadata']['identifier'],'observedUnit':ref['tracks'][ti]['unit'],'metrics':ms,'preview':preview,
                                     'checkpointProvenance':receipt['checkpoints'],'replicateMeanAbsoluteDisagreement':float(np.mean(np.abs(models['f0']-models['f1']))),
                                     'interpretation':'Assay reference-DNA prediction; not a protein-abundance estimate or a complete cell state.'})
    summaries={}
    for track in panel['tracks']:
        tid=str(track['index']); summaries[tid]={}
        for model in ['f0','f1','ensemble']:
            chosen=[r for r in rows if r['cohort']=='heldout' and r['track']==track['index'] and r['model']==model]
            summaries[tid][model]=aggregate(chosen,panel['seed'])
    groups={f'{track["index"]}:{model}:{axis}:{level}':aggregate([r for r in rows if r['cohort']=='heldout' and r['track']==track['index'] and r['model']==model and r[axis]==level],panel['seed'])
            for track in panel['tracks'] for model in ['f0','f1','ensemble'] for axis in ['expressionStratum','lengthStratum'] for level in sorted({r[axis] for r in rows})}
    result={'schema':'fold.borzoi.panel-evaluation/1','run':run,'panelSha256':panel['sha256'],'testLoci':panel['testLoci'],'illustrativeLoci':panel['illustrativeLoci'],
            'tracks':panel['tracks'],'checkpoints':receipt['checkpoints'],'summary':summaries,'strata':groups,'perLocus':rows,'geneResults':gene_results,'artifacts':sources,
            'reference':ref,'inferenceSeconds':receipt['seconds'],'replicateSeconds':receipt['replicateSeconds'],'sequenceProvenance':receipt['loci'],
            'ensemblePairedComparisons':{f'{t["index"]}:{baseline}:{metric}':paired_comparison(rows,t['index'],baseline,metric,panel['seed']) for t in panel['tracks'] for baseline in ('f0','f1') for metric in ('pearson','spearman')},
            'sourceRevision':receipt['sourceRevision'],'baskervilleRevision':receipt['baskervilleRevision'],
            'metricDefinitions':{'pearson':'Pearson correlation of log1p(raw prediction) and log1p(original ENCODE signal).','spearman':'Rank correlation across fully covered bins.',
                                 'uncertainty':'2,000 locus bootstrap draws, separately per track and model. Adjacent bins are not independent replicates.'},
            'limitations':['Same-source assays included in model training; fold3 is held-out genomic sequence, not independent-study validation.',
                           'Original ENCODE coverage differs from author-processed targets. Calibrated MAE/MSE and transcript abundance are not established.',
                           'Low-coverage and constant-signal loci remain explicit failures, not silently omitted from attempted counts.',
                           'Two-replicate disagreement is not calibrated uncertainty. Tissue/context generalisation beyond the selected assays is not established.',
                           'Annotation/expression strata use the installed HepG2 RNA reference; K-562 results are not expression-stratified by K-562 measurements.'],
            'software':{'evaluationImplementationSha256':file_hash(__file__),'numpy':np.__version__}}
    result['sha256']=_hash(result); folder=Path(root)/'virtualcell/borzoi-panels'/run; folder.mkdir(parents=True,exist_ok=True)
    (folder/'evaluation.json').write_text(json.dumps(result,indent=1,allow_nan=False)); return result


def load(root,run):
    if not re.fullmatch('[a-f0-9]{32}',str(run)): raise ValueError('Invalid panel identifier.')
    path=Path(root)/'virtualcell/borzoi-panels'/run/'evaluation.json'
    report=json.loads(path.read_text()); digest=report.pop('sha256',None)
    if report.get('schema')!='fold.borzoi.panel-evaluation/1' or report.get('run')!=run or _hash(report)!=digest: raise ValueError('Borzoi panel evaluation checksum mismatch.')
    artifacts=report.get('artifacts',[])
    if sorted(a.get('path','') for a in artifacts)!=['predictions-f0.npz','predictions-f1.npz']: raise ValueError('Panel prediction artifact manifest incomplete.')
    for artifact in artifacts:
        if file_hash(Path(root)/'gpu_tasks'/run/'outputs'/artifact['path'])!=artifact['sha256']: raise ValueError('Panel prediction artifact integrity failed.')
    return {**report,'sha256':digest}


def listing(root):
    folder=Path(root)/'virtualcell/borzoi-panels'
    return [{k:r[k] for k in ('run','testLoci','illustrativeLoci','tracks','summary','limitations','inferenceSeconds')}
            for path in sorted(folder.glob('*/evaluation.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]
            for r in [load(root,path.parent.name)]]


def for_gene(root,symbol,cellosaurus,region,gene_id=None):
    """Read only completed, checksummed panel records matching this exact gene/context."""
    folder=Path(root)/'virtualcell/borzoi-panels'; results=[]
    for path in sorted(folder.glob('*/evaluation.json')) if folder.exists() else []:
        report=load(root,path.parent.name)
        for item in report.get('geneResults',[]):
            if (item['symbol']==symbol and item['cellosaurus']==cellosaurus and item['region'][0]==region['chromosome']
                and item['region'][1]<region['end'] and item['region'][2]>region['start']
                and (not gene_id or item['geneId'].split('.')[0]==gene_id.split('.')[0])):
                results.append({'provider':'bio_borzoi_panel','panel':path.parent.name,**item})
    return results
