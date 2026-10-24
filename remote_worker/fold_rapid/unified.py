"""Durable, sequential molecular evolution. One coordinator, isolated stage stores.

Journal claims are written BEFORE expensive dispatch. An uncertain claimed stage
is never retried automatically. Candidate files are immutable; journal snapshots
and cancellation flags are distinct so readers cannot race a cancel away.
"""
import base64
import contextlib
import copy
import datetime
import fcntl
import json
import os
import pathlib
import subprocess
import sys
import time
from .contracts import canonical,digest,file_digest,identifier,manifest
from .molecules import inspect,confined
from .unified_contract import campaign,blockers,estimate,analysis_modules,FAMILIES,OPERATIONS

TERMINAL={'COMPLETED','PARTIALLY_COMPLETE','FAILED','CANCELLED'}
STATES={'CREATED','VALIDATING','WAITING_FOR_APPROVAL','QUEUED','RUNNING','CHECKPOINTING','STAGE_COMPLETE',*TERMINAL}


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic(path,value):
    path=pathlib.Path(path);temp=path.with_name(path.name+'.partial')
    with temp.open('w') as out:out.write(canonical(value));out.flush();os.fsync(out.fileno())
    os.replace(temp,path)


class CampaignStore:
    def __init__(self,root):
        self.root=pathlib.Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.campaigns=self.root/'campaigns';self.campaigns.mkdir(exist_ok=True)
    def folder(self,id):return self.campaigns/identifier(id)
    def submit(self,value,key,approved=False):
        value=campaign(value)
        if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('A stable campaign idempotency key is required.')
        id=digest(key.encode())[:32];folder=self.folder(id);folder.mkdir(exist_ok=True)
        with (folder/'claim.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if (folder/'campaign.json').is_file():
                old=self.get(id)
                if old['manifestSha256']!=digest(canonical(value).encode()):raise ValueError('Idempotency key conflicts with different campaign inputs.')
                return {'campaignId':id,'created':False,'state':old['state']}
            row={'campaignId':id,'manifest':value,'manifestSha256':digest(canonical(value).encode()),'state':'CREATED','created':now(),'updated':now(),'revision':0,'stages':[],'candidateIds':[],'events':[],'reservationsUSD':0.0,'estimate':estimate(value),'scientificCloudQualified':False,'qualifiedCandidates':[],'executionPolicy':'modular_sequential','executionPolicyBasis':'No measured warm-worker comparison exists.'}
            self.write(row,'VALIDATING','Validating scientific handoffs')
            missing=blockers(value)
            self.write(row,'PARTIALLY_COMPLETE' if missing else 'QUEUED' if approved else 'WAITING_FOR_APPROVAL','; '.join(missing) if missing else 'Awaiting explicit cloud workload approval' if not approved else 'Approved workload queued')
        return {'campaignId':id,'created':True,'state':row['state']}
    def get(self,id):
        path=self.folder(id)/'campaign.json'
        if not path.is_file():raise ValueError('Campaign not found.')
        return json.loads(path.read_text())
    def write(self,row,state=None,message=None):
        if state is not None:
            if state not in STATES:raise ValueError('Unknown campaign state.')
            row['state']=state
        row['updated']=now();row['revision']+=1
        if message:row['events'].append({'cursor':row['revision'],'time':row['updated'],'state':row['state'],'message':message})
        atomic(self.folder(row['campaignId'])/'campaign.json',row)
    def cancel(self,id):
        row=self.get(id)
        if row['state'] not in TERMINAL:atomic(self.folder(id)/'cancel.json',{'requested':now()})
        return {'campaignId':id,'state':row['state'] if row['state'] in TERMINAL else 'cancel_requested','billingStopped':False}
    def cancelled(self,id):return (self.folder(id)/'cancel.json').is_file()
    def add_candidate(self,row,node,operation):
        value=copy.deepcopy(node);value['candidateId']=digest(canonical(value).encode());id=value['candidateId']
        folder=self.folder(row['campaignId'])/'candidates';folder.mkdir(exist_ok=True)
        path=folder/(id+'.json')
        if path.exists() and json.loads(path.read_text())!=value:raise ValueError('Immutable candidate conflict.')
        if not path.exists():atomic(path,value)
        if id not in row['candidateIds']:row['candidateIds'].append(id)
        row['events'].append({'cursor':row['revision']+1,'time':now(),'operation':operation,'candidateId':id,'parents':value.get('parents',[])})
        self.write(row)
        return value
    def candidates(self,id):return [json.loads((self.folder(id)/'candidates'/(c+'.json')).read_text()) for c in self.get(id)['candidateIds']]
    def status(self,id):
        row=self.get(id);row['manifest']['target'].pop('contentBase64',None)
        return row


class Halt(Exception):pass


class LocalStages:
    """Existing RAPID supervisor, with separate SQLite per stage and one GPU lock."""
    def __init__(self,root,campaign_root,configuration_root=None):self.root=pathlib.Path(root);self.folder=pathlib.Path(campaign_root);self.configuration_root=pathlib.Path(configuration_root or root)
    def preflight(self,engine,value):
        from .registry import inventory
        row=next(e for e in inventory(self.configuration_root)['engines'] if e['id']==engine)
        return {'ready':row['executionAvailable'],'reason':row['status'],'scientificCloudQualified':False}
    def __call__(self,stage,value,checkpoint,cancelled):
        import threading
        from .store import Store
        from .runner import execute
        root=self.folder/'stages'/stage['stageId'];root.mkdir(parents=True,exist_ok=True)
        if (self.configuration_root/'config.json').exists():atomic(root/'config.json',json.loads((self.configuration_root/'config.json').read_text()))
        # All portable campaigns share the original worker's accelerator lease.
        lock=root/'accelerator.lock'
        if not lock.exists():lock.symlink_to((self.root/'accelerator.lock').resolve())
        store=Store(root);job=store.submit(value,stage['stageId']);checkpoint({'jobId':job['jobId'],'stageRoot':str(root)})
        stopped=threading.Event()
        def watch():
            while not stopped.wait(.25):
                if cancelled():store.cancel(job['jobId']);break
        thread=threading.Thread(target=watch,daemon=True);thread.start()
        try:execute(root,job['jobId'])
        finally:stopped.set();thread.join(timeout=1)
        return {'job':store.get(job['jobId']),'folder':str(store.folder(job['jobId']))}


def coordinate(folder,record):
    coord=record['coordinates'];path=confined(pathlib.Path(folder),coord['artifact']);raw=path.read_bytes()
    if digest(raw)!=coord['sha256']:raise ValueError('Coordinate checksum changed at a stage handoff.')
    fmt='pdb' if path.suffix=='.pdb' else 'cif';mapping=inspect(raw,fmt)
    if mapping!=coord['mapping']:raise ValueError('Coordinate mapping differs from the immutable engine record.')
    return {'format':fmt,'contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':coord['chainRoles']['target']},mapping


def model_manifest(row,node,engine):
    m=row['manifest'];flow=m['workflow'];b=m['stageBudgets'][engine];source=node.get('coordinates') or node.get('backboneReference')
    if not source:raise ValueError('This operation requires a verified structural backbone.')
    biology={'sequences':node['sequences'],'parents':[{'id':node['candidateId'],'chain':ch,'sequenceSha256':digest(node['sequences'][ch].encode())} for ch in node['binderChains']]}
    # The original single-engine parent contract requires unique IDs per chain.
    for item in biology['parents']:item['id']=digest((node['candidateId']+':'+item['chain']).encode())
    if engine in ('proteinmpnn','solublempnn'):
        biology['constraints']={ch:m.get('constraints',{}).get(ch,{'mutable':list(range(1,len(node['sequences'][ch])+1))}) for ch in node['binderChains']}
    if engine.startswith('esmfold2'):biology['prediction']=flow.get('prediction',{})
    if engine=='rosetta':biology['relax']={'repeats':1}
    budget={'seconds':b['seconds']}
    if 'gpuMemoryMiB' in b:budget['gpuMemoryMiB']=b['gpuMemoryMiB']
    return manifest({'schemaVersion':1,'engine':engine,'operation':OPERATIONS[engine],'target':source,'design':{'modality':'peptide' if sum(len(node['sequences'][ch]) for ch in node['binderChains'])<=128 else 'binder','lengths':[sum(len(node['sequences'][ch]) for ch in node['binderChains'])],'count':flow['count'] if engine in ('proteinmpnn','solublempnn') else 1,'attempts':1,'designChains':node['binderChains']},'seed':m['seed'],'budget':budget,'mode':'reference','biology':biology,'parentCandidates':[p['id'] for p in biology['parents']]})


def run(root,id,executor=None,publish=lambda row:None,cancelled=lambda:False,lock_path=None):
    store=CampaignStore(root);folder=store.folder(id)
    with pathlib.Path(lock_path or folder/'coordinator.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return store.status(id)
        row=store.get(id)
        if row['state'] in TERMINAL or row['state']=='WAITING_FOR_APPROVAL':return store.status(id)
        if any(s['state']=='RUNNING' for s in row['stages']):
            store.write(row,'PARTIALLY_COMPLETE','An earlier stage has an uncertain dispatch/completion outcome. Reconcile its saved execution ID; automatic retry refused.');publish(store.status(id));return store.status(id)
        m=row['manifest'];rules=analysis_modules().policy(m['policy']);expires=datetime.datetime.fromisoformat(row['created']).timestamp()+m['budget']['seconds'];executor=executor or LocalStages(root,folder)
        def stop_requested():return store.cancelled(id) or cancelled() or time.time()>=expires
        def check():
            if stop_requested():raise Halt('Cancellation requested' if store.cancelled(id) or cancelled() else 'Campaign wall-time allowance exhausted')
        def update(message):store.write(row,'CHECKPOINTING',message);publish(store.status(id))
        def stage(engine,value,parent=None):
            check();b=m['stageBudgets'][engine];remaining=expires-time.time()
            admission=executor.preflight(engine,value) if hasattr(executor,'preflight') else {'ready':True}
            if not admission['ready']:
                row['stages'].append({'stageId':digest((id+str(len(row['stages']))+engine).encode())[:32],'engine':engine,'parentCandidate':parent,'state':'BLOCKED','reservedUSD':0,'reason':admission['reason']})
                update(engine+' blocked before allocating a GPU: '+admission['reason']);return [],None
            if remaining<b['seconds']:raise Halt('Insufficient remaining runtime for the next bounded '+engine+' stage')
            cost=b['seconds']/3600*b['hourlyEstimateUSD']
            if row['reservationsUSD']+cost>m['budget']['maxEstimatedUSD']:raise Halt('Insufficient approved estimated-cost allowance for '+engine)
            stage_id=digest(canonical({'campaign':id,'index':len(row['stages']),'engine':engine,'parent':parent,'manifest':value}).encode())[:32]
            entry={'stageId':stage_id,'engine':engine,'parentCandidate':parent,'state':'RUNNING','manifestSha256':digest(canonical(value).encode()),'reservedUSD':cost,'started':now()}
            row['stages'].append(entry);row['reservationsUSD']+=cost;store.write(row,'RUNNING','Dispatching '+engine);publish(store.status(id))
            def checkpoint(data):entry.update(data);update('Saved '+engine+' execution identity')
            try:
                response=executor(entry,value,checkpoint,stop_requested);entry.update(state='STAGE_COMPLETE' if response['job']['state'] in ('completed','no_qualified_candidates') else 'FAILED',result=response['job'].get('result'),jobState=response['job']['state'],error=response['job'].get('error'),finished=now())
            except Exception as exc:
                entry.update(state='FAILED',error=str(exc)[:2000],dispatchOutcomeUncertain=True);update('Stage failed; no automatic costly retry');raise Halt('Uncertain/failed '+engine+' dispatch; inspect saved evidence') from exc
            update(engine+' finished: '+entry['jobState']);check()
            if entry['state']=='FAILED':return [],response['folder']
            output=pathlib.Path(response['folder'])/'candidates.json'
            records=json.loads(output.read_text()) if output.is_file() else []
            if len(records)>10000:raise ValueError('Engine candidate output exceeds bounded import.')
            return records,response['folder']
        def node_from_record(record,job_folder,parent,operation):
            if len(row['candidateIds'])>=rules['maxDescendants']+len(m['parents']):raise Halt('Immutable candidate-count allowance exhausted')
            coords=None;backbone=None
            if record.get('coordinates'):
                coords,mapping=coordinate(job_folder,record);roles=record['coordinates']['chainRoles'];binders=roles['binder'];targets=roles['target']
                if not binders or set(binders)&set(targets):raise ValueError('Engine chain roles are missing or overlap.')
                sequences={ch:mapping['chains'][ch]['sequence'] for ch in targets+binders}
                if parent:
                    if binders!=parent['binderChains'] or sequences!=parent['sequences']:raise ValueError('A refold/relax output changed submitted sequence or chain identity.')
                else:
                    original=inspect(base64.b64decode(m['target']['contentBase64']),m['target']['format'])
                    if len(targets)!=len(m['target']['chains']) or [sequences[ch] for ch in targets]!=[original['chains'][ch]['sequence'] for ch in m['target']['chains']]:raise ValueError('Generated construct differs from the submitted target; explicit verified construct mapping is required.')
                if record.get('binderSequence')!='/'.join(sequences[ch] for ch in binders):raise ValueError('Candidate sequence and coordinates disagree.')
            else:
                if not parent:raise ValueError('A generated original requires genuine coordinates.')
                pieces=(record.get('binderSequence') or '').split('/');binders=parent['binderChains']
                if len(pieces)!=len(binders):raise ValueError('Decoder changed binder chain count.')
                sequences={**parent['sequences'],**dict(zip(binders,pieces))};targets=parent['targetChains'];backbone=parent.get('coordinates') or parent.get('backboneReference')
                from .biology_contract import validate_outputs
                expected=parent['sequences'];constraints={ch:m.get('constraints',{}).get(ch,{'mutable':list(range(1,len(expected[ch])+1))}) for ch in binders}
                validate_outputs(sequences,expected,constraints)
            mutations=[]
            if parent:
                for ch in binders:
                    mutations.extend({'chain':ch,'position':i,'from':a,'to':b} for i,(a,b) in enumerate(zip(parent['sequences'][ch],sequences[ch]),1) if a!=b)
            return store.add_candidate(row,{'sequences':sequences,'binderChains':binders,'targetChains':targets,'coordinates':coords,'backboneReference':backbone,'parents':[parent['candidateId']] if parent else [],'operation':operation,'generator':record['generator'],'nativeCandidate':record,'sourceJobFolder':str(pathlib.Path(job_folder).relative_to(folder)),'mutationHistory':mutations,'conditionedFamilies':parent['conditionedFamilies'] if parent else [FAMILIES.get(record['generator'],record['generator'])],'seed':m['seed'],'structureStatus':'fresh_prediction' if operation=='REFOLD' else 'derived_relaxation' if operation=='RELAX' else 'sequence_requires_refold' if not coords else 'generator_output'},operation)
        def assess(prediction,reference):
            mi=analysis_modules().mi
            raw=base64.b64decode(prediction['coordinates']['contentBase64']);structure=mi.parse_structure(raw.decode(),prediction['coordinates']['format'])
            assignments={ch:{'role':'target'} for ch in prediction['targetChains']};assignments.update({ch:{'role':'candidate'} for ch in prediction['binderChains']})
            analysis=mi.analyze(structure,assignments,{'spherePoints':96},check=check)
            seq=''.join(prediction['sequences'][ch] for ch in prediction['binderChains'])
            metrics=analysis_modules().metrics(analysis,seq);ref=reference.get('coordinates') or reference.get('backboneReference');original=mi.parse_structure(base64.b64decode(ref['contentBase64']).decode(),ref['format'])
            drifts=[]
            for ch in prediction['binderChains']:
                mutable=m.get('constraints',{}).get(ch,{'mutable':list(range(1,len(prediction['sequences'][ch])+1))})['mutable'];fixed=[i for i in range(1,len(prediction['sequences'][ch])+1) if i not in mutable]
                drifts.append(analysis_modules().drift(original,structure,prediction['targetChains'],ch,fixed))
            drift=max(drifts,key=lambda d:d['candidatePoseRmsd'])
            report={'candidateId':prediction['candidateId'],'family':FAMILIES.get(prediction['generator'],prediction['generator']),'metrics':metrics,'drift':drift,'analysisArtifact':'assessments/'+prediction['candidateId']+'.json','predictionConfidence':prediction.get('nativeCandidate',{}).get('metrics',{}),'noAffinityClaim':True}
            dest=folder/'assessments';dest.mkdir(exist_ok=True);atomic(dest/(prediction['candidateId']+'.json'),{**report,'analysis':analysis})
            row['events'].append({'operation':'EVALUATE','candidateId':prediction['candidateId'],'artifact':'assessments/'+prediction['candidateId']+'.json','time':now()});store.write(row)
            return report
        try:
            check();store.write(row,'RUNNING','Automatic compatible scientific stages started');publish(store.status(id));originals=[]
            for p in m['parents']:
                originals.append(store.add_candidate(row,{'sequences':p['sequences'],'binderChains':p['binderChains'],'targetChains':m['target']['chains'],'coordinates':m['target'],'backboneReference':None,'parents':[],'operation':'CREATE','generator':'provided_observed_structure','sourceCandidateId':p['id'],'conditionedFamilies':['AlphaFold2'],'seed':m['seed'],'structureStatus':'provided_model_not_experimentally_validated'},'CREATE'))
            for generator in m['generators']:
                e=generator['engine'];b=m['stageBudgets'][e]
                value=manifest({'schemaVersion':1,'engine':e,'operation':'design','target':m['target'],'design':generator['design'],'settings':generator.get('settings',{}),'biology':generator.get('biology',{}),'parentCandidates':[p['id'] for p in generator.get('biology',{}).get('parents',[])],'seed':m['seed'],'budget':{'seconds':b['seconds']},'mode':'reference'})
                records,path=stage(e,value)
                for record in records:
                    if record['outcome'] in ('accepted','passed_upstream_filters') and record.get('coordinates'):originals.append(node_from_record(record,path,None,'CREATE'))
                    else:row['events'].append({'operation':'REJECT','nativeCandidateId':record['candidateId'],'reason':record['outcome'],'time':now()})
            frontier=originals;all_selections=[]
            for round_index in range(rules['rounds']):
                row['round']=round_index+1;branches=list(frontier)
                for parent in frontier:
                    for e in m['workflow']['redesign']:
                        records,path=stage(e,model_manifest(row,parent,e),parent['candidateId'])
                        for record in records:branches.append(node_from_record(record,path,parent,'REDESIGN'))
                evaluations=[]
                for candidate in branches:
                    samples=[];predictions=[]
                    for e in m['workflow']['predictors']:
                        records,path=stage(e,model_manifest(row,candidate,e),candidate['candidateId'])
                        for record in records:
                            prediction=node_from_record(record,path,candidate,'REFOLD');predictions.append(prediction);samples.append(assess(prediction,candidate))
                    disagreement=None
                    if len(predictions)>1:
                        values=[]
                        for i,a in enumerate(predictions):
                            for bnode in predictions[i+1:]:
                                for ch in a['binderChains']:
                                    astruct=analysis_modules().mi.parse_structure(base64.b64decode(a['coordinates']['contentBase64']).decode(),a['coordinates']['format']);bstruct=analysis_modules().mi.parse_structure(base64.b64decode(bnode['coordinates']['contentBase64']).decode(),bnode['coordinates']['format'])
                                    values.append(analysis_modules().drift(astruct,bstruct,a['targetChains'],ch,[])['candidatePoseRmsd'])
                        disagreement=max(values)
                    physics=[]
                    if m['workflow']['rosetta'] and predictions:
                        # Explicit first fresh prediction, never the stale redesign backbone.
                        records,path=stage('rosetta',model_manifest(row,predictions[0],'rosetta'),predictions[0]['candidateId'])
                        for record in records:
                            relaxed=node_from_record(record,path,predictions[0],'RELAX');physics.append(relaxed['candidateId'])
                            # Relaxation is a distinct derived pose, not an independent predictor.
                            assess(relaxed,predictions[0])
                    evaluations.append({'id':candidate['candidateId'],'samples':samples,'maxDisagreement':disagreement,'conditionedFamilies':candidate['conditionedFamilies'],'physics':physics,'physicsAssessment':bool(physics)})
                from .biology_contract import pareto
                selected=analysis_modules().select(evaluations,rules,pareto)
                for decision in selected:decision['decision']='retain_for_computational_review' if decision['eligible'] and not decision['dominatedBy'] else 'no_supported_improvement'
                all_selections.append({'round':round_index+1,'rows':selected})
                atomic(folder/'selection.json',all_selections)
                retained={r['id'] for r in selected if r.get('decision')=='retain_for_computational_review'}
                for decision in selected:row['events'].append({'operation':'RETAIN' if decision['id'] in retained else 'REJECT','candidateId':decision['id'],'basis':decision,'time':now()})
                frontier=[c for c in branches if c['candidateId'] in retained]
                # Only a freshly predicted backbone can drive another redesign.
                candidates=store.candidates(id)
                frontier=[next((p for p in reversed(candidates) if p['operation']=='REFOLD' and p['parents']==[c['candidateId']]),c) for c in frontier]
                update('Recorded explicit Pareto decisions for round '+str(round_index+1))
                if not frontier:break
            row['selection']=all_selections;row['qualifiedCandidates']=[]
            failures=any(s['state'] in ('FAILED','BLOCKED') for s in row['stages'])
            store.write(row,'PARTIALLY_COMPLETE' if failures else 'COMPLETED','Workflow finished; computational review only, no experimental certification.');publish(store.status(id))
        except Halt as exc:
            store.write(row,'CANCELLED' if store.cancelled(id) or cancelled() else 'PARTIALLY_COMPLETE',str(exc));publish(store.status(id))
        except Exception as exc:
            store.write(row,'FAILED',type(exc).__name__+': '+str(exc)[:2000]);publish(store.status(id))
        finally:
            report={k:v for k,v in store.status(id).items() if k!='manifest'}
            report.update(candidateCount=len(row['candidateIds']),scientificCloudQualified=False,experimentalBindingEstablished=False,notes=['ESM Fast/full share one family. Provided AF2-derived structures conservatively count as AF2-conditioned.','Reservations are deliberately not refunded after ambiguous outcomes. Actual billing is reported separately by Modal.'])
            atomic(folder/'report.json',report)
        return store.status(id)


def spawn(root,id):
    folder=CampaignStore(root).folder(id)
    with (folder/'supervisor.log').open('ab') as log:
        child=subprocess.Popen([sys.executable,'-m','fold_rapid.cli','--root',str(root),'run-campaign',id],stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'PYTHONPATH':str(pathlib.Path(__file__).resolve().parents[1])})
    return child.pid
