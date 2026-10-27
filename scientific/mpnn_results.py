"""Validate exact fixed-backbone results before importing any sequence.

No neural model or coordinates are synthesized here. Samples remain sequence
proposals; immutable source references are never labelled fresh predictions.
"""
import hashlib
import json
import math
import re

AMINO=frozenset('ACDEFGHIKLMNPQRSTVWY')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate(result,request,checkpoint_sha256):
    if not isinstance(result,dict) or type(result.get('schemaVersion')) is not int or result['schemaVersion']!=1 or result.get('execution')!='cpu':
        raise ValueError('ProteinMPNN result protocol or execution backend differs.')
    if result.get('settings')!=request or result.get('sourceSha256')!=request['sha256']:
        raise ValueError('ProteinMPNN output differs from the immutable scientific request.')
    if not isinstance(checkpoint_sha256,str) or result.get('checkpointSha256')!=checkpoint_sha256 or not re.fullmatch('[a-f0-9]{64}',checkpoint_sha256):
        raise ValueError('ProteinMPNN checkpoint identity differs from the queued model.')
    samples=result.get('candidates')
    if not isinstance(samples,list) or len(samples)!=request['count']:
        raise ValueError('ProteinMPNN returned a different number of sequence samples.')
    original=request['sequences'];constraints=request.get('constraints',{})
    layout=constraints.get('residues',{})
    for sample in samples:
        if not isinstance(sample,dict) or set(sample.get('chains',{}))!=set(original):
            raise ValueError('ProteinMPNN output lost or added a source context chain.')
        metrics=sample.get('metrics')
        if not isinstance(metrics,dict) or not metrics or any(type(v) not in (int,float) or not math.isfinite(v) for v in metrics.values()):
            raise ValueError('ProteinMPNN output has missing or nonfinite sequence-model metrics.')
        for chain,reference in original.items():
            sequence=sample['chains'][chain]
            if not isinstance(sequence,str) or len(sequence)!=len(reference) or set(sequence)-AMINO:
                raise ValueError('ProteinMPNN output changed chain length or canonical sequence identity.')
            rows=layout.get(chain)
            if rows is not None and (len(rows)!=len(reference) or ''.join(row['aminoAcid'] for row in rows)!=reference):
                raise ValueError('Prepared residue constraints differ from the source sequence.')
            for index,(before,after) in enumerate(zip(reference,sequence)):
                row=rows[index] if rows is not None else {'design':chain in request['designChains']}
                editable=chain in request['designChains'] and row['design']
                if not editable and before!=after:
                    raise ValueError('ProteinMPNN changed a fixed source residue or context chain.')
                if editable and after in constraints.get('omitAminoAcids','')+row.get('excluded',''):
                    raise ValueError('ProteinMPNN output violates an amino-acid exclusion.')
        for group in constraints.get('tiedChains',[]):
            if len({sample['chains'][chain] for chain in group})!=1:
                raise ValueError('ProteinMPNN output violates tied-chain equality.')
    return samples


def summarize(samples,job_id,request_sha256,result_sha256,design_chains):
    seen={};rows=[]
    for index,sample in enumerate(samples,1):
        sequence_identity=digest(sample['chains'])
        identity=digest({'jobId':job_id,'sample':index,'requestSha256':request_sha256,'resultSha256':result_sha256,'chains':sample['chains']})
        rows.append({'candidateId':identity,'sample':index,'chains':{ch:sample['chains'][ch] for ch in design_chains},
                     'fixedContextChains':[ch for ch in sample['chains'] if ch not in design_chains],
                     'sequenceIdentitySha256':sequence_identity,'duplicateOfSample':seen.get(sequence_identity),
                     'metrics':sample['metrics'],'metricNamespace':'ProteinMPNN sequence-model metrics',
                     'structurePredicted':False,'requiresFreshStructuralPrediction':True})
        seen.setdefault(sequence_identity,index)
    return rows
