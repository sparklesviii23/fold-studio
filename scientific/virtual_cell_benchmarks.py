"""Bounded, retrospective Tahoe response evaluation. Never writes to input datasets.

Protocol v1 holds out whole Cellosaurus identities AND plates. No test-response
filtering, hyperparameter tuning, imputation of missing targets, or model downloads.
All predictors are deliberately simple; this does not validate a foundation model.
"""
import hashlib
import json
import pathlib
import platform
import re
import time
import uuid
import warnings

import numpy as np

SCHEMA = 'fold.virtualcell.benchmark/1'
PROTOCOL = 'tahoe-line-plate-holdout/1'
MODELS = ('unchanged', 'training_mean', 'drug_dose_mean', 'nearest_context')
MODEL_LABELS = {'unchanged': 'Unchanged DMSO (zero response)', 'training_mean': 'Compound-agnostic training mean',
                'drug_dose_mean': 'Training donor mean at matched drug and dose', 'nearest_context': 'Nearest untreated RNA context'}
FOLDER = ('virtualcell', 'benchmarks')
LIMITATIONS = [
    'Retrospective pseudobulk DESeq2 log2 fold changes, not per-cell distributions or experimental validation.',
    'A small, deterministic sample of conditions; no selection for activity or effect size.',
    'Train plates 1–10, validation plates 11–12, test plates 13–14. Shared drug identities and doses are intentional.',
    'Plate identifiers are the finest available batch identifiers. Donor/specimen/well identity is not retained in this atlas; duplicate specimens cannot be audited.',
    'Test lines can share wells and plate effects. Crossed line/compound bootstrap intervals are conditional on the two test plates, not evidence of generalisation to all batches.',
    'DepMap untreated bulk RNA and Tahoe treatment responses come from different experiments; they are not paired single-cell multiomics.',
    'Float16 atlas values and missing genes are retained. Metrics use the identical finite gene mask for every model; no top-gene selection from test effects.',
    'Parental HepG2 and K-562 have no test targets here. HepG2/C3A results do not validate parental HepG2.',
    'No calibrated per-gene predictive intervals, longitudinal dynamics, unseen-compound performance or therapeutic efficacy is established.',
]


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(8 << 20), b''):
            h.update(part)
    return h.hexdigest()


def split_lines(lines, seed=17):
    """Fixed 60/20/20 split; the requested C3A demonstration is prespecified test."""
    names = sorted(lines)
    if len(names) < 15:
        raise ValueError('At least 15 distinct cell lines are required for this protocol.')
    rng = np.random.default_rng(seed)
    rng.shuffle(names)
    n = max(3, len(names) // 5)
    test = names[:n]
    if 'CVCL_1098' in names and 'CVCL_1098' not in test:
        j = names.index('CVCL_1098'); names[0], names[j] = names[j], names[0]
    return {'test': sorted(names[:n]), 'validation': sorted(names[n:2*n]), 'train': sorted(names[2*n:])}


def assert_split(split):
    sets = [set(split[k]) for k in ('train', 'validation', 'test')]
    if any(not x for x in sets) or any(sets[i] & sets[j] for i in range(3) for j in range(i)):
        raise ValueError('Cell-line splits must be nonempty and disjoint.')


def _mean(rows):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        return np.nanmean(np.where(np.isfinite(rows), rows, np.nan), axis=0, dtype=np.float64)


def group_rows(conditions):
    """Do not silently merge different units or plates."""
    groups = {}
    identities = {}
    for i, c in enumerate(conditions):
        if c.get('unit') != 'uM':
            raise ValueError('This protocol requires explicitly identified uM concentrations.')
        dose = float(c['concentration'])
        if not np.isfinite(dose) or dose <= 0:
            raise ValueError('Treatment concentrations must be finite and positive.')
        if not re.fullmatch(r'CVCL_[A-Z0-9]{4}', str(c['cellosaurus'])):
            raise ValueError('Invalid Cellosaurus identity.')
        identity = (c.get('depmap'), c['cellLine'])
        prior = identities.setdefault(c['cellosaurus'], identity)
        if prior != identity:
            raise ValueError('Inconsistent cell-line identity in the dataset.')
        key = (c['cellosaurus'], str(c['drug']).strip().lower(), dose, int(c['plate']))
        if key in groups:
            raise ValueError('Duplicate line/drug/dose/plate rows; resolve sample identities before evaluation.')
        groups[key] = i
    return groups


def metrics(observed, predictions, min_genes=100):
    mask = np.isfinite(observed)
    for pred in predictions.values():
        if pred.shape != observed.shape:
            raise ValueError('Prediction and observation shapes differ.')
        mask &= np.isfinite(pred)
    if mask.sum() < min_genes:
        raise ValueError('Too few genes with observed and predicted values in common.')
    truth = observed[mask].astype(np.float64)
    out = {}
    for model, pred in predictions.items():
        pred = pred[mask].astype(np.float64); error = pred - truth
        x, y = pred - pred.mean(), truth - truth.mean()
        den = float(np.linalg.norm(x) * np.linalg.norm(y))
        out[model] = {'mae': float(np.abs(error).mean()), 'mse': float(np.square(error).mean()),
                      'pearson': float(np.dot(x, y) / den) if den > 0 else None, 'genes': int(mask.sum())}
    return out, mask


def crossed_interval(rows, model, metric, seed=17, baseline=None, draws=1000):
    """Pigeonhole bootstrap: resample whole lines and compounds, never genes/cells."""
    lines = sorted({r['cellosaurus'] for r in rows}); drugs = sorted({r['drug'] for r in rows})
    values = [r['metrics'][model][metric] for r in rows]
    ok = np.array([x is not None for x in values])
    if not ok.any():
        return {'mean': None, 'ci95': None, 'n': 0}
    v = np.array([x if x is not None else 0.0 for x in values], float)
    if baseline:
        b = [r['metrics'][baseline][metric] for r in rows]
        ok &= np.array([x is not None for x in b]); v -= np.array([x or 0.0 for x in b])
    li = np.array([lines.index(r['cellosaurus']) for r in rows]); di = np.array([drugs.index(r['drug']) for r in rows])
    rng = np.random.default_rng(seed); samples = []
    if ok.any() and len(lines) >= 3 and len(drugs) >= 3:
        for _ in range(draws):
            lw = np.bincount(rng.integers(len(lines), size=len(lines)), minlength=len(lines))
            dw = np.bincount(rng.integers(len(drugs), size=len(drugs)), minlength=len(drugs))
            weights = lw[li] * dw[di] * ok
            if weights.sum():
                samples.append(float(np.dot(weights, v) / weights.sum()))
    return {'mean': float(v[ok].mean()) if ok.any() else None,
            'ci95': np.quantile(samples, [.025, .975]).tolist() if samples else None, 'n': int(ok.sum())}


def _contexts(root, split):
    """Independent untreated RNA inputs; select and normalise features on train lines."""
    folder = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4'
    meta = json.loads((folder / 'expression.json').read_text())
    raw = np.load(folder / 'expression.npy', mmap_mode='r', allow_pickle=False)
    return meta, raw


def _neighbours(root, atlas, split):
    meta, raw = _contexts(root, split)
    line_ids = sorted(split['train'] + split['validation'] + split['test'])
    try:
        indices = [meta['models'].index(atlas.lines[line]['depmap']) for line in line_ids]
    except ValueError as e:
        raise ValueError('Missing untreated DepMap profile for a Tahoe line.') from e
    x = np.asarray(raw[indices], dtype=np.float64)
    train = np.array([line_ids.index(line) for line in split['train']])
    finite = np.isfinite(x[train]).all(axis=0)
    variance = np.var(x[train], axis=0)
    selected = np.where(finite & (variance > .01))[0]
    selected = selected[np.argsort(-variance[selected], kind='stable')[:256]]
    if len(selected) < 20:
        raise ValueError('Too few finite variable untreated RNA features in training lines.')
    center = x[train][:, selected].mean(axis=0); scale = x[train][:, selected].std(axis=0)
    z = (x[:, selected] - center) / scale
    if not np.isfinite(z).all():
        raise ValueError('Missing untreated RNA inputs; no zero imputation permitted.')
    neighbours = {}
    for line, profile in zip(line_ids, z):
        distance = np.square(z[train] - profile).mean(axis=1)
        neighbours[line] = [split['train'][i] for i in np.argsort(distance, kind='stable')]
    return neighbours, {'model': 'nearest-context/1', 'features': [meta['genes'][i] for i in selected],
                        'center': center.tolist(), 'scale': scale.tolist(), 'selection': '256 highest-variance genes in training untreated bulk RNA only'}


def evaluate(root, seed=17, conditions_per_line=8):
    """Reads the library only. Returns a report and arrays; caller owns output storage."""
    import virtual_cell_drugs as VD
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError('Seed must be a nonnegative 32-bit integer.')
    if type(conditions_per_line) is not int or not 1 <= conditions_per_line <= 12:
        raise ValueError('Choose 1–12 conditions per line for this bounded pilot.')
    started = time.monotonic(); A = VD.atlas(root)
    if A is None or not A.complete:
        raise ValueError('A completed Tahoe-100M atlas is required; no downloads are started.')
    untreated, _ = _contexts(root, None)
    eligible = {line for line in A.lines if A.lines[line]['depmap'] in untreated['models']}
    excluded = [{'cellosaurus': line, 'cellLine': A.lines[line]['name'], 'reason': 'No matching untreated DepMap 24Q4 RNA profile'} for line in sorted(set(A.lines) - eligible)]
    split = split_lines(eligible, seed); assert_split(split)
    rows = group_rows(A.conditions)
    neighbours, nn = _neighbours(root, A, split)
    train_set = set(split['train']); train_rows = {k: r for k, r in rows.items() if k[0] in train_set and 1 <= k[3] <= 10}
    donor_groups = {}
    for (line, drug, dose, plate), row in train_rows.items():
        donor_groups.setdefault((drug, dose), {}).setdefault(line, []).append(row)
    # Same prespecified metadata-only condition sample for each evaluation line.
    def selected_keys(lines, plates):
        possible = sorted({(drug, dose) for (line, drug, dose, plate) in rows if line in lines and plate in plates
                           and len(donor_groups.get((drug, dose), {})) >= 10})
        return sorted(possible, key=lambda k: _hash([PROTOCOL, seed, list(k)]))[:conditions_per_line]
    keys = {'validation': selected_keys(set(split['validation']), {11, 12}), 'test': selected_keys(set(split['test']), {13, 14})}
    if any(not v for v in keys.values()):
        raise ValueError('No independently held-out plate/line targets with at least ten training donors.')
    # Baseline fit uses a fixed metadata-only sample of up to 128 conditions PER train line.
    generic_per_line = []; generic_rows = []
    for line in split['train']:
        candidates = [(k, r) for k, r in train_rows.items() if k[0] == line]
        candidates.sort(key=lambda x: _hash([PROTOCOL, seed, list(x[0])]))
        picked = [r for _, r in candidates[:128]]; generic_rows.extend(picked)
        generic_per_line.append(_mean(np.asarray(A.lfc[picked], np.float64)))
    generic = _mean(np.vstack(generic_per_line))
    donor_cache = {}
    for key in set(keys['validation'] + keys['test']):
        donors = donor_groups[key]
        donor_cache[key] = {line: _mean(np.asarray(A.lfc[sorted(rs)], np.float64)) for line, rs in sorted(donors.items())}
    scores = {'validation': [], 'test': []}; artifacts = {}; counters = {'missing_targets': 0, 'insufficient_genes': 0}
    training_ids = set(generic_rows)
    for mode, plates in (('validation', {11, 12}), ('test', {13, 14})):
        for line in split[mode]:
            for drug, dose in keys[mode]:
                target_rows = sorted(r for (l, d, c, p), r in rows.items() if l == line and d == drug and c == dose and p in plates)
                if not target_rows:
                    counters['missing_targets'] += 1; continue
                donors = donor_cache[(drug, dose)]; nearest = next(d for d in neighbours[line] if d in donors)
                used = sorted(r for rs in donor_groups[(drug, dose)].values() for r in rs)
                if set(used) & set(target_rows) or any(A.conditions[r]['cellosaurus'] not in train_set or int(A.conditions[r]['plate']) > 10 for r in used):
                    raise ValueError('Train/test leakage detected.')
                training_ids.update(used)
                observed = _mean(np.asarray(A.lfc[target_rows], np.float64))
                predicted = {'unchanged': np.zeros(len(A.genes)), 'training_mean': generic,
                             'drug_dose_mean': _mean(np.vstack(list(donors.values()))), 'nearest_context': donors[nearest]}
                try:
                    ms, mask = metrics(observed, predicted)
                except ValueError:
                    counters['insufficient_genes'] += 1; continue
                index = len(scores[mode]); prefix = mode + '_' + str(index)
                artifacts[prefix + '_observed'] = observed
                artifacts[prefix + '_mask'] = mask
                for model, pred in predicted.items():
                    artifacts[prefix + '_' + model] = pred
                scores[mode].append({'cellosaurus': line, 'cellLine': A.lines[line]['name'], 'drug': drug, 'concentration': dose, 'unit': 'uM',
                                     'targetRows': target_rows, 'targetPlates': sorted({A.conditions[r]['plate'] for r in target_rows}),
                                     'donorRows': used, 'donorLines': sorted(donors), 'nearestDonor': nearest, 'artifactPrefix': prefix, 'metrics': ms})
    if any(not values for values in scores.values()):
        raise ValueError('No evaluable validation or test observations; no successful report will be saved.')
    summaries = {}
    for mode, rs in scores.items():
        summaries[mode] = {model: {metric: crossed_interval(rs, model, metric, seed) for metric in ('mae', 'mse', 'pearson')} for model in MODELS}
    contrasts = {model: crossed_interval(scores['test'], model, 'mse', seed, baseline='training_mean') for model in ('drug_dose_mean', 'nearest_context')}
    observed_keys = {k for mode in scores.values() for row in mode for k in row['targetRows']}
    if training_ids & observed_keys:
        raise ValueError('Baseline training data overlaps evaluation targets.')
    folder = pathlib.Path(root) / 'virtualcell' / 'data' / 'tahoe100m'
    depmap = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4'
    files = [folder / name for name in ('conditions.json', 'genes.json', 'manifest.json', 'progress.json', 'lfc.f16')]
    files += [depmap / 'expression.json', depmap / 'expression.npy']
    # Full hashes, including the 2.3 GB input matrix; no writable shared hash cache.
    inputs = [{'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': file_hash(path)} for path in files]
    artifacts['genes'] = np.asarray(A.genes, dtype=str)
    artifacts['training_mean'] = generic
    report = {'schema': SCHEMA, 'protocol': PROTOCOL, 'status': 'benchmarked', 'evidence': 'prediction compared with held-out measurements',
              'dataset': {'id': 'tahoe100m', 'source': 'https://huggingface.co/datasets/tahoebio/Tahoe-100M', 'licence': 'CC0-1.0',
                          'measurement': 'pseudobulk_differential_expression', 'unit': 'DESeq2 log2 fold change versus DMSO', 'conditions': len(A.conditions), 'genes': len(A.genes)},
              'config': {'seed': seed, 'conditionsPerLine': conditions_per_line, 'trainingBaselineSamplePerLine': 128},
              'split': {**split, 'trainPlates': list(range(1, 11)), 'validationPlates': [11, 12], 'testPlates': [13, 14]},
              'selection': {'rule': 'SHA-256 of protocol, seed, drug and dose; no test-response access', 'keys': {mode: [list(k) for k in values] for mode, values in keys.items()}},
              'trainingRows': sorted(training_ids), 'baselineRows': sorted(generic_rows), 'models': MODEL_LABELS, 'nearestContextFit': nn,
              'summary': summaries, 'testMseDifferenceVsTrainingMean': contrasts, 'results': scores, 'skipped': counters, 'excludedContexts': excluded,
              'metricDefinition': 'Per-condition MAE, MSE and Pearson correlation over the identical finite genes for every model; macro-average over conditions. Constant-vector Pearson is undefined (null).',
              'uncertainty': {'method': '1000 crossed cell-line/compound bootstrap draws, percentile 95% intervals', 'predictiveCalibration': 'not established', 'note': 'Conditions and genes are not independent experimental replicates.'},
              'promotion': {'recommendedDefault': False, 'reason': 'Pilot, two test plates, no independent-dataset validation; existing model routing is unchanged.'},
              'inputs': inputs, 'software': {'python': platform.python_version(), 'numpy': np.__version__, 'implementationSha256': file_hash(__file__)},
              'limitations': LIMITATIONS, 'seconds': round(time.monotonic() - started, 3)}
    return report, artifacts


def save(root, report, arrays):
    folder = pathlib.Path(root).joinpath(*FOLDER); folder.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex; dest = folder / run_id; dest.mkdir()
    np.savez_compressed(dest / 'predictions.npz', **arrays)
    rec = {**report, 'id': run_id, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'artifacts': [{'path': 'predictions.npz', 'sha256': file_hash(dest / 'predictions.npz')}], 'complete': True}
    rec['sha256'] = _hash(rec)
    temp = dest / 'result.partial'; temp.write_text(json.dumps(rec, indent=1, allow_nan=False)); temp.replace(dest / 'result.json')
    return rec


def load(root, run_id):
    if not re.fullmatch(r'[0-9a-f]{32}', str(run_id)):
        raise ValueError('Invalid benchmark identifier.')
    folder = pathlib.Path(root).joinpath(*FOLDER, run_id)
    rec = json.loads((folder / 'result.json').read_text()); digest = rec.pop('sha256', None)
    if rec.get('id') != run_id or rec.get('schema') != SCHEMA or rec.get('complete') is not True or _hash(rec) != digest:
        raise ValueError('Benchmark report integrity failed.')
    for artifact in rec.get('artifacts', []):
        if artifact['path'] != 'predictions.npz' or file_hash(folder / artifact['path']) != artifact['sha256']:
            raise ValueError('Benchmark prediction artifact integrity failed.')
    return {**rec, 'sha256': digest}


def listing(root, cellosaurus=None):
    rows = []
    folder = pathlib.Path(root).joinpath(*FOLDER)
    if folder.exists():
        for path in sorted(folder.glob('*/result.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            rec = load(root, path.parent.name)
            role = next((part for part in ('test', 'validation', 'train') if cellosaurus in rec['split'][part]), None)
            rows.append({'id': rec['id'], 'created': rec['created'], 'protocol': rec['protocol'], 'status': rec['status'],
                         'summary': rec['summary']['test'], 'contextRole': role,
                         'contextNote': 'No benchmark targets for this context.' if not role else f'This context is in the {role} split; global test scores cover all test lines.',
                         'testConditions': len(rec['results']['test']), 'limitations': rec['limitations']})
    return rows


def run(root, seed=17, conditions_per_line=8):
    report, arrays = evaluate(root, seed, conditions_per_line)
    return save(root, report, arrays)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library'); parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--conditions-per-line', type=int, default=8)
    args = parser.parse_args(); result = run(args.library, args.seed, args.conditions_per_line)
    print(json.dumps({'id': result['id'], 'seconds': result['seconds'], 'test': result['summary']['test'], 'contrasts': result['testMseDifferenceVsTrainingMean']}, indent=2))
