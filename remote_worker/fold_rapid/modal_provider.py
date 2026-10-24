"""Modal provider for the SAME RAPID engine supervisor, not a second engine.

Construction is offline. Deployment, setup and GPU submission require explicit
approval at the caller. A persistent atomic lease prevents multiple writers to
the scientific SQLite/model volume. Live progress/cancel use a Modal Dict;
completed evidence remains on the Volume beyond Dict expiry.
"""
import hashlib
import json
import math
import pathlib
import re
from .contracts import fields,integer,canonical,manifest,digest


def configuration(value):
    fields(value,('appName','gpu','maxSeconds','hourlyEstimateUSD'),('imageDigest','imageRecipe','volumeName','stateName','privateLicensedImage','modelVolumeName','engineImages','workerMemoryMiB','workerCPUs','setupMaxSeconds'))
    if not re.fullmatch('[a-z][a-z0-9-]{2,60}',value['appName']):raise ValueError('Choose a Modal application name with lowercase letters, digits and hyphens.')
    from .cloud_image import RECIPE,BASE
    if value.get('imageRecipe') not in (None,RECIPE):raise ValueError('Unknown reviewed cloud image recipe.')
    value={**value,'imageDigest':value.get('imageDigest') or (BASE if value.get('imageRecipe')==RECIPE else '')}
    if not isinstance(value['imageDigest'],str) or not re.fullmatch('[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}',value['imageDigest']):raise ValueError('Use a version-pinned existing RAPID CUDA image digest, not a mutable tag.')
    if value['gpu'] not in ('T4','L4','A10','L40S','A100','A100-40GB','A100-80GB','H100','H200','B200'):raise ValueError('Unsupported Modal GPU selection; availability is provider dependent.')
    integer(value['maxSeconds'],60,7200,'Maximum execution seconds')
    rate=value['hourlyEstimateUSD']
    if type(rate)not in(int,float) or not math.isfinite(rate) or not 0<rate<=100:raise ValueError('Supply a reviewed hourly GPU estimate; CPU, memory, storage and network charges are additional.')
    result={**value,'volumeName':value.get('volumeName',value['appName']+'-data'),'stateName':value.get('stateName',value['appName']+'-state')}
    integer(value.get('workerMemoryMiB',65536),4096,262144,'Scientific worker host memory MiB')
    integer(value.get('workerCPUs',2),1,16,'Scientific worker CPUs')
    integer(value.get('setupMaxSeconds',900),60,1800,'CPU setup seconds')
    result['modelVolumeName']=value.get('modelVolumeName',value['appName']+'-models')
    if 'privateLicensedImage' in value and type(value['privateLicensedImage'])is not bool:raise ValueError('Licensed-image consent must be explicit.')
    from .unified_contract import OPERATIONS
    if not isinstance(value.get('engineImages',{}),dict):raise ValueError('Specialized engine images must be an object.')
    for engine,ref in value.get('engineImages',{}).items():
        if engine not in OPERATIONS or not re.fullmatch('[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}',str(ref)):raise ValueError('Use immutable specialized engine image digests.')
    for key in ('volumeName','stateName','modelVolumeName'):
        if not re.fullmatch('[a-zA-Z0-9_-]{1,64}',result[key]):raise ValueError('Invalid provider object name.')
    return result


def cost(value,config):
    cfg=configuration(config);value=manifest(value)
    if value['budget']['seconds']>cfg['maxSeconds']:raise ValueError('Campaign runtime exceeds the deployed function limit.')
    if value['engine']=='rosetta' and cfg.get('privateLicensedImage') is not True:raise ValueError('Rosetta requires an approved private licensed image.')
    return {'gpuEstimateUSD':cfg['hourlyEstimateUSD']*value['budget']['seconds']/3600,'maximumScienceSeconds':value['budget']['seconds'],'gpu':cfg['gpu'],'imageDigest':cfg['imageDigest'],'scope':'GPU runtime estimate only. Cold-start, CPU, memory, storage and transfer charges may apply. Not a hard spending cap; configure a Modal workspace budget.','boltzAPIChargesIncluded':False}


def build_app(value,worker_source=None):
    import modal
    cfg=configuration(value)
    source=pathlib.Path(worker_source or pathlib.Path(__file__).resolve().parents[1])
    code_sha=digest(canonical({str(p.relative_to(source)):digest(p.read_bytes()) for p in sorted((source/'fold_rapid').glob('*.py'))}).encode())
    if cfg.get('imageRecipe'):
        from .cloud_image import definition
        image,cloud_receipt=definition(source.parent)
    else:
        image=modal.Image.from_registry(cfg['imageDigest']);cloud_receipt={}
    image=image.add_local_dir(source,'/opt/fold-worker',copy=True,ignore=['**/__pycache__/**','**/*.pyc','**/dist/**','**/.env*'])
    app=modal.App(cfg['appName']);volume=modal.Volume.from_name(cfg['volumeName'],create_if_missing=True);state=modal.Dict.from_name(cfg['stateName'],create_if_missing=True)
    environment={'PYTHONPATH':'/opt/fold-worker','RAPID_ROOT':'/data/rapid','RAPID_IMAGE_DIGEST':cfg['imageDigest'],'HF_HOME':'/data/rapid/models/huggingface','BGMEE_CODE_SHA256':code_sha,'FOLD_COMPUTE_PROVIDER':'modal','FOLD_ENGINE_ROLE':'cloud','RAPID_IMAGE_RECIPE_SHA256':cloud_receipt.get('recipeSha256','external_registry_image')}
    image=image.env(environment)
    analysis=source.parent/'scientific'
    if analysis.is_dir():
        for name in ('intelligence.py','biology_assessment.py','research.py','peptides.py','amino-acids.json'):image=image.add_local_file(analysis/name,'/opt/fold-worker/native_analysis/'+name,copy=True)

    @app.function(serialized=True,name='execute',image=image,gpu=cfg['gpu'],volumes={'/data':volume},timeout=cfg['maxSeconds']+180,min_containers=0,max_containers=1,scaledown_window=30,retries=0)
    def execute(value,key,approved=False):
        import threading
        from fold_rapid.store import Store
        from fold_rapid.runner import execute as run_engine
        value=manifest(value);cost(value,cfg)
        if approved is not True:raise ValueError('Explicit scientific workload and cost approval is required.')
        # Atomic across GPU and setup functions/containers; not a filesystem lock.
        token={'kind':'scientific','request':key}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('Another setup/scientific operation owns the volume; reconnect rather than submit a duplicate.')
        stopped=threading.Event();original_event=Store.event
        try:
            volume.reload();store=Store('/data/rapid');submitted=store.submit(value,key);id=submitted['jobId']
            state['request:'+key]={'jobId':id,'manifestSha256':digest(canonical(value).encode()),'state':store.get(id)['state']}
            if not submitted['created']:
                return store.get(id)
            def event(self,job,value):
                original_event(self,job,value)
                row=self.get(job);row['manifest']['target'].pop('contentBase64',None)
                state['job:'+job]={'job':row,'lastEvent':value}
            Store.event=event
            def cancellations():
                while not stopped.wait(1):
                    try:
                        if state.get('cancel:'+id,False):store.cancel(id)
                    except Exception:pass  # Deadline remains enforced even during a control-plane outage.
            thread=threading.Thread(target=cancellations,daemon=True);thread.start()
            run_engine('/data/rapid',id)
            result=store.get(id);result['manifest']['target'].pop('contentBase64',None)
            volume.commit();state['job:'+id]={'job':result,'artifactsCommitted':True};return result
        finally:
            stopped.set();Store.event=original_event
            try:volume.commit()
            finally:
                if state.get('writer-lease')==token:state.pop('writer-lease')

    @app.function(serialized=True,name='control',image=image,volumes={'/data':volume},timeout=90,min_containers=0,max_containers=2,scaledown_window=10,retries=0)
    def control(operation,payload):
        from fold_rapid.contracts import identifier
        if operation=='request_status':
            fields(payload,('idempotencyKey',));return state.get('request:'+payload['idempotencyKey'],{'state':'not_observed','resubmit':False})
        id=identifier(payload.get('jobId'))
        if operation=='cancel':state['cancel:'+id]=True;return {'jobId':id,'state':'cancel_requested','billingStopped':False}
        if operation=='status':
            result=state.get('job:'+id)
            if result:return result
        if state.get('writer-lease'):raise ValueError('Live metadata is unavailable; the persistent volume is busy. No resubmission performed.')
        volume.reload()
        from fold_rapid.api import Worker
        if operation not in ('status','artifact_list','artifact_read','candidate_list'):raise ValueError('Unsupported provider control operation.')
        name='job_status' if operation=='status' else operation
        return Worker('/data/rapid').dispatch({'apiVersion':2,'requestId':'modal-control','operation':name,'payload':payload})['result']

    @app.function(serialized=True,name='setup',image=image,cpu=(2,2),memory=(8192,8192),volumes={'/data':volume},timeout=cfg.get('setupMaxSeconds',900),min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def setup(engine,kind,approved=False):
        if approved is not True:raise ValueError('Approve the CPU setup cost and any model download separately.')
        if kind not in ('runtime','models'):raise ValueError('Unknown setup operation.')
        token={'kind':kind,'engine':engine}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('A scientific/setup operation owns the volume.')
        try:
            volume.reload()
            pathlib.Path('/data/rapid').mkdir(parents=True,exist_ok=True)
            if kind=='runtime':
                from fold_rapid.install import install
                result=install('/data/rapid',engine,True)
            else:
                from fold_rapid.models import install
                result=install('/data/rapid',engine,True)
            volume.commit();return result
        finally:
            if state.get('writer-lease')==token:state.pop('writer-lease')
    from .unified_modal import attach
    model_volume=modal.Volume.from_name(cfg['modelVolumeName'],create_if_missing=True)
    attach(app,cfg,image,volume,state,model_volume)
    app._fold_resources=(state,volume,model_volume)
    return app


def submit(config,value,key,approved,maximum_estimate):
    import modal
    cfg=configuration(config);estimate=cost(value,cfg)
    if approved is not True or type(maximum_estimate)not in(int,float) or not math.isfinite(maximum_estimate) or maximum_estimate<estimate['gpuEstimateUSD']:raise ValueError('Review and approve this workload and its current estimate first.')
    # Modal functions do not promise client-side exactly-once submission. The
    # native ledger claims the request before calling this method; ambiguous
    # responses require request_status reconciliation, never an automatic retry.
    call=modal.Function.from_name(cfg['appName'],'execute').spawn(value,key,True)
    return {'callId':call.object_id,'idempotencyKey':key,'estimate':estimate,'provider':'modal','state':'submitted','scientificGPUValidated':False}


def deploy_app(app):
    """Hydrate closure-owned durable objects before serialized function upload."""
    for resource in app._fold_resources:resource.hydrate()
    return app.deploy()
