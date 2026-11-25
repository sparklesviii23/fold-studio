"""RNA Design jobs use the existing local and Modal job stores."""
import json
import os
import subprocess
import sys
from pathlib import Path

from rna_design_actions import ACTIONS
from rna_design_core import VERSION, atomic, digest, validate

HERE = Path(__file__).resolve().parent


def result(folder):
    path = folder / 'result.json'
    if not path.is_file():
        return None
    value = json.loads(path.read_text())
    if value.get('sha256') != digest({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('RNA Design result integrity check failed.')
    return value


def owned(s, p):
    job = s.job(p['id'])
    if job['engine'] != 'rna-design' or job['project_id'] != p['projectId']:
        raise ValueError('RNA Design run does not belong to this project.')
    return job, s.root / 'jobs' / job['id']


def quote(s, p):
    import execution_policy
    request = validate(p)
    mode = execution_policy.selected(s)['mode']
    if mode not in ('local', 'modal'):
        raise ValueError('RNA Design supports This Mac and Modal CPU.')
    seconds = request['maxSeconds']
    accounts = s.setting('modalAccounts', {'activeId': None, 'profiles': []}) if mode == 'modal' else {}
    account_id = accounts.get('activeId')
    account_name = next((a.get('name') for a in accounts.get('profiles', []) if a.get('id') == account_id), None)
    # This is a planning rate. The account invoice is the cost authority.
    rate = 0.00003942 + 2 * 0.00000667
    hardware = ('This Mac · CPU' if request['method'] == 'solver' else 'This Mac · Qwen on MPS when available; CPU otherwise') if mode == 'local' else 'Modal · 1 CPU core · 2048 MiB · no GPU'
    return {'request': request, 'mode': mode, 'hardware': hardware, 'accountId': account_id, 'accountName': account_name,
            'uploads': [] if mode == 'local' else ['Target dot-bracket', 'Sequence constraints', 'Seed and run limits', 'RNA Design source modules'],
            'limits': {'searchSeconds': seconds, 'containerSeconds': min(900, int(seconds) + 120), 'candidates': request['maxCandidates']},
            'cost': {'currency': 'USD', 'estimatedMaximum': 0 if mode == 'local' else round((seconds + 120) * rate, 5),
                     'planningRatePerSecond': rate if mode == 'modal' else 0, 'rateSource': 'https://modal.com/pricing', 'rateChecked': '2026-11-16', 'billedCost': None,
                     'note': 'No cloud charge. Local power cost is not measured.' if mode == 'local' else 'Estimate only. Includes a 120 s startup allowance. Image build and account charges can differ. Billed cost is not available from this workflow.'},
            'quoteSha256': digest({'request': request, 'mode': mode, 'accountId': account_id, 'version': VERSION})}


def launch_local(s, job, folder):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', '__PYVENV_LAUNCHER__', 'VIRTUAL_ENV', 'PYTHONEXECUTABLE')}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    if job['data']['request']['method'] != 'solver':
        config = json.loads((HERE / 'qwen_rna_install.json').read_text())
        env['PYTHONPATH'] = os.pathsep.join(config['sitePackages'])
    runtime = HERE / 'rna_design_runtime.py'
    with (folder / 'execution.log').open('a') as log:
        process = subprocess.Popen([sys.executable, '-B', str(runtime), '--supervise', '--root', str(s.root), '--job', job['id']],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    s.job_metadata(job['id'], {'pid': process.pid, 'workerPath': str(runtime)})


def launch_cloud(s, job, request, q, resume_state=None):
    import gpu_tasks
    files = {name: (HERE / name).read_text() for name in ('rna_design_core.py', 'rna_design_cloud.py', 'rna_lab_fold.py')}
    cloud_inputs = {'request': request, 'runId': job['id'], 'files': files, 'resumeState': resume_state}
    task = gpu_tasks.submit(s, {'recipe': 'rna_design_cpu', 'inputs': {'design': json.dumps(cloud_inputs)},
                               'gpu': None, 'timeout': q['limits']['containerSeconds'], 'approvedRemoteCost': True,
                               'projectId': job['project_id'], 'label': job['name']})
    old = job['data'].get('remoteTaskIds', [])
    s.job_metadata(job['id'], {'remoteTaskId': task['id'], 'remoteTaskIds': old + [task['id']], 'phase': 'Starting Modal CPU'})


def start(s, p):
    s.project(p['projectId'])
    q = quote(s, p)
    if p.get('quoteSha256') != q['quoteSha256']:
        raise ValueError('Review the current hardware, uploads, cost estimate and limits before launch.')
    if q['request']['method'] != 'solver' and q['mode'] == 'modal':
        raise ValueError('The inverse Qwen pilot is local only. Select Solver for Modal CPU.')
    if q['request']['method'] != 'solver' and not checkpoint().is_file():
        raise ValueError('The inverse Qwen checkpoint is not available. Select Solver.')
    if q['mode'] == 'modal' and p.get('approvedRemoteCost') is not True:
        raise ValueError('Approve this bounded Modal CPU workload before launch.')
    if s.active():
        raise ValueError('Finish or cancel the active scientific job first.')
    inputs = {'projectId': p['projectId'], 'name': 'RNA Design · ' + str(len(q['request']['target'])) + ' nt', 'request': q['request'], 'quote': q, 'quoteHistory': [q]}
    job = s.job_new(inputs, 'rna-design', 'queued')
    folder = s.root / 'jobs' / job['id']
    folder.mkdir()
    atomic(folder / 'request.json', inputs)
    try:
        if q['mode'] == 'local':
            launch_local(s, job, folder)
        else:
            launch_cloud(s, job, q['request'], q)
    except Exception as e:
        s.job_update(job['id'], 'failed', {'error': str(e)})
        raise
    return s.job(job['id'])


def checkpoint():
    receipt = HERE / 'rna_design_install.json'
    if not receipt.is_file():
        return HERE / 'missing-inverse-checkpoint.json'
    config = json.loads(receipt.read_text())
    path = Path(config['checkpoint'])
    if path.is_file() and __import__('hashlib').sha256(path.read_bytes()).hexdigest() != config['checkpointSha256']:
        raise ValueError('Inverse Qwen checkpoint receipt changed.')
    return path


def poll(s, p):
    job, folder = owned(s, p)
    remote_id = job['data'].get('remoteTaskId')
    if remote_id and (job['state'] in ('running', 'queued') or p.get('retryFetch')):
        import gpu_tasks
        remote = gpu_tasks.status(s, {'taskId': remote_id, 'retryFetch': p.get('retryFetch', False)})
        remote_folder = gpu_tasks._folder(s) / remote_id / 'outputs'
        for name in ('result.json', 'state.json'):
            path = remote_folder / name
            if path.is_file():
                atomic(folder / name, json.loads(path.read_text()))
        terminal = {'done': 'completed', 'failed': 'failed', 'stopped': 'cancelled', 'cancelled': 'cancelled'}
        state = terminal.get(remote['state'], 'running')
        usage_path = remote_folder / 'usage.json'
        usage = json.loads(usage_path.read_text()) if usage_path.is_file() else None
        s.job_update(job['id'], state, {'phase': remote.get('phase', remote['state']), 'remoteState': remote['state'],
                                      'error': remote.get('error'), 'runtimeUsage': usage, 'billedCost': None})
    return {'job': s.job_read({'id': job['id']}), 'result': result(folder)}


def dispatch(s, action, p):
    if action == 'rna_design_catalog':
        return {'version': VERSION, 'methods': ['solver'] + (['qwen', 'hybrid'] if checkpoint().is_file() else []),
                'simpleTarget': '((((....))))', 'hardTarget': '(((..(((.......)))..(((.......)))..)))',
                'evidence': 'Computational prediction. No experimental design claim.', 'checkpoint': str(checkpoint()) if checkpoint().is_file() else None}
    if action == 'rna_design_quote':
        return quote(s, p)
    if action == 'rna_design_start':
        return start(s, p)
    if action == 'rna_design_run':
        return poll(s, p)
    if action == 'rna_design_history':
        s.project(p['projectId'])
        return [s.job(r['id']) for r in s.rows("SELECT id FROM jobs WHERE engine='rna-design' AND project_id=? ORDER BY created DESC LIMIT 40", (p['projectId'],))]
    job, folder = owned(s, p)
    if action == 'rna_design_cancel':
        if job['data'].get('remoteTaskId'):
            import gpu_tasks
            gpu_tasks.dispatch(s, 'gpu_task_cancel', {'taskId': job['data']['remoteTaskId']})
            return poll(s, p)
        return {'job': s.job_cancel({'id': job['id']}), 'result': result(folder)}
    if action == 'rna_design_resume':
        if job['state'] in ('running', 'queued') or s.active():
            raise ValueError('Finish or cancel the active run before resume.')
        import execution_policy
        if execution_policy.selected(s)['mode'] != job['data']['quote']['mode']:
            raise ValueError('Select the original compute backend before resume.')
        new = validate({**job['data']['request'], **{k: p[k] for k in ('maxCandidates', 'maxSeconds', 'wanted') if k in p}})
        q = quote(s, new)
        if q['mode'] == 'modal' and (p.get('approvedRemoteCost') is not True or p.get('quoteSha256') != q['quoteSha256']):
            raise ValueError('Review and approve the current Modal resume quote.')
        import fcntl
        with (folder / 'run.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Cancellation is still saving a batch. Wait before resume.') from None
        resume_state = json.loads((folder / 'state.json').read_text()) if (folder / 'state.json').is_file() else None
        if q['mode'] == 'modal' and not resume_state:
            raise ValueError('Recover prior remote outputs before resume. If no batch was saved, start a new run.')
        quote_history = job['data'].get('quoteHistory', [job['data']['quote']]) + [q]
        inputs = {**job['data'], 'request': new, 'quote': q, 'quoteHistory': quote_history}
        atomic(folder / 'request.json', inputs)
        s.job_update(job['id'], 'queued', {'request': new, 'quote': q, 'quoteHistory': quote_history, 'error': None, 'phase': 'Resuming saved batches'})
        try:
            if q['mode'] == 'local':
                launch_local(s, job, folder)
            else:
                launch_cloud(s, job, new, q, resume_state)
        except Exception as e:
            s.job_update(job['id'], 'failed', {'error': str(e), 'phase': 'Resume failed. Saved batches were kept.'})
            raise
        return s.job(job['id'])
    if action == 'rna_design_save':
        out = result(folder)
        if not out:
            raise ValueError('Wait for at least one saved batch.')
        choice = next((c for c in out['candidates'] if c['id'] == p.get('candidateId')), None)
        if not choice:
            raise ValueError('Choose a candidate from this exact run.')
        for row in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis'", (p['projectId'],)):
            data = json.loads(row['data'])
            if data.get('domain') == 'rna_design' and data.get('runId') == job['id'] and data.get('candidate', {}).get('id') == choice['id'] and data.get('sha256') == out['sha256']:
                return {**row, 'data': data}
        return s.record_save({'projectId': p['projectId'], 'kind': 'analysis', 'name': p.get('name') or 'RNA Design · ' + choice['sequence'][:18],
                              'data': {'domain': 'rna_design', 'runId': job['id'], 'candidate': choice, 'target': out['request']['target'],
                                       'sequence': choice['sequence'], 'structure': choice['structure'], 'sha256': out['sha256'],
                                       'result': out, 'quote': job['data']['quote'], 'quoteHistory': job['data'].get('quoteHistory', []), 'hasAtomicCoordinates': False,
                                       'source': 'RNA Design · computational secondary structure prediction'}})
    raise ValueError('Unsupported RNA Design action.')
