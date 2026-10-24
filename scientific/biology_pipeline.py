"""Persistent, bounded scientific controller over existing local engine jobs.

One controller owns local compute admission. Descendants are immutable. Missing
predictors leave proposals unqualified, rather than approving a proxy score.
"""
import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import uuid

import evolution as ev
import intelligence as mi
import mpnn
import research
import biology_assessment as assessment

ACTIONS={'biology_pipeline_start','biology_pipeline_jobs','biology_pipeline_report','biology_pipeline_plan','biology_runtime_register','biology_services_configure','biology_model_register','biology_bindcraft_prepare','biology_chemistry_derive','biology_counterfactual_start'}


def common():
    root=pathlib.Path(__file__).resolve().parents[1]/'remote_worker'
    if root.is_dir() and str(root) not in sys.path:sys.path.insert(0,str(root))
    from fold_rapid.biology_contract import validate,validate_outputs,pareto
    return validate,validate_outputs,pareto


def file_sha(path):
    with pathlib.Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def config_path(s):return s.root/'engine/biology-config.json'


def runtime_config(s):
    path=config_path(s)
    return json.loads(path.read_text()) if path.is_file() else {'runtimes':{},'models':{}}


def runtime_register(s,p):
    """Register an existing reviewed runtime; never download or install implicitly."""
    engine=p.get('engine');allowed={'esmfold2','solublempnn','rosetta','rfdiffusion'}
    if engine not in allowed or p.get('approved') is not True:raise ValueError('Approve a supported existing isolated scientific runtime.')
    python=pathlib.Path(str(p.get('python',''))).expanduser().absolute();source=pathlib.Path(str(p.get('source',''))).expanduser().absolute()
    if not python.is_file() or not source.is_dir():raise ValueError('Runtime interpreter or scientific source directory is missing.')
    # Import-only probes are not scientific qualification. No arbitrary commands.
    probe={'esmfold2':'import esm,torch,importlib.metadata as m;print(m.version("esm"))','solublempnn':'import torch,numpy;print(torch.__version__)','rosetta':'import pyrosetta;print(pyrosetta.version())','rfdiffusion':'import torch,rfdiffusion;print(torch.__version__)'}[engine]
    result=subprocess.run([str(python),'-I','-B','-c',probe],capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError('Runtime import probe failed: '+result.stderr[-1000:])
    if engine=='esmfold2' and result.stdout.strip()!='3.4.1.post1':raise ValueError('Use the pinned esm==3.4.1.post1 runtime.')
    if engine=='rosetta' and p.get('licenseApproved') is not True:raise ValueError('Explicit Rosetta license authorization is required.')
    cfg=runtime_config(s);cfg['runtimes'][engine]={'python':str(python),'source':str(source),'version':result.stdout.strip()[-300:],'licenseApproved':p.get('licenseApproved') is True,'registered':research.utc(),'modelExecutionValidated':False}
    file=config_path(s);file.parent.mkdir(exist_ok=True);pending=file.with_suffix('.pending');pending.write_text(ev.canonical(cfg));os.replace(pending,file)
    return cfg['runtimes'][engine]


def model_register(s,p):
    if p.get('approved') is not True:raise ValueError('Approve registration of an existing checkpoint; downloads are separate.')
    common()
    from fold_rapid.models import CATALOG
    models=CATALOG;key=p.get('model');path=pathlib.Path(str(p.get('path',''))).expanduser().absolute()
    if key not in ('solublempnn','esmfold2-bundle','esmfold2-fast-bundle'):raise ValueError('Unsupported registered checkpoint.')
    if not path.is_file() or path.is_symlink():raise ValueError('Choose a regular existing checkpoint or bundle receipt.')
    if key=='solublempnn':
        expected=models['solublempnn']['sha256']
        if file_sha(path)!=expected:raise ValueError('Checkpoint differs from the official pinned SolubleMPNN identity.')
    else:
        entries=json.loads(path.read_text())
        if not isinstance(entries,list) or not entries:raise ValueError('Bundle receipt must list every official cached artifact.')
        required=set()
        repositories=('biohub/ESMFold2-Fast',) if key=='esmfold2-fast-bundle' else ('biohub/ESMFold2','biohub/ESMC-6B')
        # Same official catalogue as RAPID download verification, including the CCD.
        for repo in repositories:
            for name,item in models['esmfold2-fast' if key=='esmfold2-fast-bundle' else 'esmfold2'][repo]['files'].items():required.add((repo,name,item['sha256']))
        verified=set()
        for entry in entries:
            repo=entry.get('repository');name=entry.get('file') or pathlib.Path(entry['path']).name
            file=pathlib.Path(entry['path'])
            if not file.is_file() or file_sha(file)!=entry.get('sha256'):raise ValueError('A cached bundle artifact changed.')
            verified.add((repo,name,entry['sha256']))
        ccd=models['esmfold2']['biohub/ESMFold2']['files']['ccd.pkl']['sha256']
        if not required<=verified or not any(pathlib.Path(e['path']).name=='ccd.pkl' and e['sha256']==ccd for e in entries):raise ValueError('Bundle is missing an official model shard/config or CCD.')
    cfg=runtime_config(s);cfg.setdefault('models',{})[key]={'path':str(path),'sha256':file_sha(path),'registered':research.utc(),'modelExecutionValidated':False}
    file=config_path(s);file.parent.mkdir(exist_ok=True);pending=file.with_suffix('.pending');pending.write_text(ev.canonical(cfg));os.replace(pending,file)
    return cfg['models'][key]


def seeded_prepare(s,p):
    import fold_engine
    candidate=ev.Evolution(s).candidate(p['projectId'],p['candidateId']);chain='binder'
    protocol={'parents':[{'id':candidate['id'],'sequenceSha256':candidate['sequenceSha256'],'chain':chain}],'sequences':{chain:candidate['sequence']},'constraints':{chain:{k:candidate['constraints'][k] for k in ('mutable','excluded','preferred')}}}
    if candidate['chemistry']['representation']!='canonical_linear_protein':raise ValueError('This BindCraft initialization supports canonical linear peptides only.')
    if candidate['constraints']['preferred']:raise ValueError('Persistent position-specific preferences are not supported by this upstream seeded optimizer.')
    # Upstream semi-greedy omissions are chain-wide. Refuse silently over-restricting position-specific masks.
    exclusions=candidate['constraints']['excluded']
    if exclusions and (set(map(int,exclusions))!=set(candidate['constraints']['mutable']) or len(set(exclusions.values()))!=1):raise ValueError('Seeded BindCraft currently requires identical exclusions at every mutable position; separate MPNN redesign supports position-specific exclusions.')
    common()[0](protocol)
    options=p.get('configuration',{})
    if not isinstance(options,dict) or set(options)&{'projectId','binderLengths','modality','core','additionalTargets'}:raise ValueError('Seeded campaign length, modality and source topology are fixed by the selected candidate.')
    job=fold_engine.Engine(s).bindcraft_prepare({**options,'projectId':p['projectId'],'modality':'peptide' if len(candidate['sequence'])<=50 else 'binder','binderLengths':[len(candidate['sequence']),len(candidate['sequence'])]})
    folder=s.root/'jobs'/job['id'];file=folder/'seed-protocol.json';file.write_text(ev.canonical(protocol))
    s.job_metadata(job['id'],{'biologySeed':{'candidateId':candidate['id'],'protocolSha256':file_sha(file),'file':file.name,'validation':'initialization_contract_test_required'}})
    with s.db:ev.Evolution(s).event(p['projectId'],candidate['id'],'bindcraft_preparation',{'jobId':job['id'],'protocolSha256':file_sha(file),'computed':False})
    return s.job(job['id'])


def chemistry_derive(s,p):
    parent=ev.Evolution(s).candidate(p['projectId'],p['candidateId'])
    value={'sequences':{'binder':parent['sequence']},'chemistry':p.get('chemistry')};common()[0](value)
    chemistry=value['chemistry']
    if not chemistry or not chemistry.get('bonds') and not chemistry.get('modifications'):raise ValueError('Specify CCD modifications or explicit covalent links.')
    with s.db:
        child=ev.Evolution(s).insert(p['projectId'],p.get('name',parent['name']+' · chemical hypothesis'),parent['sequence'],copy.deepcopy(parent['constraints']),copy.deepcopy(parent['reference']),parent['residueMap'],parent,'chemical_modification')
        child['chemistry']={'representation':'ccd_modified_protein','chain':'binder',**chemistry,'status':'requires_CCD_atom_valence_and_conformer_validation'}
        child['backboneReference']=parent.get('structure') or parent.get('backboneReference');child['validation']='chemistry_hypothesis_unvalidated'
        s.db.execute('UPDATE evolution_candidates SET data=? WHERE id=?',(ev.canonical(child),child['id']))
        ev.Evolution(s).event(p['projectId'],child['id'],'chemical_hypothesis',{'chemistry':child['chemistry'],'scope':'Typed CCD/bond indices are not a chemical or structural validation. No predictor substitution or fabricated conformer.'})
    return child


def candidate_source(s,p):
    candidate=ev.Evolution(s).candidate(p['projectId'],p['candidateId'])
    if not candidate.get('structure'):
        observations=s.rows("SELECT data FROM evolution_events WHERE candidate_id=? AND project_id=? AND kind='prediction' ORDER BY created DESC,id DESC",(candidate['id'],p['projectId']))
        if observations:candidate={**candidate,'structure':json.loads(observations[0]['data'])['structure']}
        else:raise ValueError('This candidate requires a fresh prediction before fixed-backbone redesign; parent coordinates cannot be relabelled as a mutant structure.')
    record,path=mi.Lab(s).record(candidate['structure']['recordId'])
    if record['project_id']!=p['projectId'] or record['data']['sha256']!=candidate['structure']['sha256']:raise ValueError('Candidate structure reference changed.')
    structure=mi.parse_structure(path.read_text(),record['data']['format']);chain=candidate['structure']['chain']
    observed=next((c for c in structure['chains'] if c['id']==chain),None)
    if not observed or observed['sequence']!=candidate['sequence']:raise ValueError('Saved candidate sequence and coordinate identities differ.')
    targets=p.get('targetChains')
    if not isinstance(targets,list) or not targets or len(set(targets))!=len(targets) or chain in targets or set(targets)-{c['id'] for c in structure['chains']}:raise ValueError('Choose separate observed target chains in this same complex.')
    return candidate,record,path,structure,chain,targets


def plan(s,p):
    s.project(p['projectId']);candidate,record,path,structure,chain,targets=candidate_source(s,p)
    seconds=ev.integer(p.get('seconds',1800),'Wall budget seconds',1,7200);count=ev.integer(p.get('count',2),'Sequences per branch',1,8);seed=ev.integer(p.get('seed',42),'Seed',0,2147483647)
    engines=p.get('engines',['proteinmpnn','solublempnn'])
    if not isinstance(engines,list) or len(set(engines))!=len(engines) or set(engines)-{'proteinmpnn','solublempnn','esmfold2_fast','esmfold2','rosetta'}:raise ValueError('Choose compatible redesign/prediction/physics engines.')
    rules=assessment.policy(p.get('policy'));cfg=runtime_config(s);stages=[{'operation':'geometry','required':True}]
    for engine in ('proteinmpnn','solublempnn','esmfold2_fast','esmfold2','rosetta'):
        if engine in engines:stages.append({'operation':engine,'required':False})
    value={'schemaVersion':1,'candidateId':candidate['id'],'sourceSha256':record['data']['sha256'],'structureId':record['id'],'binderChain':chain,'targetChains':targets,'constraints':candidate['constraints'],'seed':seed,'seconds':seconds,'count':count,'selectionRules':rules,'stages':stages,'policy':{'version':'transparent-staged-v1','heavyConcurrency':1,'acceptance':'No descendant is accepted without structural re-prediction, hard-constraint checks and separate assessment. Missing evidence remains missing.','stopping':['deadline','cancel','no_compatible_available_operation','all_proposals_fail_hard_constraints']},'runtimeReadiness':{e:bool(cfg.get('runtimes',{}).get('esmfold2' if e.startswith('esmfold2') else e)) for e in engines},'paidCompute':False,'modelsDownloaded':False}
    comparisons=p.get('counterfactualCandidates',[])
    if not isinstance(comparisons,list) or len(comparisons)>8 or len(set(comparisons))!=len(comparisons):raise ValueError('Choose at most eight separate characterized variants.')
    for id in comparisons:
        variant=ev.Evolution(s).candidate(p['projectId'],id)
        if variant['parentId']!=candidate['id'] or len(variant['sequence'])!=len(candidate['sequence']):raise ValueError('Counterfactuals require direct, explicitly mapped equal-length descendants of this parent.')
    if comparisons:
        if any(e in engines for e in ('proteinmpnn','solublempnn')):raise ValueError('Matched counterfactual prediction cannot redesign the supplied experimental variants.')
        value['counterfactualCandidates']=comparisons;value['selectionRules']['rounds']=1
        value['counterfactualComparison']={'metric':p.get('comparisonMetric'),'higher':p.get('higherIsBetter',True),'neutralTolerance':p.get('neutralTolerance',0)}
        assessment.counterfactual([],{},value['counterfactualComparison']['metric'],value['counterfactualComparison']['higher'],value['counterfactualComparison']['neutralTolerance'])
    value['manifestSha256']=ev.sha(value);return value


def start(s,p):
    if p.get('approved') is not True:raise ValueError('Approve the bounded local scientific computation first.')
    value=plan(s,p)
    s.db.execute('BEGIN IMMEDIATE')
    if s.active():s.db.rollback();raise ValueError('Another local scientific job is active; no competing model calculation started.')
    job=s.job_new({'projectId':p['projectId'],'name':'Molecular evolution · '+ev.Evolution(s).candidate(p['projectId'],p['candidateId'])['name'],'manifest':value,'stages':[],'children':[],'descendants':[],'qualifiedCandidates':[]},'bgmee','queued')
    return s.spawn(job,'--biology-job')


def geometry(s,candidate,record,path,targets,check):
    structure=mi.parse_structure(path.read_text(),record['data']['format']);assignments={ch:{'role':'target'} for ch in targets};assignments[candidate['structure']['chain']]={'role':'candidate'}
    result=mi.analyze(structure,assignments,{'spherePoints':96},check=check)
    result.pop('structure',None)
    return result


def ingest_sequences(s,parent,chains,engine,receipt):
    chain=parent['structure']['chain'];seq=chains[chain]
    _,check,_=common();mask={chain:{k:copy.deepcopy(parent['constraints'][k]) for k in ('mutable','excluded','preferred')}}
    check({chain:seq},{chain:parent['sequence']},mask)
    with s.db:
        value=ev.Evolution(s).insert(parent['projectId'],parent['name']+' · '+engine,seq,copy.deepcopy(parent['constraints']),copy.deepcopy(parent['reference']),parent['residueMap'],parent,engine)
        value['changes']=[{'position':i+1,'from':a,'to':b} for i,(a,b) in enumerate(zip(parent['sequence'],seq)) if a!=b]
        value['backboneReference']=parent['structure'];value['validation']='sequence_only_requires_refold';value['engineReceipt']=receipt
        value['provenance']['conditioning'].append({'model':engine,'family':'ProteinMPNN','role':'sequence_optimization'})
        s.db.execute('UPDATE evolution_candidates SET data=? WHERE id=?',(ev.canonical(value),value['id']))
        ev.Evolution(s).event(parent['projectId'],value['id'],'engine_result',{'engine':engine,'receipt':receipt,'rePredictionRequired':True})
    return value


def local_model_admission(engine,models):
    if not engine.startswith('esmfold2'):return
    key='esmfold2-fast-bundle' if engine=='esmfold2_fast' else 'esmfold2-bundle'
    bundle=models.get(key)
    if not bundle:raise ValueError('Approved, checksum-verified ESM checkpoint bundle is missing.')
    entries=json.loads(pathlib.Path(bundle['path']).read_text())
    weight_bytes=sum(pathlib.Path(item['path']).stat().st_size for item in entries if str(item['path']).endswith('.safetensors'))
    if weight_bytes>12*1024**3:raise ValueError('This ESM checkpoint alone exceeds the protected local CPU memory allowance (12 GiB weights plus working-memory reserve within 14 GiB). Use a separately approved compatible GPU or a future validated local memory profile; no model truncation or fallback was performed.')


def local_biology_task(s,job,parent,record,path,targets,engine,check):
    """Same scientific task functions as RAPID; native runtime/device are explicit."""
    common()
    cfg=runtime_config(s);runtime=cfg['runtimes'].get('esmfold2' if engine.startswith('esmfold2') else engine)
    if not runtime:raise ValueError('Register the isolated '+engine+' runtime before execution.')
    model_key='esmfold2-fast-bundle' if engine=='esmfold2_fast' else 'esmfold2-bundle' if engine=='esmfold2' else 'solublempnn'
    models=cfg.get('models',{})
    if engine!='rosetta' and model_key not in models:raise ValueError('Approved, checksum-verified checkpoint missing: '+model_key)
    local_model_admission(engine,models)
    for key,item in models.items():
        file=pathlib.Path(item['path'])
        if not file.is_file() or file_sha(file)!=item['sha256']:raise ValueError('Registered model checksum changed: '+key)
        if key.endswith('-bundle'):
            for member in json.loads(file.read_text()):
                if file_sha(member['path'])!=member['sha256']:raise ValueError('Registered model bundle member changed.')
    chain=parent['structure']['chain'];folder=s.root/'jobs'/job['id']/(engine+'-'+parent['id']);folder.mkdir(exist_ok=True);(folder/'output').mkdir(exist_ok=True)
    mask={k:copy.deepcopy(parent['constraints'][k]) for k in ('mutable','excluded','preferred')}
    manifest={'schemaVersion':1,'engine':engine,'operation':'redesign' if engine=='solublempnn' else 'relax' if engine=='rosetta' else 'evaluate','target':{'format':'pdb' if record['data']['format']=='pdb' else 'cif','sha256':record['data']['sha256'],'chains':targets},'design':{'modality':'peptide','lengths':[len(parent['sequence'])],'count':job['data']['manifest']['count'],'attempts':job['data']['manifest']['count'],'designChains':[chain],'temperature':.1},'seed':job['data']['manifest']['seed'],'biology':{'parents':[{'id':parent['id'],'sequenceSha256':parent['sequenceSha256'],'chain':chain}],'sequences':{chain:parent['sequence']},'constraints':{chain:mask}}}
    if engine!='solublempnn':manifest['biology'].pop('constraints')
    (folder/('target.'+manifest['target']['format'])).write_bytes(path.read_bytes());(folder/'manifest.json').write_text(ev.canonical(manifest));(folder/'biology-runtime.json').write_text(ev.canonical({'runtime':runtime,'models':models}))
    package=pathlib.Path(__file__).resolve().parents[1]/'remote_worker';package=package if package.is_dir() else pathlib.Path(__file__).parent
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(package),runtime['source']+'/src',runtime['source']]),'BGMEE_DEVICE':'cpu','HF_HUB_OFFLINE':'1','HF_DATASETS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2'}
    with (folder/'execution.log').open('ab') as log:
        child=subprocess.Popen([runtime['python'],'-B','-m','fold_rapid.biology_tasks',engine,str(folder)],stdout=log,stderr=log,env=env)
        try:
            peak=0;last_memory=0
            while child.poll() is None:
                check()
                if sys.platform=='darwin' and time.monotonic()-last_memory>1:
                    from process_memory import process_memory,exceeds_footprint_budget
                    try:reading=process_memory(child.pid)
                    except ProcessLookupError:continue
                    peak=max(peak,reading['residentBytes'],reading['physicalFootprintBytes']);last_memory=time.monotonic()
                    if exceeds_footprint_budget(reading,14*1024**3):raise ValueError('Scientific task exceeded the protected 14 GiB footprint ceiling.')
                time.sleep(.2)
        except BaseException:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            raise
    if child.returncode:raise ValueError(engine+' exited with code '+str(child.returncode)+'; full log retained.')
    file=folder/'output'/('mpnn.json' if engine=='solublempnn' else 'biology-result.json')
    return json.loads(file.read_text()),{'artifact':str(file.relative_to(s.root)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'engine':engine,'device':'cpu','runtime':runtime,'seed':manifest['seed'],'peakObservedFootprintBytes':peak,'taskLimitBytes':14*1024**3}


def ingest_prediction(s,parent,receipt,row,family):
    source=s.root/receipt['artifact'];folder=source.parent
    name=row['structure'];path=folder/name
    if pathlib.Path(name).name!=name or path.is_symlink() or not path.is_file():raise ValueError('Prediction artifact missing or outside its task.')
    parsed=mi.parse_structure(path.read_text(),'pdb' if path.suffix=='.pdb' else 'mmcif');chain=parent['structure']['chain']
    observed=next((c for c in parsed['chains'] if c['id']==chain),None)
    if not observed or observed['sequence']!=parent['sequence']:raise ValueError('Prediction differs from the immutable candidate sequence.')
    record=s.import_structure({'projectId':parent['projectId'],'path':str(path),'name':parent['name']+' · '+receipt['engine'],'source':'BGMEE genuine computational prediction','metadata':{'evolutionCandidateId':parent['id'],'engineReceipt':receipt,'family':family,'experimentalValidation':False,'rawMetrics':row.get('metrics',{})}})
    structure={'recordId':record['id'],'sha256':record['data']['sha256'],'chain':chain}
    with s.db:ev.Evolution(s).event(parent['projectId'],parent['id'],'prediction',{'structure':structure,'receipt':receipt,'family':family,'metrics':row.get('metrics',{}),'experimentalValidation':False})
    return {**parent,'structure':structure},record,path,parsed


def evaluate(s,job,candidate,source_record,source_path,targets,predictors,check):
    original=mi.parse_structure(source_path.read_text(),source_record['data']['format'])
    row={'id':candidate['id'],'samples':[],'blocked':[],'physicsAssessment':False,'conditionedFamilies':[c['family'] for c in ev.Evolution(s).conditioned(candidate)['provenance']['conditioning']]}
    structures=[];preferred=None
    for engine in predictors:
        check()
        try:
            result,receipt=local_biology_task(s,job,candidate,source_record,source_path,targets,engine,check)
            predictions=result.get('predictions',[])
            if not predictions:raise ValueError('Predictor returned no coordinate outputs.')
            for sample_index,output in enumerate(predictions):
                predicted,record,path,parsed=ingest_prediction(s,candidate,receipt,output,result['family'])
                analysis=geometry(s,predicted,record,path,targets,check)
                change=assessment.drift(original,parsed,targets,candidate['structure']['chain'],candidate['constraints']['fixed'])
                row['samples'].append({'engine':engine,'sampleIndex':sample_index,'family':result['family'],'recordId':record['id'],'receipt':receipt,'confidence':output.get('metrics',{}),'metrics':assessment.metrics(analysis,candidate['sequence']),'drift':change})
                structures.append(parsed);preferred=preferred or (predicted,record,path)
        except (TimeoutError,InterruptedError):raise
        except Exception as error:row['blocked'].append({'engine':engine,'reason':str(error)})
    disagreements=[]
    for i,a in enumerate(structures):
        for b in structures[i+1:]:disagreements.append(assessment.drift(a,b,targets,candidate['structure']['chain'],candidate['constraints']['fixed'])['candidatePoseRmsd'])
    row['maxDisagreement']=max(disagreements) if disagreements else 0 if structures else None
    # Relax only a genuinely re-predicted descendant, never parent coordinates with its sequence relabelled.
    if preferred and any(step['operation']=='rosetta' for step in job['data']['manifest']['stages']):
        try:
            result,receipt=local_biology_task(s,job,*preferred,targets,'rosetta',check)
            row['physicsAssessment']={'receipt':receipt,'result':result,'model':'Rosetta','role':'held_out_assessment'}
        except (TimeoutError,InterruptedError):raise
        except Exception as error:row['blocked'].append({'engine':'rosetta','reason':str(error)})
    row['preferredPrediction']=preferred[0]['structure'] if preferred else None
    with s.db:ev.Evolution(s).event(candidate['projectId'],candidate['id'],'controller_assessment',row)
    return row


def run(s,id):
    job=s.job(id)
    if job['engine']!='bgmee' or job['state'] not in ('queued','running'):raise ValueError('Biology campaign cannot run in this state.')
    s._compute_owner=id
    manifest=job['data']['manifest'];deadline=time.monotonic()+manifest['seconds'];folder=s.root/'jobs'/id
    folder.mkdir(exist_ok=True);s.job_update(id,'running',{'started':research.utc()});stages=[];descendants=[];children=[];rounds=[];retained=[]
    def check():
        if s.job(id)['state']=='cancelled':raise InterruptedError('Campaign cancelled; existing artifacts retained.')
        if time.monotonic()>=deadline:raise TimeoutError('Campaign wall budget exhausted; completed scientific results retained.')
    def redesign(parent,record,path,structure,chain,targets,engine):
        if engine=='solublempnn':return local_biology_task(s,job,parent,record,path,targets,engine,check)
        ids=[r['id'] for r in structure['residues'] if r['chain']==chain and r['polymer']];mutable=[ids[i-1] for i in parent['constraints']['mutable']]
        if not mutable:raise ValueError('No permitted mutable residues.')
        position_constraints={ids[int(pos)-1]:{key:parent['constraints'][key].get(pos,'') for key in ('excluded','preferred')} for pos in set(parent['constraints']['excluded'])|set(parent['constraints']['preferred'])}
        child=mpnn.start(s,{'projectId':job['project_id'],'structureId':record['id'],'designChains':[chain],'designResidues':mutable,'positionConstraints':position_constraints,'count':manifest['count'],'seed':manifest['seed'],'temperature':.1,'variant':'neutral'})
        children.append(child['id']);s.job_metadata(id,{'children':children})
        while child['state'] in ('queued','running'):
            try:check()
            except (TimeoutError,InterruptedError):s.job_cancel({'id':child['id']});raise
            time.sleep(.2);child=s.job(child['id'])
        if child['state']!='completed':raise ValueError('ProteinMPNN child '+child['state']+': '+str(child['data'].get('error','')))
        result_path=s.root/'jobs'/child['id']/'result.json';result=json.loads(result_path.read_text());receipt={'jobId':child['id'],'checkpointSha256':result['checkpointSha256'],'resultSha256':file_sha(result_path),'seed':manifest['seed'],'device':'cpu','engine':engine}
        return result,receipt
    try:
        parent,record,path,structure,chain,targets=candidate_source(s,{'projectId':job['project_id'],'candidateId':manifest['candidateId'],'targetChains':manifest['targetChains']})
        if record['data']['sha256']!=manifest['sourceSha256']:raise ValueError('Prepared source changed.')
        rules=assessment.policy(manifest.get('selectionRules'));_,_,pareto=common();seen=set();stopping='round_budget_exhausted'
        predictors=[step['operation'] for step in manifest['stages'] if step['operation'].startswith('esmfold2')]
        branches=[step['operation'] for step in manifest['stages'] if step['operation'] in ('proteinmpnn','solublempnn')]
        analysis=geometry(s,parent,record,path,targets,check);(folder/'geometry.json').write_text(ev.canonical(analysis))
        stages.append({'engine':'geometry','state':'completed','metrics':assessment.metrics(analysis,parent['sequence'])})
        for iteration in range(rules['rounds']):
            check();proposals=[ev.Evolution(s).candidate(job['project_id'],cid) for cid in manifest.get('counterfactualCandidates',[])]
            for engine in branches:
                stage={'engine':engine,'round':iteration+1,'parentId':parent['id'],'started':research.utc()}
                try:
                    result,receipt=redesign(parent,record,path,structure,chain,targets,engine)
                    for output in result['candidates']:
                        sequence=output['chains'][chain];digest=hashlib.sha256(sequence.encode()).hexdigest()
                        key=(engine,digest)
                        if digest==parent['sequenceSha256'] or key in seen:
                            with s.db:ev.Evolution(s).event(parent['projectId'],parent['id'],'proposal_rejected',{'engine':engine,'reason':'duplicate_sequence','sequenceSha256':digest,'receipt':receipt})
                            continue
                        if len(descendants)>=rules['maxDescendants']:break
                        try:
                            value=ingest_sequences(s,parent,output['chains'],engine,receipt);seen.add(key);proposals.append(value);descendants.append(value['id'])
                        except ValueError as error:
                            with s.db:ev.Evolution(s).event(parent['projectId'],parent['id'],'proposal_rejected',{'engine':engine,'sequence':sequence,'reason':str(error),'receipt':receipt})
                    stage.update(state='completed',receipt=receipt)
                except (TimeoutError,InterruptedError):raise
                except Exception as error:stage.update(state='blocked',reason=str(error))
                stage['finished']=research.utc();stages.append(stage);s.job_metadata(id,{'stages':stages,'descendants':descendants})
            if not proposals:stopping='no_new_constraint_valid_sequence';break
            if not predictors:stopping='prediction_not_configured';break
            rows=[evaluate(s,job,parent,record,path,targets,predictors,check)]
            for proposal in proposals:
                # Backbone reference is input context only; all inference uses the descendant's explicit sequence.
                input_candidate={**proposal,'structure':parent['structure']}
                rows.append(evaluate(s,job,input_candidate,record,path,targets,predictors,check))
            selection=assessment.select(rows,rules,pareto);baseline=next(r for r in selection if r['id']==parent['id'])
            chosen=[r for r in selection if r['id']!=parent['id'] and r['eligible'] and r['id'] in baseline['dominatedBy']]
            round_report={'round':iteration+1,'parentId':parent['id'],'assessments':selection,'supportedImprovements':[r['id'] for r in chosen]}
            if manifest.get('counterfactualCandidates'):
                spec=manifest['counterfactualComparison'];round_report['counterfactuals']=assessment.counterfactual(rows,{c['id']:c for c in proposals},spec['metric'],spec['higher'],spec['neutralTolerance'])
            rounds.append(round_report)
            s.job_metadata(id,{'rounds':rounds})
            for row in selection:
                with s.db:ev.Evolution(s).event(parent['projectId'],row['id'],'selection',{'round':iteration+1,'decision':'retain_for_computational_review' if row in chosen else 'no_supported_improvement','reasons':row['reasons'],'dominatedBy':row['dominatedBy'],'experimentalValidation':False})
            if not chosen:stopping='no_supported_held_out_improvement';break
            retained.extend(r['id'] for r in chosen)
            # Deterministic continuation through an eligible nondominated candidate, no universal composite score.
            chosen.sort(key=lambda r:r['id']);best=chosen[0]
            parent=ev.Evolution(s).candidate(job['project_id'],best['id']);parent={**parent,'structure':best['preferredPrediction']}
            with s.db:
                for family in best['predictionFamilies']:ev.Evolution(s).event(parent['projectId'],parent['id'],'assessment',{'model':'controller_selection','family':family,'role':'optimization','contextId':manifest['manifestSha256'],'metrics':best['metrics']})
            record,path=mi.Lab(s).record(parent['structure']['recordId']);structure=mi.parse_structure(path.read_text(),record['data']['format'])
            if len(descendants)>=rules['maxDescendants']:stopping='descendant_budget_exhausted';break
        report={'schemaVersion':2,'manifest':manifest,'stages':stages,'rounds':rounds,'descendants':descendants,'retainedForComputationalReview':retained,'qualifiedCandidates':[],'stoppingReason':stopping,'scientificCertification':False,'selection':'Explicit Pareto objectives, worst-sample hard gates, matched parent re-prediction, protected-residue/pose drift, family dependence and held-out physics. Descriptive criteria are not binding affinity or experimental efficacy.','finished':research.utc()}
        file=folder/'biology-report.json';file.write_text(ev.canonical(report));s.job_update(id,'completed',{'report':str(file.relative_to(s.root)),'stages':stages,'rounds':rounds,'descendants':descendants,'retainedForComputationalReview':retained,'qualifiedCandidates':[],'finished':research.utc()})
    except BaseException as error:
        for child in children:
            if s.job(child)['state'] in ('queued','running'):s.job_cancel({'id':child})
        if s.job(id)['state']!='cancelled':s.job_update(id,'interrupted' if isinstance(error,(TimeoutError,InterruptedError)) else 'failed',{'error':str(error),'stages':stages,'rounds':rounds,'descendants':descendants,'finished':research.utc()})
        print('Biology campaign:',type(error).__name__,str(error),flush=True)


def dispatch(s,action,p):
    s.project(p['projectId'])
    if action=='biology_services_configure':
        import biology_providers
        path=pathlib.Path(str(p.get('python',''))).expanduser().absolute()
        if p.get('approved') is not True or not path.is_file():raise ValueError('Approve an existing isolated provider interpreter.')
        # Store temporarily only for this import probe, commit after exact version checks.
        prior=s.setting('biologyServicesPython');s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('biologyServicesPython',json.dumps(str(path))))
        try:
            value=biology_providers.status(s)
            if not value['installed']:raise ValueError('Provider SDK versions differ from the pinned contract.')
            s.db.commit();return value
        except BaseException:s.db.rollback();raise
    if action=='biology_runtime_register':return runtime_register(s,p)
    if action=='biology_model_register':return model_register(s,p)
    if action=='biology_bindcraft_prepare':return seeded_prepare(s,p)
    if action=='biology_chemistry_derive':return chemistry_derive(s,p)
    if action=='biology_pipeline_plan':return plan(s,p)
    if action=='biology_pipeline_start':return start(s,p)
    if action=='biology_counterfactual_start':
        if not p.get('counterfactualCandidates'):raise ValueError('Select mapped experimental or negative-control descendants.')
        return start(s,p)
    if action=='biology_pipeline_jobs':return [s.job(r['id']) for r in s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='bgmee' ORDER BY created DESC",(p['projectId'],))]
    job=s.job(p['id'])
    if job['project_id']!=p['projectId'] or job['engine']!='bgmee':raise ValueError('Choose a biology campaign in this project.')
    file=job['data'].get('report')
    if not file:return {'job':job,'report':None}
    path=s.root/file
    if path.is_symlink() or (s.root/'jobs'/job['id']).resolve() not in path.resolve().parents:raise ValueError('Invalid report path.')
    return {'job':job,'report':json.loads(path.read_text())}
