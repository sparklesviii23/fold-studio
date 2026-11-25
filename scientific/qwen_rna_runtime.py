"""Owned offline job process. Loads numerical weights, never generates scientific prose."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def predict(checkpoint, sequence, arm='qwen_adapter'):
    import torch
    from safetensors.torch import load_file
    from transformers import Qwen2Model
    from qwen_rna_model import RNAModel, marginals
    from qwen_rna_contract import clean, result
    sequence = clean(sequence)
    checkpoint = Path(checkpoint)
    config = json.loads(checkpoint.read_text())
    path = checkpoint.parent / config['weights'][arm]['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != config['weights'][arm]['sha256']:
        raise ValueError('Scientific checkpoint weights changed.')
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    torch.set_num_threads(8)
    backbone = None
    if arm.startswith('qwen'):
        backbone = Qwen2Model.from_pretrained(config['baseCheckpoint'], local_files_only=True, trust_remote_code=False,
                                             use_safetensors=True, dtype=torch.float16, attn_implementation='sdpa').to(device)
    model = RNAModel(backbone, config['tokenIds'], adapters=arm == 'qwen_adapter').to(device).eval()
    model.restore(load_file(str(path)))
    with torch.no_grad():
        matrix = marginals(model(sequence)).float().cpu().tolist()
    return result(sequence, matrix, config['selected'][arm]['threshold'],
                  {'engine': arm, 'version': config['version'], 'weightsSha256': config['weights'][arm]['sha256'],
                   'checkpointSha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                   'baseRevision': config['baseRevision'], 'splitSha256': config['splitSha256'],
                   'device': device, 'torch': torch.__version__, 'transformers': __import__('transformers').__version__,
                   'runtimePython': sys.executable,
                   'externalEngines': [], 'teacherSignals': [], 'evidence': 'Reference-annotation-trained research prediction'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--supervise', action='store_true')
    parser.add_argument('--python')
    args = parser.parse_args()
    if args.supervise:
        # Bound interpreter startup/imports too, before the child's own alarm exists.
        command = [args.python, '-B', __file__, '--root', str(args.root), '--job', args.job]
        def fail(message):
            from worker import Service
            s = Service(args.root)
            if s.job(args.job)['state'] in ('queued', 'running'):
                s.job_update(args.job, 'failed', {'error': message, 'phase': 'Runtime failed'})
        try:
            child = subprocess.Popen(command)
        except OSError as e:
            fail('Could not start qualified Python: ' + str(e))
            raise SystemExit(1)
        try:
            code = child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
            fail('Qualified Python runtime did not finish within 180 seconds; no retry.')
            raise SystemExit(124)
        if code:
            fail('Qualified Python exited with code ' + str(code) + '; review the full execution log. No retry.')
        raise SystemExit(code)
    from worker import Service
    from qwen_rna import run_folder
    from qwen_rna_contract import accuracy, digest, pairs
    service = Service(args.root)
    job = service.job(args.job)
    folder, _ = run_folder(service, args.job, job['project_id'])
    def expired(*_):
        raise TimeoutError('Qwen RNA exceeded the 180-second local inference limit.')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(180)
    started = time.monotonic()
    try:
        service.job_update(args.job, 'running', {'phase': 'Loading local numerical checkpoint'})
        request = json.loads((folder / 'request.json').read_text())
        if hashlib.sha256(Path(request['checkpoint']).read_bytes()).hexdigest() != request['checkpointSha256']:
            raise ValueError('Requested model version changed after submission.')
        print('Native inference; external folding engines disabled during prediction.', flush=True)
        out = predict(request['checkpoint'], request['sequence'], request['engine'])
        out['runId'] = args.job
        if request['reference']:
            out['comparison'] = {'reference': request['reference'], **accuracy(out['structure'], request['reference'])}
        entropy = sum(x['entropyBits'] for x in out['bases']) / out['length']
        out['verification'] = {'enabled': request['verify'], 'ran': False, 'policy': 'entropy-threshold/1',
                               'reason': 'Native mean partner entropy > 1 bit' if entropy > 1 else 'Native entropy below policy threshold',
                               'meanEntropyBits': entropy}
        if request['verify'] and entropy > 1:
            print('Explicit verification enabled: running the existing RNA Lab nearest-neighbour solver.', flush=True)
            service.job_update(args.job, 'running', {'phase': 'Checking disagreement with RNA Lab solver'})
            from rna_lab_fold import Builtin, MODEL, to_dotbracket
            solver = Builtin(out['sequence'])
            structure = to_dotbracket(solver.mfe_pairs, out['length'])
            disagreement = len(set(pairs(structure)) ^ set(pairs(out['structure'])))
            out['verification'].update(ran=True, engine='rna-lab.fold', version='1.0.0', backend='builtin-nn',
                                       structure=structure, energyKcalMol=solver.mfe_energy,
                                       inputs={'sequence': out['sequence'], 'temperatureC': 37., 'parameterSet': MODEL},
                                       pairDisagreement=disagreement,
                                       referenceAccuracy=accuracy(structure, request['reference']) if request['reference'] else None,
                                       effect='Independent cross-check; native probabilities and fold are retained.')
            out['provenance']['externalEngines'].append({'engine': 'rna-lab.fold', 'version': '1.0.0', 'role': 'verification only'})
        out['seconds'] = time.monotonic() - started
        out['sha256'] = digest({k:v for k,v in out.items() if k!='sha256'})
        temp = folder / 'result.pending'
        temp.write_text(json.dumps(out, allow_nan=False))
        temp.replace(folder / 'result.json')
        # Cancellation wins if it committed before this transaction.
        service.db.execute('BEGIN IMMEDIATE')
        if service.job(args.job)['state'] not in ('cancelled', 'interrupted'):
            service.job_update(args.job, 'completed', {'phase': 'Prediction ready', 'resultSha256': out['sha256'], 'seconds': out['seconds']})
        else:
            service.db.rollback()
        print('Completed: ' + out['sha256'], flush=True)
    except Exception as e:
        if service.job(args.job)['state'] != 'cancelled':
            service.job_update(args.job, 'failed', {'error': str(e), 'phase': 'Prediction failed'})
        print(str(e), file=sys.stderr, flush=True)
        raise
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
