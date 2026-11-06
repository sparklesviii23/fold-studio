"""Evidence-backed cell/intervention features. Missing evidence stays explicit."""
import csv,gzip,hashlib,json,re,time,urllib.parse,urllib.request
from pathlib import Path
import numpy as np

SEED=20261106
FEATURE_VERSION='fold.cell-features/2'


def canonical_name(value):return re.sub(r'[^a-z0-9]','',str(value).lower())


def signed_hash(tokens,width):
    out=np.zeros(width,np.float32)
    for token in sorted(set(str(t) for t in tokens if t)):
        b=hashlib.sha256(token.encode()).digest();out[int.from_bytes(b[:4],'little')%width]+=1 if b[4]&1 else -1
    return out/max(float(np.linalg.norm(out)),1.)


def project_expression(values,genes,width=64):
    """A fixed, gene-aligned signed projection; no test statistics are fitted."""
    values=np.asarray(values,np.float32);out=np.zeros((*values.shape[:-1],width),np.float32)
    for i,g in enumerate(genes):
        h=hashlib.sha256(('expression:'+str(g)).encode()).digest();out[...,int.from_bytes(h[:4],'little')%width]+=values[...,i]*(1 if h[4]&1 else -1)
    return out/np.sqrt(max(len(genes)/width,1))


def gene_features(symbol,annotations):
    r=annotations.get(str(symbol),{});tokens=['gene:'+str(symbol)]
    tokens+=['reactome:'+str(x['id'] if isinstance(x,dict) else x) for x in r.get('reactome',[])]
    tokens+=['go:'+str(x) for x in r.get('goComponent',[])]
    tokens+=['biological_process:'+str(x) for x in r.get('goProcess',[])]
    tokens+=['molecular_function:'+str(x) for x in r.get('goFunction',[])]
    tokens+=['location:'+str(x.get('location','')) for x in r.get('uniprotLocations',[])]
    return signed_hash(tokens,64),bool(r)


def molecular_features(smiles):
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator,Descriptors,rdMolDescriptors,Crippen
    mol=Chem.MolFromSmiles(str(smiles))
    if mol is None:raise ValueError('Invalid source SMILES.')
    fp=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=256).GetFingerprintAsNumPy(mol).astype(np.float32)
    desc=np.array([Descriptors.MolWt(mol)/500,Crippen.MolLogP(mol)/5,rdMolDescriptors.CalcTPSA(mol)/150,
                   rdMolDescriptors.CalcNumHBD(mol)/5,rdMolDescriptors.CalcNumHBA(mol)/10,
                   rdMolDescriptors.CalcNumRotatableBonds(mol)/10,mol.GetNumHeavyAtoms()/40,rdMolDescriptors.CalcFractionCSP3(mol)],np.float32)
    return np.concatenate([fp,desc]),Chem.MolToSmiles(mol,isomericSmiles=True)


def compound_knowledge(root):
    """Existing GDSC identity/target annotations only; never response labels."""
    path=Path(root)/'oncology/gdsc/8.5/original/screened_compounds_rel_8.5.csv';index={}
    if path.exists():
        for row in csv.DictReader(path.open()):
            for name in [row['DRUG_NAME'],*row.get('SYNONYMS','').split(',')]:
                key=canonical_name(name)
                if key:index.setdefault(key,[]).append({k:row.get(k,'') for k in ['DRUG_NAME','TARGET','TARGET_PATHWAY']})
    return index


def fetch_compounds(root,names,event=lambda *a,**k:None):
    """Bounded public metadata retrieval; no weights, response outcomes or retries."""
    directory=Path(root)/'virtualcell/training/compound-evidence';directory.mkdir(parents=True,exist_ok=True);knowledge=compound_knowledge(root)
    result={}
    for i,name in enumerate(sorted(set(names))):
        key=hashlib.sha256(name.lower().encode()).hexdigest();path=directory/(key+'.json')
        if path.exists():record=json.loads(path.read_text())
        else:
            url='https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/'+urllib.parse.quote(name,safe='')+'/property/ConnectivitySMILES,InChIKey/JSON'
            record={'name':name,'source':url,'retrieved':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'state':'unavailable'}
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'FoldStudio/4.3 public research metadata'})
                with urllib.request.urlopen(req,timeout=12) as response:raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Metadata response too large.')
                record['responseSha256']=hashlib.sha256(raw).hexdigest();values=json.loads(raw)['PropertyTable']['Properties']
                structures={(r.get('ConnectivitySMILES') or r.get('CanonicalSMILES'),r.get('InChIKey','')) for r in values}
                if len(structures)!=1:raise ValueError('Ambiguous compound identity; not selected automatically.')
                sm,ik=next(iter(structures));features,canonical=molecular_features(sm)
                record.update(state='resolved',cid=[r['CID'] for r in values],smiles=canonical,inchiKey=ik,molecularFeatures=features.tolist())
            except Exception as error:record['reason']=str(error)[:250]
            record['annotations']=knowledge.get(canonical_name(name),[])
            path.write_text(json.dumps(record,indent=2)+'\n');time.sleep(.25)
        result[name.lower()]=record
        if i%16==0 or i+1==len(names):event('compound_evidence',completed=i+1,total=len(names),resolved=sum(r['state']=='resolved' for r in result.values()))
    return result


def intervention_features(task,baseline,measured,genes,annotations,targets=(),compound=None,dose=None,remaining=None,duration=None):
    """Layout: baseline64 + target64 + structure264 + mechanism64 + metadata12."""
    baseline=np.asarray(baseline,np.float32);measured=np.asarray(measured,bool)
    if baseline.shape!=(len(genes),) or measured.shape!=baseline.shape or not np.isfinite(baseline[measured]).all():raise ValueError('Invalid measured starting cell profile.')
    if task not in ['pair','activation','inhibition','drug','state']:raise ValueError('Unknown intervention modality.')
    target=np.zeros(64,np.float32);known=[]
    for g in targets:
        a,k=gene_features(g,annotations);target+=a;known.append(k)
    target/=max(len(targets),1)
    chem=np.zeros(264,np.float32);mechanism=np.zeros(64,np.float32);compound=compound or {}
    if compound.get('state')=='resolved':chem=np.asarray(compound['molecularFeatures'],np.float32)
    terms=[r.get(k,'') for r in compound.get('annotations',[]) for k in ['TARGET','TARGET_PATHWAY']]
    if terms:mechanism=signed_hash(terms,64)
    metadata=np.array([float(task=='pair'),float(task=='activation'),float(task=='inhibition'),float(task=='drug'),float(task=='state'),
                       np.log10(dose) if dose is not None and dose>0 else 0.,remaining if remaining is not None else 0.,
                       np.log1p(duration) if duration is not None and duration>=0 else 0.,float(measured.mean()),
                       float(compound.get('state')=='resolved'),float(bool(terms)),float(bool(known) and all(known))],np.float32)
    # Missing strength/time are encoded explicitly in text; the last two slots
    # distinguish measured zero from unavailable values numerically too.
    return np.concatenate([project_expression(np.where(measured,baseline,0),genes),target,chem,mechanism,metadata,
                           np.array([remaining is not None,duration is not None],np.float32)])


def fresh_split(groups,previously_evaluated,counts,namespace):
    """Fresh final/validation groups, with all aliases of a compound kept together."""
    seen=set(previously_evaluated);names=sorted(set(groups),key=lambda g:hashlib.sha256(f'{SEED}:v2:{namespace}:{g}'.encode()).hexdigest())
    train_n,val_n,test_n=counts;fresh=[g for g in names if g not in seen]
    if len(fresh)<val_n+test_n:raise ValueError('Insufficient untouched intervention groups; do not recycle an opened test.')
    test=fresh[:test_n];validation=fresh[test_n:test_n+val_n];excluded=set(test+validation)
    train=[g for g in names if g not in excluded][:train_n]
    if len(train)<train_n:raise ValueError('Insufficient training intervention groups.')
    return {'train':train,'validation':validation,'test':test}


def gene_text(targets,annotations,pathways):
    rows=[]
    for g in targets:
        r=annotations.get(str(g),{});ps=[pathways.get(x['id'] if isinstance(x,dict) else x,{}).get('name',str(x)) for x in r.get('reactome',[])[:6]]
        rows.append(str(g)+'; pathways '+(', '.join(ps) or 'unavailable')+'; cellular components '+(', '.join(r.get('goComponent',[])[:4]) or 'unavailable')+
                    '; molecular functions '+(', '.join(r.get('goFunction',[])[:6]) or 'unavailable')+'; biological processes '+(', '.join(r.get('goProcess',[])[:6]) or 'unavailable'))
    return ' | '.join(rows)
