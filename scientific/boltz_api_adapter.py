"""Optional official Boltz SDK adapter; no dependency install or implicit billing.

Contract inspected against boltz-api 0.50.0, not the similarly named Bitcoin API.
External Boltz service charges are separate from Modal/Vast GPU charges.
"""
import datetime
from decimal import Decimal, InvalidOperation
import importlib.metadata
import os
import uuid

import evolution as ev

ACTIONS = {'biology_engines', 'biology_boltz_prepare', 'biology_boltz_quote', 'biology_boltz_start', 'biology_boltz_read', 'biology_boltz_jobs', 'biology_boltz_stop','biology_boltz_import','biology_boltz_reconcile'}
SDK_VERSION = '0.50.0'
API_URL = 'https://api.boltz.bio'


def capabilities(service=None):
    try:
        version = importlib.metadata.version('boltz-api')
    except importlib.metadata.PackageNotFoundError:
        version = None
    if service is not None and version is None:
        from biology_providers import status
        version=status(service).get('versions',{}).get('boltz-api')
    authenticated=bool(os.environ.get('BOLTZ_API_KEY'))
    if service is not None and not authenticated and __import__('sys').platform=='darwin':
        from provider_credentials import access
        try:authenticated=bool(access('boltz-api-key'))
        except ValueError:pass
    return {'id': 'boltzprot-1', 'provider': 'Boltz API', 'sdkVersion': version, 'contractVersion': SDK_VERSION,
            'sdkReady': version == SDK_VERSION, 'authenticated': authenticated,
            'operations': ['design', 'protein_library_screen'], 'realServiceQualified': False,
            'selfHosting': 'unverified; no verified official weights/runtime integrated',
            'scoreSemantics': 'Raw provider binding/structure confidence; not calibrated peptide affinity, Kd or success probability.',
            'billing': 'Separate external API charges; a quote is an estimate, not a billing cap.',
            'source': 'https://api.boltz.com/docs/api/guides/protein-library-screen/'}


def client():
    info = capabilities()
    if not info['sdkReady']:
        raise ValueError('Install the separately approved boltz-api=='+SDK_VERSION+' integration environment first; no automatic installation.')
    if not info['authenticated']:
        raise ValueError('Configure BOLTZ_API_KEY securely in the scientific service environment; never put it in a project or report.')
    from boltz_api import Boltz
    return Boltz(api_key=os.environ['BOLTZ_API_KEY'], base_url=API_URL, max_retries=0, timeout=30)


def plain(value):
    return value.model_dump(mode='json')


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid USD amount.') from None
    if not amount.is_finite() or not 0 <= amount <= 10000:
        raise ValueError('USD amount must be finite and between 0 and 10,000.')
    return amount


class BoltzAPI:
    def __init__(self, service):
        self.s = service
        self.evolution = ev.Evolution(service)
        service.db.execute('CREATE TABLE IF NOT EXISTS biology_api_requests(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL)')

    def read(self, p):
        row = self.s.db.execute('SELECT data FROM biology_api_requests WHERE id=? AND project_id=?', (p.get('id'), p['projectId'])).fetchone()
        if not row:
            raise ValueError('Choose a prepared Boltz request from this project.')
        import json
        return json.loads(row[0])

    def save(self, value):
        with self.s.db:
            self.s.db.execute('INSERT OR REPLACE INTO biology_api_requests VALUES(?,?,?,?)', (value['id'], value['projectId'], ev.canonical(value), value['created']))
        return value

    def biology_engines(self, p):
        # Never equate registration with scientific readiness.
        return {'engines': [capabilities(self.s),
            {'id': 'bindcraft2', 'state': 'existing_path', 'detail': 'Use Compute & Run; readiness checked there.'},
            {'id': 'boltzgen', 'state': 'legacy_adapter', 'detail': 'Existing remote adapter retained; not BoltzProt-1.'},
            {'id': 'proteinmpnn', 'state': 'existing_path', 'detail': 'Authentic local fixed-backbone redesign; separate from SolubleMPNN.'},
            {'id': 'solublempnn', 'state': 'adapter_implemented_model_unvalidated', 'detail': 'Independent decoder and explicit constraints; official checkpoint registration and inference qualification required.'},
            {'id': 'esmfold2-fast', 'state': 'adapter_implemented_model_unvalidated', 'detail': 'Official Fast model loading, multichain inference and raw confidence output; checkpoints and hardware validation required.'},
            {'id': 'esmfold2', 'state': 'adapter_implemented_model_unvalidated', 'detail': 'Official full model and ESMC loading, MSA and CCD/bond inputs; checkpoints and inference validation required.'},
            {'id': 'rosetta', 'state': 'requires_license', 'detail': 'No licensed runtime configured; no automatic redistribution.'},
            {'id': 'rfdiffusion', 'state': 'adapter_implemented_model_unvalidated', 'detail': 'Official CLI motif contigs and output drift checks; exact source/runtime/checkpoint registration required.'},
            {'id': 'modal', 'state': 'provider_implemented_unqualified', 'detail': 'Native ledger, RAPID worker deployment and control; account, immutable image and approved GPU qualification required.'}],
            'paidOperationStarted': False}

    def biology_boltz_prepare(self, p):
        operation = p.get('operation')
        if operation not in ('design', 'protein_library_screen'):
            raise ValueError('Choose design or protein_library_screen; no standalone PPI scoring endpoint is assumed.')
        # Explicit sequence-only representation; never imply source coordinates were uploaded.
        records = self.s.fasta_parse({'text': p.get('targetFasta', '')})
        if len(records) > 20:
            raise ValueError('At most 20 sequence target chains in this adapter.')
        entities = [{'type': 'protein', 'value': r['sequence'], 'chain_ids': [chr(65+i)]} for i, r in enumerate(records)]
        target = {'type': 'no_template', 'entities': entities}
        refs = []; snapshots = []
        if operation == 'design':
            length = ev.integer(p.get('length'), 'Design length', 5, 500)
            count = ev.integer(p.get('count'), 'Design count', 1, 100)
            request = {'target': target, 'binder_specification': {'type': 'no_template', 'modality': 'peptide' if p.get('modality') == 'peptide' else 'custom_protein',
                        'entities': [{'type': 'designed_protein', 'value': str(length), 'chain_ids': ['Z']}]}, 'num_proteins': count}
        else:
            refs = p.get('candidateIds')
            if not isinstance(refs, list) or not 1 <= len(refs) <= 100 or len(set(refs)) != len(refs):
                raise ValueError('Select 1–100 distinct saved evolution candidates.')
            candidates = [self.evolution.candidate(p['projectId'], id) for id in refs]
            request = {'target': target, 'proteins': [{'id': c['id'], 'entities': [{'type': 'protein', 'value': c['sequence'], 'chain_ids': ['Z']}]} for c in candidates]}
            snapshots = [{'id': c['id'], 'sequenceSha256': c['sequenceSha256']} for c in candidates]
        value = {'id': str(uuid.uuid4()), 'projectId': p['projectId'], 'created': ev.research.utc(), 'state': 'prepared',
                 'provider': 'Boltz API', 'operation': operation, 'sdkContract': SDK_VERSION,
                 'request': request, 'requestSha256': ev.sha(request), 'candidateSnapshots': snapshots,
                 'quote': None, 'remoteId': None, 'result': None,
                 'representation': 'Sequence-only target and candidates. Source poses, biological assembly and peptide applicability are unverified.',
                 'billing': capabilities()['billing']}
        return self.save(value)

    def resource(self, api, value):
        return api.protein.design if value['operation'] == 'design' else api.protein.library_screen

    def biology_boltz_quote(self, p):
        value = self.read(p)
        if value['state'] not in ('prepared', 'quoted'):
            raise ValueError('This request is already submitted or needs reconciliation.')
        if p.get('approveUpload') is not True:
            raise ValueError('Explicitly approve uploading these target/candidate sequences to the external service for a cost estimate.')
        with client() as api:
            try:
                quote = plain(self.resource(api, value).estimate_cost(**value['request']))
            except Exception:
                raise ValueError('Boltz cost estimate failed; check authentication, service availability and the pinned SDK contract. No compute was submitted.') from None
        money(quote['estimated_cost_usd'])
        self.s.db.execute('BEGIN IMMEDIATE')
        current = self.read(p)
        if current['state'] not in ('prepared', 'quoted') or current['requestSha256'] != value['requestSha256']:
            self.s.db.rollback()
            raise ValueError('The request was submitted while its estimate was being obtained; no new quote saved.')
        value.update(state='quoted', quote={'received': ev.research.utc(), 'raw': quote, 'requestSha256': value['requestSha256']})
        return self.save(value)

    def biology_boltz_start(self, p):
        value = self.read(p)
        if value['state'] != 'quoted' or p.get('approved') is not True:
            raise ValueError('Review a current quote and explicitly approve the external paid operation.')
        age = datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(value['quote']['received'])
        if age.total_seconds() > 600 or value['quote']['requestSha256'] != ev.sha(value['request']):
            raise ValueError('The estimate expired or the request changed. Obtain a new quote.')
        limit = money(p.get('maxEstimatedCostUSD'))
        if money(value['quote']['raw']['estimated_cost_usd']) > limit:
            raise ValueError('Quoted cost exceeds the approved estimate; no job submitted.')
        # Resolve credentials first, then atomically claim this one request. On an
        # ambiguous network failure do not auto-resubmit and risk double billing.
        with client() as api:
            import json
            self.s.db.execute('BEGIN IMMEDIATE')
            current = self.read(p)
            if current['state'] != 'quoted' or current['quote'] != value['quote']:
                self.s.db.rollback()
                raise ValueError('Request changed or another submission claimed it.')
            value.update(state='submission_uncertain', approvedEstimateUSD=str(limit), approvalAt=ev.research.utc())
            self.s.db.execute('UPDATE biology_api_requests SET data=? WHERE id=?', (ev.canonical(value), value['id']))
            self.s.db.commit()
            try:
                run = plain(self.resource(api, value).start(**value['request'], idempotency_key=value['id']))
            except Exception:
                raise ValueError('Submission outcome is uncertain. Inspect the Boltz console using this request ID; do not submit a duplicate.') from None
        value.update(state='submitted', remoteId=run['id'], result=run)
        return self.save(value)

    def biology_boltz_jobs(self, p):
        import json
        return [json.loads(r['data']) for r in self.s.rows('SELECT data FROM biology_api_requests WHERE project_id=? ORDER BY created DESC', (p['projectId'],))]

    def biology_boltz_read(self, p):
        value = self.read(p)
        if not value['remoteId']:
            return value
        with client() as api:
            try:
                resource = self.resource(api, value)
                run = plain(resource.retrieve(value['remoteId']))
                # One bounded page only; explicit cursor supports reconnecting.
                page = resource.list_results(value['remoteId'], limit=20, **({'after_id': p['afterId']} if p.get('afterId') else {}))
                results = [plain(row) for row in page.data]
            except Exception:
                raise ValueError('Could not retrieve the saved Boltz job. Reconnecting does not create a new job.') from None
        value.update(result=run, state=run['status'])
        self.save(value)
        return {**value, 'resultPage': results, 'hasMore': page.has_more, 'lastId': results[-1]['id'] if results else None,
                'scoreInterpretation': capabilities()['scoreSemantics'], 'artifactImport': 'Select an official result ID for bounded coordinate download, sequence checks and local SHA-256 receipt. Provider-independent content checksum is not supplied by the SDK.'}

    def biology_boltz_import(self,p):
        if p.get('approvedDownload') is not True:raise ValueError('Approve downloading this selected official result artifact.')
        value=self.read(p)
        if not value.get('remoteId'):raise ValueError('Reconcile the official remote job before downloading outputs.')
        result_id=ev.text(p.get('resultId'),'official result ID',100)
        with client() as api:
            page=self.resource(api,value).list_results(value['remoteId'],ids=result_id,limit=1)
            if len(page.data)!=1:raise ValueError('Official result was not found in this request.')
            result=plain(page.data[0])
        if result['id']!=result_id:raise ValueError('Official API returned a different result identity.')
        artifact=result.get('artifacts',{}).get('structure')
        if not artifact:raise ValueError('Provider has no coordinate artifact for this result.')
        from boltz_artifacts import download,import_result
        raw,receipt=download(artifact)
        return import_result(self.s,value,result,raw,receipt)

    def biology_boltz_reconcile(self,p):
        value=self.read(p)
        if value['state']!='submission_uncertain':return value
        remote=ev.text(p.get('remoteId'),'remote ID from the provider console',100)
        if p.get('confirmedProviderAssociation') is not True:raise ValueError('Confirm that this provider run belongs to the saved request; unknown submissions are never retried automatically.')
        with client() as api:run=plain(self.resource(api,value).retrieve(remote))
        if run['id']!=remote:raise ValueError('Provider run identity mismatch.')
        value.update(remoteId=remote,state=run['status'],result=run,reconciliation={'association':'explicit_user_confirmed_in_provider_console','at':ev.research.utc(),'requestSha256':value['requestSha256']})
        return self.save(value)

    def biology_boltz_stop(self, p):
        value = self.read(p)
        if not value['remoteId']:
            raise ValueError('No known remote job to stop. Reconcile an uncertain submission in the Boltz console.')
        with client() as api:
            try:
                result = plain(self.resource(api, value).stop(value['remoteId']))
            except Exception:
                raise ValueError('Remote stop failed; inspect the service before assuming compute/billing stopped.') from None
        value.update(result=result, state=result['status'])
        return self.save(value)


def dispatch(service, action, payload):
    service.project(payload['projectId'])
    if action in ('biology_boltz_quote','biology_boltz_start','biology_boltz_read','biology_boltz_stop','biology_boltz_import','biology_boltz_reconcile') and os.environ.get('FOLD_PROVIDER_CHILD')!='1':
        try:version=importlib.metadata.version('boltz-api')
        except importlib.metadata.PackageNotFoundError:version=None
        if version!=SDK_VERSION:
            from biology_providers import rpc
            return rpc(service,action,payload)
    return getattr(BoltzAPI(service), action)(payload)
