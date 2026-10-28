"""Read-only coordinate assessments and versioned research evidence.

No predictor or simulation is silently launched by a research assessment.
"""
import collections
import datetime
import hashlib
import json
import math
import pathlib
import re
import uuid

import intelligence as mi
import assay_statistics

ACTIONS = {'research_candidate', 'research_annotation', 'research_assay_save', 'research_assay_summary', 'research_assay_import', 'research_full_target', 'research_full_scene', 'research_contacts', 'research_export', 'research_variants', 'research_screen_plan'}
KD = dict(zip('ACDEFGHIKLMNPQRSTVWY', [1.8,2.5,-3.5,-3.5,2.8,-0.4,-3.2,4.5,-3.9,3.8,1.9,-3.5,-1.6,-3.5,-4.5,-0.8,-0.7,4.2,-0.9,-1.3]))


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def liabilities(sequence):
    """Sequence descriptors and motif flags, not trained property predictions."""
    flags = []
    for index, aa in enumerate(sequence):
        if aa in 'MW':
            flags.append({'position': index+1, 'residue': aa, 'type': 'oxidation-sensitive residue', 'evidence': 'sequence heuristic; no rate predicted'})
        if sequence[index:index+2] in ('NG', 'NS', 'NT', 'DG'):
            flags.append({'position': index+1, 'residue': sequence[index:index+2], 'type': 'chemical-liability motif', 'evidence': 'sequence heuristic; depends on conformation and conditions'})
    return {'length': len(sequence), 'composition': dict(collections.Counter(sequence)),
            'gravy': sum(KD[a] for a in sequence)/len(sequence) if sequence and not set(sequence)-KD.keys() else None,
            'gravyMethod': 'Kyte–Doolittle arithmetic mean; not a solubility predictor',
            'formalSideChainCharge': sum(sequence.count(a) for a in 'KR')-sum(sequence.count(a) for a in 'DE'),
            'chargeAssumptions': 'Lys/Arg +1, Asp/Glu -1; excludes termini and histidine; no pH-dependent calculation',
            'flags': flags, 'unavailable': ['measured solubility', 'aggregation probability', 'proteolytic half-life', 'permeability', 'immunogenicity', 'affinity']}


class Research:
    def __init__(self, service):
        self.s = service
        self.lab = mi.Lab(service)
        service.db.execute('CREATE TABLE IF NOT EXISTS research_evidence(id TEXT PRIMARY KEY,structure_id TEXT,project_id TEXT,kind TEXT,data TEXT,created TEXT)')

    def source(self, p):
        record, path = self.lab.record(p['structureId'])
        if p.get('projectId') and record['project_id'] != p['projectId']:
            raise ValueError('Choose a structure in the current project.')
        return record, path

    def evidence(self, id):
        return [{**dict(row), 'data': json.loads(row['data'])} for row in self.s.db.execute('SELECT * FROM research_evidence WHERE structure_id=? ORDER BY created DESC', (id,))]

    def save(self, record, kind, value):
        encoded = canonical({**value, 'sourceSha256': record['data']['sha256']})
        id = str(uuid.uuid4())
        self.s.db.execute('INSERT INTO research_evidence VALUES(?,?,?,?,?,?)', (id, record['id'], record['project_id'], kind, encoded, utc()))
        self.s.db.commit()
        return {'id': id, 'kind': kind, 'data': json.loads(encoded)}

    def research_candidate(self, p):
        record, path = self.source(p)
        st = mi.parse_structure(path.read_text(), record['data']['format'])
        metadata = record['data'].get('metadata', {})
        assignments = self.lab.assigned(record['id']) or metadata.get('chainRoles', {})
        chains = [{**c, 'role': assignments.get(c['id'], {}).get('role', 'unassigned'), 'descriptors': liabilities(c['sequence'])} for c in st['chains']]
        tasks = self.s.rows('SELECT id,kind,state,data FROM intelligence_tasks WHERE project_id=?', (record['project_id'],))
        related = []
        for task in tasks:
            data = json.loads(task.pop('data') or '{}')
            if data.get('structureId') == record['id'] or any(spec.get('candidate',{}).get('data',{}).get('sourceStructure')==record['id'] for spec in data.get('specs',[])):
                related.append(task)
        registered=self.lab.intelligence_candidates({'projectId':record['project_id']})
        source_ids={c['id'] for c in registered if c['data'].get('sourceStructure')==record['id']}
        candidate_sequences=[c for c in registered if c['id'] in source_ids or c['data'].get('controlFor') in source_ids or c['data'].get('parentCandidateId') in source_ids]
        evidence = self.evidence(record['id'])
        assay = [e for e in evidence if e['kind'] == 'assay']
        return {'schemaVersion': 1, 'record': record, 'sourceSha256': record['data']['sha256'], 'model': st['model'],
                'chains': chains, 'atomCount': len(st['atoms']), 'warnings': st['warnings'], 'metrics': metadata.get('rawMetrics', {}),
                'confidence': self.lab.confidence(record, st), 'tasks': related, 'candidateSequences':candidate_sequences, 'evidence': evidence,
                'checks': [
                    {'name': 'Original coordinate integrity', 'state': 'verified', 'detail': 'SHA-256 matches the saved source.'},
                    {'name': 'Chain identity', 'state': 'recorded' if all(c['role'] != 'unassigned' for c in chains) else 'needs assignment', 'detail': 'Roles are explicit metadata, never guessed from chain length.'},
                    {'name': 'Preparation inspection', 'state': 'measured', 'detail': str(sum(len(c['missingAtoms']) for c in chains))+' residues with missing heavy atoms; numbering gaps do not establish missing biological sequence.'},
                    {'name': 'Full assembly assessment', 'state': 'recorded' if any(e['kind']=='full_target' for e in evidence) else 'not run', 'detail': 'Geometric transfer requires an explicit full-target chain map.'},
                    {'name': 'Experimental measurements', 'state': 'supplied' if assay else 'not supplied', 'detail': 'Uploaded measurements are user-supplied evidence, not independently certified results.'}],
                'claim': 'Computational structure; binding, inhibition and safety are not established by these assessments.'}

    def research_annotation(self, p):
        record, _ = self.source(p)
        text = str(p.get('text', '')).strip()
        if not text or len(text) > 20000:
            raise ValueError('Enter a research note of 1–20,000 characters.')
        return self.save(record, 'note', {'text': text, 'author': str(p.get('author', 'Local researcher'))[:160]})

    def research_contacts(self,p):
        record,path=self.source(p);st=mi.parse_structure(path.read_text(),record['data']['format'])
        binders=p.get('binderChains',[]);targets=p.get('targetChains',[]);known={c['id'] for c in st['chains']}
        if not isinstance(binders,list) or not isinstance(targets,list) or not binders or not targets or set(binders)&set(targets) or (set(binders)|set(targets))-known:raise ValueError('Specify separate observed peptide and target chains.')
        for previous in self.evidence(record['id']):
            d=previous['data']
            if previous['kind']=='pose_contacts' and d.get('binderChains')==sorted(set(binders)) and d.get('targetChains')==sorted(set(targets)) and d.get('sourceSha256')==record['data']['sha256']:return previous
        target=[a for a in st['atoms'] if a['chain'] in targets and a['element'] not in ('H','D')];grid=mi.Grid(target,4);pairs=[];marked={}
        def identity(a):return {'chain':a['chain'],'residue':a['num'],'insertion':a['ins'],'atom':a['name']}
        for atom in st['atoms']:
            if atom['chain'] not in binders or atom['element'] in ('H','D'):continue
            for other in grid.near(atom['xyz'],4):
                distance=math.dist(atom['xyz'],other['xyz'])
                if distance<=4:
                    pairs.append({'peptide':identity(atom),'target':identity(other),'distanceAngstrom':distance})
                    for a in (atom,other):marked[canonical(identity(a))]={**identity(a),'xyz':a['xyz']}
        return self.save(record,'pose_contacts',{'binderChains':sorted(set(binders)),'targetChains':sorted(set(targets)),'cutoffAngstrom':4,'pairs':len(pairs),'atomPairs':pairs,'atoms':list(marked.values()),'method':'Observed heavy-atom centre distance ≤4.0 Å in the saved pose. No hydrogen-bond, energy or binding inference. Presentation translations do not change this source assessment.'})

    def research_assay_save(self, p):
        record,value=self.assay_value(p)
        return self.save(record,'assay',value)

    def research_assay_import(self,p):
        import assay_csv
        if set(p)-{'projectId','structureId','name','concentrationUnit','responseUnit','conditions','endpoint','path','csvText'}:raise ValueError('Unsupported CSV import field.')
        rows,source=assay_csv.read(p)
        payload={key:value for key,value in p.items() if key not in ('path','csvText')}
        record,value=self.assay_value({**payload,'rows':rows,'replicateDesign':'explicit_biological_technical'})
        value['sourceCSV']=source
        return self.save(record,'assay',value)

    def assay_value(self, p):
        if set(p)-{'projectId','structureId','name','concentrationUnit','responseUnit','conditions','rows','replicateDesign','endpoint'}:
            raise ValueError('Unsupported assay field; declare the endpoint, units and replicate design explicitly.')
        record, _ = self.source(p)
        name = str(p.get('name', '')).strip()
        unit = str(p.get('concentrationUnit', ''))
        rows = p.get('rows')
        if not name or len(name)>200 or unit not in ('M','mM','µM','nM','pM') or not isinstance(rows, list) or not 1<=len(rows)<=10000:
            raise ValueError('Supply an assay name, concentration unit and 1–10,000 measurement rows.')
        design = p.get('replicateDesign')
        endpoint = None
        if design is not None and design != 'explicit_biological_technical':
            raise ValueError('Unsupported replicate design.')
        if design:
            endpoint = assay_statistics.identifier(p.get('endpoint'), 'measured endpoint')
            response_unit = assay_statistics.identifier(p.get('responseUnit'), 'response unit')
            clean = assay_statistics.explicit_rows(rows, endpoint, response_unit)
        else:
            clean = []
        for row in ([] if design else rows):
            if not isinstance(row, dict):
                raise ValueError('Each measurement must be an object.')
            concentration, response = row.get('concentration'), row.get('response')
            if any(type(v) not in (float,int) or not math.isfinite(v) for v in (concentration,response)) or concentration<0:
                raise ValueError('Measurements must be finite numbers with nonnegative concentration.')
            clean.append({'concentration': concentration, 'response': response, 'replicate': str(row.get('replicate','1'))[:80]})
        response_unit=str(p.get('responseUnit','')).strip()
        if not response_unit or len(response_unit)>100:
            raise ValueError('Identify the response unit, including arbitrary units when appropriate.')
        return record, {'name': name, 'concentrationUnit': unit, 'responseUnit': response_unit,
                    'conditions': str(p.get('conditions',''))[:10000], 'rows': clean, **({'replicateDesign':design,'endpoint':endpoint} if design else {}), 'evidence': 'user-supplied measurements; unverified; no affinity fit inferred'}

    def research_assay_summary(self, p):
        if set(p)-{'projectId','structureId','assayId'}:
            raise ValueError('Choose one saved assay; the replicate method is fixed and recorded.')
        record, _ = self.source(p)
        evidence = self.evidence(record['id'])
        assay = next((item for item in evidence if item['kind']=='assay' and item['id']==p.get('assayId')), None)
        if assay is None:
            raise ValueError('Choose an assay saved on this exact structure in the current project.')
        if assay['data'].get('sourceSha256') != record['data']['sha256']:
            raise ValueError('The assay source identity differs from the current coordinate record.')
        assay_sha = hashlib.sha256(canonical(assay['data']).encode()).hexdigest()
        implementation_sha = hashlib.sha256(pathlib.Path(assay_statistics.__file__).read_bytes()).hexdigest()
        previous = next((item for item in evidence if item['kind']=='assay_summary' and item['data'].get('assayId')==assay['id'] and item['data'].get('assaySha256')==assay_sha and item['data'].get('algorithm')==assay_statistics.VERSION and item['data'].get('summarySourceSha256')==implementation_sha), None)
        if previous:
            return previous
        summary = assay_statistics.summarize(assay['data'])
        return self.save(record, 'assay_summary', {**summary, 'assayId':assay['id'], 'assayName':assay['data']['name'], 'assaySha256':assay_sha, 'summarySourceSha256':implementation_sha,
                                                'classification':'Descriptive analysis of supplied experimental readings; not independently certified observations'})

    def research_full_target(self, p):
        record, path = self.source(p)
        full, full_path = self.lab.record(p['fullStructureId'])
        if full['project_id'] != record['project_id'] or full['id'] == record['id']:
            raise ValueError('Choose a different full-target structure in this project.')
        a = mi.parse_structure(path.read_text(), record['data']['format'])
        b = mi.parse_structure(full_path.read_text(), full['data']['format'])
        mapping = p.get('chainMap', {}); binder = p.get('binderChains', [])
        if not isinstance(mapping,dict) or not mapping or not isinstance(binder,list) or not binder or len(set(mapping.values()))!=len(mapping) or set(mapping)&set(binder):
            raise ValueError('Specify distinct target chain correspondences and separate binder chains.')
        ca={c['id']:c for c in a['chains']};cb={c['id']:c for c in b['chains']}
        if set(mapping)-ca.keys() or set(mapping.values())-cb.keys() or set(binder)-ca.keys():
            raise ValueError('Chain correspondence references an absent chain.')
        moving=[];fixed=[];maps=[]
        def residues(st,chain):return [r for r in st['residues'] if r['chain']==chain and r['polymer']]
        def alpha(st,r):return next((st['atoms'][i]['xyz'] for i in r['atoms'] if st['atoms'][i]['name']=='CA'),None)
        for left,right in mapping.items():
            rs,rf=residues(a,left),residues(b,right)
            starts=[i for i in range(len(rf)-len(rs)+1) if ''.join(r['one'] for r in rf[i:i+len(rs)])==''.join(r['one'] for r in rs)]
            if len(starts)!=1 or not rs or 'X' in ca[left]['sequence']:
                raise ValueError('Full-target mapping requires a unique exact observed-sequence fragment for each explicitly paired chain.')
            start=starts[0]
            for r,q in zip(rs,rf[start:]):
                x,y=alpha(a,r),alpha(b,q)
                if x is not None and y is not None:moving.append(x);fixed.append(y);maps.append({'construct':r['id'],'full':q['id']})
        transform=mi.fit(moving,fixed)
        tolerance=p.get('alignmentToleranceAngstrom',2.0)
        if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or not .1<=tolerance<=20:
            raise ValueError('Alignment tolerance must be 0.1–20 Å. This is a user-selected geometric criterion, not a biological acceptance threshold.')
        registration='within_requested_tolerance' if transform['rmsd']<=tolerance else 'poor_fit'
        target_atoms=[v for v in b['atoms'] if v['element'] not in ('H','D')]
        grid=mi.Grid(target_atoms,4);close=[];count=0
        for atom in a['atoms']:
            if atom['chain'] not in binder or atom['element'] in ('H','D'):continue
            xyz=mi.apply_fit(atom['xyz'],transform)
            for other in grid.near(xyz,4):
                overlap=mi.RADII.get(atom['element'],0)+mi.RADII.get(other['element'],0)-math.dist(xyz,other['xyz'])
                if overlap>0.6:
                    count+=1
                    if len(close)<200:close.append({'binder':{'chain':atom['chain'],'residue':atom['num'],'atom':atom['name']},'target':{'chain':other['chain'],'residue':other['num'],'atom':other['name']},'overlapAngstrom':overlap})
        result={'registrationState':registration,'alignmentToleranceAngstrom':tolerance,'interpretation':'Geometric overlap is not interpretable as full-target compatibility when registration is poor. Even a good fit and zero overlap do not establish binding.','fullStructureId':full['id'],'fullSha256':full['data']['sha256'],'chainMap':mapping,'binderChains':binder,'transform':transform,
                'referenceScope':'User-selected coordinate reference; biological completeness and physiological assembly are unverified.','referenceChains':[{ 'id':c['id'],'observedResidues':c['proteinResidues']} for c in b['chains']],'residueMap':maps,'clashPairs':count,'firstClashes':close,'criterion':'Heavy-atom Bondi radius overlap >0.6 Å; geometric screening, not force-field relaxation.',
                'claim':'Rigid pose transfer hypothesis only. No new prediction or experimental binding evidence. Unobserved regions and modifications remain unassessed.'}
        return self.save(record,'full_target',result)

    def candidate_chain(self, p):
        record,path=self.source(p)
        st=mi.parse_structure(path.read_text(),record['data']['format'])
        chain=next((c for c in st['chains'] if c['id']==p.get('binderChain')),None)
        if not chain or not chain['sequence'] or set(chain['sequence'])-set(KD):
            raise ValueError('Choose one observed canonical peptide chain. Modified chemistry needs a separately qualified backend.')
        return record,st,chain

    def research_full_scene(self,p):
        """Save a separate rigid pose-transfer hypothesis, never replace either source."""
        import tempfile
        import pathlib
        record,path=self.source(p)
        assessment=self.research_full_target(p)
        result=assessment['data']
        if result['registrationState']=='poor_fit' and p.get('allowPoorFit') is not True:
            raise ValueError('The reference fit is poor. Review its RMSD and explicitly choose an illustrative pose-transfer scene; this is not full-target validation.')
        full,full_path=self.lab.record(p['fullStructureId'])
        original=mi.parse_structure(path.read_text(),record['data']['format'])
        reference=mi.parse_structure(full_path.read_text(),full['data']['format'])
        binders=set(p['binderChains']);full_chains={a['chain'] for a in reference['atoms']}
        if binders&full_chains:raise ValueError('The peptide chain identity collides with the reference. Save an explicitly renamed derived input first.')
        atoms=[dict(a) for a in reference['atoms']]+[{**a,'xyz':mi.apply_fit(a['xyz'],result['transform'])} for a in original['atoms'] if a['chain'] in binders]
        # Explicit analysis conformer selection: primary model, highest-occupancy
        # alternate, no waters; this is recorded rather than silently repaired.
        def token(v):
            if v is None or v=='':return '.'
            value=str(v)
            if any(c in value for c in '\n\r') or ('"' in value and "'" in value):raise ValueError('Unsupported CIF identifier in presentation input.')
            return ('"'+value+'"') if "'" in value else ("'"+value+"'") if any(c.isspace() for c in value) or value[0] in '#_$;[]' or '"' in value else value
        def loop(names,rows):return 'loop_\n'+'\n'.join(names)+'\n'+'\n'.join(' '.join(token(v) for v in row) for row in rows)+'\n#\n'
        chains=list(dict.fromkeys(a['chain'] for a in atoms));entities={c:str(i+1) for i,c in enumerate(chains)};numbers={};counts=collections.Counter()
        for atom in atoms:
            key=(atom['chain'],atom['num'],atom['ins'])
            if key not in numbers:counts[atom['chain']]+=1;numbers[key]=counts[atom['chain']]
        text='data_fold_pose_transfer\n#\n'+loop(['_entity.id','_entity.type'],[(entities[c],'polymer') for c in chains])
        text+=loop(['_entity_poly.entity_id','_entity_poly.type'],[(entities[c],'polypeptide(L)') for c in chains])
        if any(a['resname'] not in mi.CODES for a in atoms):raise ValueError('This pose-transfer serializer supports observed canonical protein residues only; use the original viewer for unsupported components.')
        text+=loop(['_chem_comp.id','_chem_comp.type','_chem_comp.mon_nstd_flag','_chem_comp.name'],[(name,'L-peptide linking','n',name) for name in sorted({a['resname'] for a in atoms})])
        names=['group_PDB','id','type_symbol','label_atom_id','label_alt_id','label_comp_id','label_asym_id','label_entity_id','label_seq_id','pdbx_PDB_ins_code','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv','auth_seq_id','auth_comp_id','auth_asym_id','auth_atom_id','pdbx_PDB_model_num']
        rows=[[a['group'],i+1,a['element'],a['name'],a['alt'],a['resname'],a['chain'],entities[a['chain']],numbers[(a['chain'],a['num'],a['ins'])],a['ins'],*(format(v,'.10f') for v in a['xyz']),a['occupancy'],a['bfactor'],a['num'],a['resname'],a['chain'],a['name'],1] for i,a in enumerate(atoms)]
        text+=loop(['_atom_site.'+name for name in names],rows)
        disclosure='POSE TRANSFER · '+('POOR FIT · ' if result['registrationState']=='poor_fit' else '')+'UNVERIFIED PLACEMENT'
        metadata={'parentStructureId':record['id'],'sourceStructure':record['id'],'sourceSha256':record['data']['sha256'],'referenceStructureId':full['id'],'referenceSha256':full['data']['sha256'],'poseAssessmentId':assessment['id'],'poseTransfer':result,'presentationDisclosure':disclosure,'conformerSelection':'First observed model; highest summed-occupancy alternate per residue; waters omitted. No missing atoms or biological regions invented.','chainRoles':{c:{'role':'candidate' if c in binders else 'target'} for c in chains},'scientificClaim':'Derived rigid pose-transfer hypothesis; not a new structure prediction or simulated binding result.'}
        with tempfile.TemporaryDirectory(prefix='pose-transfer-',dir=self.s.root/'cache') as directory:
            output=pathlib.Path(directory)/'pose-transfer.cif';output.write_text(text)
            imported=self.s.import_structure({'projectId':record['project_id'],'path':str(output),'name':str(p.get('name','Full reference + peptide · pose hypothesis'))[:160],'source':'Derived illustrative pose transfer','metadata':metadata})
        return {'record':imported,'assessment':assessment,'disclosure':disclosure}

    def registered_chain(self,record,chain):
        existing=self.lab.intelligence_candidates({'projectId':record['project_id']})
        same=next((c for c in existing if c['data'].get('sourceStructure')==record['id'] and c['data'].get('sourceChain')==chain['id'] and c['data']['sequence']==chain['sequence']),None)
        return same or self.lab.intelligence_candidate_save({'projectId':record['project_id'],'name':record['name']+' · chain '+chain['id'],'sequence':chain['sequence'],'role':'candidate','sourceStructure':record['id'],'sourceSha256':record['data']['sha256'],'sourceChain':chain['id'],'evidence':'Observed sequence from predicted coordinates; binding is unverified'})

    def research_variants(self,p):
        record,st,chain=self.candidate_chain(p)
        substitutions=p.get('substitutions',[])
        if not isinstance(substitutions,list) or not 1<=len(substitutions)<=100:
            raise ValueError('Supply 1–100 explicit single-residue substitutions.')
        saved=[];seen=set()
        residues=[r for r in st['residues'] if r['chain']==chain['id'] and r['polymer']]
        for sub in substitutions:
            index=sub.get('position');aa=sub.get('aminoAcid')
            if type(index)!=int or not 1<=index<=len(chain['sequence']) or aa not in KD or chain['sequence'][index-1]==aa or (index,aa) in seen:
                raise ValueError('Each variant needs a unique observed-sequence position and a different canonical amino acid.')
            seen.add((index,aa))
        parent=self.registered_chain(record,chain)
        for sub in substitutions:
            index,aa=sub['position'],sub['aminoAcid'];seq=chain['sequence'][:index-1]+aa+chain['sequence'][index:]
            saved.append(self.lab.intelligence_candidate_save({'projectId':record['project_id'],'name':parent['name']+' · '+chain['sequence'][index-1]+str(index)+aa,'sequence':seq,'role':'candidate','parentCandidateId':parent['id'],'sourceStructure':record['id'],'sourceSha256':record['data']['sha256'],'sourceChain':chain['id'],'mutation':{'observedPosition':index,'authorResidue':residues[index-1]['id'],'from':chain['sequence'][index-1],'to':aa},'evidence':'Sequence proposal only; no new coordinates or binding prediction'}))
        return {'parent':parent,'variants':saved,'claim':'Registered single-mutant sequence proposals; no affinity improvement inferred.'}

    def research_screen_plan(self,p):
        record,st,chain=self.candidate_chain(p)
        targets=p.get('targetChains',[])
        if not isinstance(targets,list) or not targets or len(set(targets))!=len(targets) or chain['id'] in targets or set(targets)-{c['id'] for c in st['chains']}:
            raise ValueError('Choose distinct target chains separate from the peptide.')
        seeds=p.get('seeds',[42])
        if not isinstance(seeds,list) or not 1<=len(seeds)<=50 or any(type(v)!=int or not 0<=v<=2147483647 for v in seeds) or len(set(seeds))!=len(seeds):raise ValueError('Use 1–50 distinct integer seeds.')
        for key,default,low,high in [('samples',1,1,5),('steps',200,10,500),('recycles',3,1,10)]:
            value=p.get(key,default)
            if type(value)!=int or not low<=value<=high:raise ValueError('Invalid screening '+key)
        if len(targets)>25 or sum(c['proteinResidues'] for c in st['chains'] if c['id'] in targets)+len(chain['sequence'])>1500:raise ValueError('Screening inputs exceed the existing local engine limits.')
        seed=p.get('controlSeed',42)
        if p.get('includeScramble') and (type(seed)!=int or not 0<=seed<=2147483647):raise ValueError('Use an integer control seed.')
        if p.get('includeScramble') and len(set(chain['sequence']))<2:raise ValueError('This sequence has no distinct composition-matched scramble.')
        parent=self.registered_chain(record,chain);ids=[parent['id']]
        if p.get('includeScramble'):
            seed=p.get('controlSeed',42)
            if type(seed)!=int or not 0<=seed<=2147483647:raise ValueError('Use an integer control seed.')
            existing=self.lab.intelligence_candidates({'projectId':record['project_id']})
            control=next((c for c in existing if c['data'].get('controlFor')==parent['id'] and c['data'].get('seed')==seed),None)
            control=control or self.lab.intelligence_scramble({'projectId':record['project_id'],'candidateId':parent['id'],'seed':seed})
            ids.append(control['id'])
        fasta='\n'.join('>'+c['id']+'\n'+c['sequence'] for c in st['chains'] if c['id'] in targets)
        plan=self.lab.intelligence_screen({'projectId':record['project_id'],'candidateIds':ids,'targetFasta':fasta,'seeds':p.get('seeds',[42]),'msa':'single','samples':p.get('samples',1),'steps':p.get('steps',200),'recycles':p.get('recycles',3),'start':False})
        return {**plan,'sourceStructure':record['id'],'sourceSha256':record['data']['sha256'],'candidateIds':ids,'startPayload':{'projectId':record['project_id'],'candidateIds':ids,'targetFasta':fasta,'seeds':p.get('seeds',[42]),'msa':'single','samples':p.get('samples',1),'steps':p.get('steps',200),'recycles':p.get('recycles',3),'start':True},'controlMeaning':'Scrambled sequences are proposed controls, not experimentally established nonbinders.'}

    def research_export(self, p):
        data=self.research_candidate(p)
        data['exported']=utc()
        data['software']='Fold Studio Research Suite 1'
        encoded=json.dumps(data,indent=2,allow_nan=False)
        return {'name':'fold-candidate-study.json','text':encoded,'sha256':hashlib.sha256(encoded.encode()).hexdigest()}


def dispatch(service, action, payload):
    return getattr(Research(service), action)(payload)
