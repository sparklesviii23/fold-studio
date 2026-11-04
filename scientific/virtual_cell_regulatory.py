"""Read-only bridge from completed Biological Models jobs to Virtual Cell tracks.

Does not launch jobs, change the cell state, infer phenotype, or relabel raw model
coverage as TPM. Every file is checked against the existing job artifact manifest.
"""
import csv
import hashlib
import io
import json
import math
import pathlib
import re

from virtual_cell_registry import unsupported


def _context(metadata):
    description = metadata.get('description', '')
    if re.search(r'(?:^|:)HepG2(?:$|[ ,])', description): return 'CVCL_0027'
    if re.search(r'(?:^|:)K-?562(?:$|[ ,])', description): return 'CVCL_0004'
    return None


def _task(root, run):
    if not re.fullmatch(r'[0-9a-f]{32}', str(run)): raise ValueError('Invalid model job identifier.')
    folder = pathlib.Path(root) / 'gpu_tasks' / run
    task = json.loads((folder / 'task.json').read_text())
    if task.get('id') != run or task.get('recipe') != 'bio_borzoi': raise ValueError('Not a Borzoi job.')
    return task, folder


def _artifact(task, folder, name, limit):
    entry = next((f for f in task.get('outputs', []) if f['path'] == name), None)
    path = folder / 'outputs' / name
    if not entry or path.stat().st_size > limit: raise ValueError('Missing or oversized regulatory artifact.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']: raise ValueError('Regulatory artifact checksum mismatch.')
    return raw


def get(root, run, cellosaurus, include_values=False):
    task, folder = _task(root, run)
    if task.get('state') != 'done' or task.get('fetchError'):
        return unsupported('vcell.regulatory', 'The Borzoi job has no completed, retrieved result.', ['completed bio_borzoi job'])
    result = json.loads(_artifact(task, folder, 'result.json', 2_000_000))
    if result.get('schema') != 'fold-studio.biological-model-result.v1' or result.get('recipe') != 'bio_borzoi' or result.get('inputsSha256') != task.get('inputsSha256'):
        raise ValueError('Regulatory result identity mismatch.')
    source_context = _context(result.get('trackMetadata', {}))
    if source_context is None or source_context != cellosaurus:
        return unsupported('vcell.regulatory', 'The selected assay does not establish compatibility with this cell line.', ['an explicitly matching cell-line assay'])
    inputs = task.get('inputs', {}); ref = result.get('reference', {})
    if hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest() != task.get('inputsSha256'):
        raise ValueError('Regulatory task inputs checksum mismatch.')
    if ref.get('assembly') != 'hg38' or ref.get('chromosome') != inputs.get('chromosome') or ref.get('start') != inputs.get('start') or ref.get('end') != inputs.get('start', -1) + 524288:
        raise ValueError('Regulatory reference assembly or coordinates mismatch.')
    bins, width, start = result.get('bins'), result.get('binSize'), result.get('outputStart')
    if type(bins) is not int or not 1 <= bins <= 16384 or width != 32 or type(start) is not int or start < ref['start'] or start + bins*width > ref['end']:
        raise ValueError('Invalid regulatory bin geometry.')
    if result.get('trackIndex') != inputs.get('track') or not re.fullmatch(r'[0-9a-f]{64}', result.get('checkpointSha256', '')):
        raise ValueError('Regulatory track or checkpoint identity mismatch.')
    values = []
    for i, row in enumerate(csv.DictReader(io.StringIO(_artifact(task, folder, 'regulatory-track.csv', 5_000_000).decode()))):
        value = float(row['raw_model_value'])
        if i >= bins or row['chromosome'] != ref['chromosome'] or int(row['start_0based']) != start+i*width or int(row['end_exclusive']) != start+(i+1)*width or not math.isfinite(value) or value < 0:
            raise ValueError('Regulatory track contains invalid coordinates or values.')
        values.append(value)
    if len(values) != bins: raise ValueError('Regulatory track is truncated.')
    stride = max(1, math.ceil(bins / 512)); preview = []
    for i in range(0, bins, stride):
        block = values[i:i+stride]
        preview.append({'start': start+i*width, 'end': start+(i+len(block))*width, 'min': min(block), 'max': max(block), 'mean': sum(block)/len(block)})
    comparison = None; comp_folder = pathlib.Path(root) / 'virtualcell/regulatory-comparisons' / run
    if (comp_folder / 'comparison.json').is_file():
        comp = json.loads((comp_folder / 'comparison.json').read_text()); digest = comp.pop('sha256', None)
        actual = hashlib.sha256(json.dumps(comp, sort_keys=True, allow_nan=False).encode()).hexdigest()
        csv_hash = hashlib.sha256((comp_folder / 'comparison.csv').read_bytes()).hexdigest()
        result_hash = next(f['sha256'] for f in task['outputs'] if f['path'] == 'result.json')
        if digest != actual or comp.get('run') != run or comp.get('schema') != 'fold.virtualcell.regulatory-comparison/1' or comp.get('checkpointSha256') != result['checkpointSha256'] or comp.get('modelResultSha256') != result_hash or comp.get('csvSha256') != csv_hash:
            raise ValueError('Regulatory comparison integrity or model identity failed.')
        comparison = {**comp, 'sha256': digest}
    return {**({'values': {f"{ref['chromosome']}:{start+i*width}-{start+(i+1)*width}": v for i, v in enumerate(values)}} if include_values else {}),
            'supported': True, 'run': run, 'evidence': 'prediction', 'status': 'integrated; one held-out locus checked' if comparison else 'integrated; independent benchmark pending',
            'context': source_context, 'reference': ref, 'coordinateConvention': 'zero-based half-open', 'track': result['trackMetadata'],
            'trackIndex': result['trackIndex'], 'binSize': width, 'bins': bins, 'start': start, 'end': start+bins*width,
            'unit': result.get('outputUnit', 'raw transformed assay coverage'), 'preview': preview,
            'model': result.get('model'), 'checkpointSha256': result['checkpointSha256'], 'sourceRevision': result.get('sourceRevision'),
            'comparison': comparison, 'uncertainty': result.get('uncertainty', {'supported': False, 'reason': 'Not reported by this older run.'}),
            'note': 'The prediction describes an assay on reference DNA, not this cell’s measured RNA, transcript TPM, causal regulatory network or whole-cell phenotype.'}


def listing(root, cellosaurus):
    folder = pathlib.Path(root) / 'gpu_tasks'; rows = []
    for path in sorted(folder.glob('*/task.json')) if folder.exists() else []:
        task = json.loads(path.read_text())
        if task.get('recipe') == 'bio_borzoi':
            rows.append({'run': task['id'], 'created': task.get('created'), 'jobState': task.get('state'),
                         'trackIndex': task.get('inputs', {}).get('track'), 'context': cellosaurus})
    return {'runs': rows, 'note': 'Only completed, checksum-verified results with an explicitly matching assay can be opened. Submit inference through the existing Biological Models workbench.'}
