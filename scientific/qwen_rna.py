"""Project-scoped Qwen RNA jobs, immutable evidence, and explicit Library saves."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import uuid

from qwen_rna_actions import ACTIONS
from qwen_rna_contract import accuracy, clean, digest, pairs

HERE = pathlib.Path(__file__).resolve().parent


def install_config(path):
    """Read an install receipt and expand ${FOLD_WORKSPACE} in its paths."""
    import workspace
    config = json.loads(path.read_text())
    for key in ('checkpoint', 'python', 'trainingRuntime'):
        if key in config:
            config[key] = workspace.expand(config[key])
    if 'sitePackages' in config:
        config['sitePackages'] = [workspace.expand(p) for p in config['sitePackages']]
    return config


def installation():
    path = HERE / 'qwen_rna_install.json'
    if not path.is_file():
        raise ValueError('Qwen RNA is not configured. See docs/QWEN_RNA_ENGINE.md for the local runtime and checkpoint contract.')
    config = install_config(path)
    checkpoint = pathlib.Path(config['checkpoint'])
    if not checkpoint.is_file() or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != config['checkpointSha256']:
        raise ValueError('Qwen RNA checkpoint receipt is missing or changed. Requalify the checkpoint before use.')
    if not pathlib.Path(config['python']).is_file():
        raise ValueError('The qualified Qwen PyTorch runtime is missing: ' + config['python'])
    return config, json.loads(checkpoint.read_text())


def run_folder(s, identity, project):
    if not isinstance(identity, str) or not re.fullmatch('[a-f0-9-]{36}', identity) or str(uuid.UUID(identity)) != identity:
        raise ValueError('Choose a saved Qwen RNA run.')
    job = s.job(identity)
    if job['engine'] != 'qwen-rna' or job['project_id'] != project:
        raise ValueError('Qwen RNA run does not belong to this project.')
    return s.root / 'jobs' / identity, job


def read_result(folder):
    value = json.loads((folder / 'result.json').read_text())
    if value['sha256'] != digest({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('Saved RNA prediction integrity check failed.')
    return value


def catalog():
    try:
        install, checkpoint = installation()
        benchmark = json.loads((pathlib.Path(install['checkpoint']).parent / 'benchmark.json').read_text())
        ready, issue = True, None
    except (OSError, ValueError, KeyError) as e:
        install, checkpoint, benchmark, ready, issue = {}, {}, None, False, str(e)
    demo = json.loads((HERE / 'qwen_rna_demo.json').read_text())
    return {'ready': ready, 'issue': issue, 'version': '0.1.0', 'demo': demo,
            'checkpoints': checkpoint.get('selected', {}), 'benchmark': benchmark,
            'baseline': json.loads((HERE / 'qwen_rna_benchmark.json').read_text()),
            'engines': [
                {'id': 'qwen_adapter', 'title': 'Native Qwen · research candidate', 'inputs': ['8–128 ACGU nucleotides'],
                 'outputs': ['pair marginals', 'nested dot-bracket fold', 'base and region entropy'],
                 'runtime': install.get('python'), 'evidence': '48 ArchiveII 5S reference annotations; family-held-out pilot',
                 'version': '0.1.0', 'trained': ['scientific pair head', 'last two Qwen layers: rank-8 query/value adapters'],
                 'limits': 'Low cross-family accuracy; uncalibrated uncertainty; no 3D or cellular-function prediction.'},
                {'id': 'qwen_frozen', 'title': 'Frozen Qwen + scientific head', 'version': '0.1.0'},
                {'id': 'compact', 'title': 'RNA-only control', 'version': '0.1.0'}],
            'verification': {'id': 'builtin-nn', 'version': 'rna-lab.fold/1.0.0',
                             'inputs': ['same exact RNA sequence'], 'outputs': ['MFE dot-bracket structure', 'kcal/mol energy', 'pair disagreement'],
                             'runtime': 'standard-library RNA Lab solver',
                             'evidence': 'Reduced nearest-neighbour thermodynamic model; see RNA Lab validation',
                             'policy': 'Explicit opt-in; check when native mean partner entropy > 1 bit. Rule-based policy, not a learned tool router.'},
            'deferred': {'3d': 'Needs matched sequence/3D training corpus, geometry head and independent RNA3DB-style split; current secondary head emits no coordinates.',
                         'design': 'No inverse-trained Qwen weights yet. Existing specialist design workflows remain separate.',
                         'cell': 'Needs one defined context, measured persistence/partner outcome, time and assay units. K562 CRISPRa expression response is a separate preserved capability.'}}


def start(s, p):
    s.project(p['projectId'])
    sequence = clean(p.get('sequence'))
    reference = p.get('reference') or None
    if reference:
        if not isinstance(reference, str) or len(reference) != len(sequence):
            raise ValueError('Reference must have one dot-bracket character per nucleotide.')
        pairs(reference)
    arm = p.get('engine', 'qwen_adapter')
    if arm not in ('qwen_adapter', 'qwen_frozen', 'compact'):
        raise ValueError('Choose a qualified RNA checkpoint.')
    if type(p.get('verify', False)) is not bool:
        raise ValueError('Verification must be explicitly enabled or disabled.')
    config, checkpoint = installation()
    if s.active() or s.rows("SELECT id FROM jobs WHERE engine='qwen-rna' AND state IN ('queued','running') LIMIT 1"):
        raise ValueError('Finish the active local scientific run before loading Qwen.')
    inputs = {'projectId': p['projectId'], 'name': 'Qwen RNA · ' + str(len(sequence)) + ' nt',
              'sequence': sequence, 'reference': reference, 'engine': arm, 'verify': p.get('verify', False),
              'checkpoint': config['checkpoint'], 'checkpointSha256': config['checkpointSha256'],
              'inputsSha256': digest({'sequence': sequence, 'reference': reference, 'engine': arm, 'verify': p.get('verify', False)})}
    job = s.job_new(inputs, 'qwen-rna', 'queued')
    folder = s.root / 'jobs' / job['id']
    folder.mkdir()
    (folder / 'request.json').write_text(json.dumps(inputs, indent=2) + '\n')
    runtime = HERE / 'qwen_rna_runtime.py'
    try:
        env = {k:v for k,v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH', '__PYVENV_LAUNCHER__', 'PYTHONEXECUTABLE', 'VIRTUAL_ENV')}
        env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false', PYTHONNOUSERSITE='1')
        if config.get('sitePackages'):
            env['PYTHONPATH'] = os.pathsep.join(config['sitePackages'])
        with (folder / 'execution.log').open('w') as log:
            child = subprocess.Popen([sys.executable, '-B', str(runtime), '--supervise', '--python', config['python'], '--root', str(s.root), '--job', job['id']],
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        s.job_metadata(job['id'], {'pid': child.pid, 'workerPath': str(runtime)})
    except Exception as e:
        s.job_update(job['id'], 'failed', {'error': str(e)})
        raise
    return s.job(job['id'])


def save(s, p):
    folder, job = run_folder(s, p['id'], p['projectId'])
    if job['state'] != 'completed':
        raise ValueError('Wait for a completed RNA prediction before saving.')
    out = read_result(folder)
    for row in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis'", (p['projectId'],)):
        data = json.loads(row['data'])
        if data.get('domain') == 'qwen_rna' and data.get('runId') == job['id']:
            row['data'] = data
            return row
    return s.record_save({'projectId': p['projectId'], 'kind': 'analysis',
                          'name': str(p.get('name') or 'RNA fold · ' + out['sequence'][:18]),
                          'data': {'domain': 'qwen_rna', 'runId': job['id'], 'sequence': out['sequence'],
                                   'structure': out['structure'], 'sha256': out['sha256'],
                                   'source': 'Native ' + out['provenance']['engine'] + ' · secondary structure prediction',
                                   'result': out, 'hasAtomicCoordinates': False}})


def dispatch(s, action, p):
    if action == 'qwen_rna_catalog':
        return catalog()
    if action == 'qwen_rna_start':
        return start(s, p)
    if action == 'qwen_rna_run':
        folder, job = run_folder(s, p['id'], p['projectId'])
        out = read_result(folder) if (folder / 'result.json').is_file() and job['state'] == 'completed' else None
        return {'job': s.job_read({'id': job['id']}), 'result': out}
    if action == 'qwen_rna_save':
        return save(s, p)
    if action == 'qwen_rna_history':
        s.project(p['projectId'])
        rows = s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='qwen-rna' ORDER BY created DESC LIMIT 30", (p['projectId'],))
        return [s.job(row['id']) for row in rows]
    if action == 'qwen_rna_measure':
        folder, job = run_folder(s, p['id'], p['projectId'])
        out = read_result(folder)
        reference = p.get('structure')
        source = p.get('source')
        if not isinstance(source, str) or not source.strip() or len(source) > 2000:
            raise ValueError('Record the measurement accession, version and assay source.')
        if not isinstance(reference, str) or len(reference) != out['length']:
            raise ValueError('Measured structure must preserve all nucleotide positions.')
        measurement = {'runId': job['id'], 'predictionSha256': out['sha256'], 'structure': reference,
                       'source': source, 'recorded': time.time(), 'accuracy': accuracy(out['structure'], reference),
                       'evidence': 'user-supplied outcome; not independently verified', 'usedForTraining': False}
        measurement['sha256'] = digest(measurement)
        with (folder / ('measurement-' + measurement['sha256'] + '.json')).open('x') as f:
            json.dump(measurement, f, indent=2)
        return measurement
    raise ValueError('Unsupported Qwen RNA action.')
