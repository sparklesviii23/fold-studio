"""RPC v2, exclusively over an authenticated SSH process's stdin/stdout."""
import base64
import json
import os
import pathlib
import platform
import shutil
from . import API_VERSION,VERSION
from .contracts import fields,identifier,digest,integer,file_digest
from .molecules import confined,selected_target
from .registry import inventory
from .store import Store,TERMINAL

class Worker:
    def __init__(self,root):self.store=Store(root)
    def dispatch(self,request):
        fields(request,('apiVersion','requestId','operation','payload'))
        if request['apiVersion']!=API_VERSION or type(request['apiVersion']) is not int:raise ValueError('Unsupported worker API version.')
        if not isinstance(request['requestId'],str) or not 1<=len(request['requestId'])<=100:raise ValueError('Invalid request identity.')
        op=request['operation'];p=request['payload']
        if not isinstance(p,dict):raise ValueError('Payload must be an object.')
        allowed={'health','engine_inventory','model_status','engine_install','model_install','installation_status','campaign_validate','job_submit','job_list','job_status','job_events','job_cancel','job_recover','candidate_list','artifact_list','artifact_read','worker_shutdown','unified_validate','unified_submit','unified_status','unified_list','unified_cancel','unified_stage'}
        if op not in allowed:raise ValueError('Unsupported RAPID operation.')
        result=getattr(self,op)(p)
        return {'apiVersion':API_VERSION,'requestId':request['requestId'],'result':result}
    def health(self,p):
        fields(p,())
        from .hardware import inventory as gpu
        return {'state':'worker_available','workerVersion':VERSION,'apiVersion':API_VERSION,'platform':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'diskFreeBytes':shutil.disk_usage(self.store.root).free,'gpu':gpu(),'transport':'authenticated SSH stdin; no listener','root':str(self.store.root),'imageDigest':os.environ.get('RAPID_IMAGE_DIGEST'),'scientificCUDAQualified':False,**inventory(self.store.root)}
    def engine_inventory(self,p):fields(p,());return inventory(self.store.root)
    def model_status(self,p):return self.engine_inventory(p)
    def engine_install(self,p):
        fields(p,('engine','approved'))
        if p['approved'] is not True or p['engine'] not in ('bindcraft2','boltzgen','esmfold2','esmfold2_fast','solublempnn'):raise ValueError('Approve a supported isolated runtime installation.')
        from .install import background
        engine='esmfold2' if p['engine']=='esmfold2_fast' else 'boltzgen' if p['engine']=='solublempnn' else p['engine']
        return background(self.store.root,engine)
    def model_install(self,p):
        fields(p,('engine','approved'))
        if p['approved'] is not True or p['engine'] not in ('bindcraft2','boltzgen','esmfold2','esmfold2_fast','solublempnn'):raise ValueError('Approve a supported model download.')
        from .models import background
        return background(self.store.root,p['engine'])
    def installation_status(self,p):
        fields(p,())
        return {'installations':{path.stem:json.loads(path.read_text()) for pattern in ('install-*.json','models-*.json') for path in self.store.root.glob(pattern)},'modelDownloadsAutomatic':False}
    def campaign_validate(self,p):
        fields(p,('manifest',))
        from .contracts import manifest,deadline_seconds
        value=manifest(p['manifest']);mapping=selected_target(value)
        return {'valid':True,'target':mapping,'effectiveDeadlineSeconds':deadline_seconds(value),'mode':value['mode'],'policy':'Single engine with enforced deadline. Adaptive model selection requires measured GPU costs.','cudaExecutionTested':False,'models':next(e['models'] for e in inventory(self.store.root)['engines'] if e['id']==value['engine'])}
    def job_submit(self,p):
        fields(p,('manifest','idempotencyKey','approvedResearchTransfer'))
        if p['approvedResearchTransfer'] is not True:raise ValueError('Explicit research transfer and execution approval is required.')
        value=self.store.submit(p['manifest'],p['idempotencyKey'])
        if value['created']:
            from .runner import spawn
            spawn(self.store.root,value['jobId'])
        return {**value,'state':self.store.get(value['jobId'])['state']}
    def job_list(self,p):fields(p,());return {'jobs':self.store.list()}
    def job_status(self,p):
        fields(p,('jobId',));value=self.store.get(p['jobId'])
        value['manifest']['target'].pop('contentBase64',None)
        return value
    def job_events(self,p):fields(p,('jobId',),('after',));return {'events':self.store.events(p['jobId'],p.get('after'))}
    def job_cancel(self,p):fields(p,('jobId',));return self.store.cancel(p['jobId'])
    def job_recover(self,p):fields(p,());return self.store.recover()
    def candidate_list(self,p):
        fields(p,('jobId',),('offset','limit'));self.store.get(p['jobId'])
        offset=integer(p.get('offset',0),0,1000000,'Candidate offset');limit=integer(p.get('limit',8),1,20,'Candidate page size')
        files=sorted((self.store.folder(p['jobId'])/'candidates').glob('*.json'))
        end=min(offset+limit,len(files))
        return {'candidates':[json.loads(path.read_text()) for path in files[offset:end]],'nextOffset':end if end<len(files) else None,'total':len(files)}
    def artifact_list(self,p):
        fields(p,('jobId',));self.store.get(p['jobId']);path=self.store.folder(p['jobId'])/'artifact-manifest.json'
        entries=json.loads(path.read_text()) if path.is_file() else []
        package=self.store.folder(p['jobId'])/'results.zip'
        if package.is_file():entries.append({'path':'results.zip','bytes':package.stat().st_size,'sha256':file_digest(package)})
        return {'artifacts':entries}
    def artifact_read(self,p):
        fields(p,('jobId','path'),('offset','length'));self.store.get(p['jobId'])
        path=confined(self.store.folder(p['jobId']),p['path'])
        allowed={a['path'] for a in self.artifact_list({'jobId':p['jobId']})['artifacts']}
        if p['path'] not in allowed:raise ValueError('Artifact is not in the finished result manifest.')
        offset=integer(p.get('offset',0),0,2**40,'Offset');length=integer(p.get('length',786432),1,1048576,'Read length')
        with path.open('rb') as f:f.seek(offset);raw=f.read(length)
        return {'path':p['path'],'offset':offset,'contentBase64':base64.b64encode(raw).decode(),'chunkSha256':digest(raw),'eof':offset+len(raw)>=path.stat().st_size}
    def unified_validate(self,p):
        fields(p,('manifest',))
        from .unified_contract import campaign,estimate,blockers
        value=campaign(p['manifest'])
        return {'valid':True,'blockers':blockers(value),'estimate':estimate(value),'engines':inventory(self.store.root),'scientificCloudQualified':False}
    def unified_submit(self,p):
        fields(p,('manifest','idempotencyKey','approvedResearchTransfer','approvedWorkload'))
        if p['approvedResearchTransfer'] is not True or p['approvedWorkload'] is not True:raise ValueError('Approve this entire molecular campaign and reviewed workload allowance.')
        from .unified import CampaignStore,spawn
        result=CampaignStore(self.store.root).submit(p['manifest'],p['idempotencyKey'],True)
        if result['created'] and result['state']=='QUEUED':spawn(self.store.root,result['campaignId'])
        return result
    def unified_status(self,p):
        fields(p,('campaignId',))
        from .unified import CampaignStore
        return CampaignStore(self.store.root).status(p['campaignId'])
    def unified_list(self,p):
        fields(p,())
        from .unified import CampaignStore
        store=CampaignStore(self.store.root)
        return {'campaigns':[store.status(path.name) for path in sorted(store.campaigns.iterdir()) if (path/'campaign.json').is_file()][-100:]}
    def unified_cancel(self,p):
        fields(p,('campaignId',))
        from .unified import CampaignStore
        return CampaignStore(self.store.root).cancel(p['campaignId'])
    def unified_stage(self,p):
        fields(p,('campaignId','stageId','operation'),('payload',))
        if p['operation'] not in ('job_status','job_events','candidate_list','artifact_list','artifact_read'):raise ValueError('Read-only stage operation required.')
        from .unified import CampaignStore
        row=CampaignStore(self.store.root).get(p['campaignId']);entry=next((s for s in row['stages'] if s['stageId']==p['stageId']),None)
        if not entry or not entry.get('jobId'):raise ValueError('Stage execution identity has not been committed yet.')
        if entry['state'] not in ('STAGE_COMPLETE','FAILED'):raise ValueError('Read the live campaign until stage artifacts are committed.')
        worker=Worker(CampaignStore(self.store.root).folder(p['campaignId'])/'stages'/identifier(p['stageId']))
        result=getattr(worker,p['operation'])({**p.get('payload',{}),'jobId':entry['jobId']})
        if p['operation']=='candidate_list':
            lineage=CampaignStore(self.store.root).candidates(p['campaignId'])
            for candidate in result['candidates']:
                node=next((n for n in lineage if n.get('nativeCandidate',{}).get('candidateId')==candidate['candidateId']),None)
                if node:candidate['unifiedLineage']={'campaignId':p['campaignId'],'candidateId':node['candidateId'],'parents':node['parents'],'operation':node['operation'],'sequences':node['sequences'],'targetChains':node['targetChains'],'binderChains':node['binderChains'],'mutationHistory':node.get('mutationHistory',[]),'structureStatus':node['structureStatus'],'conditionedFamilies':node['conditionedFamilies']}
        return result
    def worker_shutdown(self,p):
        fields(p,())
        active=[j for j in self.store.list() if j['state'] not in TERMINAL]
        if active:raise ValueError('Active jobs must finish or be explicitly cancelled before worker shutdown.')
        return {'state':'idle','publicListener':False,'billingChanged':False,'reason':'SSH worker processes exit after each request. This does not stop a rented instance or its billing.'}
