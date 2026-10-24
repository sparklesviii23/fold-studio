"""Matched coordinate assessments, explicit limits, no universal binding score."""
import math
import intelligence as mi
import research


def ca_chains(structure):
    result={}
    for res in structure['residues']:
        if not res['polymer']:continue
        atoms=[structure['atoms'][i] for i in res['atoms'] if structure['atoms'][i]['name']=='CA']
        if len(atoms)!=1:raise ValueError('Drift requires one resolved C-alpha per observed residue.')
        result.setdefault(res['chain'],[]).append((res,atoms[0]['xyz']))
    return result


def drift(reference,moving,targets,binder,fixed):
    """No sequence-alignment guess: equal, explicitly mapped chain lengths required."""
    a,b=ca_chains(reference),ca_chains(moving)
    if set(targets+[binder])-set(a) or set(targets+[binder])-set(b):raise ValueError('Prediction lost a required context chain.')
    mobile=[];original=[]
    for ch in targets+[binder]:
        if len(a[ch])!=len(b[ch]):raise ValueError('Drift correspondence changed chain length.')
        if ch in targets:
            if any(x[0]['one']!=y[0]['one'] for x,y in zip(a[ch],b[ch])):raise ValueError('Fixed target sequence changed.')
            mobile += [r[1] for r in b[ch]];original += [r[1] for r in a[ch]]
    if len(original)<3:raise ValueError('At least three target C-alpha atoms are required for pose alignment.')
    transform=mi.fit(mobile,original)
    def rmsd(rows):
        return math.sqrt(sum(mi.dist(mi.apply_fit(p,transform),q)**2 for p,q in rows)/len(rows)) if rows else None
    fixed_pairs=[]
    for i in fixed:
        x,y=a[binder][i-1],b[binder][i-1]
        if x[0]['one']!=y[0]['one']:raise ValueError('Protected candidate residue identity changed.')
        fixed_pairs.append((y[1],x[1]))
    return {'targetRmsd':rmsd(list(zip(mobile,original))),
            'candidatePoseRmsd':rmsd([(y[1],x[1]) for x,y in zip(a[binder],b[binder])]),
            'protectedPoseRmsd':rmsd(fixed_pairs),
            'targetAtoms':len(original),'candidateAtoms':len(a[binder]),
            'method':'Least-squares target C-alpha alignment, explicit chain identity and sequence-position correspondence. No target symmetry permutation inferred. Å.'}


def metrics(analysis,sequence):
    area=analysis['surface'].get('interfaceArea')
    result={'severeClashes':analysis['summary']['severeClashes'],'atomicContacts':analysis['summary']['atomicContacts'],'liabilityCount':len(research.liabilities(sequence)['flags'])}
    if type(area) in (int,float) and math.isfinite(area):result['interfaceArea']=area
    return result


def policy(value=None):
    value=value or {}
    if not isinstance(value,dict) or set(value)-{'objectives','limits','maxPoseRmsd','maxModelDisagreement','rounds','maxDescendants'}:raise ValueError('Unsupported transparent selection rule.')
    objectives=value.get('objectives',{'severeClashes':'min','interfaceArea':'max','liabilityCount':'min'})
    supported={'severeClashes','interfaceArea','liabilityCount','atomicContacts'}
    if not isinstance(objectives,dict) or not objectives or set(objectives)-supported or any(v not in ('min','max') for v in objectives.values()):raise ValueError('Choose supported descriptive objectives and explicit min/max directions.')
    limits=value.get('limits',{'severeClashes':[0,0]})
    if not isinstance(limits,dict) or set(limits)-supported:raise ValueError('Unknown hard-limit metric.')
    for key,bounds in limits.items():
        if not isinstance(bounds,list) or len(bounds)!=2 or any(v is not None and (type(v)not in(int,float) or not math.isfinite(v)) for v in bounds) or all(v is not None for v in bounds) and bounds[0]>bounds[1]:raise ValueError('Hard limits require ordered finite [minimum, maximum] bounds, with null for an open bound.')
    result={'objectives':objectives,'limits':limits,'maxPoseRmsd':value.get('maxPoseRmsd',3.0),'maxModelDisagreement':value.get('maxModelDisagreement',3.0),'rounds':value.get('rounds',1),'maxDescendants':value.get('maxDescendants',16)}
    for key in ('maxPoseRmsd','maxModelDisagreement'):
        if type(result[key])not in(int,float) or not math.isfinite(result[key]) or not 0<result[key]<=100:raise ValueError('Drift/disagreement limits must be positive, explicit Å values.')
    for key,high in [('rounds',3),('maxDescendants',32)]:
        if type(result[key])is not int or not 1<=result[key]<=high:raise ValueError('Invalid bounded '+key+'.')
    return result


def select(rows,rules,pareto):
    """Conservative worst-sample descriptors; independent methods remain explicit."""
    result=[]
    for row in rows:
        samples=row.get('samples',[]);reasons=[];raw={}
        for key,direction in rules['objectives'].items():
            values=[s['metrics'].get(key) for s in samples]
            if values and all(type(v)in(int,float) and math.isfinite(v) for v in values):raw[key]=(max if direction=='min' else min)(values)
        for key in rules['limits']:
            vals=[s['metrics'].get(key) for s in samples]
            if vals and all(type(v)in(int,float) and math.isfinite(v) for v in vals):
                low,high=rules['limits'][key]
                # Both endpoints are checked against every sample, not a misleading mean.
                if low is not None and min(vals)<low or high is not None and max(vals)>high:reasons.append('hard_limit_any_sample:'+key)
                raw.setdefault(key,vals[0])
        if not samples:reasons.append('missing_structural_reprediction')
        for sample in samples:
            if sample['drift']['candidatePoseRmsd']>rules['maxPoseRmsd']:reasons.append('structural_drift')
        if row.get('maxDisagreement') is None and len(samples)>1:reasons.append('model_disagreement_unavailable')
        elif row.get('maxDisagreement',0) is not None and row['maxDisagreement']>rules['maxModelDisagreement']:reasons.append('model_disagreement')
        # Fast/full ESM are the same family; two checkpoints never count as two independent methods.
        families={s['family'] for s in samples};used=set(row.get('conditionedFamilies',[]))
        if not families-used:reasons.append('no_unconditioned_prediction_family')
        if not row.get('physicsAssessment'):reasons.append('missing_held_out_physics_assessment')
        result.append({**row,'metrics':raw,'gateReasons':sorted(set(reasons)),'predictionFamilies':sorted(families),'trainingIndependence':'unverified'})
    compared=pareto(result,rules['objectives'],rules['limits'])
    for row in compared:
        row['eligible']=row['eligible'] and not row['gateReasons']
        row['reasons']+=row['gateReasons']
    # Recompute dominance after gating; a failed candidate cannot dominate a valid one.
    valid=pareto([r for r in compared if r['eligible']],rules['objectives'],rules['limits'])
    byid={r['id']:r for r in valid}
    for row in compared:row['dominatedBy']=byid.get(row['id'],{}).get('dominatedBy',[])
    return compared


def counterfactual(rows,candidates,metric=None,higher=True,neutral_tolerance=0):
    """Matched raw predictor/geometry differences, not activity probabilities."""
    if type(higher)is not bool or type(neutral_tolerance)not in(int,float) or not math.isfinite(neutral_tolerance) or neutral_tolerance<0:raise ValueError('Use an explicit metric direction and a finite nonnegative neutral tolerance in native units.')
    if not rows:return []
    baseline=rows[0];results=[]
    for variant in rows[1:]:
        pairs=[];experimental=candidates[variant['id']].get('mutationEvidence',{})
        original={(sample['engine'],sample.get('sampleIndex',0)):sample for sample in baseline.get('samples',[])}
        modified={(sample['engine'],sample.get('sampleIndex',0)):sample for sample in variant.get('samples',[])}
        for key in sorted(original.keys()&modified.keys()):
            a,b=original[key],modified[key]
            ar,br=a['receipt'],b['receipt']
            if a['engine']!=b['engine'] or a['family']!=b['family'] or any(ar.get(k)!=br.get(k) for k in ('seed','runtime','device')):raise ValueError('Counterfactual prediction settings are unmatched.')
            one={**a['confidence'],**a['metrics']};two={**b['confidence'],**b['metrics']}
            deltas={k:two[k]-one[k] for k in one.keys()&two.keys() if type(one[k])in(int,float) and type(two[k])in(int,float) and math.isfinite(one[k]) and math.isfinite(two[k])}
            effect=deltas.get(metric);direction=None
            if effect is not None:direction='neutral' if abs(effect)<=neutral_tolerance else 'gain' if effect*(1 if higher else -1)>0 else 'loss'
            pairs.append({'engine':a['engine'],'family':a['family'],'delta':deltas,'metric':metric,'predictedMetricDirection':direction,'experimentalDirection':experimental.get('direction'),'directionalAgreement':direction==experimental['direction'] if direction and experimental.get('direction') else None,'neutralTolerance':neutral_tolerance,'scope':'Exploratory direction agreement in the chosen raw computational metric; confidence/geometry is not calibrated biological activity.'})
        results.append({'parentId':baseline['id'],'candidateId':variant['id'],'matchedPairs':pairs,'experimentalEvidence':experimental or None,'missingResults':not pairs or original.keys()!=modified.keys(),'independentFamilyCount':len({p['family'] for p in pairs}),'inconsistentDirections':len({p['predictedMetricDirection'] for p in pairs if p['predictedMetricDirection']})>1})
    return results
