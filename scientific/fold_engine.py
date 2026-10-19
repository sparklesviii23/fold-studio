"""FOLD SCIENTIFIC ENGINE foundation using the existing library, jobs and IPC.

Upstream remains unmodified. Immutable library coordinates are the only campaign
inputs. Preparation is not execution; imported predictions are not experiments.
"""
import ast, csv, hashlib, io, json, math, os, pathlib, re, uuid
import intelligence as mi
import fold_compute

BASE=pathlib.Path(__file__).resolve().parents[1]
UPSTREAM=BASE/'vendor'/'bindcraft2'
PIN='c0ee638d11bc010817c2c97ee58ed5c323e664e2'
ACTIONS={'bindcraft_results','bindcraft_review','bindcraft_resume','bindcraft_repeat','fold_fragment','fold_engine_status','fold_structure','fold_compute','bindcraft_validate','bindcraft_prepare','bindcraft_campaigns','bindcraft_import','bindcraft_start'}
CONFIG_KEYS={'core','properties','projectId','structureId','name','modality','targetChains','hotspots','coldspots','binderLengths','candidates','attempts','seed','additionalTargets'}
SUPPORTED_MODALITIES=('binder','large_binder','multidomain','induced_fit','fold_switch','peptide','cyclic_peptide','VHH','ARP','scFv','homo_oligomer')
SCAFFOLD_MODALITIES=('VHH','ARP','scFv')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def checksum(data):return hashlib.sha256(data).hexdigest()
def integer(value,name,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError(f'{name} must be an integer from {low} to {high}.')
    return value

def source_status():
    manifest=BASE/'vendor'/'bindcraft2-source.json'
    if not manifest.is_file():return {'state':'missing','revision':PIN}
    data=json.loads(manifest.read_text())
    return {'state':'present' if UPSTREAM.is_dir() else 'missing','revision':data['revision'],'manifestSha256':checksum(manifest.read_bytes()),'license':'BindCraft2 Source-Available License (Hosting-Restricted)','modified':False}

def verify_source():
    data=json.loads((BASE/'vendor'/'bindcraft2-source.json').read_text())
    if data['revision']!=PIN:raise ValueError('Unexpected BindCraft2 source revision.')
    for name,expected in data['files'].items():
        path=UPSTREAM/name
        if not path.is_file() or path.is_symlink() or checksum(path.read_bytes())!=expected:
            raise ValueError('Pinned BindCraft2 source changed: '+name)
    return source_status()

class Engine:
    def __init__(self,service):self.s=service;self.lab=mi.Lab(service)
    def dispatch(self,action,p):return getattr(self,action)(p)
    def fold_engine_status(self,p):
        modalities=[]
        for path in sorted((UPSTREAM/'settings'/'modality').glob('*.json')):
            modalities.append({'name':path.stem,'description':json.loads(path.read_text()).get('description',''),'configuration':'tested' if path.stem in SUPPORTED_MODALITIES else 'not_started','execution':'experimental' if path.stem in SUPPORTED_MODALITIES else 'blocked'})
        return {'name':'FOLD SCIENTIFIC ENGINE','schemaVersion':1,'source':source_status(),'modalities':modalities,
                'properties':__import__('campaign_profile').property_catalog(UPSTREAM),'coreProfiles':__import__('campaign_profile').core_catalog(UPSTREAM),
                'engines':[{'id':'bindcraft2','configuration':'implemented','resultImport':'implemented','execution':'experimental_cpu_and_metal','metalExecution':'experimental_float32_requires_pinned_runtime','modelEnsembles':'original_upstream_selection','profiles':['experimental-cpu-single-model','experimental-cpu-float32-single-model','experimental-cpu-float32-scaffold','experimental-cpu-float32-320','experimental-cpu-float32-conformational','experimental-cpu-float32-multitarget','experimental-metal-float32-single-model','experimental-cpu-float32-ensemble','experimental-metal-float32-ensemble']},
                           {'id':'openmm','execution':'cpu','scope':'Short Amber ff14SB/OBC2 protein pilot; not equilibrated sampling or Metal execution'}, {'id':'rdkit','execution':'cpu','scope':'Ligand ETKDGv3/MMFF94s preparation; not docking or biological activity validation'}, {'id':'proteinmpnn','execution':'cpu','scope':'Fixed-backbone sequence redesign; mpnn_start/mpnn_jobs'}, {'id':'boltz2','adapter':'existing prediction_start'}, {'id':'chimerax','adapter':'existing chimerax_execute; separately installed runtime; command availability is not validation'}],
                'commands':[{'name':x,'status':'implemented' if x!='bindcraft_start' else 'experimental'} for x in sorted(ACTIONS)],
                'dataModel':'Existing structure records/assets, stable residue/atom identities from Molecular Intelligence; existing jobs table. No parallel coordinate store.'}
    def fold_fragment(self,p):
        from target_fragment import create
        return create(self,p)
    def fold_compute(self,p):return fold_compute.diagnostic(self.s)
    def fold_structure(self,p):
        record,path=self.lab.record(p['structureId'])
        if p.get('projectId') and record['project_id']!=p['projectId']:raise ValueError('Structure belongs to another project.')
        structure=mi.parse_structure(path.read_text(),record['data']['format'])
        return {'schemaVersion':1,'reference':{'structureId':record['id'],'projectId':record['project_id'],'sha256':record['data']['sha256'],'format':record['data']['format'],'model':structure['model']},'structure':structure}
    def bindcraft_validate(self,p):
        unknown=set(p)-CONFIG_KEYS
        if unknown:raise ValueError('Unsupported campaign fields: '+', '.join(sorted(unknown)))
        self.s.project(p['projectId']);shared=self.fold_structure(p);st=shared['structure']
        modality=p.get('modality','binder')
        if modality not in SUPPORTED_MODALITIES:raise ValueError('Other upstream modalities remain blocked until their constraints and execution are validated.')
        if modality in SCAFFOLD_MODALITIES and 'binderLengths' in p:raise ValueError(modality+' length follows the original scaffold '+('repeat' if modality=='ARP' else 'CDR')+' edit choices; free binder length bounds do not apply.')
        chains=p.get('targetChains')
        if not isinstance(chains,list) or not chains or any(not isinstance(c,str) for c in chains) or len(chains)!=len(set(chains)):raise ValueError('Choose distinct target chains.')
        available={c['id']:c for c in st['chains']}
        if any(c not in available or not re.fullmatch('[A-Za-z]',c) for c in chains):raise ValueError('Initial adapter requires explicit one-letter PDB chain identifiers.')
        selected=[r for r in st['residues'] if r['chain'] in chains]
        record,path=self.lab.record(p['structureId'])
        raw_atoms=list(mi.atom_rows(path.read_text(),record['data']['format']))
        if len(st['models'])!=1 or any(a['chain'] in chains and (a['alt'] or a['occupancy']<=0) for a in raw_atoms):raise ValueError('Initial campaign preparation requires one coordinate model and resolved alternate conformers/occupancies.')
        if any(not r['polymer'] or r['one']=='X' or r['ins'] or r['num']<1 for r in selected):raise ValueError('Selected chains must contain canonical protein residues with positive numbering and no insertion codes. Prepare an explicit derived input for other cases.')
        for r in selected:
            if not {'N','CA','C','O'}.issubset(st['atoms'][i]['name'] for i in r['atoms']):raise ValueError('Selected target residues require complete N, CA, C, O backbone atoms.')
        lengths=p.get('binderLengths',{'peptide':[15,25],'cyclic_peptide':[7,16],'homo_oligomer':[40,120],'large_binder':[250,600],'multidomain':[120,300]}.get(modality,[60,100]))
        if not isinstance(lengths,list) or len(lengths) not in (1,2):raise ValueError('Binder lengths must be [fixed] or [minimum, maximum].')
        for length in lengths:integer(length,'Binder length',5,600 if modality=='large_binder' else 500)
        if lengths!=sorted(lengths):raise ValueError('Binder length bounds must be ordered.')
        candidates=integer(p.get('candidates',5),'Candidates',1,1000);attempts=integer(p.get('attempts',20),'Attempts',1,100000);seed=integer(p.get('seed',42),'Seed',0,2147483647)
        if attempts<candidates:raise ValueError('Attempts must be at least the requested candidate count.')
        def sites(key):
            requested=p.get(key,[])
            if not isinstance(requested,list) or any(not isinstance(x,str) for x in requested) or len(requested)!=len(set(requested)):raise ValueError('Choose distinct '+key+' residue identities.')
            by_id={r['id']:r for r in selected}
            if set(requested)-set(by_id):raise ValueError(key+' must reference observed residues on selected target chains.')
            return [by_id[x] for x in requested]
        hot,cold=sites('hotspots'),sites('coldspots')
        if {r['id'] for r in hot}&{r['id'] for r in cold}:raise ValueError('A residue cannot be both a hotspot and a coldspot.')
        # Presets are upstream data, retained verbatim; never invent optimization defaults.
        preset=json.loads((UPSTREAM/'settings'/'modality'/(modality+'.json')).read_text());preset.pop('description',None)
        from campaign_profile import property_preset
        resolved,properties=property_preset(self.s,modality,p.get('properties',[]),UPSTREAM,p.get('core'))
        if resolved is not None:preset=resolved
        scaffold=None
        if preset.get('binder_scaffold'):
            source=UPSTREAM/preset['binder_scaffold']
            if not source.is_file() or not source.resolve().is_relative_to(UPSTREAM.resolve()):raise ValueError('Pinned scaffold asset is unavailable.')
            scaffold={'file':'scaffold.cif','source':str(source.relative_to(UPSTREAM)),'sha256':checksum(source.read_bytes()),'modality':modality}
            preset['binder_scaffold']=scaffold['file']
        config={**preset,'binder_lengths':lengths,'number_of_final_designs':candidates,'max_trajectories':attempts,'campaign_seed':seed,'attention_backend':'stock','use_cueq':False,'auto_multi_gpu':False,'design_workers':1,'resume':False,
                'targets':[{'name':'target','target_path':'input'+('.pdb' if shared['reference']['format']=='pdb' else '.cif'),'chains':','.join(chains),'hotspots':','.join(r['chain']+str(r['num']) for r in hot),'coldspots':','.join(r['chain']+str(r['num']) for r in cold)}],'project_folder':'output'}
        name=p.get('name','Design campaign')
        if not isinstance(name,str) or not name.strip() or len(name)>160:raise ValueError('Enter a campaign name of 1–160 characters.')
        checked={'schemaVersion':1,'name':name.strip(),'valid':True,'executionReady':False,'modality':modality,'scaffold':scaffold,'source':shared['reference'],'config':config,'residueMap':[{'id':r['id'],'chain':r['chain'],'number':r['num'],'aminoAcid':r['one']} for r in selected],
                'settingsSha256':checksum(canonical(config).encode()),'upstream':source_status(),'warnings':['Prepared configuration is not a completed design or a validated full-model Metal backend.','Hotspots use observed source numbering; no biological numbering conversion is inferred.','Memory feasibility has not been established for this target.']}
        if properties:checked['propertyPresets']=properties;checked['warnings'].append('Original property presets change scientific objectives and filters. Their preparation is not modality or biological validation.')
        if p.get('core'):
            from campaign_profile import core_catalog
            checked['corePresets']=[entry for entry in core_catalog(UPSTREAM) if entry['name']==p['core']]
        if modality=='homo_oligomer':checked['warnings'].append('Two identical binder-chain copies follow the original symmetric tying preset. Length bounds are per chain; memory estimates include both copies and the target.')
        if modality=='scFv':checked['warnings'].append('Original heavy and light variable domains are separate chains; no connecting linker is designed. Full target/scaffold memory feasibility must pass the selected profile before computation.')
        from campaign_inputs import extend
        if modality in ('induced_fit','fold_switch') and p.get('additionalTargets'):raise ValueError('The experimental conformational adapter currently supports one observed target and its unbound binder state.')
        checked=extend(self,p,checked)
        if modality in ('induced_fit','fold_switch'):checked['warnings'].append('Experimental conformational design includes a separate unbound binder prediction. Only the explicitly bounded CPU profile is enabled; full conformational generation validation remains pending.')
        if properties:
            from campaign_profile import property_conflicts
            property_conflicts(self.s,checked['config'],UPSTREAM,checked.get('scaffold'))
        return checked
    def bindcraft_prepare(self,p):
        checked=self.bindcraft_validate(p);checked['upstream']=verify_source()
        record,path=self.lab.record(p['structureId']);job=self.s.job_new({'projectId':p['projectId'],'name':checked['name'],'preparation':checked,'outputs':[]},'bindcraft2','preparing')
        folder=self.s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True)
        try:
            from campaign_inputs import snapshots
            for target in snapshots(checked):
                target_record,target_path=self.lab.record(target['source']['structureId']);raw=target_path.read_bytes()
                if checksum(raw)!=target['source']['sha256']:raise ValueError('Source changed during preparation.')
                (folder/target['file']).write_bytes(raw)
            if checked.get('scaffold'):
                scaffold=checked['scaffold'];raw=(UPSTREAM/scaffold['source']).read_bytes()
                if checksum(raw)!=scaffold['sha256']:raise ValueError('Scaffold changed during preparation.')
                (folder/scaffold['file']).write_bytes(raw)
            (folder/'settings.json').write_text(json.dumps(checked['config'],indent=2))
            (folder/'provenance.json').write_text(json.dumps(checked,indent=2))
            self.s.job_update(job['id'],'prepared',{'settingsFile':'settings.json','provenanceFile':'provenance.json'})
        except Exception as e:
            self.s.job_update(job['id'],'failed',{'error':str(e)});raise
        return self.s.job(job['id'])
    def bindcraft_campaigns(self,p):
        self.s.project(p['projectId'])
        return [self.s.job_read({'id':r['id']}) for r in self.s.rows("SELECT id FROM jobs WHERE project_id=? AND engine='bindcraft2' ORDER BY created DESC",(p['projectId'],))]
    def campaign(self,p):
        job=self.s.job(p['id'])
        if job['engine']!='bindcraft2' or job['project_id']!=p['projectId']:raise ValueError('Choose a design campaign in this project.')
        return job
    def bindcraft_repeat(self,p):
        from campaign_repeat import prepare
        return prepare(self,p)
    def bindcraft_results(self,p):
        from campaign_review import results
        return results(self,p)
    def bindcraft_review(self,p):
        from campaign_review import review
        return review(self,p)
    def bindcraft_resume(self,p):
        from campaign_recovery import prepare
        from bindcraft_cpu import start
        recovery=prepare(self,p)
        return start(self,{**p,'profile':recovery['job']['data']['profile']},recovery=recovery)
    def bindcraft_start(self,p):
        self.campaign(p)
        import bindcraft_cpu
        return bindcraft_cpu.start(self,p)
    def bindcraft_import(self,p):
        job=self.campaign(p);root=pathlib.Path(p['directory']).expanduser().resolve()
        if not root.is_dir():raise ValueError('Choose the upstream campaign result directory.')
        def read(path):
            if not path.resolve().is_relative_to(root) or path.is_symlink():raise ValueError('Result paths must stay within the selected campaign directory.')
            if path.stat().st_size>100*1024**2:raise ValueError('Result file exceeds 100 MB.')
            return path.read_bytes()
        # Only ranked outputs are candidates; never present failed trajectories as accepted.
        ranked=root/'3_Ranked'
        if not ranked.is_dir():raise ValueError('Expected upstream 3_Ranked result folder. Legacy and trajectory imports are not yet supported.')
        files=sorted(f for f in ranked.iterdir() if f.suffix.lower() in ('.cif','.mmcif','.pdb'))
        if not files or len(files)>200:raise ValueError('Import requires 1–200 ranked coordinate files.')
        table=ranked/'!_Ranked.csv';meta=root/'campaign_metadata.json'
        if not table.is_file() or not meta.is_file():raise ValueError('Ranked CSV and campaign_metadata.json are required for provenance.')
        table_bytes,meta_bytes=read(table),read(meta)
        if len(table_bytes)+len(meta_bytes)>5*1024**2:raise ValueError('Campaign metadata exceeds 5 MB.')
        if sum(f.stat().st_size for f in files)>250*1024**2:raise ValueError('Coordinate import exceeds 250 MB total.')
        metadata=json.loads(meta_bytes)
        if not isinstance(metadata,dict) or not isinstance(metadata.get('settings'),dict):raise ValueError('Invalid upstream campaign metadata.')
        from bindcraft_provenance import native_receipt,prediction_context,enrich_existing
        native=native_receipt(self.s,job,root,metadata)
        provenance_match='native_receipts_verified' if native else 'external_unverified'
        rows=list(csv.DictReader(io.StringIO(table_bytes.decode('utf-8-sig'))))
        if not rows or len(rows)>10000 or any(not row.get('design') for row in rows):raise ValueError('Ranked table requires nonempty design identities.')
        # Snapshot everything before writes; retain raw metric units/columns without guessing semantics.
        prepared=[]
        for file in files:
            raw=read(file);fmt='pdb' if file.suffix.lower()=='.pdb' else 'mmcif';st=mi.parse_structure(raw.decode(),fmt)
            matches=[row for row in rows if file.stem==row['design'] or file.stem.startswith(row['design']+'_')]
            if len(matches)!=1:raise ValueError('Cannot unambiguously associate ranked structure with a CSV design: '+file.name)
            prepared.append((file,raw,fmt,matches[0],len(st['atoms'])))
        target_states={}
        if native:
            from campaign_inputs import snapshots
            for file,raw,fmt,row,count in prepared:target_states[file.name]=prediction_context(job['data']['preparation'],file.name,row,raw,mi.parse_structure(raw.decode(),fmt),fmt)
            expected={state['name'] for state in snapshots(job['data']['preparation'])}
            for row in rows:
                actual={target_states[file.name]['name'] for file,raw,fmt,matched,count in prepared if matched['design']==row['design'] and target_states[file.name]['kind']=='target_complex'}
                if actual!=expected:raise ValueError('Native ranked candidate is missing a prepared target-state coordinate output.')
                prep=job['data']['preparation']
                if prep['modality'] in ('induced_fit','fold_switch') and prep['config'].get('save_binder_monomers',True) and not any(matched['design']==row['design'] and target_states[file.name]['kind']=='binder_alone' for file,raw,fmt,matched,count in prepared):raise ValueError('Native conformational candidate is missing its required unbound binder coordinate output.')
        evidence={'metadata':metadata,'rankedRows':rows,'metadataSha256':checksum(meta_bytes),'rankedCsvSha256':checksum(table_bytes),'sourceRevision':metadata.get('revision'),'provenanceMatch':'external_unverified','note':'Externally generated predictions. Source provenance is retained; correspondence to prepared inputs is not asserted.'}
        if native:evidence.update(provenanceMatch=provenance_match,nativeRun=native,note=native['scope'],sourceRevision=PIN)
        folder=self.s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True)
        batch=checksum(meta_bytes+b'\0'+table_bytes+b'\0'+b''.join(raw for _,raw,_,_,_ in prepared));evidence['batchSha256']=batch
        existing=job['data'].get('imports',[])
        if any(x['batchSha256']==batch for x in existing):
            prior=next(x for x in existing if x['batchSha256']==batch);enrich_existing(self.s,job,prior['outputs'],native,folder/prior['evidenceFolder'])
            return {'state':'already_imported','records':prior['outputs'],'batchSha256':batch,'provenanceMatch':provenance_match}
        saved=[];created_assets=[]
        # Continuing a campaign can retain earlier accepted coordinate files.
        # Reuse their immutable library identities across new ranking batches.
        known={}
        for item in self.s.rows("SELECT id,data FROM records WHERE project_id=? AND kind='structure'",(job['project_id'],)):
            info=json.loads(item['data']);stamp=info.get('metadata',{})
            if stamp.get('campaignId')==job['id']:known[(stamp.get('sourceFilename'),info.get('sha256'))]=(item['id'],info['asset'])
        try:
            self.s.db.execute('BEGIN IMMEDIATE')
            current=self.s.job(job['id']);existing=current['data'].get('imports',[])
            if any(x['batchSha256']==batch for x in existing):
                self.s.db.rollback();prior=next(x for x in existing if x['batchSha256']==batch);enrich_existing(self.s,job,prior['outputs'],native,folder/prior['evidenceFolder']);return {'state':'already_imported','records':prior['outputs'],'batchSha256':batch,'provenanceMatch':provenance_match}
            job=current
            for file,raw,fmt,row,count in prepared:
                prior=known.get((file.name,checksum(raw)))
                if prior:
                    if checksum((self.s.root/'assets'/prior[1]).read_bytes())!=checksum(raw):raise ValueError('An earlier imported campaign coordinate asset changed.')
                    saved.append(prior[0]);continue
                id=str(uuid.uuid4());asset=id+('.pdb' if fmt=='pdb' else '.cif');dest=self.s.root/'assets'/asset;dest.write_bytes(raw);created_assets.append(dest)
                info={'asset':asset,'format':fmt,'sha256':checksum(raw),'source':'Imported external BindCraft2 ranked prediction','imported':mi.now(),'confidenceKind':None,'metadata':{'campaignId':job['id'],'sourceFilename':file.name,'rawMetrics':row,'upstreamRevision':metadata.get('revision'),'batchSha256':batch,'provenanceMatch':'external_unverified','atoms':count}}
                if native:
                    context=target_states[file.name];info['source']='Local BindCraft2 '+native['execution']+' '+('unbound binder prediction' if context['kind']=='binder_alone' else 'ranked prediction');info['confidenceKind']='BindCraft2 AlphaFold2 pLDDT';info['metadata'].update(nativeRun=native,**context['metadata'],provenanceMatch=provenance_match,upstreamRevision=PIN,reportedCampaignRevision=metadata.get('revision'))
                    roles=context['roles']
                    if roles:
                        info['metadata']['chainRoles']=roles;self.s.db.execute('INSERT INTO intelligence_assignments VALUES(?,?,?,?)',(id,job['project_id'],json.dumps(roles),mi.now()))
                name=file.stem[:200];self.s.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(id,job['project_id'],'structure',name,json.dumps(info),mi.now()));saved.append(id)
            raw_folder=folder/('import-'+batch);raw_folder.mkdir(exist_ok=True);(raw_folder/'campaign_metadata.json').write_bytes(meta_bytes);(raw_folder/'!_Ranked.csv').write_bytes(table_bytes);(raw_folder/'manifest.json').write_text(json.dumps(evidence,indent=2))
            if native:(raw_folder/'native-verification.json').write_text(json.dumps(native,indent=2))
            data={**job['data'],'outputs':list(dict.fromkeys(job['data'].get('outputs',[])+saved)),'imports':existing+[{'batchSha256':batch,'evidenceFolder':raw_folder.name,'outputs':saved, 'imported':mi.now()}]}
            self.s.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('imported',json.dumps(data),mi.now(),job['id']));self.s.db.commit()
        except Exception:
            self.s.db.rollback()
            for path in created_assets:path.unlink(missing_ok=True)
            raise
        return {'state':'imported','records':saved,'batchSha256':batch,'provenanceMatch':provenance_match}
