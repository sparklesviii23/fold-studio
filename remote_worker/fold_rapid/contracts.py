"""Bounded, versioned contracts. No executable commands or caller-owned paths."""
import base64
import hashlib
import json
import math
import re

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(4*1024**2):value.update(block)
    return value.hexdigest()

def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}].')
    return value

def fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise ValueError('Invalid fields: expected '+', '.join(required)+'.')
    canonical(value)  # Reject NaN/Infinity recursively before persistence.

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('Invalid job identifier.')
    return value

def target_bytes(target):
    fields(target, ('format', 'contentBase64', 'sha256', 'chains'), ('label',))
    if target['format'] not in ('pdb', 'cif') or not isinstance(target['contentBase64'], str) or len(target['contentBase64'])>3_000_000:
        raise ValueError('Target must be a bounded PDB/mmCIF snapshot.')
    raw=base64.b64decode(target['contentBase64'], validate=True)
    if not raw or len(raw)>2_000_000 or digest(raw)!=target['sha256']:
        raise ValueError('Target snapshot checksum or size is invalid.')
    chains=target['chains']
    if not isinstance(chains,list) or not chains or len(set(chains))!=len(chains) or any(not isinstance(c,str) or not re.fullmatch('[A-Za-z0-9_]{1,8}',c) for c in chains):
        raise ValueError('Explicit unique target chain identities are required.')
    return raw

def manifest(value):
    fields(value, ('schemaVersion','engine','operation','target','design','seed','budget','mode'), ('settings','parentCandidates','biology'))
    if value['schemaVersion']!=1 or type(value['schemaVersion']) is not int:
        raise ValueError('Unsupported scientific manifest version.')
    allowed={'bindcraft2':('design',), 'boltzgen':('design',), 'proteinmpnn':('redesign',), 'af2_multimer':('evaluate',), 'structure_screen':('screen',)}
    from .biology_contract import BIO_ENGINES,validate as biology_validate
    allowed.update({name:(operation,) for name,operation in BIO_ENGINES.items()})
    if value['engine'] not in allowed or value['operation'] not in allowed[value['engine']]:
        raise ValueError('Unsupported engine operation; no replacement engine will be used.')
    if value['mode'] not in ('reference','rapid','exploration','precision'):
        raise ValueError('Unknown scheduling mode.')
    fields(value['budget'], ('seconds',), ('maxCost','hourlyPrice','gpuMemoryMiB'))
    integer(value['budget']['seconds'],1,86400,'Runtime limit')
    for k in ('maxCost','hourlyPrice'):
        if k in value['budget'] and (type(value['budget'][k]) not in (int,float) or not math.isfinite(value['budget'][k]) or value['budget'][k]<=0):
            raise ValueError('Invalid spending limit or hourly price.')
    if 'maxCost' in value['budget'] and 'hourlyPrice' not in value['budget']:
        raise ValueError('A verified hourly price is required to enforce a spending estimate.')
    if 'gpuMemoryMiB' in value['budget']:integer(value['budget']['gpuMemoryMiB'],512,200000,'GPU memory ceiling')
    integer(value['seed'],0,2**31-1,'Random seed')
    fields(value['design'], ('modality','lengths','count','attempts'), ('hotspots','designChains','temperature'))
    d=value['design']
    if d['modality'] not in ('peptide','binder'):raise ValueError('Only peptide and binder CUDA reference contracts are implemented.')
    if not isinstance(d['lengths'],list) or not 1<=len(d['lengths'])<=2:raise ValueError('Supply one binder length or inclusive bounds.')
    for length in d['lengths']:integer(length,4,500,'Binder length')
    if d['lengths']!=sorted(d['lengths']):raise ValueError('Length bounds must be ordered.')
    integer(d['count'],1,10000,'Candidate count');integer(d['attempts'],1,100000,'Attempt count')
    if not isinstance(value.get('settings',{}),dict):raise ValueError('Scientific settings must be an object.')
    # Scientific loss/filter overrides are allowed. Paths, launch topology and
    # callbacks are worker-owned, not arbitrary remote execution inputs.
    forbidden={'targets','target','target_path','project_folder','parameters','redesign_weights','resume','campaign_seed','binder_lengths','number_of_final_designs','max_trajectories','modality','core','num_gpus','gpu_ids'}
    if set(value.get('settings',{})) & forbidden:raise ValueError('Worker-owned scientific setting cannot be overridden.')
    for key in value.get('settings',{}):
        if not re.fullmatch('[a-z][a-z0-9_]*',key) or any(part in key for part in ('path','folder','scaffold','callback','command','script','parameter_sweep')):raise ValueError('Invalid or filesystem-owned scientific setting name.')
    dchains=d.get('designChains',[])
    if not isinstance(dchains,list) or len(set(dchains))!=len(dchains) or any(not isinstance(ch,str) or not re.fullmatch('[A-Za-z0-9_]{1,8}',ch) for ch in dchains):raise ValueError('Invalid design chain identities.')
    if 'temperature' in d and (type(d['temperature']) not in (float,int) or not 0<d['temperature']<=2):raise ValueError('Invalid redesign temperature.')
    biology=biology_validate(value.get('biology',{}))
    expected_parents=[p['id'] for p in biology.get('parents',[])]
    if value.get('parentCandidates',[])!=expected_parents:raise ValueError('Cross-engine derivation requires explicit parent sequence checksums and chain identities.')
    if value['engine'] in BIO_ENGINES and value.get('settings'):raise ValueError('Use typed biology options for this engine; arbitrary settings are unsupported.')
    if value['engine'] not in BIO_ENGINES and value['engine'] not in ('proteinmpnn','af2_multimer','bindcraft2') and value.get('biology'):raise ValueError('This engine does not support biological transformation inputs.')
    supported={
        'bindcraft2':{'parents','sequences','constraints'},
        'proteinmpnn':{'parents','sequences','constraints'},
        'solublempnn':{'parents','sequences','constraints'},
        'af2_multimer':{'parents','sequences','af2'},
        'esmfold2':{'parents','sequences','prediction','chemistry'},
        'esmfold2_fast':{'parents','sequences','prediction','chemistry'},
        'rosetta':{'parents','sequences','relax'},
        'rfdiffusion':{'parents','sequences','motif'},
    }
    if set(biology)-supported.get(value['engine'],set()):raise ValueError('Biology option is unsupported by the selected engine; it would be silently ignored.')
    if value['engine']=='bindcraft2' and any(mask.get('preferred') for mask in biology.get('constraints',{}).values()):raise ValueError('Seeded BindCraft currently supports fixed positions and exclusions, not a persistent preferred-amino-acid prior.')
    if value['engine']=='rfdiffusion' and 'motif' not in biology:raise ValueError('Select an explicit atomic motif before scaffolding.')
    target_bytes(value['target'])
    return json.loads(canonical(value))

def deadline_seconds(value):
    b=value['budget'];seconds=b['seconds']
    if 'maxCost' in b:seconds=min(seconds,b['maxCost']/b['hourlyPrice']*3600)
    return seconds
