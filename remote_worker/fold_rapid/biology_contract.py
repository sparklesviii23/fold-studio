"""Shared, data-only transformations for the biology controller and engine workers."""
import copy
import hashlib
import math
import re
from .contracts import fields, integer, canonical, digest

AA='ACDEFGHIKLMNPQRSTVWY'
BIO_ENGINES={'esmfold2_fast':'evaluate','esmfold2':'evaluate','solublempnn':'redesign','rosetta':'relax','rfdiffusion':'scaffold'}


def validate(value, mapping=None):
    fields(value,(),('parents','sequences','constraints','prediction','motif','chemistry','relax'))
    parents=value.get('parents',[])
    if not isinstance(parents,list) or len(parents)>26:raise ValueError('Supply at most 26 explicit parents.')
    ids=[]
    for parent in parents:
        fields(parent,('id','sequenceSha256','chain'))
        if not isinstance(parent['id'],str) or not re.fullmatch('[a-zA-Z0-9_-]{1,100}',parent['id']):raise ValueError('Invalid parent identity.')
        if not re.fullmatch('[a-f0-9]{64}',str(parent['sequenceSha256'])):raise ValueError('Parent sequence hash is required.')
        ids.append(parent['id'])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate parent identities.')
    sequences=value.get('sequences',{})
    if not isinstance(sequences,dict) or len(sequences)>26:raise ValueError('Explicit chain sequences must be an object.')
    for chain,sequence in sequences.items():
        if not isinstance(chain,str) or not re.fullmatch('[A-Za-z0-9_]{1,8}',chain) or not isinstance(sequence,str) or not sequence or len(sequence)>4000 or set(sequence)-set(AA):raise ValueError('Use canonical, explicitly identified protein sequences.')
        if mapping and (chain not in mapping['chains'] or len(sequence)!=len(mapping['chains'][chain]['sequence'])):raise ValueError('Replacement sequence must match the observed chain length; no indels or remapping are inferred.')
    for parent in parents:
        if parent['chain'] not in sequences or hashlib.sha256(sequences[parent['chain']].encode()).hexdigest()!=parent['sequenceSha256']:raise ValueError('Parent sequence identity mismatch.')
    constraints=value.get('constraints',{})
    if not isinstance(constraints,dict) or set(constraints)-set(sequences):raise ValueError('Constraints require an explicit sequence for each chain.')
    for chain,mask in constraints.items():
        fields(mask,('mutable',),('excluded','preferred'))
        length=len(sequences[chain]);positions=mask['mutable']
        if not isinstance(positions,list) or len(set(positions))!=len(positions) or any(type(i)is not int or not 1<=i<=length for i in positions):raise ValueError('Mutable indices are distinct 1-based sequence positions.')
        for key in ('excluded','preferred'):
            table=mask.get(key,{})
            if not isinstance(table,dict):raise ValueError('Residue restrictions must be position-keyed objects.')
            for pos,codes in table.items():
                if not isinstance(pos,str) or not pos.isdecimal() or str(int(pos))!=pos or int(pos) not in positions or not isinstance(codes,str) or not codes or set(codes)-set(AA) or len(set(codes))!=len(codes) or key=='excluded' and len(codes)==20:raise ValueError('Invalid position-specific amino-acid restriction.')
    prediction=value.get('prediction',{})
    fields(prediction,(),('loops','samplingSteps','samples','kernel','msa','lmDropout'))
    for key,default,lo,hi in [('loops',10,1,40),('samplingSteps',100,1,500),('samples',1,1,8)]:integer(prediction.get(key,default),lo,hi,key)
    if prediction.get('kernel','reference') not in ('reference','fused','cuequivariance'):raise ValueError('Unsupported official inference kernel.')
    dropout=prediction.get('lmDropout',.3)
    if type(dropout)not in(int,float) or not math.isfinite(dropout) or not 0<=dropout<=1:raise ValueError('Invalid LM dropout.')
    msas=prediction.get('msa',{})
    if not isinstance(msas,dict) or set(msas)-set(sequences):raise ValueError('MSA chains require explicit sequences.')
    for chain,msa in msas.items():
        if not isinstance(msa,str) or len(msa)>2000000:raise ValueError('A3M exceeds the per-chain limit.')
        rows=[];parts=[]
        for line in msa.splitlines():
            if line.startswith('>'):
                if parts:rows.append(''.join(parts));parts=[]
            elif line.strip():parts.append(line.strip())
        if parts:rows.append(''.join(parts))
        if not rows or rows[0].replace('-','')!=sequences[chain] or any(len(re.sub('[a-z]','',row))!=len(sequences[chain]) for row in rows):raise ValueError('A3M query and aligned column counts must match the submitted sequence exactly.')
    chemistry=value.get('chemistry',{})
    fields(chemistry,(),('modifications','bonds'))
    for mod in chemistry.get('modifications',[]):
        fields(mod,('chain','position','ccd'))
        if mod['chain'] not in sequences or not isinstance(mod['ccd'],str) or not re.fullmatch('[A-Z0-9]{1,8}',mod['ccd']):raise ValueError('Use an explicit CCD modification on a known chain.')
        integer(mod['position'],1,len(sequences[mod['chain']]),'Modified position')
    for bond in chemistry.get('bonds',[]):
        fields(bond,('chain1','position1','atomIndex1','chain2','position2','atomIndex2'))
        for side in ('1','2'):
            chain=bond['chain'+side]
            if chain not in sequences:raise ValueError('Crosslink chain missing.')
            integer(bond['position'+side],1,len(sequences[chain]),'Crosslink position');integer(bond['atomIndex'+side],0,200,'CCD heavy-atom index')
        if all(bond[k+'1']==bond[k+'2'] for k in ('chain','position','atomIndex')):raise ValueError('A crosslink cannot join an atom to itself.')
    if 'relax' in value:
        fields(value['relax'],('repeats',));integer(value['relax']['repeats'],1,5,'Relax repeats')
    if 'motif' in value:
        motif=value['motif'];fields(motif,('chain','start','end','prefix','suffix','maxRmsd'))
        for key in ('start','end'):integer(motif[key],1,100000,key)
        if motif['end']<motif['start']:raise ValueError('Motif range is reversed.')
        for key in ('prefix','suffix'):integer(motif[key],0,250,key)
        if type(motif['maxRmsd'])not in(int,float) or not math.isfinite(motif['maxRmsd']) or not 0<motif['maxRmsd']<=10:raise ValueError('Specify a positive motif preservation threshold in Å.')
        if not re.fullmatch('[A-Za-z]',str(motif['chain'])):raise ValueError('RFdiffusion contigs require a single-letter source chain.')
        if mapping:
            observed=mapping['chains'].get(motif['chain'],{}).get('residues',[])
            numbers={r['authorNumber'] for r in observed if not r['insertionCode']}
            if not set(range(motif['start'],motif['end']+1))<=numbers:raise ValueError('Motif requires complete, unambiguous observed author numbering.')
    return copy.deepcopy(value)


def validate_outputs(sequences, expected, constraints):
    """Reject a decoder violating fixed residues or exclusions before publication."""
    if set(sequences)!=set(expected):raise ValueError('Output chain identities changed.')
    for chain,original in expected.items():
        seq=sequences[chain];mask=constraints.get(chain,{'mutable':[]})
        if len(seq)!=len(original) or set(seq)-set(AA):raise ValueError('Output sequence length or representation changed.')
        for i,(a,b) in enumerate(zip(original,seq),1):
            if i not in mask['mutable'] and a!=b:raise ValueError('A fixed residue changed.')
            if i in mask['mutable'] and b in mask.get('excluded',{}).get(str(i),''):raise ValueError('An excluded residue was sampled.')


def pareto(rows, objectives, limits):
    """No aggregate score; missing, nonfinite or hard-limit failures are retained."""
    if not isinstance(objectives,dict) or not objectives or any(v not in ('min','max') for v in objectives.values()):raise ValueError('State min/max direction for every objective.')
    result=[]
    for row in rows:
        metrics=row['metrics'];reasons=[]
        for key in set(objectives)|set(limits):
            if key not in metrics or type(metrics[key])not in(int,float) or not math.isfinite(metrics[key]):reasons.append('missing_or_nonfinite:'+key)
            elif key in limits:
                low,high=limits[key]
                if low is not None and metrics[key]<low or high is not None and metrics[key]>high:reasons.append('hard_limit:'+key)
        result.append({**row,'eligible':not reasons,'reasons':reasons,'dominatedBy':[]})
    for row in result:
        if not row['eligible']:continue
        for other in result:
            if other['id']==row['id'] or not other['eligible']:continue
            differences=[(other['metrics'][k]-row['metrics'][k])*(1 if direction=='max' else -1) for k,direction in objectives.items()]
            if all(d>=0 for d in differences) and any(d>0 for d in differences):row['dominatedBy'].append(other['id'])
    return result
