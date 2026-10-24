"""Modal modular functions for the portable unified controller.

Only the CPU coordinator writes campaign metadata. Every model owns a different
stage SQLite database; model installation has its own Volume and global lease.
No retry policy can replay an ambiguous paid stage.
"""
import pathlib
import math
from .unified_contract import campaign,estimate,OPERATIONS
from .contracts import digest,canonical


def cost(value,cfg):
    value=campaign(value)
    if value['budget']['seconds']>cfg['maxSeconds']:raise ValueError('Campaign exceeds the deployed coordinator runtime.')
    for e,b in value['stageBudgets'].items():
        if e!='rosetta' and b['hourlyEstimateUSD']!=cfg['hourlyEstimateUSD']:raise ValueError('GPU stage rates must match the reviewed deployment GPU rate; no silent price or GPU change.')
    if value['workflow']['rosetta'] and not cfg.get('privateLicensedImage'):raise ValueError('Rosetta requires an authorized private licensed runtime/image.')
    return {**estimate(value),'workerHostMemoryMiB':cfg.get('workerMemoryMiB',65536),'workerCPUs':cfg.get('workerCPUs',2),'gpu':cfg['gpu'],'imageDigest':cfg['imageDigest'],'scientificGPUValidated':False}


def attach(app,cfg,image,data,state,model_volume):
    import modal
    functions={}
    for engine in OPERATIONS:
        def factory(engine):
            stage_image=image
            if engine in cfg.get('engineImages',{}):
                stage_image=modal.Image.from_registry(cfg['engineImages'][engine]).add_local_dir(pathlib.Path(__file__).resolve().parents[1],'/opt/fold-worker',copy=True,ignore=['**/__pycache__/**','**/*.pyc','**/dist/**']).env({'PYTHONPATH':'/opt/fold-worker','RAPID_RELEASE_DIR':'/opt/fold-rapid-release','FOLD_COMPUTE_PROVIDER':'modal','RAPID_IMAGE_DIGEST':cfg['engineImages'][engine]})
            @app.function(serialized=True,name='unified_'+engine,image=stage_image,gpu=None if engine=='rosetta' else cfg['gpu'],volumes={'/data':data,'/models':model_volume},cpu=cfg.get('workerCPUs',2),memory=cfg.get('workerMemoryMiB',65536),timeout=cfg['maxSeconds']+150,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
            def execute_stage(campaign_id,stage,value):
                from fold_rapid.unified import CampaignStore,LocalStages
                from fold_rapid.store import Store
                import threading
                data.reload();model_volume.reload();folder=CampaignStore('/data/rapid').folder(campaign_id)
                row=CampaignStore('/data/rapid').get(campaign_id)
                if not any(s['stageId']==stage['stageId'] and s['manifestSha256']==digest(canonical(value).encode()) for s in row['stages']):raise ValueError('Stage identity is not committed in the campaign journal.')
                if value['engine']!=engine:raise ValueError('Stage engine differs from the specialized function.')
                import datetime,time
                expires=datetime.datetime.fromisoformat(row['created']).timestamp()+row['manifest']['budget']['seconds']
                cancelled=lambda:bool(state.get('unified-cancel:'+campaign_id,False)) or time.time()>=expires
                if cancelled():raise ValueError('Campaign cancellation prevents this stage.')
                # Claim once across all invocations, not just one container.
                key='unified-stage:'+campaign_id+':'+stage['stageId']
                if not state.put(key,{'state':'claimed'},skip_if_exists=True):raise ValueError('Stage already claimed. Reconcile its committed outputs; never replay automatically.')
                original=Store.event
                def event(self,id,value):
                    original(self,id,value)
                    state[key]={'state':self.get(id)['state'],'jobId':id,'lastEvent':value}
                Store.event=event
                def checkpoint(value):state[key]={**value,'state':'running'}
                try:
                    result=LocalStages('/data/rapid',folder,configuration_root='/models/rapid')(stage,value,checkpoint,cancelled)
                    data.commit();state[key]={'jobId':result['job']['id'],'state':result['job']['state'],'artifactsCommitted':True}
                    return result
                finally:Store.event=original;data.commit()
            return execute_stage
        functions[engine]=factory(engine)

    @app.function(serialized=True,name='unified_execute',image=image,volumes={'/data':data,'/models':model_volume},cpu=1,memory=4096,timeout=cfg['maxSeconds']+180,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def unified_execute(value,key,approved=False):
        from fold_rapid.unified import CampaignStore,run
        import time
        if approved is not True:raise ValueError('Approve the complete cloud campaign before execution.')
        cost(value,cfg);token={'kind':'unified','request':key}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('Another campaign/setup owns shared scientific storage; reconcile existing operations.')
        try:
            data.reload();model_volume.reload();store=CampaignStore('/data/rapid');submitted=store.submit(value,key,True);id=submitted['campaignId']
            state['unified-request:'+key]=submitted
            def publish(row):data.commit();state['unified:'+id]=row
            if not submitted['created']:
                return store.status(id)  # reconnect never restarts a claimed campaign
            publish(store.status(id))
            class DistributedStages:
                def preflight(self,engine,value):
                    from fold_rapid.registry import inventory
                    description=next(e for e in inventory('/models/rapid')['engines'] if e['id']==engine)
                    return {'ready':description['executionAvailable'],'reason':description['status']}
                def __call__(self,stage,value,checkpoint,cancelled):
                    call=functions[stage['engine']].spawn(id,stage,value)
                    checkpoint({'callId':call.object_id})
                    while True:
                        try:result=call.get(timeout=1);break
                        except TimeoutError:
                            live=state.get('unified-stage:'+id+':'+stage['stageId'],{})
                            if live.get('jobId') and stage.get('jobId')!=live['jobId']:checkpoint({'jobId':live['jobId']})
                            # The model supervisor observes cancellation and finalizes
                            # artifacts. Don't terminate it before evidence is committed.
                    data.reload()
                    checkpoint({'jobId':result['job']['id']})
                    return result
            result=run('/data/rapid',id,DistributedStages(),publish,lambda:bool(state.get('unified-cancel:'+id,False)),lock_path='/tmp/unified-'+id+'.lock')
            publish(result);return result
        finally:
            data.commit()
            if state.get('writer-lease')==token:state.pop('writer-lease')

    @app.function(serialized=True,name='unified_control',image=image,volumes={'/data':data,'/models':model_volume},timeout=90,min_containers=0,max_containers=2,scaledown_window=10,retries=0)
    def unified_control(operation,payload):
        from fold_rapid.contracts import fields,identifier
        from fold_rapid.unified import CampaignStore,TERMINAL
        if operation=='request_status':
            fields(payload,('idempotencyKey',));return state.get('unified-request:'+payload['idempotencyKey'],{'state':'not_observed','resubmit':False})
        if operation=='inventory':
            fields(payload,());model_volume.reload()
            from fold_rapid.registry import inventory
            return {'deploymentReachable':True,'scientificCloudQualified':False,'models':inventory('/models/rapid'),'campaignStatesDurable':True,'executionPolicy':'modular_sequential'}
        id=identifier(payload.get('campaignId'))
        if operation=='cancel':state['unified-cancel:'+id]=True;return {'campaignId':id,'state':'cancel_requested','billingStopped':False}
        live=state.get('unified:'+id)
        if operation=='status' and live:
            for stage in live.get('stages',[]):
                if stage['state']=='RUNNING':stage['live']=state.get('unified-stage:'+id+':'+stage['stageId'])
            return live
        # Never open/reload a shared scientific volume while its owner writes.
        if state.get('writer-lease'):raise ValueError('Artifacts are being committed by the campaign owner; use live status and reconnect later.')
        data.reload()
        from fold_rapid.api import Worker
        name={'status':'unified_status','stage':'unified_stage'}.get(operation)
        if not name:raise ValueError('Unsupported unified control operation.')
        return Worker('/data/rapid').dispatch({'apiVersion':2,'requestId':'unified-control','operation':name,'payload':payload})['result']

    @app.function(serialized=True,name='unified_qualify',image=image,gpu=cfg['gpu'],cpu=2,memory=4096,volumes={'/models':model_volume},timeout=120,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def unified_qualify(engine,approved=False):
        if approved is not True:raise ValueError('Approve the bounded 120-second GPU qualification workload first.')
        from fold_rapid.registry import verified_runtime,ENGINES
        from fold_rapid.hardware import require_cuda,inventory
        if engine not in OPERATIONS or engine=='rosetta':raise ValueError('Select one installed GPU engine.')
        token={'kind':'qualification','engine':engine}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('A scientific/setup operation is active.')
        try:
            model_volume.reload();runtime,models=verified_runtime('/models/rapid',engine)
            reading=require_cuda(runtime['python'],{'PYTHONPATH':runtime['source'],'HF_HUB_OFFLINE':'1'},timeout=90)
            result={'engine':engine,'gpu':inventory(),'cudaNumerics':reading,'runtime':runtime,'models':models,'imageDigest':cfg.get('engineImages',{}).get(engine,cfg['imageDigest']),'source':ENGINES[engine],'scientificCloudQualified':False,'scope':'Tiny genuine CUDA forward/backward in this engine runtime. This is not trained-model inference or multi-engine scientific qualification.'}
            state['qualification:'+engine]=result;return result
        finally:
            if state.get('writer-lease')==token:state.pop('writer-lease')

    @app.function(serialized=True,name='unified_setup',image=image,cpu=2,memory=8192,volumes={'/models':model_volume},timeout=7200,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def unified_setup(engine,kind,approved=False):
        if approved is not True:raise ValueError('Approve CPU setup and model downloads separately.')
        token={'kind':'unified_setup','engine':engine}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('A campaign/setup is active.')
        try:
            model_volume.reload();pathlib.Path('/models/rapid').mkdir(parents=True,exist_ok=True)
            if kind=='runtime':
                from fold_rapid.install import install
                # Existing installers own model-specific pinned environments.
                engine={'proteinmpnn':'bindcraft2','af2_multimer':'bindcraft2','esmfold2_fast':'esmfold2','solublempnn':'boltzgen'}.get(engine,engine)
            elif kind=='models':
                from fold_rapid.models import install
            else:raise ValueError('Unknown setup operation.')
            result=install('/models/rapid',engine,True);model_volume.commit();return result
        finally:
            if state.get('writer-lease')==token:state.pop('writer-lease')
    return functions


def submit(cfg,value,key,approved,maximum_estimate):
    import modal
    quote=cost(value,cfg)
    if approved is not True or type(maximum_estimate)not in(int,float) or not math.isfinite(maximum_estimate) or maximum_estimate<value['budget']['maxEstimatedUSD']:raise ValueError('Approve this campaign allowance and research transfer explicitly.')
    call=modal.Function.from_name(cfg['appName'],'unified_execute').spawn(value,key,True)
    return {'callId':call.object_id,'idempotencyKey':key,'estimate':quote,'provider':'modal','state':'submitted','kind':'unified','scientificGPUValidated':False}
