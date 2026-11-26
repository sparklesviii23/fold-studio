"""Project-scoped biological model jobs and persistent research dossiers."""
import hashlib
import json
import pathlib
import time
import uuid

ACTIONS = {'bio_models_catalog', 'bio_models_submit', 'bio_models_runs', 'bio_models_result', 'bio_models_cancel',
           'bio_models_export', 'bio_models_structure', 'bio_studies', 'bio_study_create', 'bio_study_evidence'}
RECIPE_IDS = {'bio_evo2', 'bio_borzoi', 'bio_esmc', 'bio_esmfold2', 'bio_antisense'}
CATEGORIES = ('research_note', 'literature', 'model_prediction', 'laboratory_report')


def _text(p, key, limit, optional=False):
    v = p.get(key, '')
    if not isinstance(v, str) or len(v) > limit or '\0' in v or (not optional and not v.strip()):
        raise ValueError(f'{key}: enter text of up to {limit} characters.')
    return v.strip()


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _study(s, p):
    rows = s.rows('SELECT * FROM records WHERE id=? AND project_id=?', (p.get('id'), p['projectId']))
    if not rows: raise ValueError('Study not found in this project.')
    row = rows[0]; row['data'] = json.loads(row['data']); data = row['data']
    if data.get('domain') != 'biological_models' or _sha(data.get('content')) != data.get('sha256'): raise ValueError('Study identity or integrity check failed.')
    return row


def dispatch(s, action, p):
    import gpu_tasks as gpu
    if action == 'bio_models_catalog':
        return {'models': {k: {f: v for f, v in gpu.RECIPES[k].items() if f not in ('script', 'image')} for k in sorted(RECIPE_IDS)},
                'evidenceCategories': list(CATEGORIES), 'clinicalUse': False, 'qualification': 'Integration implemented; real remote inference not yet qualified.'}
    s.project(p.get('projectId'))
    if action == 'bio_models_submit':
        if p.get('recipe') not in RECIPE_IDS: raise ValueError('Choose a biological model.')
        # Submit via the existing cost-gated provider path. Never infer locally.
        source = _text(p, 'inputSource', 500)
        return gpu.submit(s, {**p, 'inputSource': source, 'label': 'Biological Models'})
    if action == 'bio_models_runs':
        rows = []
        for folder in gpu._folder(s).iterdir():
            path = folder / 'task.json'
            if not path.is_file(): continue
            rec = json.loads(path.read_text())
            if rec.get('recipe') in RECIPE_IDS and rec.get('projectId') == p['projectId']:
                rows.append(rec)
        return sorted(rows, key=lambda r: r['created'], reverse=True)[:100]
    if action in ('bio_models_result', 'bio_models_cancel', 'bio_models_export', 'bio_models_structure'):
        rec = gpu._read(s, p.get('taskId'))
        if rec.get('projectId') != p['projectId'] or rec.get('recipe') not in RECIPE_IDS: raise ValueError('Model run not found in this project.')
        if action == 'bio_models_cancel': return gpu.dispatch(s, 'gpu_task_cancel', p)
        if action in ('bio_models_export', 'bio_models_structure'):
            name = p.get('file')
            entry = next((f for f in rec.get('outputs', []) if f['path'] == name), None)
            if not entry or name not in ('result.json','dna-embeddings.npy','protein-embeddings.npy','prediction.cif','regulatory-track.csv','artifacts.json'):
                raise ValueError('Choose a returned model artifact.')
            f = gpu._folder(s) / rec['id'] / 'outputs' / name
            if not f.is_file() or f.stat().st_size > 100*1024*1024:
                raise ValueError('Artifact missing or exceeds the 100 MB export limit.')
            raw = f.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['sha256']: raise ValueError('Artifact checksum mismatch.')
            if action == 'bio_models_structure':
                if name != 'prediction.cif' or rec['recipe'] != 'bio_esmfold2' or rec['state'] != 'done': raise ValueError('Choose a completed ESMFold2 structure.')
                return s.import_structure({'projectId': p['projectId'], 'path': str(f), 'name': 'ESMFold2 · '+rec['id'][:8],
                    'source': rec['source'], 'confidenceKind': 'Predicted structure; raw confidence retained in model result',
                    'metadata': {'biologicalModelRun': rec['id'], 'inputsSha256': rec['inputsSha256'], 'coordinateSha256': entry['sha256'], 'evidence': 'Model prediction; not experimental'}})
            dest = pathlib.Path(_text(p, 'path', 4000))
            if dest.suffix != pathlib.Path(name).suffix: raise ValueError('Keep the original artifact file extension.')
            if dest.resolve().is_relative_to(s.root): raise ValueError('Export outside the managed research library.')
            dest.write_bytes(raw)
            return {'path': str(dest), 'sha256': entry['sha256']}

        # Poll only this explicitly requested run; no automatic submission/retry.
        rec = gpu.status(s, p)
        result = None
        if rec.get('state') == 'done' and not rec.get('fetchError'):
            manifest = next((f for f in rec.get('outputs', []) if f['path'] == 'result.json'), None)
            if manifest:
                f = gpu._folder(s) / rec['id'] / 'outputs' / 'result.json'
                raw = f.read_bytes()
                if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != manifest['sha256']: raise ValueError('Model result checksum mismatch.')
                result = json.loads(raw)
                if result.get('schema') != 'fold.biological-model-result.v1' or result.get('recipe') != rec['recipe'] or result.get('inputsSha256') != rec['inputsSha256']:
                    raise ValueError('Model result identity mismatch.')
        full = gpu.dispatch(s, 'gpu_task_record', p)
        return {'run': {**full, **rec}, 'result': result}
    if action == 'bio_studies':
        library = s.library({})
        return [r for r in library['records'] if r['project_id'] == p['projectId'] and r['data'].get('domain') == 'biological_models']
    if action == 'bio_study_create':
        name = _text(p, 'name', 160)
        content = {'schemaVersion': 1, 'organism': _text(p, 'organism', 200), 'reference': _text(p, 'reference', 300, True),
                   'question': _text(p, 'question', 3000), 'evidence': [], 'clinicalUse': False}
        return s.record_save({'projectId': p['projectId'], 'kind': 'analysis', 'name': name,
                              'data': {'domain': 'biological_models', 'source': 'Biological Models · research dossier', 'content': content, 'sha256': _sha(content)}})
    if action == 'bio_study_evidence':
        row = _study(s, p); old = json.dumps(row['data'])
        if p.get('expectedSha256') != row['data']['sha256']: raise ValueError('Study changed. Reload before adding evidence.')
        kind = p.get('category')
        if kind not in CATEGORIES: raise ValueError('Choose an evidence category.')
        evidence = row['data']['content']['evidence']
        if len(evidence) >= 200: raise ValueError('A dossier supports up to 200 entries.')
        entry = {'id': uuid.uuid4().hex, 'category': kind, 'title': _text(p, 'title', 200), 'source': _text(p, 'source', 1000),
                 'summary': _text(p, 'summary', 6000), 'recorded': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 'verification': 'User-supplied; not independently verified by fold'}
        entry['sha256'] = _sha(entry); evidence.append(entry)
        row['data']['sha256'] = _sha(row['data']['content'])
        # Compare-and-swap protects concurrent append operations without overwriting evidence.
        with s.db:
            cursor = s.db.execute('UPDATE records SET data=? WHERE id=? AND project_id=? AND data=?',
                                 (json.dumps(row['data']), row['id'], p['projectId'], old))
            if cursor.rowcount != 1: raise ValueError('Study changed. Reload before adding evidence.')
        return row
    raise ValueError('Unknown biological model action.')
