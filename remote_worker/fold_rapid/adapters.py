"""Real upstream execution contracts; no dummy predictions or CPU fallback."""
import csv
import json
import os
import pathlib
import re
import sys
from .contracts import canonical,digest,target_bytes
from .molecules import inspect,selected_target
from .registry import ENGINES,verified_runtime

def prepare(root, job, manifest):
    mapping=selected_target(manifest);target=job/('target.'+manifest['target']['format'])
    target.write_bytes(target_bytes(manifest['target']))
    output=job/'output';output.mkdir(exist_ok=True)
    (job/'target-mapping.json').write_text(canonical(mapping))
    engine=manifest['engine'];d=manifest['design']
    if engine=='structure_screen':return {'command':[sys.executable,'-m','fold_rapid.engine_tasks','screen',str(job)],'environment':{},'models':{},'mapping':mapping}
    runtime,models=verified_runtime(root,engine);python=runtime['python'];source=pathlib.Path(runtime['source'])
    if engine in ('esmfold2','esmfold2_fast','solublempnn','rosetta','rfdiffusion'):
        from .biology_contract import validate
        validate(manifest.get('biology',{}),mapping)
        (job/'biology-runtime.json').write_text(canonical({'runtime':runtime,'models':models}))
        environment={'PYTHONPATH':os.pathsep.join([str(source/'src'),str(source),str(pathlib.Path(__file__).resolve().parents[1])]),'HF_HOME':str(pathlib.Path(root)/'models/huggingface'),'HF_HUB_OFFLINE':'1','HF_DATASETS_OFFLINE':'1','BGMEE_DEVICE':'cpu' if engine=='rosetta' else 'cuda'}
        if engine=='rfdiffusion':
            from .scaffolding import prepare as scaffold_prepare
            command=scaffold_prepare(job,manifest,runtime,models)
        else:command=[python,'-m','fold_rapid.biology_tasks',engine,str(job)]
        return {'command':command,'environment':environment,'models':models,'mapping':mapping,'sourceRevision':ENGINES[engine]['revision'],'runtimeReceipt':runtime}
    env={'PYTHONPATH':str(source),'JAX_PLATFORMS':'cuda','JAX_PLATFORM_NAME':'gpu','XLA_PYTHON_CLIENT_PREALLOCATE':'false','HF_HUB_OFFLINE':'1','HF_DATASETS_OFFLINE':'1','BINDCRAFT_AF2_PARAMS':str(pathlib.Path(next((v['path'] for k,v in models.items() if k.startswith('model_')),'' )).parent),'BINDCRAFT_MPNN_WEIGHTS':str(pathlib.Path(models['mpnn-neutral']['path']).parent) if 'mpnn-neutral' in models else str(source/'bindcraft/weights/proteinmpnn/weights_neutral')}
    if engine=='bindcraft2':
        # Original settings resolver owns scientific defaults. Only target,
        # requested format/lengths/attempt budget/seed/output are translated.
        if any(not str(v).lstrip('-').isdigit() for values in d.get('hotspots',{}).values() for v in values):raise ValueError('BindCraft hotspot insertion-code translation needs an explicitly validated construct; no residue renumbering is inferred.')
        settings={**manifest.get('settings',{}),'targets':[{'name':'target','target_path':str(target),'chains':','.join(manifest['target']['chains']),'hotspots':','.join(chain+str(v) for chain in manifest['target']['chains'] for v in d.get('hotspots',{}).get(chain,[]))}], 'modality':[d['modality']], 'binder_lengths':d['lengths'],'campaign_seed':manifest['seed'],'number_of_final_designs':d['count'],'max_trajectories':d['attempts'],'project_folder':str(output),'resume':False}
        (job/'execution-settings.json').write_text(canonical(settings))
        command=[python,str(source/'bindcraft.py'),'design',str(job/'execution-settings.json')]
        if manifest.get('biology'):
            bio=manifest['biology']
            if len(bio.get('parents',[]))!=1 or len(bio.get('sequences',{}))!=1:raise ValueError('Seeded BindCraft requires one explicit reference per campaign.')
            sequence=next(iter(bio['sequences'].values()))
            if d['lengths'] not in ([len(sequence)],[len(sequence),len(sequence)]):raise ValueError('Seeded BindCraft must retain the reference length.')
            (job/'seed-protocol.json').write_text(canonical(bio))
            env['PYTHONPATH']=os.pathsep.join([str(source),str(pathlib.Path(__file__).resolve().parents[1])])
            command=[python,'-m','fold_rapid.seeded_bindcraft',str(job/'execution-settings.json'),str(job/'seed-protocol.json')]
    elif engine=='boltzgen':
        if manifest.get('settings'):raise ValueError('BoltzGen arbitrary overrides are not enabled; use its pinned original protocol.')
        if 'G' in manifest['target']['chains']:raise ValueError('Target chain G conflicts with the generated binder; prepare a separately numbered construct.')
        # JSON is valid YAML 1.2. Preserve target file bytes and chain IDs.
        entities=[{'protein':{'id':'G','sequence':str(d['lengths'][0])+'..'+str(d['lengths'][-1])}}, {'file':{'path':str(target),'include':[{'chain':{'id':c}} for c in manifest['target']['chains']],'structure_groups':'all'}}]
        if d.get('hotspots'):entities[1]['file']['binding_types']=[{'chain':{'id':c,'binding':','.join(map(str,values))}} for c,values in d['hotspots'].items()]
        (job/'design.yaml').write_text(canonical({'entities':entities}))
        # Explicit local paths prevent upstream first-use model downloads.
        command=[python,'-m','boltzgen.cli.boltzgen','run',str(job/'design.yaml'),'--output',str(output),'--protocol','peptide-anything' if d['modality']=='peptide' else 'protein-anything','--devices','1','--num_designs',str(d['count']),'--budget',str(d['count']),'--cache',str(pathlib.Path(models['folding']['path']).parent),'--design_checkpoints',models['design-diverse']['path'],models['design-adherence']['path'],'--solublempnn_checkpoint',models['solublempnn']['path'],'--folding_checkpoint',models['folding']['path'],'--moldir',runtime.get('moldir','')]
        if not runtime.get('moldir') or not pathlib.Path(runtime['moldir']).is_dir():raise ValueError('Verified extracted BoltzGen molecule cache is required.')
        if not runtime.get('esmfold2Python') or not pathlib.Path(runtime['esmfold2Python']).is_file():raise ValueError('The separately pinned ESMFold2 scoring environment is required by the original BoltzGen pipeline.')
        command+=['--esmfold2_python',runtime['esmfold2Python'],'--esmfold2_acceleration','off','--use_kernels','false']
        # BoltzGen's diffusion count is an intermediate sampling budget; its
        # final diversity-selection budget is the requested candidate count.
        if d['count']>d['attempts']:raise ValueError('BoltzGen requested final candidates cannot exceed its generation budget.')
        command[command.index('--num_designs')+1]=str(d['attempts'])
        command=[python,'-m','fold_rapid.boltz_entry',str(manifest['seed']),*command[3:]]
        env['PYTHONPATH']=os.pathsep.join([str(source/'src'),str(pathlib.Path(__file__).resolve().parents[1])])
        env['PYTHONHASHSEED']=str(manifest['seed'])
        env['HF_HOME']=str(pathlib.Path(root)/'models/huggingface');env['UV_OFFLINE']='1'
    else:
        # Dedicated executable calls the pinned upstream classes directly.
        if not d.get('designChains') or set(d['designChains'])-set(mapping['chains']):raise ValueError('Explicit existing binder/redesign chains are required.')
        if set(d['designChains']) & set(manifest['target']['chains']):raise ValueError('Design chains and fixed target chains must be disjoint.')
        env['PYTHONPATH']=os.pathsep.join([str(source),str(pathlib.Path(__file__).resolve().parents[1])])
        command=[python,'-m','fold_rapid.engine_tasks',engine,str(job)]
    return {'command':command,'environment':env,'models':models,'mapping':mapping,'sourceRevision':ENGINES[engine]['revision'],'runtimeReceipt':runtime}

def parse_progress(line):
    clean=re.sub(r'\x1b\[[0-9;]*m','',line)[-4000:]
    stages=[s for s in ('screen','refine','anneal','harden','mutate','ProteinMPNN','refold','filter','rank') if s.lower() in clean.lower()]
    return {'kind':'engine_log','message':clean,'observedStages':stages,'scope':'Parsed upstream log; not a certified optimizer checkpoint.'}

def collect(job, manifest, provenance):
    """Normalize authentic upstream rows and retain engine-specific semantics."""
    output=job/'output';rows=[]
    engine=manifest['engine']
    if engine=='bindcraft2':
        tables=sorted(output.glob('**/!_Ranked.csv'))+sorted(output.glob('**/!_Refolded.csv'))+sorted(output.glob('**/!_Trajectories.csv'))
        for table in tables:
            with table.open(newline='') as f:
                for row in csv.DictReader(f):
                    if not row.get('design'):continue
                    structure=next((p for p in output.rglob(row['design']+'.cif') if p.is_file() and not p.is_symlink()),None)
                    if structure is None:
                        structure=next((p for p in output.rglob(row['design']+'_trajectory.cif') if p.is_file() and not p.is_symlink()),None)
                    if table.name=='!_Ranked.csv':
                        row={**row,'outcome':'accepted','upstreamStage':'ranked','acceptanceScope':'Original upstream ranked computational prediction; not experimental or full-engine qualification.'}
                    elif table.name=='!_Refolded.csv' and row.get('outcome')=='passed':
                        row={**row,'upstreamOutcome':'passed','outcome':'passed_upstream_filters','upstreamStage':'refolded'}
                    elif row.get('terminated'):
                        row={**row,'outcome':'rejected','failed_filters':row['terminated'],'coordinateStatus':'Incomplete upstream optimization; inspect trajectory and independently refold any diagnostic sequence.'}
                    rows.append((row,structure,'design','Binder_Sequence'))
    elif engine=='boltzgen':
        for table in sorted(output.glob('**/all_designs_metrics.csv')):
            with table.open(newline='') as f:
                for row in csv.DictReader(f):
                    name=row.get('file_name') or row.get('id')
                    if not name:continue
                    matches=[p for p in output.rglob(pathlib.Path(name).name) if p.suffix in ('.cif','.mmcif') and not p.is_symlink()]
                    # Upstream keeps diffusion backbones and their refolded
                    # complexes under the same filename. Metrics describe the
                    # refolded complex; traversal order must never select a
                    # different coordinate stage accidentally.
                    refolds=[p for p in matches if p.parent.name=='refold_cif']
                    choices=refolds or matches
                    if len({digest(p.read_bytes()) for p in choices})>1:raise ValueError('Ambiguous BoltzGen coordinate outputs; preserve native artifacts for inspection.')
                    structure=next(iter(choices),None)
                    rows.append((row,structure,'id','designed_sequence'))
    elif engine=='af2_multimer':
        report=output/'evaluation.json'
        if report.is_file():
            for row in json.loads(report.read_text())['predictions']:
                rows.append(({'design':row['model'],'outcome':'evaluated','metrics':row['metrics'],'arrayMetricsArtifact':row['arrayMetricsArtifact']},output/(row['model']+'.cif'),'design','sequence'))
    elif engine in ('proteinmpnn','solublempnn'):
        report=output/'mpnn.json'
        if report.is_file():
            for i,row in enumerate(json.loads(report.read_text())['candidates']):
                rows.append(({'design':f'sequence-{i}','outcome':'sequence_redesigned','metrics':row['metrics'],'sequence':'/'.join(row['chains'][ch] for ch in manifest['design']['designChains']),'fastaArtifact':f'output/sequence-{i}.fasta'},None,'design','sequence'))
    elif engine in ('esmfold2','esmfold2_fast','rosetta'):
        report=output/'biology-result.json'
        if report.is_file():
            data=json.loads(report.read_text())
            if engine=='rosetta':rows.append(({'design':'relaxed','outcome':'physical_refinement_requires_validation','metrics':{k:v for k,v in data.items() if type(v) in (int,float)},'method':data},output/data['structure'],'design','sequence'))
            else:
                for row in data['predictions']:rows.append(({'design':'prediction-'+str(row['sample']),'outcome':'evaluated','metrics':row['metrics'],'confidenceArtifact':row['confidenceArtifact'],'modelFamily':data['family']},output/row['structure'],'design','sequence'))
    elif engine=='rfdiffusion':
        from .scaffolding import collect as scaffold_collect
        rows=scaffold_collect(job,manifest)
    exposure={}
    if engine=='bindcraft2' and (output/'campaign_metadata.json').is_file():
        receipt=json.loads((output/'campaign_metadata.json').read_text());resolved=receipt.get('resolved',{})
        exposure={'gradientDesignModels':resolved.get('design_models',[]),'validationModels':resolved.get('validation_models',[]),'sourceArtifact':'output/campaign_metadata.json','sourceSha256':digest((output/'campaign_metadata.json').read_bytes())}
    candidates=[];seen=set()
    for row,path,id_key,seq_key in rows:
        raw=path.read_bytes() if path else None
        mapping=inspect(raw,'pdb' if path.suffix.lower()=='.pdb' else 'cif') if raw else None
        roles={}
        if raw and engine=='bindcraft2':
            # Explicit native chain roles, never guessed from chain order.
            import gemmi
            block=gemmi.cif.read_string(raw.decode()).sole_block()
            for role in ('binder','target'):
                text=block.find_value('_bindcraft.'+role+'_chains')
                if text:roles[role]=text.strip("'\"").split(',')
        elif mapping and engine=='boltzgen':
            roles={'binder':['G'],'target':manifest['target']['chains']}
            if not set(roles['binder']+roles['target'])<=set(mapping['chains']):raise ValueError('BoltzGen output chain identities differ from the submitted construct; no chain mapping is inferred.')
        elif mapping:roles=row.get('chainRoles',{'binder':manifest['design'].get('designChains',[]),'target':manifest['target']['chains']})
        sequence=row.get(seq_key,'')
        if not sequence and mapping and roles.get('binder'):
            sequence='/'.join(mapping['chains'][c]['sequence'] for c in roles['binder'] if c in mapping['chains'])
        if engine=='bindcraft2' and row.get('upstreamStage')=='ranked':
            if not mapping or not roles.get('binder') or not roles.get('target') or sequence!='/'.join(mapping['chains'][ch]['sequence'] for ch in roles['binder']):
                raise ValueError('Original ranked acceptance needs matching coordinates, source chain roles and sequence; acceptance cannot be inferred from a table alone.')
        key=digest(canonical({'runId':provenance.get('jobId'),'manifestSha256':provenance.get('manifestSha256'),'targetSha256':manifest['target']['sha256'],'engine':engine,'row':row,'coordinate':digest(raw) if raw else None}).encode())
        if key in seen:continue
        seen.add(key)
        flags={k:str(v).lower() in ('true','1','1.0') for k,v in row.items() if k.startswith('pass_') and k.endswith('_filter')}
        outcome=row.get('outcome','passed_upstream_filters' if flags and all(flags.values()) else 'rejected' if flags else 'unclassified')
        record={'schemaVersion':1,'candidateId':key,'generator':engine,'upstreamId':row.get(id_key),'parentCandidates':manifest.get('parentCandidates',[]), 'binderSequence':sequence or None,'binderLength':len(sequence.replace('/','')) if sequence else None,'target':{'sha256':manifest['target']['sha256'],'chains':manifest['target']['chains'],'mappingArtifact':'target-mapping.json'},'coordinates':{'artifact':str(path.relative_to(job)),'sha256':digest(raw),'mapping':mapping,'chainRoles':roles} if raw else None,'metrics':row,'metricNamespace':engine,'outcome':outcome,'rejectionReasons':row.get('failed_filters',','.join(k for k,v in flags.items() if not v)),'seed':manifest['seed'],'provenance':provenance,'independentEvaluationHistory':[row] if engine=='af2_multimer' else [],'sequenceRedesignHistory':[row] if engine=='proteinmpnn' else [],'biologicalValidation':'Not experimentally validated; predictions do not establish binding or inhibition.'}
        record['sequenceScreen']={'canonical':bool(sequence) and set(sequence.replace('/',''))<=set('ACDEFGHIKLMNPQRSTVWY'),'scope':'Sequence identity check only; no binding prediction.'}
        if exposure:record['af2ModelExposure']=exposure
        dest=job/'candidates'/f'{key}.json';dest.parent.mkdir(exist_ok=True)
        if dest.exists() and dest.read_text()!=canonical(record):raise ValueError('Immutable candidate identity conflict.')
        dest.write_text(canonical(record));candidates.append(record)
    (job/'candidates.json').write_text(canonical(candidates))
    return candidates
