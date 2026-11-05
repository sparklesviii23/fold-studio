"""Official-model batch inference, executed inside the existing approved Modal job.

The enclosing recipe supplies BASE_RUNNER (the shared Biological Models adapter).
Reproduces the old FABP1 inference first. A failed numerical gate stops the panel.
"""
import csv
import base64
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import zlib

import numpy as np
import tensorflow as tf
from baskerville import seqnn


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for part in iter(lambda:f.read(8<<20),b''): h.update(part)
    return h.hexdigest()


def decode_panel_input(inputs,name='panel.json.gz.b64'):
    files=inputs.get('files',{})
    if 'panel.json.gz.b64' not in files or set(files)-{'panel.json.gz.b64','preflight.json.gz.b64','verification.json.gz.b64'}: raise ValueError('Unexpected panel input files.')
    compressed=base64.b64decode(files[name],validate=True)
    if len(compressed)>24000: raise ValueError('Compressed panel exceeds transport bound.')
    decoder=zlib.decompressobj(31); raw=decoder.decompress(compressed,200001)
    if len(raw)>200000 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail: raise ValueError('Invalid or oversized compressed panel.')
    return raw.decode('utf-8')


def sequence(chrom,start,expected_sha=None):
    if expected_sha:
        path=Path('/cache/models/predictive-cell-reference/verified')/(expected_sha+'.txt')
        dna=path.read_text()
        if len(dna)!=524288 or set(dna)-set('ACGTN') or hashlib.sha256(dna.encode()).hexdigest()!=expected_sha: raise ValueError('Staged reference integrity failed.')
        return dna,'verified content-addressed reference staged before GPU allocation'
    cache=Path('/cache/models/predictive-cell-reference/hg38'); cache.mkdir(parents=True,exist_ok=True)
    path=cache/f'{chrom}-{start}-524288.txt'
    url='https://api.genome.ucsc.edu/getData/sequence?'+urllib.parse.urlencode({'genome':'hg38','chrom':chrom,'start':start,'end':start+524288})
    if path.exists(): dna=path.read_text()
    else:
        with urllib.request.urlopen(url,timeout=120) as r: raw=r.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Oversized genomic reference response.')
        dna=json.loads(raw)['dna'].upper()
        if len(dna)!=524288 or set(dna)-set('ACGTN'): raise ValueError('Invalid reference sequence; no padding.')
        temp=path.with_suffix('.'+os.environ['FOLD_TASK_ID']+'.partial'); temp.write_text(dna); temp.replace(path)
    if len(dna)!=524288 or set(dna)-set('ACGTN'): raise ValueError('Invalid cached genomic sequence.')
    return dna,url


def main():
    started=time.monotonic(); raw=decode_panel_input(json.loads(os.environ['FOLD_INPUT'])); panel=json.loads(raw)
    if panel['schema']!='fold.borzoi.panel/1' or panel['testLoci']!=100 or len(panel['loci'])>110: raise ValueError('Unsupported panel manifest.')
    digest=panel.pop('sha256')
    if hashlib.sha256(json.dumps(panel,sort_keys=True,allow_nan=False).encode()).hexdigest()!=digest: raise ValueError('Panel checksum mismatch.')
    panel['sha256']=digest
    preflight=json.loads(decode_panel_input(json.loads(os.environ['FOLD_INPUT']),'preflight.json.gz.b64'))
    preflight_sha=preflight.pop('sha256')
    if hashlib.sha256(json.dumps(preflight,sort_keys=True,allow_nan=False).encode()).hexdigest()!=preflight_sha or preflight['panelSha256']!=digest or len(preflight['loci'])!=len(panel['loci']): raise ValueError('Sequence preflight identity failed.')
    # Check every staged input before constructing the model; no reference API requests on paid GPU time.
    seqs=[]; provenance=[]
    for i,(locus,ref) in enumerate(zip(panel['loci'],preflight['loci'])):
        if (ref['index'],ref['symbol'],ref['chromosome'],ref['start'],ref['end'])!=(i,locus['symbol'],locus['chromosome'],locus['inputStart'],locus['inputStart']+524288): raise ValueError('Preflight locus coordinates changed.')
        if ref['status']=='unsupported_input_window':
            seqs.append(None); provenance.append(ref); continue
        if ref['status']!='ready': raise ValueError('An unresolved reference cannot be submitted for inference.')
        dna,_=sequence(locus['chromosome'],locus['inputStart'],ref['sequenceSha256']); seqs.append(dna); provenance.append(ref)
    out=Path('/cache/out')/os.environ['FOLD_TASK_ID']; out.mkdir(parents=True,exist_ok=True)
    (out/'panel.json').write_text(raw)
    base={"__name__":"fold_shared_borzoi_runner"}; exec(BASE_RUNNER,base)
    gate=panel['reproduction']; old=Path('/cache/out')/gate['sourceRun']/'regulatory-track.csv'
    if sha(old)!=gate['artifactSha256']: raise ValueError('Prior remote prediction artifact changed or is missing.')
    old_values=np.array([float(r['raw_model_value']) for r in csv.DictReader(old.open())])
    first=out/'reproduction'; first.mkdir(exist_ok=True)
    portable='verification.json.gz.b64' in json.loads(os.environ['FOLD_INPUT'])['files']
    policy=json.loads(decode_panel_input(json.loads(os.environ['FOLD_INPUT']),'verification.json.gz.b64')) if portable else None
    if portable:
        historical=Path('/cache/out')/policy['historicalRun']/'reproduction.json'
        if policy.get('schema')!='fold.borzoi.portable-verification/1' or sha(historical)!=policy['historicalReceiptSha256']:raise ValueError('Historical exact-reproduction receipt identity failed.')
        prior=json.loads(historical.read_text())
        if prior.get('passed') is not True or prior['maxAbsoluteDifference']!=0 or prior['checkpointSha256']!=policy['checkpointSha256'] or prior['result']['reference']['sequenceSha256']!=gate['sequenceSha256']:raise ValueError('Historical exact reproduction is not established.')
    anchor=next(dna for locus,dna in zip(panel['loci'],seqs) if locus['symbol']=='FABP1')
    repeat=base['borzoi'](gate['inputs'],first,anchor)
    new_values=np.array([float(r['raw_model_value']) for r in csv.DictReader((first/'regulatory-track.csv').open())])
    passed=repeat['reference']['sequenceSha256']==gate['sequenceSha256'] and old_values.shape==new_values.shape and np.allclose(old_values,new_values,rtol=gate['rtol'],atol=gate['atol'])
    repro={'passed':bool(passed),'bins':len(new_values),'priorBins':len(old_values),'rtol':gate['rtol'],'atol':gate['atol'],'maxAbsoluteDifference':float(np.max(np.abs(old_values-new_values))) if old_values.shape==new_values.shape else None,
           'checkpointSha256':repeat['checkpointSha256'],'result':repeat}
    (out/'reproduction.json').write_text(json.dumps(repro,indent=1,allow_nan=False))
    if portable:
        # Retain the original cross-device check as a separate, unchanged diagnostic.
        second=out/'same-device-repeat';second.mkdir(exist_ok=True)
        tf.keras.backend.clear_session();gc.collect()
        again=base['borzoi'](gate['inputs'],second,anchor)
        again_values=np.array([float(r['raw_model_value']) for r in csv.DictReader((second/'regulatory-track.csv').open())])
        same=again['checkpointSha256']==repeat['checkpointSha256'] and again['reference']['sequenceSha256']==repeat['reference']['sequenceSha256'] and np.allclose(new_values,again_values,rtol=gate['rtol'],atol=gate['atol'])
        verification={'schema':policy['schema'],'historicalExactReproduction':True,'historicalRun':policy['historicalRun'],'crossDeviceOriginalTolerancePassed':bool(passed),'sameDeviceOriginalTolerancePassed':bool(same),'rtol':gate['rtol'],'atol':gate['atol'],'sameDeviceMaxAbsoluteDifference':float(np.max(np.abs(new_values-again_values))),'policy':policy}
        (out/'verification.json').write_text(json.dumps(verification,indent=1,allow_nan=False))
        if not same:raise ValueError('Same-device repeatability failed; panel not executed.')
        print('[fold] historical exact reproduction verified; same-device repeatability passed; cross-device diagnostic retained',flush=True)
    elif not passed: raise ValueError('Fresh inference reproduction gate FAILED; panel not executed.')
    else: print('[fold] fresh inference reproduction passed',flush=True)
    tf.keras.backend.clear_session(); gc.collect()
    params=json.loads(Path('/opt/borzoi/examples/params_pred.json').read_text())
    indices=[t['index'] for t in panel['tracks']]
    targets=list(csv.DictReader(open('/opt/borzoi/examples/targets_human.txt'),delimiter='\t'))
    for track in panel['tracks']:
        if targets[track['index']]!=track['metadata']: raise ValueError('Track catalogue identity mismatch.')
    with gzip.open(out/'reference-sequences.fasta.gz','wt') as f:
        for locus,dna in zip(panel['loci'],seqs):
            if dna is not None: f.write(f'>{locus["symbol"]} hg38 {locus["chromosome"]}:{locus["inputStart"]}-{locus["inputStart"]+524288} zero-based-half-open\n{dna}\n')
    checkpoints=[]; timings={}
    for replicate in (0,1):
        tf.keras.backend.clear_session(); gc.collect(); t0=time.monotonic()
        weight=base['borzoi_checkpoint']('/cache/models',replicate)
        model=seqnn.SeqNN(params['model']); model.restore(str(weight),0); model.build_slice(indices)
        predictions={}
        for i,(locus,dna) in enumerate(zip(panel['loci'],seqs)):
            if dna is None:
                print(f'[fold] replicate {replicate} locus {i+1}/{len(panel["loci"])} {locus["symbol"]}: unsupported input window',flush=True); continue
            encoded=np.frombuffer(dna.encode(),dtype=np.uint8); onehot=np.stack([encoded==b for b in b'ACGT'],axis=-1).astype(np.float32)
            pred=np.asarray(model(onehot[None,...]))
            if pred.shape!=(1,16352,len(indices)) or not np.isfinite(pred).all() or (pred<0).any(): raise ValueError('Invalid batch model output.')
            predictions[f'locus_{i}']=pred[0,5104:11248,:].astype(np.float32)
            print(f'[fold] replicate {replicate} locus {i+1}/{len(panel["loci"])} {locus["symbol"]}',flush=True)
        np.savez_compressed(out/f'predictions-f{replicate}.npz',**predictions)
        checkpoints.append({'replicate':replicate,'sha256':sha(weight),'source':f'https://storage.googleapis.com/seqnn-share/borzoi/f{replicate}/model0_best.h5'})
        timings[str(replicate)]=time.monotonic()-t0; del model,predictions
    receipt={'schema':'fold.borzoi.panel-inference/1','panelSha256':digest,'checkpoints':checkpoints,'loci':provenance,'tracks':panel['tracks'],
             'rawOutputBins':16352,'retainedBins':6144,'binSize':32,'retainedOffsetFromInput':163840,'coordinateConvention':'zero-based half-open',
             'predictedUnit':'raw model assay transform; use each track metadata','reproductionPassed':True,'seconds':time.monotonic()-started,'replicateSeconds':timings,
             'sequencePreflightSha256':preflight_sha,
             'verificationPolicy':policy,'crossDeviceOriginalTolerancePassed':bool(passed),
             'sourceRevision':os.environ['FOLD_BORZOI_REVISION'],'baskervilleRevision':os.environ['FOLD_BASKERVILLE_REVISION'],'uncertainty':'Two-replicate disagreement is not calibrated prediction uncertainty.'}
    (out/'panel-inference.json').write_text(json.dumps(receipt,indent=1,allow_nan=False))
    manifest=[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()]
    (out/'artifacts.json').write_text(json.dumps(manifest,indent=1)); print('[fold] panel inference complete',flush=True)


if __name__=='__main__': main()
