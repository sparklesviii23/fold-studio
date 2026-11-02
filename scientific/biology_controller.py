"""Reference-analysis controller. Plans inference; does not generate or optimize sequences."""
import hashlib
import json
import math
import pathlib
import sqlite3
import time
import biological_models as models
import antisense_workflow as pna

ACTIONS = {'bio_controller_create', 'bio_controller_plans', 'bio_controller_report', 'bio_controller_run', 'bio_controller_refresh',
           'bio_controller_automate', 'bio_controller_local_run', 'bio_controller_catalog'}
LIMITATIONS = [
    'No sequence generation, mutation search, host-range optimization or treatment design is implemented.',
    'DNA likelihood, protein embeddings and structure confidence do not establish phage-host compatibility.',
    'All model integrations await real GPU qualification in Fold Studio.',
    'Borzoi is a human regulatory model and is not applicable to this microbial reference study.',
]


def _table(s):
    s.db.execute('CREATE TABLE IF NOT EXISTS bio_controller_claims(plan_id TEXT NOT NULL,step_id TEXT NOT NULL,state TEXT NOT NULL,task_id TEXT,error TEXT,PRIMARY KEY(plan_id,step_id))')
    s.db.commit()
    s.db.execute('CREATE TABLE IF NOT EXISTS bio_controller_local_results(plan_id TEXT PRIMARY KEY, result TEXT NOT NULL, sha256 TEXT NOT NULL)')
    s.db.commit()


def _plan(s, p):
    s.project(p.get('projectId'))
    rows = s.rows('SELECT * FROM records WHERE id=? AND project_id=?', (p.get('id'), p['projectId']))
    if not rows: raise ValueError('Analysis plan not found in this project.')
    row = rows[0]; row['data'] = json.loads(row['data']); d = row['data']
    if d.get('domain') != 'biology_controller' or models._sha(d.get('content')) != d.get('sha256'): raise ValueError('Analysis plan integrity check failed.')
    if row['id'] in {r['id'] for r in s.library({})['removedRecords']}: raise ValueError('Restore this plan in the Research Library before using it.')
    return row


def _claims(s, plan_id):
    _table(s)
    return {r['step_id']: r for r in s.rows('SELECT * FROM bio_controller_claims WHERE plan_id=?', (plan_id,))}


def _summary(result):
    # Deliberately no aggregate score, ranking or compatibility inference.
    keys = ('model', 'scores', 'scoreDefinition', 'embeddingShape', 'pLDDTMean', 'pTM', 'note', 'checkpointRevision', 'checkpointSha256', 'analysis')
    return {k: result[k] for k in keys if k in result}


def _cached(s, task):
    import gpu_tasks as gpu
    if task['state'] != 'done' or task.get('fetchError'): return None
    entry = next((e for e in task.get('outputs', []) if e['path'] == 'result.json'), None)
    if entry is None: raise ValueError('Provider finished without a model result; no prediction is established.')
    f = gpu._folder(s) / task['id'] / 'outputs/result.json'
    if f.stat().st_size > 2_000_000: raise ValueError('Model result exceeds the report limit.')
    raw = f.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']: raise ValueError('Model result checksum mismatch.')
    r = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite model result.')))
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value): raise ValueError('Non-finite model result.')
        if isinstance(value, dict):
            for v in value.values(): finite(v)
        if isinstance(value, list):
            for v in value: finite(v)
    finite(r)
    if r.get('schema') != 'fold-studio.biological-model-result.v1' or r.get('recipe') != task['recipe'] or r.get('inputsSha256') != task['inputsSha256']:
        raise ValueError('Model result identity mismatch.')
    if task['recipe'] == 'bio_antisense':
        if r.get('recipeSha256') != task['recipeSha256'] or r.get('analysis', {}).get('schema') != 'fold-studio.antisense-analysis.v1':
            raise ValueError('PNA result recipe or analysis identity mismatch.')
        if r['analysis']['request'] != task['inputs']['request']: raise ValueError('PNA result input mismatch.')
        return _summary(r)
    required = {'bio_evo2': 'scores', 'bio_esmc': 'embeddingShape', 'bio_esmfold2': 'pTM'}[task['recipe']]
    value = r.get(required)
    if required == 'scores':
        if not isinstance(value, list) or len(value) != 1 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
            raise ValueError('DNA result has no valid reference likelihood.')
    elif required == 'embeddingShape':
        if not isinstance(value, list) or len(value) != 2 or any(type(v) is not int or v < 1 for v in value) or value[0] != len(task['inputs']['sequence']):
            raise ValueError('Protein embedding dimensions do not match the reference input.')
    elif type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Structure result has no finite confidence statistic.')
    return _summary(r)


def report(s, p):
    import gpu_tasks as gpu
    row = _plan(s, p); c = row['data']['content']; claims = _claims(s, row['id']); steps = []
    for step in c['steps']:
        claim = claims.get(step['id']); view = {**step, 'state': 'awaiting_approval', 'taskId': None, 'result': None}
        if not claim and step['engine'] == 'bio_antisense' and row['data'].get('localResult') is not None:
            saved = row['data']['localResult']
            if models._sha(saved) != row['data'].get('localResultSha256') or saved['request'] != step['inputs']['request']:
                view.update(state='result_unavailable', error='Archived local result integrity check failed.')
            else:
                view.update(state='done', result={'analysis': saved, 'model': saved['engineVersion']})
        if claim:
            view.update(state=claim['state'], taskId=claim['task_id'], error=claim['error'])
            if claim['state'] == 'done_local':
                local = s.rows('SELECT * FROM bio_controller_local_results WHERE plan_id=?', (row['id'],))
                try:
                    result = json.loads(local[0]['result'])
                    if models._sha(result) != local[0]['sha256'] or result['request'] != step['inputs']['request']:
                        raise ValueError('Local PNA result integrity check failed.')
                    view.update(state='done', result={'analysis': result, 'model': result['engineVersion']})
                except (IndexError, KeyError, ValueError) as e:
                    view.update(state='result_unavailable', error=str(e))
            if claim['task_id']:
                try:
                    task = gpu._read(s, claim['task_id'])
                    if task.get('projectId') != p['projectId'] or task['recipe'] != step['engine']: raise ValueError('Task scope mismatch.')
                    expected = gpu._clean_inputs(step['engine'], step['inputs'])
                    if task.get('inputsSha256') != hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest(): raise ValueError('Task inputs do not match the immutable plan.')
                    view.update(state=task['state'], result=_cached(s, task), outputs=task.get('outputs', []), error=task.get('error'))
                except (ValueError, OSError, KeyError) as e:
                    view.update(state='result_unavailable', result=None, error=str(e))
        steps.append(view)
    predicted = sum(1 for step in steps if step['result'] is not None)
    return {'plan': row, 'steps': steps, 'inputChecks': c['inputChecks'], 'predictionsAvailable': predicted,
            'status': 'analyses_available' if predicted == len(steps) else 'analyses_incomplete',
            'answer': 'Exploratory PNA analysis is available; antibacterial activity remains unvalidated.' if c.get('scope') == 'antisense_reference_analysis' else 'Phage-host compatibility and biological activity remain undetermined.',
            'compatibility': {'state': 'not_modelled', 'value': None, 'confidence': None},
            'limitations': (['Complementary non-replicating PNA drafts and an exploratory published-data baseline are supported; no phage design or validated efficacy model.'] + LIMITATIONS[1:]) if c.get('scope') == 'antisense_reference_analysis' else LIMITATIONS,
            'clinicalUse': False, 'sequenceGeneration': c.get('complementaryDrafts', False),
            'executionPolicy': 'Batch approval can launch the saved independent cloud steps. No automatic retry or local fallback.'}


def dispatch(s, action, p):
    import gpu_tasks as gpu
    if action == 'bio_controller_catalog': return pna.catalog()
    if action == 'bio_controller_plans':
        s.project(p.get('projectId'))
        return [r for r in s.library({})['records'] if r['project_id'] == p['projectId'] and r['data'].get('domain') == 'biology_controller']
    if action == 'bio_controller_create':
        s.project(p.get('projectId'))
        name = models._text(p, 'name', 160); source = models._text(p, 'source', 500)
        organism = models._text(p, 'organism', 200); accession = models._text(p, 'accession', 300)
        question = models._text(p, 'question', 3000)
        steps = []; checks = []
        if p.get('antisenseRequest') is not None:
            request = pna.engine.clean(p['antisenseRequest'])
            steps.append({'id': 'antisense', 'engine': 'bio_antisense', 'title': 'PNA evidence, baseline and molecule analysis',
                          'inputs': {'request': request}, 'dependsOn': ['input_identity'], 'qualification': 'exploratory_only'})
            checks.append({'input': 'PNA research request', 'length': len(request['target']) or len(request['candidates'].splitlines()),
                           'sha256': models._sha(request), 'source': request['source'], 'evidence': 'Supplied input identity'})
        for key, engine in [('dna', 'bio_evo2'), ('protein', 'bio_esmc')]:
            raw = p.get(key, '')
            if not isinstance(raw, str): raise ValueError('Supply reference sequences as text.')
            if not raw.strip(): continue
            sequence = gpu._clean_inputs(engine, {'sequence': raw})['sequence']
            if key == 'protein' and p.get('includeStructure') and len(sequence) > 600: raise ValueError('Structure analysis supports at most 600 supplied residues; no cropping is applied.')
            checks.append({'input': key, 'length': len(sequence), 'sha256': hashlib.sha256(sequence.encode()).hexdigest(), 'source': source, 'evidence': 'Input identity; not a biological prediction'})
            steps.append({'id': key, 'engine': engine, 'title': 'DNA reference analysis' if key == 'dna' else 'Protein representation', 'inputs': {'sequence': sequence}, 'dependsOn': ['input_identity'], 'qualification': 'integration_unvalidated'})
            if key == 'protein' and p.get('includeStructure'):
                steps.append({'id': 'structure', 'engine': 'bio_esmfold2', 'title': 'Independent protein structure prediction', 'inputs': {'sequence': sequence, 'loops': 4, 'steps': 100, 'seed': 0}, 'dependsOn': ['input_identity'], 'qualification': 'integration_unvalidated'})
        if not steps: raise ValueError('Supply at least one existing reference DNA or protein sequence.')
        if type(p.get('includeStructure', False)) is not bool: raise ValueError('Structure selection must be true or false.')
        c = {'schemaVersion': 1, 'scope': 'microbial_reference_analysis', 'organism': organism, 'accession': accession, 'source': source,
             'question': question, 'inputChecks': checks, 'steps': steps, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'sequenceGeneration': False, 'compatibilityModelAvailable': False}
        if p.get('antisenseRequest') is not None:
            c.update(scope='antisense_reference_analysis', complementaryDrafts=request['mode'] == 'draft')
        row = s.record_save({'projectId': p['projectId'], 'kind': 'analysis', 'name': name,
            'data': {'domain': 'biology_controller', 'source': 'Biology Controller · reference-analysis plan', 'content': c, 'sha256': models._sha(c)}})
        return report(s, {**p, 'id': row['id']})
    if action == 'bio_controller_report': return report(s, p)
    if action in ('bio_controller_automate', 'bio_controller_local_run'):
        row = _plan(s, p)
        if p.get('expectedSha256') != row['data']['sha256']: raise ValueError('Plan changed. Reload it before running.')
        if action == 'bio_controller_automate':
            if p.get('approvedRemoteCost') is not True: raise ValueError('Approve the saved batch upload and provider charges before launching.')
            for step in row['data']['content']['steps']:
                existing = _claims(s, row['id']).get(step['id'])
                if existing and existing['state'] in ('submitting', 'submission_requires_review', 'local_requires_review'):
                    raise ValueError('A prior submission needs review; the remaining batch will not launch automatically.')
                if existing: continue
                try: dispatch(s, 'bio_controller_run', {**p, 'stepId': step['id']})
                except Exception:
                    return report(s, p)  # Persisted failed/uncertain claim remains visible. Never retry it.
            return report(s, p)
        import execution_policy
        execution_policy.enforce(s, action, p)
        steps = row['data']['content']['steps']
        if len(steps) != 1 or steps[0]['engine'] != 'bio_antisense': raise ValueError('Local execution supports the PNA chain alone. Use Modal for optional foundation engines.')
        if row['data'].get('localResult') is not None: return report(s, p)
        _table(s)
        try:
            with s.db: s.db.execute('INSERT INTO bio_controller_claims VALUES(?,?,?,?,?)', (row['id'], 'antisense', 'local_running', None, None))
        except sqlite3.IntegrityError: return report(s, p)
        try:
            result = pna.engine.run(steps[0]['inputs']['request'], pna.data())
            result['execution'] = {'backend': 'local_cpu', 'codeSha256': hashlib.sha256(pathlib.Path(pna.engine.__file__).read_bytes()).hexdigest()}
            with s.db:
                s.db.execute('INSERT INTO bio_controller_local_results VALUES(?,?,?)', (row['id'], json.dumps(result, allow_nan=False), models._sha(result)))
                previous = s.rows('SELECT data FROM records WHERE id=?', (row['id'],))[0]['data']
                portable = json.loads(previous)
                portable.update(localResult=result, localResultSha256=models._sha(result))
                changed = s.db.execute('UPDATE records SET data=? WHERE id=? AND data=?', (json.dumps(portable, allow_nan=False), row['id'], previous))
                if changed.rowcount != 1: raise ValueError('The investigation changed while saving its result. Reload it before continuing.')
                s.db.execute('UPDATE bio_controller_claims SET state=? WHERE plan_id=? AND step_id=?', ('done_local', row['id'], 'antisense'))
        except Exception as e:
            with s.db: s.db.execute('UPDATE bio_controller_claims SET state=?,error=? WHERE plan_id=? AND step_id=?', ('local_requires_review', str(e)[:1000], row['id'], 'antisense'))
            raise
        return report(s, p)
    if action == 'bio_controller_run':
        row = _plan(s, p); step = next((v for v in row['data']['content']['steps'] if v['id'] == p.get('stepId')), None)
        if step is None: raise ValueError('Choose a step from this saved plan.')
        if p.get('expectedSha256') != row['data']['sha256']: raise ValueError('Plan changed. Reload it before running.')
        if p.get('approvedRemoteCost') is not True: raise ValueError('Approve input upload, model downloads and provider charges for this engine first.')
        _table(s)
        try:
            with s.db:s.db.execute('INSERT INTO bio_controller_claims VALUES(?,?,?,?,?)', (row['id'], step['id'], 'submitting', None, None))
        except sqlite3.IntegrityError:
            raise ValueError('This step already has a submission record. Inspect it; it will not be submitted twice.') from None
        try:
            task = models.dispatch(s, 'bio_models_submit', {'projectId': p['projectId'], 'recipe': step['engine'], 'inputs': step['inputs'],
                                    'inputSource': row['data']['content']['source'], 'approvedRemoteCost': True})
            with s.db:s.db.execute('UPDATE bio_controller_claims SET state=?,task_id=? WHERE plan_id=? AND step_id=?', ('submitted', task['id'], row['id'], step['id']))
        except Exception as e:
            # A process may have launched before an exception. Never automatically repeat a potentially billed request.
            with s.db:s.db.execute('UPDATE bio_controller_claims SET state=?,error=? WHERE plan_id=? AND step_id=?', ('submission_requires_review', str(e)[:1000], row['id'], step['id']))
            raise
        return report(s, p)
    if action == 'bio_controller_refresh':
        row = _plan(s, p); claims = _claims(s, row['id']); live = {}
        for step in row['data']['content']['steps']:
            claim = claims.get(step['id'])
            if claim and claim['task_id']:
                value = models.dispatch(s, 'bio_models_result', {'projectId': p['projectId'], 'taskId': claim['task_id']})
                live[step['id']] = {k: value['run'][k] for k in ('serverLog', 'phase') if k in value['run']}
        result = report(s, p)
        for step in result['steps']: step.update(live.get(step['id'], {}))
        return result
    raise ValueError('Unknown biology controller action.')
