"""Expanded, grounded training bundle with fresh local-only final answers."""
import gzip,json,hashlib
from pathlib import Path
import h5py,numpy as np
from qwen_cell_data import sha,write
from qwen_cell_expanded_data import column,stratified_rows,read_profiles,encode_complete
from qwen_cell_biology import rank_sentences
import cell_training_features as F

CONFIG={'cells':10000,'inhibitionGroups':[512,64,64],'drugGroups':[192,24,24],'conditionsPerDrug':6,'heldoutContexts':2,'seed':F.SEED}


def prepare(root,seed_data,history,checkpoint,out,event=lambda *a,**kw:None,config=CONFIG):
    from transformers import AutoTokenizer
    from virtual_cell_drugs import Atlas
    import k562_prototype as K
    root,seed_data,history,checkpoint,out=map(Path,[root,seed_data,history,checkpoint,out])
    if out.exists():raise ValueError('Existing training evidence is preserved. Choose a new experiment.')
    prior=json.loads(history.read_text());old_pair=json.loads((root/'gpu_tasks/ab4d920cc9714f9e8933b4aa150eef49/outputs/SPLIT_MANIFEST.json').read_text())['split']
    with np.load(seed_data,allow_pickle=False) as z:old={k:z[k] for k in z.files}
    data={k:v for k,v in old.items() if k.startswith('expert_')};genes=data['expert_genes'].astype(str);gi={g:i for i,g in enumerate(genes)};g=len(genes)
    data['genes']=genes;data['legacyFeatureWidth']=np.array(old['trainX'].shape[1]);expert={k[7:]:v for k,v in data.items() if k.startswith('expert_')}
    with gzip.open(root/'virtualcell/data/annotations/index.json.gz','rt') as f:annotations=json.load(f)
    functions=root/'virtualcell/training/sources/uniprot_human_functions.tsv.gz'
    if functions.is_file():
        import csv
        with gzip.open(functions,'rt') as f:
            for row in csv.DictReader(f,delimiter='\t'):
                name=row.get('Gene Names (primary)','')
                if name in annotations['genes']:
                    for key,column_name in [('goFunction','Gene Ontology (molecular function)'),('goProcess','Gene Ontology (biological process)')]:
                        annotations['genes'][name][key]=sorted(set(annotations['genes'][name].get(key,[]))|{x.strip() for x in row.get(column_name,'').split(';') if x.strip()})
    norman=root/'oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad';replogle=root/'virtualcell/data/replogle2022/ReplogleWeissman2022_K562_essential.h5ad'
    refs=root/'virtualcell/reference/k562';ref_manifest=json.loads((refs/'manifest.json').read_text())
    if sha(norman)!=K.SOURCE_SHA or sha(replogle)!=ref_manifest['inputs']['replogle2022']['sha256']:raise ValueError('Protected source integrity failed.')
    with np.load(refs/'pack.npz',allow_pickle=False) as z:kd={k:z[k] for k in ['genes','kdPerturbations','kdEffects','kdMeasured']}
    seen_genes=sum(prior['groups']['inhibition'].values(),[]);eligible=[str(g) for g in kd['kdPerturbations'] if str(g) in gi]
    split_kd=F.fresh_split(eligible,seen_genes,config['inhibitionGroups'],'inhibition')
    nm=K.metadata(norman)
    with h5py.File(replogle,'r') as f:rm={'labels':column(f['obs'],'perturbation'),'ids':column(f['obs'],str(f['obs'].attrs['_index']))}
    controls=np.flatnonzero(np.isin(rm['labels'],['control','non-targeting']));cr=np.sort(np.random.default_rng(F.SEED).choice(controls,min(256,len(controls)),replace=False));cv,rmeasured=read_profiles(replogle,cr,genes,rm);rb=cv.mean(0)
    allowed_norman=set(old_pair['train'])|set(expert['singleGenes'])|{'control'};half=config['cells']//2
    nr=stratified_rows(nm['labels'],allowed_norman,half,F.SEED);rr=stratified_rows(rm['labels'],set(split_kd['train'])|{'control','non-targeting'},config['cells']-half,F.SEED+1)
    nv,nmeasured=read_profiles(norman,nr,genes,nm);rv,rmeasured=read_profiles(replogle,rr,genes,rm)
    cell_ids=['norman:'+str(nm['cellIds'][i]) for i in nr]+['replogle:'+str(rm['ids'][i]) for i in rr]
    if len(set(cell_ids))!=config['cells']:raise ValueError('Cell identities are not distinct.')
    profiles=np.concatenate([nv,rv]);baselines=np.concatenate([np.broadcast_to(expert['baseline'],nv.shape),np.broadcast_to(rb,rv.shape)])
    measured=np.concatenate([np.broadcast_to(nmeasured,nv.shape),np.broadcast_to(rmeasured,rv.shape)]);hide=(np.random.default_rng(F.SEED).random(profiles.shape)<.2)&measured
    visible=measured&~hide;masked=np.where(visible,profiles,0);effects=np.where(measured,profiles-baselines,0).astype(np.float32)
    if np.any(hide.sum(1)==0):raise ValueError('Invalid masked training profiles.')
    text={};bio={};local_answers={};identities={};units={'pair':'Norman mean log1p counts per 10000 response','activation':'Norman mean log1p counts per 10000 response',
          'inhibition':'Replogle mean log1p counts per 10000 response','drug':'Tahoe DESeq2 log2 fold change','state':'source-control centered single-cell log1p counts per 10000'}
    def features(task,baseline,mask,**kw):return np.pad(F.intervention_features(task,baseline,mask,genes,annotations['genes'],**kw),(old['trainX'].shape[1],0))
    def add(task,part,x,y,mask,texts,basal,groups,contexts,pairs=None,weights=None):
        prefix=task+'_'+part;data[prefix+'_X']=np.asarray(x,np.float32);data[prefix+'_Mask']=np.asarray(mask,bool);text[prefix]=texts;bio[prefix]=basal
        if task=='state':starting,starting_mask=masked,visible
        elif task in ['pair','activation']:starting,starting_mask=np.broadcast_to(expert['baseline'],(len(x),g)),np.broadcast_to(nmeasured,(len(x),g))
        elif task=='inhibition':starting,starting_mask=np.broadcast_to(rb,(len(x),g)),np.broadcast_to(rmeasured,(len(x),g))
        else:starting,starting_mask=np.array([context_profiles[c][0] for c in contexts]),np.array([context_profiles[c][1] for c in contexts])
        data[prefix+'_Baseline']=np.asarray(starting,np.float32);data[prefix+'_BaselineMask']=np.asarray(starting_mask,bool)
        data[prefix+'_Group']=np.asarray(groups);data[prefix+'_Context']=np.asarray(contexts);identities[prefix]={'groups':list(groups),'contexts':list(contexts)}
        if 'test' in part:local_answers[prefix+'_Y']=np.asarray(y,np.float32)
        else:data[prefix+'_Y']=np.asarray(y,np.float32)
        if pairs is not None:data[prefix+'_Pairs']=pairs
        if weights is not None and 'test' not in part:data[prefix+'_Reliability']=weights
    state_bio=rank_sentences(masked,genes,top=128);event('masked_cells_prepared',distinctCells=len(cell_ids))
    sx=np.array([features('state',row,mask) for row,mask in zip(masked,visible)])
    add('state','train',sx,effects,hide,['Human K562 '+('CRISPRa' if i<half else 'CRISPRi')+' measured training cell. Visible genes '+s+'. Reconstruct hidden RNA; response unit log1p counts per 10000.' for i,s in enumerate(state_bio)],state_bio,cell_ids,['K562']*len(sx))
    def baseline_sentence(base,mask):return rank_sentences(np.where(mask,base,0)[None,:],genes,top=128)[0]
    nbase=baseline_sentence(expert['baseline'],nmeasured);rbase=baseline_sentence(rb,rmeasured)
    for part in ['train','validation']:
        names=old[part+'Conditions'].astype(str);x=[];ts=[]
        for i,name in enumerate(names):
            targets=name.split('+');row=features('pair',expert['baseline'],nmeasured,targets=targets);row[:old['trainX'].shape[1]]=old[part+'X'][i];x.append(row)
            ts.append('Human K562 CRISPRa paired activation. '+F.gene_text(targets,annotations['genes'],annotations['pathways'])+'. Baseline '+nbase+'. Measured single activations are supplied numerical calibration inputs. Strength and duration unavailable. Predict RNA change.')
        add('pair',part,x,old[part+'Y'],old[part+'Mask'],ts,[nbase]*len(x),names.tolist(),['K562']*len(x),old[part+'PairIndices'])
    singles=expert['singleGenes'].astype(str);ax=[features('activation',expert['baseline'],nmeasured,targets=[name]) for name in singles]
    add('activation','train',ax,expert['singleEffects'],np.ones_like(expert['singleEffects'],bool),
        ['Human K562 CRISPRa single activation. '+F.gene_text([name],annotations['genes'],annotations['pathways'])+'. Baseline '+nbase+'. Strength and duration unavailable.' for name in singles],[nbase]*len(singles),singles.tolist(),['K562']*len(singles))
    kgi={str(g):i for i,g in enumerate(kd['genes'])};kpi={str(g):i for i,g in enumerate(kd['kdPerturbations'])};cols=np.array([kgi.get(g,-1) for g in genes]);present=cols>=0
    for part,names in split_kd.items():
        y=np.zeros((len(names),g),np.float32);mask=np.zeros_like(y,bool);x=[];ts=[]
        for i,name in enumerate(names):
            y[i,present]=kd['kdEffects'][cols[present],kpi[name]];mask[i]=present&np.isfinite(y[i]);mask[i,gi[name]]=False;y[i,~mask[i]]=0
            x.append(features('inhibition',rb,rmeasured,targets=[name]));ts.append('Human K562 CRISPRi inhibition. '+F.gene_text([name],annotations['genes'],annotations['pathways'])+'. Baseline '+rbase+'. Perturbation strength and duration unavailable; measured target knockdown is excluded as an input. Predict RNA change.')
        add('inhibition',part,x,y,mask,ts,[rbase]*len(x),names,['K562']*len(x))
    A=Atlas(root/'virtualcell/data/tahoe100m');dm=root/'oncology/depmap/24Q4';em=json.loads((dm/'expression.json').read_text());expression=np.load(dm/'expression.npy',mmap_mode='r');egi={g:i for i,g in enumerate(em['genes'])};ec=np.array([egi.get(g,-1) for g in genes]);ep=ec>=0
    context_profiles={};context_bio={}
    for line,info in A.lines.items():
        if info['depmap'] not in em['models']:continue
        row=np.asarray(expression[em['models'].index(info['depmap'])],np.float32);base=np.zeros(g,np.float32);base[ep]=row[ec[ep]];mp=ep&np.isfinite(base);base[~mp]=0
        if mp.sum()<g//2:continue
        context_profiles[line]=(base,mp);context_bio[line]=baseline_sentence(base,mp)
    from collections import Counter
    records={}
    for path in (root/'virtualcell/training/compound-evidence').glob('*.json'):
        r=json.loads(path.read_text());records[r['name'].lower()]=r
    chemical_key={name:(r.get('inchiKey','').split('-')[0] or F.canonical_name(name)) for name,r in records.items() if r.get('state')=='resolved'}
    previous_names=sum(prior['groups']['drug'].values(),[]);seen_aliases={F.canonical_name(n) for n in previous_names}
    seen_aliases|={F.canonical_name(a['DRUG_NAME']) for n in previous_names for a in records.get(n,{}).get('annotations',[])}
    seen_chemical={chemical_key.get(n,F.canonical_name(n)) for n in previous_names}
    seen_chemical.update(prior.get('chemicalIdentityExposure',[]))
    seen_chemical|={identity for name,identity in chemical_key.items() if F.canonical_name(name) in seen_aliases or any(F.canonical_name(a['DRUG_NAME']) in seen_aliases for a in records[name].get('annotations',[]))}
    old_seen=sorted(set(seen_chemical));contexts=sorted(context_profiles,key=lambda c:hashlib.sha256(('context-v2:'+c).encode()).hexdigest());held_contexts=contexts[:config['heldoutContexts']]
    agi={g:i for i,g in enumerate(A.genes)};ac=np.array([agi.get(g,-1) for g in genes]);ap=ac>=0
    candidate_keys={};excluded_coverage=[]
    for key in A.groups:
        line,name,dose=key
        if dose>0 and line in context_profiles and name in chemical_key:
            available=np.isfinite(np.asarray(A.lfc[sorted(A.groups[key])][:,ac[ap]])).any(0).sum()
            if available>=g//2:candidate_keys.setdefault(chemical_key[name],[]).append(key)
            else:excluded_coverage.append(key)
    eligible_drugs=[identity for identity,keys in candidate_keys.items() if sum(k[0] not in held_contexts for k in keys)>=config['conditionsPerDrug']]
    split_drug=F.fresh_split(eligible_drugs,seen_chemical,config['drugGroups'],'drug')
    drug_conditions={}
    def drug_rows(part,keys):
        xs=[];ys=[];masks=[];reliability=[];texts=[];basal=[];groups=[];lines=[];details=[]
        for line,name,dose in keys:
            rows=sorted(A.groups[(line,name,dose)]);values=np.asarray(A.lfc[rows][:,ac[ap]],np.float32);se=np.asarray(A.se[rows][:,ac[ap]],np.float32)
            count=np.isfinite(values).sum(0);mean=np.where(np.isfinite(values),values,0).sum(0)/np.maximum(count,1);y=np.zeros(g,np.float32);m=np.zeros(g,bool);y[ap]=mean;m[ap]=count>0
            if m.sum()<g//2:raise ValueError('Drug signature has insufficient measured genes.')
            w=np.ones(g,np.float32)
            with np.errstate(invalid='ignore'):s=np.nanmedian(np.where(np.isfinite(se),se,np.nan),axis=0)
            w[ap]=1/(1+np.nan_to_num(s,nan=1.,posinf=1.)**2)
            base,bm=context_profiles[line];compound=records[name];r=A.conditions[rows[0]]
            xs.append(features('drug',base,bm,compound=compound,dose=dose));ys.append(y);masks.append(m);reliability.append(w);basal.append(context_bio[line]);groups.append(chemical_key[name]);lines.append(line)
            terms='; '.join(sorted({r[k] for r in compound.get('annotations',[]) for k in ['TARGET','TARGET_PATHWAY'] if r.get(k)})) or 'unavailable'
            texts.append(f"Human {r['cellLine']} ({line}). Measured DepMap bulk log2 TPM+1 baseline genes {context_bio[line]}. Drug {r['drug']}; source SMILES {compound['smiles']}; targets/pathways {terms}; dose {dose:g} {r['unit']}; duration unavailable. Predict Tahoe DESeq2 log2 fold change. Bulk baseline and single-cell response are different assays.")
            details.append({**r,'chemicalIdentity':chemical_key[name],'replicatePlates':len(rows),'baselineSource':'DepMap 24Q4 bulk RNA','structureSource':compound['source'],'targetSource':'GDSC 8.5' if compound.get('annotations') else None})
        if not xs:return
        add('drug',part,xs,ys,masks,texts,basal,groups,lines,weights=np.asarray(reliability));drug_conditions[part]=details
    for part,names in split_drug.items():
        keys=[]
        for identity in names:
            eligible_keys=[k for k in candidate_keys[identity] if k[0] not in held_contexts]
            eligible_keys.sort(key=lambda k:hashlib.sha256(str((F.SEED,k)).encode()).hexdigest());keys+=eligible_keys[:config['conditionsPerDrug']]
        drug_rows(part,keys)
    cross=[]
    for identity in split_drug['train']:
        keys=[k for k in candidate_keys[identity] if k[0] in held_contexts];keys.sort(key=str);cross+=keys[:2]
    drug_rows('context_test',cross[:128])
    tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    cap=int(json.loads((checkpoint/'config.json').read_text())['max_position_embeddings'])-5;lengths={}
    for prefix,ts in text.items():
        ids,attention,lens=encode_complete(tokenizer,ts,cap);data[prefix+'_Ids']=ids;data[prefix+'_Attention']=attention;data[prefix+'_BioText']=np.asarray(bio[prefix]);lengths[prefix]={'conditions':len(ts),'maximumTokens':int(lens.max()),'truncated':0}
    fitting=np.concatenate([data[t+'_train_X'][:1024] for t in ['pair','activation','inhibition','drug','state']]);data['featureCenter']=fitting.mean(0);data['featureScale']=np.maximum(fitting.std(0),.1)
    fitting=np.concatenate([data[t+'_train_Baseline'][:1024] for t in ['pair','activation','inhibition','drug','state']]);data['baselineCenter']=fitting.mean(0);data['baselineScale']=np.maximum(fitting.std(0),.1)
    for task in ['pair','activation','inhibition','drug','state']:
        y=data[task+'_train_Y'];m=data[task+'_train_Mask'];mean=np.sum(y*m,0)/np.maximum(m.sum(0),1);var=np.sum((y-mean)**2*m,0)/np.maximum(m.sum(0),1)
        data[task+'_Mean']=mean.astype(np.float32);data[task+'_Scale']=np.maximum(np.sqrt(var),.05).astype(np.float32)
    out.mkdir(parents=True);cloud=out/'cloud-inputs';cloud.mkdir();np.savez_compressed(cloud/'data.npz',**data);np.savez_compressed(out/'LOCAL_FINAL_ANSWERS.npz',**local_answers)
    local={'schema':'fold.cell-training-split/2','groups':{'inhibition':split_kd,'drug':split_drug},'identities':identities,'heldoutContexts':held_contexts,
           'cells':cell_ids,'sourceCellConditions':{'norman':nm['labels'][nr].tolist(),'replogle':rm['labels'][rr].tolist()},'drugConditions':drug_conditions,
           'previouslyUsedInterventionGroups':{'inhibition':seen_genes,'drug':old_seen},'answerSha256':sha(out/'LOCAL_FINAL_ANSWERS.npz'),'dataSha256':sha(cloud/'data.npz')}
    write(out/'SPLIT_MANIFEST.json',local)
    sources={str(p.relative_to(root)):sha(p) for p in [seed_data,history] if root in p.parents}
    for p in [root/'virtualcell/data/annotations/index.json.gz',dm/'expression.npy',dm/'expression.json',root/'virtualcell/data/tahoe100m/lfc.f16',root/'virtualcell/data/tahoe100m/se.f16',root/'virtualcell/data/tahoe100m/conditions.json',refs/'pack.npz']:
        sources[str(p.relative_to(root))]=sha(p)
    if functions.exists():sources[str(functions.relative_to(root))]=sha(functions)
    gdsc=root/'oncology/gdsc/8.5/original/screened_compounds_rel_8.5.csv'
    if gdsc.exists():sources[str(gdsc.relative_to(root))]=sha(gdsc)
    for p in (root/'virtualcell/training/compound-evidence').glob('*.json'):sources[str(p.relative_to(root))]=sha(p)
    info={'schema':'fold.cell-training-data/2','config':config,'dataSha256':sha(cloud/'data.npz'),'answerSha256':local['answerSha256'],'splitSha256':sha(out/'SPLIT_MANIFEST.json'),
          'distinctTrainingCells':len(cell_ids),'units':units,'textLengths':lengths,'sourceSha256':sources,'seedDataSha256':sha(seed_data),'historySha256':sha(history),'sourceCodeSha256':sha(__file__),
          'featureVersion':F.FEATURE_VERSION,'featureWidth':data['pair_train_X'].shape[1],'freshFinalInterventionGroups':True,'freshContextTrainingStartsFromOfficialQwenBase':True,
          'functionalGeneAnnotations':sum(bool(r.get('goFunction') or r.get('goProcess')) for g,r in annotations['genes'].items() if g in gi),
          'cellContexts':len(context_profiles),'heldoutContexts':held_contexts,'testAnswersUploaded':False,'noTruncation':True,
          'chemistry':{'resolvedCompounds':len(chemical_key),'trainChemicalIdentities':len(split_drug['train']),'excludedInsufficientCoverageConditions':len(excluded_coverage),'fingerprint':'Morgan radius2/256 + eight descriptors; RDKit','missingDuration':'explicitly unavailable'},
          'limitations':['Reused primary pair validation; no fresh pair test.','DepMap bulk baselines and Tahoe response are different assays.','Final tests are within available public datasets, not independent-study validation.','A frozen cell encoder would carry its own pretraining exposure; that is not a clean-room biological experiment.']}
    write(cloud/'manifest.json',info);event('data_prepared',distinctCells=len(cell_ids),featureWidth=info['featureWidth'],tasks=lengths);return info
