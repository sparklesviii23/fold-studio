#!/usr/bin/env python3
"""Freeze synthetic target groups, collect solver labels, and compare design arms."""
import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scientific'))
from rna_design_core import atomic, digest, pairs, search, validate

# A node is a stem. Its children form a multiloop or an internal loop.
H = ()
SHAPES = [
    (H,), ((H,),), (((H,),),), (H,H), (H,H,H), ((H,),H), (H,(H,)),
    ((H,H),), ((H,H,H),), (((H,),H),), ((H,(H,)),), (((H,),(H,)),),
    ((H,H),H), (H,(H,H)), (((H,H),),), ((((H,),),),),
    ((H,H), (H,)), (((H,),H,H),), (H,H,(H,)), (((H,),),H),
]


def structure(forest, rng, scale):
    def node(children):
        stem = rng.randint(2, 3) + scale
        inside = '.' * rng.randint(3, 7) if not children else '..' + '..'.join(node(c) for c in children) + '..'
        return '(' * stem + inside + ')' * stem
    return '..'.join(node(c) for c in forest)


def freeze(out, strict=False, prior=None):
    if (out / 'protocol.json').exists():
        raise ValueError('Protocol already exists. Use a new output directory.')
    out.mkdir(parents=True)
    generator_seed = 2026111602 if strict else 20261116
    rng = random.Random(generator_seed)
    prior_targets = set()
    if prior:
        previous = json.loads(Path(prior).read_text())
        prior_targets = {r['request']['target'] for rows in previous['splits'].values() for r in rows}
    groups = []
    for index, shape in enumerate(SHAPES):
        rows = []
        for variant in range(3):
            for attempt in range(300):
                target = structure(shape, rng, variant)
                if 8 <= len(target) <= 128 and target not in prior_targets and target not in {r['request']['target'] for rows in groups for r in rows} and target not in {r['request']['target'] for r in rows}:
                    break
            else:
                raise ValueError('Could not generate a fresh target.')
            request = validate({'target': target, 'locks': ('G' + '.' * (len(target)-2) + 'C') if index % 3 == 0 and target[0] == '(' and target[-1] == ')' and (0,len(target)-1) in pairs(target) else '',
                                'maxCandidates': 32, 'maxSeconds': 2, 'wanted': 3})
            rows.append({'id': f'g{index:02d}-v{variant}', 'group': index, 'request': request,
                         'length': len(target), 'difficulty': 'simple' if index < 3 else 'branched' if any(len(c) > 1 for c in shape) else 'multi-stem'})
        groups.append(rows)
    # Merge near-identical equal-length targets before assigning whole groups.
    parent = list(range(len(groups)))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    def coarse_node(children):
        if len(children) == 1:
            return coarse_node(children[0])
        return '(' + ''.join(sorted(coarse_node(c) for c in children)) + ')'
    def coarse_forest(forest):
        return ''.join(sorted(coarse_node(c) for c in forest))
    if strict:
        for i in range(len(groups)):
            for j in range(i):
                if coarse_forest(SHAPES[i]) == coarse_forest(SHAPES[j]):
                    parent[root(i)] = root(j)
    for i, a in enumerate(groups):
        for j, b in enumerate(groups[:i]):
            if any(x['length'] == y['length'] and 2 * len(pairs(x['request']['target']) & pairs(y['request']['target'])) / max(1,len(pairs(x['request']['target']))+len(pairs(y['request']['target']))) >= .8 for x in a for y in b):
                parent[root(i)] = root(j)
    components = {}
    for i, rows in enumerate(groups):
        components.setdefault(root(i), []).extend(rows)
    keys = sorted(components)
    # Keep topology 7 (two branches inside one outer stem) in the final test.
    test_root = root(7)
    shuffled = [k for k in keys if k != test_root]
    rng.shuffle(shuffled)
    if strict:
        test_groups = sorted({test_root, root(0)})
        remaining = [k for k in shuffled if k not in test_groups]
        val_groups = remaining[:1]
    else:
        test_groups = [test_root] + shuffled[:max(1,len(keys)//5)]
        val_groups = shuffled[max(1,len(keys)//5):max(1,len(keys)//5)+2]
    split = {name: [r for k in keys if (k in test_groups if name == 'test' else k in val_groups if name == 'validation' else k not in test_groups + val_groups) for r in components[k]] for name in ('train','validation','test')}
    for name, rows in split.items():
        for row in rows:
            row['component'] = root(row['group'])
            row['split'] = name
    protocol = {'schema': 'fold.rna-design-protocol/1', 'created': '2026-11-16', 'source': f'Synthetic nested targets; generator seed {generator_seed}. No experimental labels. No ArchiveII SRP test targets.',
                'grouping': 'Whole coarse stem-tree families: collapse unary loops, sort children and exterior stems to group mirrors and permutations; merge equal-length pair F1 >= 0.8. No target string from the prior protocol.' if strict else 'Whole stem-tree topology groups. Merge equal-length pair F1 >= 0.8 before splitting. Same topology variants stay together.',
                'splits': split, 'arms': ['solver','qwen','hybrid'], 'seeds': [17,29],
                'evaluationLimits': [8,32], 'searchSeconds': 2, 'wanted': 3,
                'qualification': 'Exact ViennaRNA MFE target, canonical pairs, mask, locks and optional GC/homopolymer limits. RNA Lab check is reported separately.',
                'accounting': 'Fresh per-arm caches. Count explicit MFE+PF scoring, independent checks, inverse_fold calls and wall time. Internal inverse_fold energy calls are unavailable; matched explicit counts do not equal matched total work.',
                'training': {'seed': 20261116, 'epochs': 24, 'headLearningRate': .002, 'backbone': 'Frozen existing Qwen2.5-Coder-3B-Instruct',
                             'selection': 'Lowest validation positive-label base CE. No held-out test selection.', 'temperature': 1.0},
                'cost': 'Local seconds, not dollars. Local energy cost is unmeasured. Modal estimate and billed usage stay separate.',
                'limitations': 'Small synthetic topology pilot. Qwen pretraining contamination is unknown. Fold ties count as an MFE match; target ensemble probability is also reported.'}
    protocol['sha256'] = digest(protocol)
    atomic(out / 'protocol.json', protocol)
    print(json.dumps({'sha256':protocol['sha256'], 'counts': {k:len(v) for k,v in split.items()}, 'components':len(keys)}))


def collect(out):
    protocol = json.loads((out / 'protocol.json').read_text())
    labels = []
    for split in ('train','validation'):
        for target in protocol['splits'][split]:
            result = search({**target['request'], 'seed': 101, 'maxCandidates': 24, 'maxSeconds': 2, 'wanted': 8}, out / 'labels-runs' / target['id'])
            for c in result['candidates']:
                labels.append({'targetId':target['id'], 'target':target['request']['target'], 'split':split, 'sequence':c['sequence'],
                               'qualifies':c['qualifies'], 'pairF1':c['pairF1'], 'failureReasons':c['failureReasons'],
                               'sourceType':'solver', 'source':'ViennaRNA 2.7.2', 'measurement':False,
                               'runSha256':result['sha256']})
            print(json.dumps({'target':target['id'],'split':split,'candidates':len(result['candidates']),'successes':result['qualifyingCount']}), flush=True)
    atomic(out / 'labels.json', {'protocolSha256':protocol['sha256'], 'labels':labels, 'sha256':digest(labels)})


def evaluate(out, checkpoint):
    protocol = json.loads((out / 'protocol.json').read_text())
    from rna_design_qwen import Proposer
    model_start = time.monotonic()
    proposer = Proposer(checkpoint)
    model_startup = time.monotonic() - model_start
    rows = []
    for target in protocol['splits']['test']:
        feature_start = time.monotonic()
        proposer.set_target(target['request']['target'])
        feature_time = time.monotonic() - feature_start
        for seed in protocol['seeds']:
            for limit in protocol['evaluationLimits']:
                for arm in protocol['arms']:
                    folder = out / 'comparison' / f"{target['id']}-{seed}-{limit}-{arm}"
                    request = {**target['request'], 'seed':seed, 'method':arm, 'maxCandidates':limit, 'maxSeconds':protocol['searchSeconds'], 'wanted':protocol['wanted']}
                    began = time.monotonic()
                    value = search(request, folder, proposals=proposer if arm != 'solver' else None)
                    wall = time.monotonic() - began
                    checked = [c for c in value['candidates'] if c['qualifies'] and c.get('independent')]
                    row = {'target':target['id'], 'group':target['group'], 'difficulty':target['difficulty'], 'length':target['length'],
                           'seed':seed, 'limit':limit, 'method':arm, 'success':value['qualifyingCount']>0, 'distinctQualifying':value['qualifyingCount'],
                           'firstSuccessSeconds':value['metrics']['firstSuccessSeconds'], 'wallSeconds':wall, 'searchMetrics':value['metrics'],
                           'startupSeconds':0 if arm == 'solver' else model_startup, 'targetFeatureSeconds':0 if arm == 'solver' else feature_time,
                           'constraintViolations':sum(bool(c['constraintViolations']) for c in value['candidates']),
                           'independentChecked':len(checked), 'independentAgreements':sum(c['independent']['agreesWithTarget'] for c in checked),
                           'bestPairF1':max((c['pairF1'] for c in value['candidates']), default=0), 'resultSha256':value['sha256']}
                    rows.append(row)
                    atomic(out / 'comparison-partial.json', rows)
                    print(json.dumps(row), flush=True)
    summary = []
    for limit in protocol['evaluationLimits']:
        for difficulty in ['all']+sorted({r['difficulty'] for r in rows}):
            for method in protocol['arms']:
                cases = [r for r in rows if r['method']==method and r['limit']==limit and (difficulty=='all' or r['difficulty']==difficulty)]
                success = sum(r['success'] for r in cases)
                checked = sum(r['independentChecked'] for r in cases)
                summary.append({'method':method,'limit':limit,'difficulty':difficulty,'cases':len(cases),'successRate':success/len(cases),
                                'meanDistinctQualifying':statistics.mean(r['distinctQualifying'] for r in cases),
                                'medianFirstSuccessSeconds':statistics.median([r['firstSuccessSeconds'] for r in cases if r['firstSuccessSeconds'] is not None]) if success else None,
                                'meanWallSeconds':statistics.mean(r['wallSeconds'] for r in cases),
                                'independentAgreement':sum(r['independentAgreements'] for r in cases)/checked if checked else None,
                                'constraintViolations':sum(r['constraintViolations'] for r in cases),
                                'secondsPerSuccessfulTarget':sum(r['wallSeconds'] for r in cases)/success if success else None,
                                'dollarsPerSuccessfulTarget':None})
    report = {'protocolSha256':protocol['sha256'], 'checkpointSha256':hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
              'modelStartupSeconds':model_startup, 'summary':summary,'cases':rows,
              'limitations':protocol['limitations'], 'accounting':protocol['accounting'],
              'startupAccounting':'The model was loaded once. Per-arm cold startup is reported separately. Cached target features are timed separately. Search time includes proposals, constraint repair, solver work, scoring, independent checks and persistence.',
              'cost':'Local dollar cost and billed Modal cost are not measured.'}
    report['sha256'] = digest(report)
    atomic(out / 'benchmark.json', report)


def matched(out, checkpoint):
    protocol=json.loads((out/'protocol.json').read_text())
    supplement={'protocolSha256':protocol['sha256'],'checkpointSha256':hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                'purpose':'Run each frozen arm to exactly 8 explicit final scoring calls. Disable early success stopping by requesting 20 sequences. Keep 2 s time limit. Report time-censored cases separately. No model or proposal tuning.',
                'seeds':protocol['seeds'],'limit':8,'maxSeconds':2,'wanted':20}
    plan=out/'matched-count-plan.json'
    if not plan.exists(): atomic(plan,supplement)
    elif json.loads(plan.read_text())!=supplement: raise ValueError('Matched-count plan changed.')
    from rna_design_qwen import Proposer
    start=time.monotonic();proposer=Proposer(checkpoint);startup=time.monotonic()-start
    rows=[]
    for target in protocol['splits']['test']:
        start=time.monotonic();proposer.set_target(target['request']['target']);features_time=time.monotonic()-start
        for seed in protocol['seeds']:
            for arm in protocol['arms']:
                value=search({**target['request'],'seed':seed,'method':arm,'maxCandidates':8,'maxSeconds':2,'wanted':20},out/'matched-count'/f"{target['id']}-{seed}-{arm}",proposals=proposer if arm!='solver' else None)
                rows.append({'target':target['id'],'difficulty':target['difficulty'],'length':target['length'],'seed':seed,'method':arm,
                             'success':value['qualifyingCount']>0,'distinctQualifying':value['qualifyingCount'],'metrics':value['metrics'],
                             'startupSeconds':0 if arm=='solver' else startup,'targetFeatureSeconds':0 if arm=='solver' else features_time,
                             'constraintViolations':sum(bool(c['constraintViolations']) for c in value['candidates'])})
                atomic(out/'matched-count-partial.json',rows)
                print(json.dumps(rows[-1]),flush=True)
    eligible={(r['target'],r['seed']) for r in rows if all(x['metrics']['evaluations']==8 for x in rows if x['target']==r['target'] and x['seed']==r['seed'])}
    summaries=[]
    for arm in protocol['arms']:
        cases=[r for r in rows if r['method']==arm and (r['target'],r['seed']) in eligible]
        summaries.append({'method':arm,'cases':len(cases),'successRate':sum(r['success'] for r in cases)/len(cases) if cases else None,
                          'meanDistinctQualifying':statistics.mean(r['distinctQualifying'] for r in cases) if cases else None,
                          'meanSearchSeconds':statistics.mean(r['metrics']['elapsedSeconds'] for r in cases) if cases else None})
    atomic(out/'matched-count.json',{'plan':supplement,'summary':summaries,'allCases':rows,'fullyMatchedTargetSeeds':len(eligible),
                                   'censoredTargetSeeds':len(protocol['splits']['test'])*len(protocol['seeds'])-len(eligible),
                                   'limitations':'This is an exact match of explicit final scores. Internal inverse_fold energy evaluations remain unobserved. Excluding time-censored target-seeds can bias the fully matched subset.'})


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('phase',choices=['freeze','collect','evaluate','matched']);p.add_argument('--out',type=Path,required=True);p.add_argument('--checkpoint',type=Path);p.add_argument('--strict-groups',action='store_true');p.add_argument('--prior-protocol',type=Path);a=p.parse_args()
    if a.phase=='freeze': freeze(a.out,a.strict_groups,a.prior_protocol)
    elif a.phase=='collect': collect(a.out)
    elif a.phase=='matched': matched(a.out,a.checkpoint)
    else: evaluate(a.out,a.checkpoint)
