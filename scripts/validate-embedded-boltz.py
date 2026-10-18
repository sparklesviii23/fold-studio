"""Real relocated-app prediction; resumes its recorded job instead of resubmitting.

Uses a private APFS cache clone and single-sequence mode, with no MSA submission.
This is same-host packaging acceptance, not a fresh-machine or accuracy claim.
"""
import argparse, hashlib, json, os, pathlib, subprocess, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEQUENCE = 'LSDEDFKAVFGMTRSAFANLPLWKQQNLKKEKGLF'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--cache-seed', required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    app = pathlib.Path(args.app).resolve()
    resources = app / 'Contents/Resources'
    root = pathlib.Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    library = root / 'library'
    cache = library / 'engine/models'
    seed = pathlib.Path(args.cache_seed).resolve()
    if library.is_relative_to(seed) or seed.is_relative_to(library):
        raise ValueError('Cache seed and isolated library must be separate.')
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['/bin/cp', '-cR', str(seed), str(cache)], check=True)
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('FOLD_', 'PYTHON', 'DYLD_', 'METALJAX_')) and k != 'JAX_PLATFORMS'}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    python = resources / 'runtime/bin/python3.12'
    worker = resources / 'scientific/worker.py'

    def seal():
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)

    def request(action, payload):
        proc = subprocess.run([str(python), '-I', '-B', str(worker), '--root', str(library)],
                              input=json.dumps({'action': action, 'payload': payload}),
                              capture_output=True, text=True, env=environment, timeout=90)
        try:
            reply = json.loads(proc.stdout)
        except ValueError:
            raise RuntimeError(proc.stderr[-4000:] + proc.stdout[-2000:]) from None
        if proc.returncode or 'error' in reply:
            raise RuntimeError(str(reply))
        return reply['result']

    seal()
    statefile = root / 'acceptance-state.json'
    if statefile.exists():
        state = json.loads(statefile.read_text())
        if state['app'] != str(app):
            raise ValueError('Recorded acceptance belongs to a different app.')
    else:
        project = request('project_create', {'name': 'Packaged Boltz isolated acceptance'})
        job = request('prediction_start', {'projectId': project['id'], 'name': 'Bundled 35-residue technical prediction',
                                           'fasta': '>Technical protein\n' + SEQUENCE, 'msa': 'single',
                                           'recycles': 1, 'samples': 1, 'steps': 10, 'seed': 42})
        state = {'app': str(app), 'projectId': project['id'], 'jobId': job['id']}
        statefile.write_text(json.dumps(state, indent=2) + '\n')
        print('Submitted actual packaged Boltz job ' + job['id'], flush=True)
    deadline = time.monotonic() + args.timeout
    last_state = None
    while True:
        job = request('job_read', {'id': state['jobId']})
        if job['state'] != last_state:
            print('Actual job state: ' + job['state'], flush=True)
            last_state = job['state']
        if job['state'] not in ('queued', 'running'):
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Job remains active; resume this validator to inspect the same saved job.')
        time.sleep(5)
    if job['state'] != 'completed':
        (root / 'failed-job.json').write_text(json.dumps(job, indent=2) + '\n')
        raise RuntimeError(job['data'].get('error', job['state']))
    provenance = job['data']['provenance']
    command = provenance['command']
    if command[0] != str(resources / 'runtime-boltz/bin/python3.12') or command[1] != '-B':
        raise ValueError('Prediction did not execute the app-owned runtime with bytecode disabled.')
    if '--use_msa_server' in command or provenance['msa'] != 'single':
        raise ValueError('Unexpected remote MSA submission.')
    if not provenance['modelResources']['checkpointPin']:
        raise ValueError('Prediction lacks the reviewed publisher model pin.')
    numba_cache = library / 'engine/cache/numba'
    if provenance['environment'].get('NUMBA_CACHE_DIR') != str(numba_cache):
        raise ValueError('Compiled feature caches are not directed outside the signed runtime.')
    library_data = request('library', {})
    records = {r['id']: r for r in library_data['records']}
    models = []
    for id in job['data']['outputs']:
        record = records[id]
        asset = library / 'assets' / record['data']['asset']
        if hashlib.sha256(asset.read_bytes()).hexdigest() != record['data']['sha256']:
            raise ValueError('Saved prediction asset checksum differs.')
        result = request('intelligence_inspect', {'structureId': id})
        structure = result['structure']
        if len(structure['residues']) != len(SEQUENCE) or not structure['atoms']:
            raise ValueError('Unexpected real coordinate output.')
        if not result['confidence']['meanByChain']:
            raise ValueError('No genuine per-residue prediction confidence was saved.')
        models.append({'id': id, 'sha256': record['data']['sha256'], 'atoms': len(structure['atoms']),
                       'residues': len(structure['residues']), 'confidence': result['confidence']})
    if not models:
        raise ValueError('No saved real prediction.')
    seal()
    report = {'state': 'passed', 'scope': 'Same-host relocated app-owned Boltz-2 MPS inference, 35-residue single-sequence technical case; not biological accuracy or fresh-machine acceptance.',
              'app': str(app), 'externalRuntimeEnvironmentRemoved': True,
              'isolatedCache': str(cache), 'originalCacheUnmodifiedByInference': True,
              'compiledFeatureCache': str(numba_cache),
              'compiledCacheFiles': len(list(numba_cache.rglob('*.nbc'))),
              'job': job, 'models': models, 'signatureAfterInference': 'passed'}
    output = ROOT / 'reports/embedded-boltz-runtime-acceptance.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('Passed: actual prediction, saved coordinates, confidence and unchanged app seal.', flush=True)


if __name__ == '__main__':
    main()
