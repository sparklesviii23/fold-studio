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
    from .billing import quote
    reviewed=estimate(value);total=quote(value,reviewed)
    if total:
        p=value['budget']['resourcePricing']
        if not math.isclose(p['gpuSecondUSD']*3600,cfg['hourlyEstimateUSD'],rel_tol=0,abs_tol=1e-9) or p['workerCPUs']!=cfg.get('workerCPUs',2) or p['workerMemoryGiB']*1024!=cfg.get('workerMemoryMiB',65536):raise ValueError('Resource prices must match the deployed GPU/CPU/memory profile.')
        if not total['withinAllowance']:raise ValueError('Projected total resources and safety reserves exceed the approved allowance.')
    return {**reviewed,'totalResources':total,'workerHostMemoryMiB':cfg.get('workerMemoryMiB',65536),'workerCPUs':cfg.get('workerCPUs',2),'gpu':cfg['gpu'],'imageDigest':cfg['imageDigest'],'scientificGPUValidated':False}


def attach(app,cfg,image,data,state,model_volume):
    import modal
    functions={}
    for engine in OPERATIONS:
        def factory(engine):
            stage_image=image
            if engine in cfg.get('engineImages',{}):
                stage_image=modal.Image.from_registry(cfg['engineImages'][engine]).add_local_dir(pathlib.Path(__file__).resolve().parents[1],'/opt/fold-worker',copy=True,ignore=['**/__pycache__/**','**/*.pyc','**/dist/**']).env({'PYTHONPATH':'/opt/fold-worker','RAPID_RELEASE_DIR':'/opt/fold-rapid-release','FOLD_COMPUTE_PROVIDER':'modal','RAPID_IMAGE_DIGEST':cfg['engineImages'][engine]})
            @app.function(serialized=True,name='unified_'+engine,image=stage_image,gpu=None if engine=='rosetta' else cfg['gpu'],volumes={'/data':data,'/models':model_volume},cpu=(cfg.get('workerCPUs',2),cfg.get('workerCPUs',2)),memory=(cfg.get('workerMemoryMiB',65536),cfg.get('workerMemoryMiB',65536)),timeout=cfg['maxSeconds']+150,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
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
                    if result['job']['state']=='completed' and result['job'].get('result',{}).get('candidates',0)>0:
                        from fold_rapid.unified import atomic
                        evidence=pathlib.Path('/models/rapid/qualification');evidence.mkdir(exist_ok=True)
                        import json
                        provenance=json.loads((pathlib.Path(result['folder'])/'provenance.json').read_text())
                        atomic(evidence/(engine+'-inference.json'),{'validOutputsObserved':True,'jobId':result['job']['id'],'campaignId':campaign_id,'provenance':provenance,'scientificReferenceValidated':False,'handoffVerification':'Recorded separately in the immutable campaign lineage after sequence/coordinate checks.'})
                        model_volume.commit()
                    data.commit();state[key]={'jobId':result['job']['id'],'state':result['job']['state'],'artifactsCommitted':True}
                    return result
                finally:Store.event=original;data.commit()
            return execute_stage
        functions[engine]=factory(engine)

    @app.function(serialized=True,name='unified_execute',image=image,volumes={'/data':data,'/models':model_volume},cpu=(1,1),memory=(4096,4096),timeout=cfg['maxSeconds']+180,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def unified_execute(value,key,approved=False):
        from fold_rapid.unified import CampaignStore,run
        import time
        if approved is not True:raise ValueError('Approve the complete cloud campaign before execution.')
        from fold_rapid.execution import require_cloud
        require_cloud(value.get('execution',{}))
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
                    from fold_rapid import billing
                    started=time.monotonic();last_meter=0
                    call=functions[stage['engine']].spawn(id,stage,value)
                    checkpoint({'callId':call.object_id})
                    while True:
                        try:result=call.get(timeout=1);break
                        except TimeoutError:
                            elapsed=time.monotonic()-started
                            campaign_row=store.get(id)
                            if elapsed-last_meter>=10 and 'resourcePricing' in campaign_row['manifest']['budget']:
                                stage['observedRemoteSeconds']=elapsed
                                next(s for s in campaign_row['stages'] if s['stageId']==stage['stageId'])['observedRemoteSeconds']=elapsed
                                estimated=billing.live(campaign_row['manifest'],campaign_row['stages'],time.time()-__import__('datetime').datetime.fromisoformat(campaign_row['created']).timestamp())
                                checkpoint({'observedRemoteSeconds':elapsed,'liveEstimatedWithSafetyUSD':estimated,'providerReportedUSD':None})
                                if estimated>=campaign_row['manifest']['budget']['maxEstimatedUSD']:state['unified-cancel:'+id]=True
                                last_meter=elapsed
                            live=state.get('unified-stage:'+id+':'+stage['stageId'],{})
                            if live.get('jobId') and stage.get('jobId')!=live['jobId']:checkpoint({'jobId':live['jobId']})
                            # The model supervisor observes cancellation and finalizes
                            # artifacts. Don't terminate it before evidence is committed.
                    data.reload()
                    checkpoint({'jobId':result['job']['id'],'observedRemoteSeconds':time.monotonic()-started})
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
            fields(payload,('idempotencyKey',))
            observed=state.get('unified-request:'+payload['idempotencyKey'])
            if observed:return observed
            if state.get('writer-lease'):return {'state':'not_observed','resubmit':False,'reason':'A writer is active; no duplicate dispatch.'}
            # The persistent identity is deterministic; recovery survives Dict
            # and FunctionCall return-value expiry without guessing a new job.
            key=payload['idempotencyKey']
            if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('Invalid campaign request key.')
            data.reload();id=digest(key.encode())[:32]
            try:row=CampaignStore('/data/rapid').get(id)
            except ValueError:return {'state':'not_observed','resubmit':False}
            return {'campaignId':id,'state':row['state'],'manifestSha256':row['manifestSha256'],'recoveredFrom':'persistent_volume','resubmit':False}
        if operation=='bootstrap_status':
            fields(payload,('requestKey',));key=payload['requestKey']
            if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('Invalid setup request key.')
            observed=state.get('bootstrap:'+key)
            if observed:return observed
            if state.get('writer-lease'):return {'state':'not_observed','resubmit':False}
            model_volume.reload();path=pathlib.Path('/models/rapid/bootstraps')/digest(key.encode())/'status.json'
            import json
            return json.loads(path.read_text()) if path.is_file() else {'state':'not_observed','resubmit':False}
        if operation=='inventory':
            fields(payload,())
            if state.get('writer-lease'):raise ValueError('Model storage is owned by an active campaign/setup; inspect its saved execution instead.')
            model_volume.reload()
            from fold_rapid.registry import inventory
            import socket,platform,os
            from fold_rapid import VERSION,API_VERSION
            return {'deploymentReachable':True,'name':'Fold Studio RAPID Cloud Engine','version':VERSION,'apiVersion':API_VERSION,'executionHost':socket.gethostname(),'executionPlatform':platform.platform(),'provider':os.environ.get('FOLD_COMPUTE_PROVIDER'),'controllerLocation':'remote','sourceCodeSha256':os.environ.get('BGMEE_CODE_SHA256'),'imageRecipeSha256':os.environ.get('RAPID_IMAGE_RECIPE_SHA256'),'scientificCloudQualified':False,'models':inventory('/models/rapid'),'campaignStatesDurable':True,'executionPolicy':'modular_sequential'}
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

    @app.function(serialized=True,name='unified_prepare_models',image=image,cpu=(2,2),memory=(8192,8192),volumes={'/models':model_volume},timeout=1800,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
    def unified_prepare_models(plan,key,approved=False):
        if approved is not True:raise ValueError('Approve the remote installation plan and its CPU/download/storage allowance.')
        from fold_rapid.bootstrap import run
        token={'kind':'bootstrap','request':key}
        if not state.put('writer-lease',token,skip_if_exists=True):raise ValueError('A campaign/setup already owns scientific storage. Reconnect rather than duplicate it.')
        try:
            model_volume.reload()
            def publish(row):model_volume.commit();state['bootstrap:'+key]=row
            return run('/models/rapid',plan,key,True,publish)
        finally:
            model_volume.commit()
            if state.get('writer-lease')==token:state.pop('writer-lease')

    @app.function(serialized=True,name='unified_qualify',image=image,gpu=cfg['gpu'],cpu=(2,2),memory=(4096,4096),volumes={'/models':model_volume},timeout=120,min_containers=0,max_containers=1,scaledown_window=10,retries=0)
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
            from fold_rapid.unified import atomic
            folder=pathlib.Path('/models/rapid/qualification');folder.mkdir(exist_ok=True)
            atomic(folder/(engine+'-cuda-numerics.json'),result);model_volume.commit()
            state['qualification:'+engine]=result;return result
        finally:
            if state.get('writer-lease')==token:state.pop('writer-lease')

    @app.function(serialized=True,name='unified_setup',image=image,cpu=(2,2),memory=(8192,8192),volumes={'/models':model_volume},timeout=cfg.get('setupMaxSeconds',900),min_containers=0,max_containers=1,scaledown_window=10,retries=0)
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
                engine={'proteinmpnn':'bindcraft2','af2_multimer':'bindcraft2'}.get(engine,engine)
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
