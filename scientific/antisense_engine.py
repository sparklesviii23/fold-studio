"""Bounded non-replicating PNA research workflow; identical code on CPU and Modal.

The fitted baseline uses exact published MIC summaries only. It is not an
infectivity, delivery, toxicity or clinical-efficacy model.
"""
import hashlib
import json
import math
import re

VERSION = 'pna-exploratory-1'
FEATURES = ['length', 'fraction_A', 'fraction_C', 'fraction_G', 'direct_to_biology']
STRAINS = ['E. coli K-12 MG1655', 'UPEC 536']
PREPARATIONS = ['commercial_HPLC_purified', 'direct_to_biology']


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sequence(value, name, limit, optional=False):
    if not isinstance(value, str) or len(value) > limit * 2:
        raise ValueError(name + ': supply bounded plain sequence text.')
    value = ''.join(value.split()).upper().replace('U', 'T')
    if (not value and not optional) or len(value) > limit or set(value) - set('ACGT'):
        raise ValueError(name + ': use canonical A/C/G/T/U symbols within the stated limit.')
    return value


def clean(p):
    if not isinstance(p, dict): raise ValueError('Supply a workflow request.')
    mode = p.get('mode', 'analyse')
    if mode not in ('analyse', 'draft', 'benchmark'): raise ValueError('Choose analysis, complementary drafts or benchmark.')
    strain = p.get('strain', STRAINS[0]); prep = p.get('preparation', PREPARATIONS[0])
    if strain not in STRAINS or prep not in PREPARATIONS: raise ValueError('Choose a supported strain context and preparation.')
    source = p.get('source', '')
    if not isinstance(source, str) or not source.strip() or len(source) > 500: raise ValueError('Identify the source of the supplied research inputs.')
    length = p.get('length', 9)
    if type(length) is not int or not 8 <= length <= 11: raise ValueError('Draft length must be an integer from 8 to 11.')
    target = sequence('' if mode == 'benchmark' else p.get('target', ''), 'Target fragment', 64, True)
    background = sequence('' if mode == 'benchmark' else p.get('background', ''), 'Background RNA', 50000, True)
    background_source = '' if mode == 'benchmark' else p.get('backgroundSource', '')
    if not isinstance(background_source, str) or len(background_source) > 500 or (background and not background_source.strip()):
        raise ValueError('Identify the supplied background sequence source.')
    raw = '' if mode == 'benchmark' else p.get('candidates', '')
    if not isinstance(raw, str) or len(raw) > 2000: raise ValueError('Supply up to 32 existing PNA sequences, one per line.')
    candidates = [sequence(line, 'PNA', 11) for line in raw.splitlines() if line.strip()]
    if len(candidates) > 32 or any(len(v) < 8 for v in candidates): raise ValueError('Use at most 32 PNA sequences, each 8–11 bases.')
    if mode == 'analyse' and not candidates: raise ValueError('Supply at least one existing PNA sequence.')
    if mode == 'draft' and not length <= len(target) <= length + 31: raise ValueError('Supply a target fragment producing at most 32 draft windows; no cropping is applied.')
    if mode == 'benchmark': target = ''; candidates = []; background = ''; background_source = ''
    return {'mode': mode, 'strain': strain, 'preparation': prep, 'source': source.strip(), 'target': target,
            'length': length, 'candidates': '\n'.join(candidates), 'background': background, 'backgroundSource': background_source.strip()}


def complement(value):
    return value.translate(str.maketrans('ACGT', 'TGCA'))[::-1]


def features(seq, preparation):
    return [len(seq), *[seq.count(base) / len(seq) for base in 'ACG'], int(preparation == 'direct_to_biology')]


def fit(rows):
    import numpy as np
    x = np.asarray([features(r['sequence'], r['preparation']) for r in rows], dtype=float)
    y = np.log2([r['lower'] for r in rows])
    # Give each unique sequence equal total weight, despite repeated preparations/studies.
    counts = {s: sum(r['sequence'] == s for r in rows) for s in {r['sequence'] for r in rows}}
    w = np.asarray([1 / counts[r['sequence']] for r in rows])
    mean = np.average(x, axis=0, weights=w); sd = np.sqrt(np.average((x-mean)**2, axis=0, weights=w)); sd[sd < 1e-9] = 1
    z = np.column_stack([np.ones(len(x)), (x-mean)/sd]); penalty = np.eye(z.shape[1]); penalty[0, 0] = 0
    coef = np.linalg.solve(z.T @ (w[:, None]*z) + penalty, z.T @ (w*y))
    return {'features': FEATURES, 'mean': mean.tolist(), 'scale': sd.tolist(), 'coefficients': coef.tolist(),
            'featureMinimum': x.min(axis=0).tolist(), 'featureMaximum': x.max(axis=0).tolist(),
            'ridgePenalty': 1.0, 'target': 'log2(MIC / 1 uM)', 'weighting': 'Equal total training weight per unique sequence'}


def predict(model, seq, prep):
    v = features(seq, prep)
    return float(model['coefficients'][0] + sum(c*(x-m)/s for c, x, m, s in zip(model['coefficients'][1:], v, model['mean'], model['scale'])))


def train(data):
    rows = []
    for dataset in data:
        for original in dataset['records']:
            r = {**original, 'study': dataset['source']['doi'], 'preparation': original.get('preparation', PREPARATIONS[0])}
            rows.append(r)
    exact = [r for r in rows if r['qualifier'] == 'exact' and not r.get('endpointTimeCaution')]
    if len(exact) < 10: raise ValueError('Too few exact measurements for the declared benchmark.')
    # Connected components keep every shared target OR exact sequence in one fold across studies.
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i, a in enumerate(rows):
        for j in range(i):
            b = rows[j]
            if a['sequence'] == b['sequence'] or (a.get('gene') is not None and a.get('gene') == b.get('gene')):
                parent[find(i)] = find(j)
    groups = {r['id']: find(i) for i, r in enumerate(rows)}
    points = []; folds = []
    for group in sorted({groups[r['id']] for r in exact}):
        training = [r for r in exact if groups[r['id']] != group]; testing = [r for r in exact if groups[r['id']] == group]
        model = fit(training); median = sorted(math.log2(r['lower']) for r in training)
        n = len(median); baseline = (median[(n-1)//2] + median[n//2])/2
        for r in testing:
            points.append({'id': r['id'], 'sequenceGroup': sha(r['sequence'])[:12], 'fold': str(group), 'study': r['study'],
                           'observed': math.log2(r['lower']), 'predicted': predict(model, r['sequence'], r['preparation']), 'baseline': baseline})
        folds.append({'fold': str(group), 'trainRows': len(training), 'testRows': len(testing),
                      'sharedSequences': len({r['sequence'] for r in training} & {r['sequence'] for r in testing})})
    def error(key):
        per_sequence = {}
        for p in points: per_sequence.setdefault(p['sequenceGroup'], []).append(abs(p['observed'] - p[key]))
        return sum(sum(v)/len(v) for v in per_sequence.values()) / len(per_sequence)
    mae = error('predicted'); baseline_mae = error('baseline')
    return rows, fit(exact), {'method': 'Leave connected target/sequence groups out; fixed ridge penalty, no tuning on test folds',
        'status': 'exploratory_only', 'exactTrainingRows': len(exact), 'excludedNonExactOrTimeQualifiedRows': len(rows)-len(exact),
        'foldCount': len(folds), 'maeLog2Mic': mae, 'medianBaselineMaeLog2Mic': baseline_mae, 'beatsMedianBaseline': mae < baseline_mae,
        'points': points, 'folds': folds, 'metricWeighting': 'Mean absolute error averaged equally over unique held-out sequences',
        'selectionBias': 'Exact MIC summaries exclude weak/censored results; selected 2025 validation candidates are not a representative screen.',
        'externalValidation': False, 'calibratedUncertainty': False}


def background_check(seq, background):
    if not background: return {'state': 'not_assessed', 'reason': 'No background RNA reference supplied.'}
    import numpy as np
    binding = complement(seq)
    if len(background) < len(binding): return {'state': 'assessed_supplied_fragment', 'exact': 0, 'oneMismatch': 0, 'windows': 0}
    b = np.frombuffer(background.encode(), dtype=np.uint8); q = np.frombuffer(binding.encode(), dtype=np.uint8)
    windows = np.lib.stride_tricks.sliding_window_view(b, len(q)); distance = np.count_nonzero(windows != q, axis=1)
    return {'state': 'assessed_supplied_fragment', 'exact': int((distance == 0).sum()), 'oneMismatch': int((distance == 1).sum()),
            'windows': int(len(distance)), 'note': 'Forward supplied RNA only; includes intended matches if present. Not a whole-transcriptome off-target assessment.'}


def run(request, data, log=lambda value: None):
    p = clean(request); stages = []
    def stage(name, detail):
        stages.append({'name': name, 'state': 'done', 'detail': detail}); log('[fold] ' + name + ': ' + detail)
    stage('Validate inputs', 'Canonical input identities and explicit limits checked')
    loaded = [r for d in data for r in d['records']]
    stage('Load published evidence', str(len(loaded)) + ' measurement rows; ' + str(len({r['sequence'] for r in loaded})) + ' unique sequences')
    rows, model, benchmark = train(data)
    stage('Train and test baseline', str(benchmark['foldCount']) + ' target/sequence-separated folds; held-out MAE ' + format(benchmark['maeLog2Mic'], '.4f'))
    drafts = []
    if p['mode'] == 'draft':
        for i in range(len(p['target'])-p['length']+1): drafts.append({'sequence': complement(p['target'][i:i+p['length']]), 'targetOffset': i, 'origin': 'Complementary draft; not a generated phage or infectious genome'})
    elif p['mode'] == 'analyse': drafts = [{'sequence': s, 'origin': 'User-supplied existing molecule'} for s in p['candidates'].splitlines()]
    stage('Prepare molecules', str(len(drafts)) + ' molecules in input/window order; no activity optimization')
    for i, d in enumerate(drafts):
        seq = d['sequence']; reasons = []
        if p['strain'] != 'UPEC 536': reasons.append('Strain is outside the UPEC 536 training context.')
        if not benchmark['beatsMedianBaseline']: reasons.append('Held-out model did not improve on the median baseline.')
        if any(v < lo-1e-9 or v > hi+1e-9 for v, lo, hi in zip(features(seq, p['preparation']), model['featureMinimum'], model['featureMaximum'])):
            reasons.append('Composition, length or preparation falls outside the observed training feature range.')
        estimate = predict(model, seq, p['preparation']) if not reasons else None
        d.update(id='PNA-'+str(i+1).zfill(2), length=len(seq), gcFraction=(seq.count('G')+seq.count('C'))/len(seq),
                 longestHomopolymer=max(len(m.group()) for m in re.finditer(r'(.)\1*', seq)),
                 model={'state': 'withheld' if reasons else 'exploratory_estimate', 'log2Mic': estimate, 'withheldReasons': reasons,
                        'probabilityOfActivity': None, 'confidenceInterval': None}, background=background_check(seq, p['background']),
                 publishedMeasurements=[{k: r.get(k) for k in ('id', 'study', 'preparation', 'reportedValue', 'qualifier', 'sourceFootnoteMeaning')}
                                        for r in rows if r['sequence'] == seq])
    stage('Analyse molecules', 'Composition, supplied-background match counts and applicability checks completed')
    stage('Assemble report', 'Measured evidence and exploratory estimates remain distinct')
    histogram = {key: sum(r['qualifier'] == key for r in rows) for key in ['exact', 'range', 'greater_than', 'greater_or_equal']}
    return {'schema': 'fold-studio.antisense-analysis.v1', 'engineVersion': VERSION, 'stages': stages, 'request': p,
            'dataset': {'measurementRows': len(rows), 'uniqueSequences': len({r['sequence'] for r in rows}), 'measurementTypes': histogram,
                        'sources': [{'doi': d['source']['doi'], 'url': d['source']['url'], 'license': d['source']['license']} for d in data], 'sha256': sha(data)},
            'model': model, 'benchmark': benchmark, 'candidates': drafts, 'clinicalUse': False, 'activityValidated': False,
            'limitations': ['Exploratory sequence/composition baseline on a small, selected, single-strain dataset.',
                'Only exact, non-time-qualified MIC summaries train the baseline; ranges and censored results remain in the evidence.',
                'A baseline comparison is not external validation or proof of biological activity.',
                'Complementarity and short-reference matching do not establish delivery, target accessibility, specificity, toxicity or efficacy.',
                'No human safety model, bacterial whole-cell simulation, phage design or treatment recommendation is implemented.']}
