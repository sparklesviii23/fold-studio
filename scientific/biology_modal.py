"""Native persistent Modal ledger using the same RAPID manifests and importers."""
import base64
import copy
import hashlib
import json
import math
import pathlib
import re
import uuid
import evolution as ev
import research
import biology_providers
import rapid_remote

ACTIONS={'biology_modal_configure','biology_modal_status','biology_modal_prepare','biology_modal_submit','biology_modal_refresh','biology_modal_cancel','biology_modal_jobs','biology_modal_import','biology_modal_deploy','biology_modal_setup','biology_provider_credentials'}
NETWORK={'biology_modal_submit','biology_modal_refresh','biology_modal_cancel','biology_modal_import','biology_modal_deploy','biology_modal_setup'}


def contract():
    import biology_pipeline
    biology_pipeline.common()
    from fold_rapid.modal_provider import configuration,cost,build_app,submit
    return configuration,cost,build_app,submit


def table(s):s.db.execute('CREATE TABLE IF NOT EXISTS biology_modal_jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL)')


def save(s,row):
    with s.db:s.db.execute('INSERT OR REPLACE INTO biology_modal_jobs VALUES(?,?,?,?)',(row['id'],row['projectId'],ev.canonical(row),row['created']))
    return row


def read(s,p):
    row=s.db.execute('SELECT data FROM biology_modal_jobs WHERE id=? AND project_id=?',(p.get('id'),p['projectId'])).fetchone()
    if not row:raise ValueError('Choose a Modal request in this project.')
    return json.loads(row[0])


def profile(s):
    value=s.setting('biologyModal')
    if not value:raise ValueError('Configure an existing immutable RAPID worker image and Modal application first.')
    return value


def control(cfg,operation,payload):
    import modal
    return modal.Function.from_name(cfg['appName'],'control').remote(operation,payload)


def public(row):
    value=copy.deepcopy(row);value.get('manifest',{}).get('target',{}).pop('contentBase64',None)
    return value


class Transport(rapid_remote.RapidRemote):
    def __init__(self,s,cfg):self.service=s;self.cfg=cfg;self.cloud=self
    def profile(self,id):return {'id':id}
    def call(self,entry,operation,payload):return control(self.cfg,{'job_status':'status','job_cancel':'cancel'}.get(operation,operation),payload)


def dispatch(s,action,p):
    s.project(p['projectId']);table(s)
    if action=='biology_provider_credentials':
        from provider_credentials import access
        if p.get('approved') is not True:raise ValueError('Approve saving or removing this provider credential in macOS Keychain.')
        access(p.get('account'),p.get('secret'),p.get('remove') is True)
        return {'saved':not p.get('remove'),'account':p['account'],'storage':'macOS Keychain','secretReturned':False}
    if action=='biology_modal_configure':
        cfg=contract()[0](p['configuration'])
        with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('biologyModal',ev.canonical(cfg)))
        return {'configuration':cfg,'deployed':False,'gpuStarted':False}
    if action=='biology_modal_status':return {'configuration':s.setting('biologyModal'),'sdk':biology_providers.status(s),'gpuQualified':False,'authentication':'Official Modal credentials or macOS Keychain; account access is verified only by a requested operation.'}
    if action=='biology_modal_jobs':return [public(json.loads(row['data'])) for row in s.rows('SELECT data FROM biology_modal_jobs WHERE project_id=? ORDER BY created DESC',(p['projectId'],))]
    cfg=profile(s)
    if action=='biology_modal_prepare':
        from intelligence import Lab
        record,path=Lab(s).record(p['structureId'])
        if record['project_id']!=p['projectId']:raise ValueError('Selected structure belongs to another project.')
        raw=path.read_bytes()
        if len(raw)>2000000 or hashlib.sha256(raw).hexdigest()!=record['data']['sha256']:raise ValueError('Target size/checksum changed.')
        value=copy.deepcopy(p['manifest']);value['target']={**value['target'],'format':'pdb' if record['data']['format']=='pdb' else 'cif','contentBase64':base64.b64encode(raw).decode(),'sha256':record['data']['sha256']}
        # Same validation and molecule admission as the Vast worker, before upload.
        import biology_pipeline
        biology_pipeline.common()
        from fold_rapid.contracts import manifest
        from fold_rapid.molecules import selected_target
        value=manifest(value);selected_target(value);estimate=contract()[1](value,cfg)
        row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'state':'prepared','configuration':cfg,'manifest':value,'manifestSha256':ev.sha(value),'estimate':estimate,'idempotencyKey':uuid.uuid4().hex,'created':research.utc(),'sourceRecordId':record['id']}
        return public(save(s,row))
    if action in NETWORK and not __import__('os').environ.get('FOLD_PROVIDER_CHILD'):return biology_providers.rpc(s,action,p)
    if action=='biology_modal_deploy':
        if p.get('approvedDeployment') is not True:raise ValueError('Approve deploying the reviewed image/source; image builds and storage may have provider costs.')
        app=contract()[2](cfg);result=app.deploy()
        return {'state':'deployed','appId':app.app_id,'result':str(result),'scientificGPUValidated':False,'configuration':cfg}
    if action=='biology_modal_setup':
        if p.get('approvedSetupCost') is not True or p.get('kind')=='models' and p.get('approvedModelDownload') is not True:raise ValueError('Approve CPU setup costs and model downloads separately.')
        if p.get('engine') not in ('bindcraft2','proteinmpnn','af2_multimer','boltzgen','solublempnn','esmfold2','esmfold2_fast') or p.get('kind') not in ('runtime','models'):raise ValueError('Unsupported provider setup request.')
        import modal
        call=modal.Function.from_name(cfg['appName'],'setup').spawn(p['engine'],p['kind'],True)
        row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'state':'setup_submitted','callId':call.object_id,'configuration':cfg,'kind':p['kind'],'engine':p['engine'],'created':research.utc()}
        return public(save(s,row))
    row=read(s,p);cfg=row['configuration']
    if action=='biology_modal_submit':
        if p.get('approvedResearchTransfer') is not True or p.get('approvedWorkload') is not True:raise ValueError('Approve this molecular upload, workload and estimate.')
        estimate=contract()[1](row['manifest'],cfg)
        if type(p.get('maxEstimatedCostUSD'))not in(int,float) or not math.isfinite(p['maxEstimatedCostUSD']) or p['maxEstimatedCostUSD']<estimate['gpuEstimateUSD']:raise ValueError('Approved estimate is below the reviewed GPU runtime estimate.')
        # Claim before the network, using a write transaction and a fresh row.
        s.db.execute('BEGIN IMMEDIATE');latest=read(s,p)
        if latest['state']!='prepared':s.db.rollback();raise ValueError('This request was already claimed; reconnect instead of resubmitting.')
        reserved=sum(json.loads(r['data']).get('estimate',{}).get('gpuEstimateUSD',0) for r in s.rows('SELECT data FROM biology_modal_jobs') if json.loads(r['data']).get('state')!='prepared')
        if reserved+estimate['gpuEstimateUSD']>30:s.db.rollback();raise ValueError('The local 30 USD cumulative GPU-estimate allowance is exhausted. Actual provider charges and separate setup/API costs must still be monitored.')
        latest.update(state='submission_uncertain',claimed=research.utc());s.db.execute('UPDATE biology_modal_jobs SET data=? WHERE id=?',(ev.canonical(latest),latest['id']));s.db.commit()
        try:result=contract()[3](cfg,row['manifest'],row['idempotencyKey'],True,p['maxEstimatedCostUSD'])
        except Exception:raise ValueError('Modal submission outcome is uncertain. Use Refresh to reconcile; no automatic retry.') from None
        latest.update(result);return public(save(s,latest))
    if action=='biology_modal_refresh':
        import modal
        if row.get('callId'):
            try:
                result=modal.FunctionCall.from_id(row['callId']).get(timeout=0)
                row.update(state='finished',result=result)
                if isinstance(result,dict) and result.get('jobId'):row['jobId']=result['jobId']
                elif isinstance(result,dict) and result.get('id'):row['jobId']=result['id']
            except TimeoutError:pass
            except modal.exception.OutputExpiredError:row['callOutputExpired']=True
        if row.get('idempotencyKey'):
            observed=control(cfg,'request_status',{'idempotencyKey':row['idempotencyKey']})
            if observed.get('jobId'):row.update(jobId=observed['jobId'],state=observed['state'])
        if row.get('jobId'):
            remote=control(cfg,'status',{'jobId':row['jobId']});row['remote']=remote;row['state']=remote.get('job',remote).get('state',row['state'])
        row['checked']=research.utc();return public(save(s,row))
    if action=='biology_modal_cancel':
        if not row.get('jobId'):raise ValueError('Reconcile the remote job ID before cancellation; unknown requests cannot be safely resubmitted.')
        result=control(cfg,'cancel',{'jobId':row['jobId']});row.update(cancellation=result,state='cancel_requested');return public(save(s,row))
    if action=='biology_modal_import':
        if not row.get('jobId'):raise ValueError('Read the finished remote job before importing.')
        remote=control(cfg,'status',{'jobId':row['jobId']});job=remote.get('job',remote)
        if job.get('state') not in ('completed','partial','rejected','failed','cancelled','interrupted'):raise ValueError('Wait until scientific outputs are finalized before synchronization.')
        return Transport(s,cfg).gpu_rapid_import({'projectId':p['projectId'],'id':row['id'],'jobId':row['jobId']})
    raise ValueError('Unsupported Modal action.')
