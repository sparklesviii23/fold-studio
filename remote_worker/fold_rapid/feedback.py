"""Explicit measured-descriptor rules for discrete, qualified-frontier feedback."""
import math
from .contracts import fields
METRICS={'severeClashes','interfaceArea','liabilityCount','atomicContacts'}
OPERATIONS={'proteinmpnn','solublempnn','bindcraft2'}

def validate(value):
    fields(value,('rules','defaultOperations'))
    if not isinstance(value['rules'],list) or len(value['rules'])>8:raise ValueError('At most eight explicit feedback rules are supported.')
    if not isinstance(value['defaultOperations'],list) or len(set(value['defaultOperations']))!=len(value['defaultOperations']) or set(value['defaultOperations'])-OPERATIONS:raise ValueError('Unsupported feedback fallback operation.')
    for rule in value['rules']:
        fields(rule,('metric','comparison','threshold','operation'))
        if rule['metric'] not in METRICS or rule['comparison'] not in ('above','below') or rule['operation'] not in OPERATIONS:raise ValueError('Unsupported measured feedback operation.')
        if type(rule['threshold'])not in(int,float) or not math.isfinite(rule['threshold']):raise ValueError('Feedback threshold must be finite, in the raw metric units.')
    return value

def operations(value):
    validate(value);return set(value['defaultOperations'])|{r['operation'] for r in value['rules']}

def choose(value,evaluation):
    validate(value)
    if not evaluation or not evaluation.get('eligible'):return {'operations':[],'reason':'No qualified evaluated frontier; feedback does not relax scientific gates.','matchedRules':[]}
    chosen=[];matched=[]
    for r in value['rules']:
        actual=evaluation['metrics'].get(r['metric'])
        if type(actual)not in(int,float) or not math.isfinite(actual):return {'operations':[],'reason':'Missing measured feedback metric: '+r['metric'],'matchedRules':[]}
        if actual>r['threshold'] if r['comparison']=='above' else actual<r['threshold']:
            matched.append({**r,'observed':actual})
            if r['operation'] not in chosen:chosen.append(r['operation'])
    return {'operations':chosen or list(value['defaultOperations']),'matchedRules':matched,'reason':'Explicit measured-descriptor rule' if matched else 'Explicit fallback; no descriptor rule matched.','bindingImprovementEstablished':False}
