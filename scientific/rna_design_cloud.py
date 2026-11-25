"""Modal CPU entry point. Commit each batch to the existing output volume."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path


def main():
    from rna_design_core import atomic, search
    body = json.loads(Path(os.environ['FOLD_INPUT_FILE']).read_text())['design']
    body = json.loads(body)
    out = Path(os.environ['OUT'])
    if body.get('resumeState'):
        atomic(out / 'state.json', body['resumeState'])
    stopped = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopped.__setitem__(0, True))
    started = time.monotonic()
    def batch(value):
        atomic(out / 'usage.json', {'runtimeSeconds': time.monotonic() - started, 'billedCost': None, 'hardware': '1 CPU core, 2048 MiB', 'runId': body['runId'],
                                    'persistence': 'sync /cache per batch; Modal background and shutdown volume commits'})
        subprocess.run(['sync', '/cache'], check=True, timeout=10)
        print(json.dumps({'evaluated': len(value['candidates']), 'qualifying': value['qualifyingCount']}), flush=True)
    search(body['request'], out, on_batch=batch, stop=lambda: stopped[0])
    subprocess.run(['sync', '/cache'], check=True, timeout=10)


if __name__ == '__main__':
    main()
