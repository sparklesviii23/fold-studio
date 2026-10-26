"""Scientific execution admission, independent of interface backend selection.

Full Fab generation and heavy downstream work are cloud-only. Historical local
records remain readable/exportable; no permission flag re-enables local Fab.
"""
import json
import pathlib

FAB_POLICY = {
    'id': 'full-fab-cloud-only-v1',
    'domain': 'full_fab',
    'localExecutionAllowed': False,
    'allowedProviders': ['modal', 'vast'],
    'cloudExecutionQualified': False,
    'approvalRequired': True,
    'historicalLocalEvidencePreserved': True,
    'scope': 'Full Fab generation, optimization and heavy redesign/refolding run only on an explicitly approved qualified cloud worker. Viewing, configuration, historical analysis and export remain available on the Mac.',
}
FAB_ERROR = 'Full Fab is cloud-only. Local Fab generation, optimization and heavy downstream execution are disabled. Prepare a separately approved cloud campaign; historical inputs, results and cancelled jobs are preserved.'


def full_fab(value):
    """Explicit scientific identity/provenance, never an atom-count/name guess."""
    if not isinstance(value, dict):
        return False
    modality = value.get('modality')
    if modality == 'Fab' or modality == ['Fab']:
        return True
    if value.get('scientificDomain') == 'full_fab' or value.get('domain') == 'full_fab' or value.get('profile') == 'experimental-cpu-fab-amme':
        return True
    if value.get('memoryPolicy') == 'fab-cpu-ssd-v1' or value.get('fabChainTransport'):
        return True
    scaffold = value.get('scaffold')
    if isinstance(scaffold, dict) and scaffold.get('source') == 'scaffolds/Fab.cif':
        return True
    return any(full_fab(value.get(key)) for key in ('data', 'preparation', 'metadata', 'executionPolicy', 'config', 'rapidCandidate', 'origin'))


def require_local_allowed(value):
    if full_fab(value):
        raise ValueError(FAB_ERROR)


def associate_record_domain(service, record_id, value, source):
    """Verified preview provenance without rewriting original record metadata."""
    if not full_fab(value):
        return
    with service.db:
        service.db.execute('CREATE TABLE IF NOT EXISTS scientific_record_domains(record_id TEXT NOT NULL,domain TEXT NOT NULL,source TEXT NOT NULL,PRIMARY KEY(record_id,domain,source))')
        service.db.execute('INSERT OR IGNORE INTO scientific_record_domains VALUES(?,?,?)',(record_id,'full_fab',source))


def record_is_fab(service, structure_id, project_id=None):
    rows = service.rows('SELECT project_id,data FROM records WHERE id=?', (structure_id,))
    if not rows:
        return False
    row = rows[0]
    if project_id and row['project_id'] != project_id:
        raise ValueError('Structure belongs to another research project.')
    if service.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='scientific_record_domains'") and service.rows('SELECT record_id FROM scientific_record_domains WHERE record_id=? AND domain=?',(structure_id,'full_fab')):
        return True
    data = json.loads(row['data'])
    if full_fab(data):
        return True
    campaign = data.get('metadata', {}).get('campaignId')
    if campaign:
        jobs = service.rows('SELECT project_id,data FROM jobs WHERE id=?', (campaign,))
        if jobs and jobs[0]['project_id'] == row['project_id']:
            return full_fab(json.loads(jobs[0]['data']))
    return False


def enforce(service, action, payload):
    if action in ('bindcraft_start', 'bindcraft_resume', 'bindcraft_repeat'):
        require_local_allowed(payload)
        if payload.get('id'):
            require_local_allowed(service.job(payload['id']))
    elif action in ('mpnn_start', 'biology_pipeline_start', 'biology_counterfactual_start', 'prediction_start'):
        require_local_allowed(payload)
        for key in ('structureId','recordId'):
            if payload.get(key) and record_is_fab(service, payload[key], payload.get('projectId')):
                raise ValueError(FAB_ERROR)


def require_local_settings_allowed(settings, upstream):
    """Direct native runner guard, before importing JAX or loading checkpoints."""
    require_local_allowed(settings)
    scaffold = settings.get('binder_scaffold')
    if scaffold:
        import hashlib
        path, original = pathlib.Path(scaffold), pathlib.Path(upstream)/'scaffolds/Fab.cif'
        if path.is_file() and original.is_file() and path.stat().st_size <= 8*1024**2 and hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(original.read_bytes()).digest():
            raise ValueError(FAB_ERROR)
