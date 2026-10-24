"""Bounded automatic campaign inputs; never implicit chemistry or paid APIs."""
import copy
import math
import re
from .contracts import fields, integer, canonical, digest, target_bytes, manifest
from .molecules import inspect,selected_target
from .biology_contract import validate

STRATEGIES=('de_novo','existing_sequences','motif_scaffolding','site_guided','evolution','chemically_stabilized','counterfactual')
OPERATIONS={'bindcraft2':'design','boltzgen':'design','proteinmpnn':'redesign','solublempnn':'redesign','esmfold2_fast':'evaluate','esmfold2':'evaluate','af2_multimer':'evaluate','rosetta':'relax'}
FAMILIES={'bindcraft2':'AlphaFold2','boltzgen':'Boltz','esmfold2_fast':'ESMFold2/ESMC','esmfold2':'ESMFold2/ESMC','af2_multimer':'AlphaFold2'}


def analysis_modules():
    import pathlib,sys
    for folder in (pathlib.Path(__file__).resolve().parents[1]/'native_analysis',pathlib.Path(__file__).resolve().parents[2]/'scientific',pathlib.Path(__file__).resolve().parents[1]):
        if (folder/'biology_assessment.py').is_file():
            if str(folder) not in sys.path:sys.path.insert(0,str(folder))
            import biology_assessment
            return biology_assessment
    raise ValueError('The shared Fold Studio assessment source is absent; no substitute metrics will be used.')


def campaign(value):
    fields(value,('schemaVersion','kind','strategy','target','parents','generators','workflow','stageBudgets','budget','seed','policy'),('constraints','hotspots','execution'))
    if value['schemaVersion']!=1 or type(value['schemaVersion'])is not int or value['kind']!='unified':raise ValueError('Unsupported unified campaign version.')
    if value['strategy'] not in STRATEGIES:raise ValueError('Unknown biological strategy.')
    if 'execution' in value:
        from .execution import policy
        policy(value['execution'])
    mapping=inspect(target_bytes(value['target']),value['target']['format'])
    if not set(value['target']['chains'])<=set(mapping['chains']):raise ValueError('Target chains are absent.')
    integer(value['seed'],0,2**31-1,'Seed')
    parents=value['parents']
    if not isinstance(parents,list) or len(parents)>8:raise ValueError('Supply at most eight original candidates.')
    ids=set()
    for parent in parents:
        fields(parent,('id','binderChains','sequences'))
        if not isinstance(parent['id'],str) or not re.fullmatch('[a-zA-Z0-9_-]{1,100}',parent['id']) or parent['id'] in ids:raise ValueError('Distinct original candidate identities are required.')
        ids.add(parent['id']);chains=parent['binderChains']
        if not isinstance(chains,list) or not chains or len(chains)!=len(set(chains)) or set(chains)&set(value['target']['chains']) or not set(chains)<=set(mapping['chains']):raise ValueError('Select observed binder chains separate from the target.')
        expected={ch:mapping['chains'][ch]['sequence'] for ch in value['target']['chains']+chains}
        if parent['sequences']!=expected:raise ValueError('Initial candidates must match observed coordinates exactly; new sequences require a fresh prediction, never relabelled atoms.')
    if not isinstance(value['generators'],list) or len(value['generators'])>2:raise ValueError('Select at most two independent generator branches.')
    seen=set()
    for generator in value['generators']:
        fields(generator,('engine','design'),('settings','biology'))
        if generator['engine'] not in ('bindcraft2','boltzgen') or generator['engine'] in seen:raise ValueError('Use distinct supported self-hosted generators. Official BoltzProt uses its separately approved API route.')
        seen.add(generator['engine'])
        generator_manifest=manifest({'schemaVersion':1,'engine':generator['engine'],'operation':'design','target':value['target'],'design':generator['design'],'settings':generator.get('settings',{}),'biology':generator.get('biology',{}),'parentCandidates':[p['id'] for p in generator.get('biology',{}).get('parents',[])],'seed':value['seed'],'budget':{'seconds':1},'mode':'reference'})
        selected_target(generator_manifest)
    if value['strategy']=='de_novo' and not seen:raise ValueError('De novo design requires a genuine generator branch.')
    if value['strategy']=='site_guided' and not any(g['design'].get('hotspots') for g in value['generators']):raise ValueError('Site-guided design requires explicit observed target hotspots in the generator configuration.')
    if not parents and not seen:raise ValueError('Choose observed parents or genuine generation.')
    fields(value['workflow'],('redesign','predictors','rosetta','count'),('prediction',))
    flow=value['workflow']
    for key,supported in [('redesign',('proteinmpnn','solublempnn')),('predictors',('esmfold2_fast','esmfold2','af2_multimer'))]:
        engines=flow[key]
        if not isinstance(engines,list) or len(set(engines))!=len(engines) or set(engines)-set(supported):raise ValueError('Unsupported '+key+' engines.')
    if type(flow['rosetta'])is not bool:raise ValueError('Rosetta is an explicit licensed option.')
    integer(flow['count'],1,4,'Redesign samples per branch')
    validate({'prediction':flow.get('prediction',{})})
    rules=analysis_modules().policy(value['policy'])
    if rules['maxDescendants']>32:raise ValueError('Candidate budget exceeds the bounded controller.')
    if not isinstance(value['stageBudgets'],dict) or set(value['stageBudgets'])-set(OPERATIONS):raise ValueError('Unknown stage budget.')
    required=seen|set(flow['redesign'])|set(flow['predictors'])|({'rosetta'} if flow['rosetta'] else set())
    if required-set(value['stageBudgets']):raise ValueError('Every selected model needs an explicit stage runtime and reviewed hourly estimate.')
    for engine,b in value['stageBudgets'].items():
        fields(b,('seconds','hourlyEstimateUSD'),('gpuMemoryMiB',))
        integer(b['seconds'],1,7200,'Stage runtime')
        rate=b['hourlyEstimateUSD']
        if type(rate)not in(int,float) or not math.isfinite(rate) or not 0<rate<=100:raise ValueError('Invalid stage hourly estimate.')
        if 'gpuMemoryMiB' in b:integer(b['gpuMemoryMiB'],512,200000,'GPU ceiling')
    fields(value['budget'],('seconds','maxEstimatedUSD'))
    integer(value['budget']['seconds'],1,7200,'Campaign runtime')
    if type(value['budget']['maxEstimatedUSD'])not in(int,float) or not math.isfinite(value['budget']['maxEstimatedUSD']) or not 0<value['budget']['maxEstimatedUSD']<=1000:raise ValueError('Set a finite campaign estimate allowance.')
    constraints=value.get('constraints',{})
    if any(ch in value['target']['chains'] for ch in constraints):raise ValueError('Fixed target chains cannot receive redesign constraints.')
    for p in parents:validate({'sequences':p['sequences'],'constraints':constraints},mapping)
    if constraints and not parents:raise ValueError('De novo chain identities are not known yet; explicit masks require an observed candidate.')
    return copy.deepcopy(value)


def blockers(value):
    reasons=[]
    if value['strategy'] in ('motif_scaffolding','chemically_stabilized','counterfactual'):
        reasons.append(value['strategy']+': complete target-aware cloud handoff/curated chemistry or matched controls not yet qualified; use the dedicated pathway until connected')
    if not value['workflow']['predictors']:reasons.append('Fresh structural predictions are required for final selection.')
    return reasons


def estimate(value):
    value=campaign(value);b=value['stageBudgets'];flow=value['workflow'];rules=analysis_modules().policy(value['policy'])
    # Upper bound on reservations, not a provider invoice. Includes all ensemble
    # stages and relaxation re-evaluation; no assumption that a model is faster.
    parents=len(value['parents'])+sum(g['design']['count'] for g in value['generators'])
    per=parents*(1+flow['count']*len(flow['redesign']))
    stages={g['engine']:1 for g in value['generators']}
    for e in flow['redesign']:stages[e]=parents*rules['rounds']
    for e in flow['predictors']:stages[e]=per*rules['rounds']*(2 if flow['rosetta'] else 1)
    if flow['rosetta']:stages['rosetta']=per*rules['rounds']
    rows=[{'engine':e,'maximumCalls':n,'secondsPerCall':b[e]['seconds'],'estimatedUSD':n*b[e]['seconds']/3600*b[e]['hourlyEstimateUSD']} for e,n in stages.items()]
    return {'stages':rows,'upperReservationUSD':sum(r['estimatedUSD'] for r in rows),'allowanceUSD':value['budget']['maxEstimatedUSD'],'billingScope':'Reviewed stage runtime rates only; CPU orchestrator, cold starts, memory, storage and network add charges. Provider workspace budget required for billing protection.','externalAPIIncluded':False,'policy':'Sequential modular workers; warm execution requires measured qualification.'}
