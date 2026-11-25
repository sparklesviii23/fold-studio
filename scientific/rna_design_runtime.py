"""Run RNA Design in an owned process with a startup deadline."""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--supervise', action='store_true')
    args = parser.parse_args()
    folder = args.root / 'jobs' / args.job
    inputs = json.loads((folder / 'request.json').read_text())
    from worker import Service
    service = Service(args.root)
    if args.supervise:
        started = time.monotonic()
        child = subprocess.Popen([sys.executable, '-B', __file__, '--root', str(args.root), '--job', args.job])
        try:
            code = child.wait(timeout=inputs['request']['maxSeconds'] + 30)
            if code and service.job(args.job)['state'] in ('queued', 'running'):
                service.job_update(args.job, 'failed', {'error': f'RNA Design worker exited with code {code}. Saved batches were kept.'})
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
            if service.job(args.job)['state'] in ('queued', 'running'):
                service.job_update(args.job, 'completed', {'phase': 'Deadline reached. Saved batches were kept.', 'stopReason': 'host_deadline'})
        finally:
            service.job_metadata(args.job, {'wallSeconds': time.monotonic() - started, 'billedCost': None})
        return
    with (folder / 'run.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stopped = [False]
        signal.signal(signal.SIGTERM, lambda *_: stopped.__setitem__(0, True))
        signal.signal(signal.SIGINT, lambda *_: stopped.__setitem__(0, True))
        from rna_design_core import search
        started = time.monotonic()
        service.job_update(args.job, 'running', {'phase': 'Searching distinct RNA sequences'})
        try:
            proposals = None
            if inputs['request']['method'] != 'solver':
                from rna_design import checkpoint
                from rna_design_qwen import Proposer
                proposals = Proposer(checkpoint(), inputs['request']['target'])
            numerical = time.monotonic()
            cache = args.root / 'rna_design'
            cache.mkdir(exist_ok=True)
            def batch(out):
                print(json.dumps({'evaluated': len(out['candidates']), 'qualifying': out['qualifyingCount'], 'seconds': out['metrics']['elapsedSeconds']}), flush=True)
                service.job_metadata(args.job, {'phase': f"{len(out['candidates'])} distinct candidates · {out['qualifyingCount']} qualify"})
            out = search(inputs['request'], folder, cache / 'evaluations.sqlite', proposals=proposals, on_batch=batch, stop=lambda: stopped[0])
            current = service.job(args.job)
            if current['state'] in ('running', 'queued'):
                service.job_update(args.job, 'cancelled' if stopped[0] else 'completed', {'phase': out['metrics']['stopReason'],
                    'startupSeconds': numerical - started, 'searchSeconds': time.monotonic() - numerical,
                    'resultSha256': out['sha256'], 'qualifyingCount': out['qualifyingCount']})
        except Exception as e:
            if service.job(args.job)['state'] in ('running', 'queued'):
                service.job_update(args.job, 'failed', {'error': str(e), 'phase': 'Saved batches were kept'})
            raise


if __name__ == '__main__':
    main()
