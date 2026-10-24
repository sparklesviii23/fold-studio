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

ACTIONS={'biology_cloud_prepare_models','biology_modal_qualify','biology_unified_prepare','biology_modal_check','biology_modal_configure','biology_modal_status','biology_modal_prepare','biology_modal_submit','biology_modal_refresh','biology_modal_cancel','biology_modal_jobs','biology_modal_import','biology_modal_deploy','biology_modal_setup','biology_provider_credentials'}
NETWORK={'biology_cloud_prepare_models','biology_modal_qualify','biology_modal_check','biology_modal_submit','biology_modal_refresh','biology_modal_cancel','biology_modal_import','biology_modal_deploy','biology_modal_setup'}
LOCAL_PROVIDER={'biology_unified_prepare','biology_modal_prepare'}


def contract():
    import biology_pipeline
    biology_pipeline.common()
    from fold_rapid.modal_provider import configuration,cost,build_app,submit
    return configuration,cost,build_app,submit


def table(s):s.db.execute('CREATE TABLE IF NOT EXISTS biology_modal_jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL)')


def save(s,row):
    if 'accountId' not in row:
        from cloud_accounts import get
        previous=s.db.execute('SELECT data FROM biology_modal_jobs WHERE id=?',(row['id'],)).fetchone()
        row['accountId']=json.loads(previous[0]).get('accountId') if previous else get(s).get('activeId')
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


def unified_control(cfg,operation,payload):
    import modal
    return modal.Function.from_name(cfg['appName'],'unified_control').remote(operation,payload)


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


class UnifiedTransport(rapid_remote.RapidRemote):
    def __init__(self,s,cfg,campaign,stage):self.service=s;self.cfg=cfg;self.cloud=self;self.campaign=campaign;self.stage=stage
    def profile(self,id):return {'id':id}
    def call(self,entry,operation,payload):
        return unified_control(self.cfg,'stage',{'campaignId':self.campaign,'stageId':self.stage,'operation':operation,'payload':{k:v for k,v in payload.items() if k!='jobId'}})


def prepare_unified(s,p):
    import biology_pipeline
    biology_pipeline.common()
    from intelligence import Lab
    from fold_rapid.molecules import inspect
    from fold_rapid.unified_contract import campaign,blockers
    record,path=Lab(s).record(p['structureId'])
    if record['project_id']!=p['projectId']:raise ValueError('Structure belongs to another project.')
    raw=path.read_bytes();fmt='pdb' if record['data']['format']=='pdb' else 'cif'
    if hashlib.sha256(raw).hexdigest()!=record['data']['sha256']:raise ValueError('Library snapshot checksum changed.')
    mapping=inspect(raw,fmt);targets=p.get('targetChains',[]);binders=p.get('binderChains',[])
    generators=p.get('generators',[])
    parents=[{'id':record['id'],'binderChains':binders,'sequences':{ch:mapping['chains'][ch]['sequence'] for ch in targets+binders}}] if binders else []
    engines=set(p['workflow']['redesign']+p['workflow']['predictors']+[g['engine'] for g in generators]+(['rosetta'] if p['workflow']['rosetta'] else []))
    cfg=profile(s)
    limits=p.get('stageLimitsSeconds',{})
    if not isinstance(limits,dict) or set(limits)-engines:raise ValueError('Runtime limits must refer to selected engines.')
    budget={'seconds':p['seconds'],'maxEstimatedUSD':p['maxEstimatedUSD']}
    if 'resourcePricing' in p:budget['resourcePricing']=p['resourcePricing']
    value=campaign({'schemaVersion':1,'kind':'unified','execution':{'mode':'cloud','provider':'modal','localFallback':False},'strategy':p['strategy'],'target':{'format':fmt,'contentBase64':base64.b64encode(raw).decode(),'sha256':record['data']['sha256'],'chains':targets,'label':record['name']},'parents':parents,'generators':generators,'workflow':p['workflow'],'stageBudgets':{e:{'seconds':limits.get(e,p['stageSeconds']),'hourlyEstimateUSD':cfg['hourlyEstimateUSD']} for e in engines},'budget':budget,'seed':p['seed'],'policy':p.get('policy',{}),'constraints':p.get('constraints',{})})
    from fold_rapid.unified_modal import cost
    quote=cost(value,cfg)
    row={'id':uuid.uuid4().hex,'kind':'unified','projectId':p['projectId'],'state':'prepared','configuration':cfg,'manifest':value,'manifestSha256':ev.sha(value),'estimate':quote,'blockers':blockers(value),'idempotencyKey':uuid.uuid4().hex,'created':research.utc(),'sourceRecordId':record['id']}
    return public(save(s,row))

def dispatch(s,action,p):
    s.project(p['projectId']);table(s)
    # Coordinate parsing/contract validation needs pinned gemmi. The bundled
    # JAX supervisor lacks it; use the existing isolated provider interpreter.
    # These preparation actions never invoke Modal or upload the snapshot.
    if action in LOCAL_PROVIDER and not __import__('os').environ.get('FOLD_PROVIDER_CHILD'):
        try:__import__('gemmi')
        except ImportError:return biology_providers.rpc(s,action,p)
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
    cfg=read(s,p)['configuration'] if p.get('id') else profile(s)
    if action=='biology_unified_prepare':return prepare_unified(s,p)
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
    if action in NETWORK:
        import biology_pipeline
        biology_pipeline.common()
    if action=='biology_cloud_prepare_models':
        if p.get('approvedCPUSetup') is not True or p.get('approvedModelDownloads') is not True or type(p.get('maxApprovedUSD'))not in(int,float) or not 0<p['maxApprovedUSD']<=1:raise ValueError('Approve this cloud-only CPU/runtime/checkpoint plan with an allowance up to 1 USD. No GPU inference is included.')
        import biology_pipeline
        biology_pipeline.common()
        from fold_rapid.bootstrap import describe
        plan=describe(p.get('plan'))
        s.db.execute('BEGIN IMMEDIATE')
        active=[json.loads(r['data']) for r in s.rows('SELECT data FROM biology_modal_jobs') if json.loads(r['data']).get('kind')=='bootstrap' and json.loads(r['data']).get('configuration',{}).get('appName')==cfg['appName'] and json.loads(r['data']).get('state') in ('submission_uncertain','submitted','running')]
        if active:s.db.rollback();raise ValueError('An existing cloud setup is active or uncertain; refresh it instead of submitting another.')
        key=uuid.uuid4().hex
        row={'id':key,'projectId':p['projectId'],'kind':'bootstrap','engine':plan['plan'],'state':'submission_uncertain','configuration':cfg,'created':research.utc(),'plan':plan,'maximumApprovedUSD':p['maxApprovedUSD'],'gpuStarted':False}
        save(s,row)
        import modal
        try:call=modal.Function.from_name(cfg['appName'],'unified_prepare_models').spawn(plan['plan'],key,True)
        except Exception:raise ValueError('Cloud setup dispatch outcome is uncertain. Refresh this saved request; no automatic resubmission.') from None
        row.update(state='submitted',callId=call.object_id);return public(save(s,row))
    if action=='biology_modal_qualify':
        if p.get('approvedQualification') is not True or type(p.get('maxEstimatedCostUSD'))not in(int,float) or not math.isfinite(p['maxEstimatedCostUSD']) or p['maxEstimatedCostUSD']<cfg['hourlyEstimateUSD']*120/3600:raise ValueError('Approve one engine’s 120-second CUDA numerical test and reviewed GPU estimate; startup/CPU/storage costs are additional.')
        if p.get('engine') not in ('bindcraft2','boltzgen','proteinmpnn','solublempnn','esmfold2_fast','esmfold2','af2_multimer'):raise ValueError('Select a supported engine runtime.')
        row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'kind':'gpu_qualification','engine':p['engine'],'state':'submission_uncertain','configuration':cfg,'created':research.utc()}
        save(s,row)
        import modal
        call=modal.Function.from_name(cfg['appName'],'unified_qualify').spawn(p['engine'],True)
        row.update(state='submitted',callId=call.object_id);return public(save(s,row))
    if action=='biology_modal_check':
        if p.get('approvedControlCost') is not True:raise ValueError('Approve a small CPU control-function invocation; no GPU or model execution.')
        return unified_control(cfg,'inventory',{})
    if action=='biology_modal_deploy':
        if p.get('approvedDeployment') is not True:raise ValueError('Approve deploying the reviewed image/source; image builds and storage may have provider costs.')
        worker_source=None
        if cfg.get('imageRecipe'):
            from fold_rapid.cloud_image import prepare_release
            release=prepare_release(s.root/'cloud-engine-source',rapid_remote.artifact()[0]);worker_source=release/'worker'
        from fold_rapid.modal_provider import deploy_app
        app=contract()[2](cfg,worker_source=worker_source);result=deploy_app(app)
        return {'state':'deployed','appId':app.app_id,'result':str(result),'scientificGPUValidated':False,'configuration':cfg}
    if action=='biology_modal_setup':
        if p.get('approvedSetupCost') is not True or p.get('kind')=='models' and p.get('approvedModelDownload') is not True:raise ValueError('Approve CPU setup costs and model downloads separately.')
        if p.get('engine') not in ('bindcraft2','proteinmpnn','af2_multimer','boltzgen','solublempnn','esmfold2','esmfold2_fast') or p.get('kind') not in ('runtime','models'):raise ValueError('Unsupported provider setup request.')
        import modal
        call=modal.Function.from_name(cfg['appName'],'unified_setup' if p.get('unified') else 'setup').spawn(p['engine'],p['kind'],True)
        row={'id':uuid.uuid4().hex,'projectId':p['projectId'],'state':'setup_submitted','callId':call.object_id,'configuration':cfg,'kind':p['kind'],'engine':p['engine'],'created':research.utc()}
        return public(save(s,row))
    row=read(s,p);cfg=row['configuration']
    if action=='biology_modal_submit':
        if p.get('approvedResearchTransfer') is not True or p.get('approvedWorkload') is not True:raise ValueError('Approve this molecular upload, workload and estimate.')
        unified=row.get('kind')=='unified'
        if unified:
            from fold_rapid.unified_modal import cost as unified_cost
            estimate=unified_cost(row['manifest'],cfg)
        else:estimate=contract()[1](row['manifest'],cfg)
        required=row['manifest']['budget']['maxEstimatedUSD'] if unified else estimate['gpuEstimateUSD']
        if row.get('blockers'):raise ValueError('This strategy is blocked: '+'; '.join(row['blockers']))
        if type(p.get('maxEstimatedCostUSD'))not in(int,float) or not math.isfinite(p['maxEstimatedCostUSD']) or p['maxEstimatedCostUSD']<required:raise ValueError('Approved estimate is below the reviewed GPU runtime estimate.')
        # Claim before the network, using a write transaction and a fresh row.
        s.db.execute('BEGIN IMMEDIATE');latest=read(s,p)
        if latest['state']!='prepared':s.db.rollback();raise ValueError('This request was already claimed; reconnect instead of resubmitting.')
        reserved=sum(json.loads(r['data']).get('estimate',{}).get('allowanceUSD',json.loads(r['data']).get('estimate',{}).get('gpuEstimateUSD',0)) for r in s.rows('SELECT data FROM biology_modal_jobs') if json.loads(r['data']).get('state')!='prepared')
        if reserved+required>30:s.db.rollback();raise ValueError('The local 30 USD cumulative GPU-estimate allowance is exhausted. Actual provider charges and separate setup/API costs must still be monitored.')
        latest.update(state='submission_uncertain',claimed=research.utc());s.db.execute('UPDATE biology_modal_jobs SET data=? WHERE id=?',(ev.canonical(latest),latest['id']));s.db.commit()
        try:
            if unified:
                from fold_rapid.unified_modal import submit
            else:submit=contract()[3]
            result=submit(cfg,row['manifest'],row['idempotencyKey'],True,p['maxEstimatedCostUSD'])
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
                if isinstance(result,dict) and result.get('campaignId'):row['campaignId']=result['campaignId']
            except TimeoutError:pass
            except modal.exception.OutputExpiredError:row['callOutputExpired']=True
            except Exception as exc:row['callFailureType']=type(exc).__name__;row['state']='remote_failure_pending_reconciliation'
        if row.get('idempotencyKey'):
            observed=(unified_control if row.get('kind')=='unified' else control)(cfg,'request_status',{'idempotencyKey':row['idempotencyKey']})
            if observed.get('campaignId'):row.update(campaignId=observed['campaignId'],state=observed['state'])
            if observed.get('jobId'):row.update(jobId=observed['jobId'],state=observed['state'])
        if row.get('jobId'):
            remote=control(cfg,'status',{'jobId':row['jobId']});row['remote']=remote;row['state']=remote.get('job',remote).get('state',row['state'])
        if row.get('kind')=='bootstrap':
            observed=unified_control(cfg,'bootstrap_status',{'requestKey':row['id']});row['remote']=observed
            if observed.get('state')!='not_observed':row['state']=observed['state']
        if row.get('campaignId'):
            remote=unified_control(cfg,'status',{'campaignId':row['campaignId']});row.update(remote=remote,state=remote['state'])
        row['checked']=research.utc();return public(save(s,row))
    if action=='biology_modal_cancel':
        if row.get('campaignId'):
            result=unified_control(cfg,'cancel',{'campaignId':row['campaignId']});row.update(cancellation=result,state='cancel_requested');return public(save(s,row))
        if not row.get('jobId'):raise ValueError('Reconcile the remote job ID before cancellation; unknown requests cannot be safely resubmitted.')
        result=control(cfg,'cancel',{'jobId':row['jobId']});row.update(cancellation=result,state='cancel_requested');return public(save(s,row))
    if action=='biology_modal_import':
        if row.get('kind')=='unified':
            if not row.get('campaignId'):raise ValueError('Refresh the existing campaign identity first.')
            remote=unified_control(cfg,'status',{'campaignId':row['campaignId']})
            if remote['state'] not in ('COMPLETED','PARTIALLY_COMPLETE','FAILED','CANCELLED'):raise ValueError('Wait until the campaign commits its scientific artifacts.')
            imported=[]
            for stage in remote['stages']:
                if stage.get('jobId') and stage['state'] in ('STAGE_COMPLETE','FAILED'):
                    result=UnifiedTransport(s,cfg,row['campaignId'],stage['stageId']).gpu_rapid_import({'projectId':p['projectId'],'id':row['id'],'jobId':stage['jobId']});imported.extend(result['records'])
            return {'records':imported,'campaignId':row['campaignId'],'qualifiedCandidates':[],'acceptanceUnchanged':True}
        if not row.get('jobId'):raise ValueError('Read the finished remote job before importing.')
        remote=control(cfg,'status',{'jobId':row['jobId']});job=remote.get('job',remote)
        if job.get('state') not in ('completed','partial','rejected','failed','cancelled','interrupted'):raise ValueError('Wait until scientific outputs are finalized before synchronization.')
        return Transport(s,cfg).gpu_rapid_import({'projectId':p['projectId'],'id':row['id'],'jobId':row['jobId']})
    raise ValueError('Unsupported Modal action.')
