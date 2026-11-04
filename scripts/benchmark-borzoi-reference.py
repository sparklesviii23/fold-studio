#!/usr/bin/env python3
"""One prespecified FABP1 held-out-locus check; never starts model inference.

Requires NumPy, SciPy and pyBigWig. Fetches official metadata and range-reads
ENCODE signal. Original ENCODE coverage is not the authors' reprocessed .w5 target:
report rank association only, preserving separate units and that limitation.
"""
import argparse
import csv
import gzip
import hashlib
import json
import pathlib
import sys
import urllib.request

import numpy as np
import pyBigWig
from scipy.stats import spearmanr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import virtual_cell_benchmarks as B
import virtual_cell_regulatory as R

PIN = 'f10f8c799639dd2cfc0c1eb09499bfc47ab9cf8a'
REGION = ('chr2', 88023337, 88219945)
ACC = 'ENCFF065PJM'


def fetch(url, path):
    if not path.exists():
        with urllib.request.urlopen(url, timeout=90) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000: raise ValueError('Reference metadata exceeds the bounded size.')
        temp = path.with_suffix('.partial'); temp.write_bytes(raw); temp.replace(path)
    return path.read_bytes()


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    bed_url = f'https://raw.githubusercontent.com/calico/borzoi/{PIN}/data/sequences_human.bed.gz'
    bed = fetch(bed_url, folder / 'sequences_human.bed.gz')
    wanted = '\t'.join(map(str, REGION)) + '\tfold3'
    if wanted not in gzip.decompress(bed).decode().splitlines(): raise ValueError('Prespecified region is not in official fold3.')
    url = f'https://www.encodeproject.org/files/{ACC}/?format=json'
    meta = json.loads(fetch(url, folder / f'{ACC}.json'))
    if meta.get('assembly') != 'GRCh38' or meta.get('accession') != ACC or meta.get('dataset') != '/experiments/ENCSR000CPE/' or meta.get('output_type') != 'plus strand signal of unique reads':
        raise ValueError('ENCODE reference assembly, assay, experiment or strand mismatch.')
    if 'Cellosaurus:CVCL_0027' not in meta.get('biosample_ontology', {}).get('dbxrefs', []): raise ValueError('ENCODE reference is not identified as parental HepG2.')
    data_url = f'https://www.encodeproject.org/files/{ACC}/@@download/{ACC}.bigWig'
    npz = folder / 'FABP1-reference.npz'; manifest_path = folder / 'FABP1-reference.json'
    if npz.exists() and manifest_path.exists():
        receipt = json.loads(manifest_path.read_text())
        if receipt['arraySha256'] != B.file_hash(npz) or receipt['bedSha256'] != hashlib.sha256(bed).hexdigest() or receipt['metadataSha256'] != B.file_hash(folder / f'{ACC}.json'):
            raise ValueError('Reference cache integrity failed.')
        return receipt
    if not pyBigWig.remote: raise ValueError('This pyBigWig build lacks remote range reading; no silent full-file download.')
    # Resolve ENCODE's official redirect with urllib; libBigWig cannot follow
    # this redirect reliably on all builds. Never persist expiring redirect URLs.
    request = urllib.request.Request(data_url, headers={'Range': 'bytes=0-63'})
    with urllib.request.urlopen(request, timeout=90) as response:
        resolved_url = response.geturl(); response.read(64)
    bw = pyBigWig.open(resolved_url)
    if bw is None: raise ValueError('Cannot open the official ENCODE reference.')
    try:
        values = np.asarray(bw.values(*REGION, numpy=True), dtype=np.float64)
    finally: bw.close()
    if values.shape != (196608,): raise ValueError('Reference interval length mismatch.')
    bins = values.reshape(-1, 32); finite = np.isfinite(bins).all(axis=1)
    # Uncovered bigWig bases are missing, not silently interpreted as zero.
    signal = np.full(len(bins), np.nan); signal[finite] = bins[finite].sum(axis=1)
    np.savez_compressed(npz, signal=signal, finite=finite)
    receipt = {'schema': 'fold.borzoi.reference/1', 'region': list(REGION), 'coordinateConvention': 'zero-based half-open',
               'assembly': 'GRCh38', 'cellosaurus': 'CVCL_0027', 'fold': 'fold3', 'source': data_url, 'accession': ACC,
               'publishedBigWigMd5': meta['md5sum'], 'download': 'remote byte ranges; full-file MD5 not independently verified',
               'bedSource': bed_url, 'bedSha256': hashlib.sha256(bed).hexdigest(), 'metadataSha256': B.file_hash(folder / f'{ACC}.json'),
               'arraySha256': B.file_hash(npz), 'binSize': 32, 'finiteBins': int(finite.sum()), 'bins': len(bins),
               'unit': 'sum of ENCODE plus-strand unique-read signal over 32 fully covered bases',
               'software': {'pyBigWig': pyBigWig.__version__, 'numpy': np.__version__},
               'limitations': 'Author .w5 reprocessing/normalisation not reproduced; original bigWig is an assay reference, not identical transformed training-target truth.'}
    manifest_path.write_text(json.dumps(receipt, indent=1)); return receipt


def compare(root, run, folder, expected_sequence_sha256):
    receipt = prepare(folder); track = R.get(root, run, 'CVCL_0027')
    if not track['supported']: raise ValueError(track['reason'])
    task, job = R._task(root, run)
    result = json.loads(R._artifact(task, job, 'result.json', 2_000_000))
    if result['reference']['sequenceSha256'] != expected_sequence_sha256 or result['trackIndex'] != 6226:
        raise ValueError('Result differs from the prespecified sequence or track.')
    rows = list(csv.DictReader(R._artifact(task, job, 'regulatory-track.csv', 5_000_000).decode().splitlines()))
    selected = [row for row in rows if int(row['start_0based']) >= REGION[1] and int(row['end_exclusive']) <= REGION[2]]
    starts = np.array([int(r['start_0based']) for r in selected]); expected = np.arange(REGION[1], REGION[2], 32)
    if not np.array_equal(starts, expected): raise ValueError('Prediction bins do not align exactly with held-out reference bins.')
    predicted = np.array([float(r['raw_model_value']) for r in selected], np.float64)
    with np.load(folder / 'FABP1-reference.npz', allow_pickle=False) as z: observed = z['signal'].copy(); mask = z['finite'].copy()
    mask &= np.isfinite(predicted)
    if mask.sum() < 20 or np.ptp(predicted[mask]) == 0 or np.ptp(observed[mask]) == 0:
        raise ValueError('Insufficient nonconstant held-out reference signal; no correlation claimed.')
    rank = float(spearmanr(predicted[mask], observed[mask]).statistic)
    preview = []
    for i in range(0, len(predicted), 16):
        obs = observed[i:i+16]; good = mask[i:i+16]
        if not good.any(): continue
        preview.append({'start': int(starts[i]), 'end': int(starts[min(i+15, len(starts)-1)]+32),
                        'predictedMean': float(predicted[i:i+16][good].mean()), 'observedMean': float(obs[good].mean())})
    dest = pathlib.Path(root) / 'virtualcell/regulatory-comparisons' / run; dest.mkdir(parents=True, exist_ok=True)
    with (dest / 'comparison.csv').open('w') as f:
        writer = csv.writer(f); writer.writerow(['chromosome', 'start_0based', 'end_exclusive', 'predicted_raw_transformed', 'observed_unique_read_signal_sum', 'scored'])
        for start, p, o, ok in zip(starts, predicted, observed, mask): writer.writerow([REGION[0], int(start), int(start+32), p, o if np.isfinite(o) else '', bool(ok)])
    out = {'schema': 'fold.virtualcell.regulatory-comparison/1', 'run': run, 'region': list(REGION), 'fold': 'fold3',
           'status': 'held-out locus check; not genome-wide validation', 'reference': receipt, 'checkpointSha256': track['checkpointSha256'],
           'modelResultSha256': next(a['sha256'] for a in task['outputs'] if a['path'] == 'result.json'),
           'sequenceSha256': expected_sequence_sha256, 'spearman': rank, 'scoredBins': int(mask.sum()), 'totalBins': len(mask),
           'predictedUnit': track['unit'], 'observedUnit': receipt['unit'], 'preview': preview,
           'csvSha256': B.file_hash(dest / 'comparison.csv'), 'uncertainty': 'No calibrated predictive interval; bins are spatially correlated, not independent replicates.',
           'limitations': [receipt['limitations'], 'One prespecified locus in an assay included in training, evaluated at held-out genomic coordinates.',
                           f'Only {int(mask.sum())} of {len(mask)} bins have complete reference coverage. Missing/omitted bigWig regions are not zero-filled; the score is conditional on covered bins.',
                           'Display points average matching eligible bins within 512-bp windows; gaps are retained as gaps.',
                           'Rank association only; no count calibration, exact author-target reproduction, universal phenotype inference, baseline superiority or AIDO parity.'],
           'software': {'comparisonScriptSha256': B.file_hash(__file__), 'numpy': np.__version__, 'pyBigWig': pyBigWig.__version__}}
    out['sha256'] = B._hash(out)
    temp = dest / 'comparison.partial'; temp.write_text(json.dumps(out, indent=1, allow_nan=False)); temp.replace(dest / 'comparison.json')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--library', required=True)
    parser.add_argument('--reference-dir', type=pathlib.Path, required=True); parser.add_argument('--run')
    parser.add_argument('--expected-sequence-sha256'); parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.prepare_only: result = prepare(args.reference_dir)
    else:
        if not args.run or not args.expected_sequence_sha256: parser.error('Comparison requires --run and --expected-sequence-sha256.')
        result = compare(args.library, args.run, args.reference_dir, args.expected_sequence_sha256)
    print(json.dumps({k: v for k, v in result.items() if k != 'preview'}, indent=1))
