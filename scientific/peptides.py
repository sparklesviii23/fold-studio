"""Canonical peptide assets and isolated arcade progress. No prediction engine imports."""
import copy, datetime, hashlib, json, math, pathlib, re, uuid
ACTIONS={'amino_acids','peptide_library','peptide_save','peptide_delete','peptide_versions','peptide_geometry','peptide_structure','peptide_transfer','arcade_load','arcade_save','arcade_status'}
TEMPLATES=json.loads((pathlib.Path(__file__).parent/'amino-acids.json').read_text())
BY_ONE={c['one']:c for c in TEMPLATES['components']}
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sub(a,b): return [x-y for x,y in zip(a,b)]
def add(a,b): return [x+y for x,y in zip(a,b)]
def mul(a,t): return [x*t for x in a]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def length(a): return math.sqrt(dot(a,a))
def unit(a): return mul(a,1/length(a))
def distance(a,b): return length(sub(a,b))
def angle(a,b,c): return math.acos(max(-1,min(1,dot(unit(sub(a,b)),unit(sub(c,b))))))
def place(a,b,c,bond,theta,torsion):
    u=unit(sub(c,b)); n=unit(cross(sub(b,a),u)); v=cross(n,u)
    return add(c,mul(add(mul(u,-math.cos(theta)),mul(add(mul(v,math.cos(torsion)),mul(n,math.sin(torsion))),math.sin(theta))),bond))
def frame(n,ca,c):
    x=unit(sub(n,ca)); z=unit(cross(x,sub(c,ca))); return [x,cross(z,x),z]
def rigid(x,origin,basis,target,tbasis):
    q=sub(x,origin);return add(target,[sum(dot(q,basis[j])*tbasis[j][i] for j in range(3)) for i in range(3)])
def canonical(sequence):
    if not isinstance(sequence,str): raise ValueError('Sequence must be text.')
    s=re.sub(r'\s+','',sequence).upper()
    if not s or len(s)>128 or set(s)-BY_ONE.keys(): raise ValueError('Use 1–128 standard amino acids.')
    return s

def construct(sequence):
    sequence=canonical(sequence); atoms=[];bonds=[];previous=None
    for i,one in enumerate(sequence):
        template=BY_ONE[one];lookup={a['id']:a for a in template['atoms']}; coords={k:a['xyz'] for k,a in lookup.items()}
        n,ca,c=[coords[k] for k in ['N','CA','C']]
        if previous:
            pn,pca,pc=previous
            tn=place(pn,pca,pc,1.329,math.radians(116.2),math.radians(135))
            tca=place(pca,pc,tn,distance(n,ca),math.radians(121.7),math.pi)
            tc=place(pc,tn,tca,distance(ca,c),angle(n,ca,c),math.radians(-135))
            f,tf=frame(n,ca,c),frame(tn,tca,tc)
            coords={k:rigid(x,ca,f,tca,tf) for k,x in coords.items()}
        n,ca,c=[coords[k] for k in ['N','CA','C']]
        if i<len(sequence)-1:
            coords['O']=place(n,ca,c,distance(c,coords['O']),angle(ca,c,coords['O']),math.radians(135+180))
        removed=set()
        if i<len(sequence)-1: removed.update(['OXT','HXT'])
        if i>0:
            removed.update(a['id'] for a in template['atoms'] if a['element']=='H' and a['leaving'] and any({b['a'],b['b']}=={'N',a['id']} for b in template['bonds']))
        for a in template['atoms']:
            if a['id'] not in removed: atoms.append({**copy.deepcopy(a),'id':f'{i+1}:{a["id"]}','atomName':a['id'],'residue':i+1,'code':template['code'],'xyz':coords[a['id']]})
        for b in template['bonds']:
            if b['a'] not in removed and b['b'] not in removed: bonds.append({**b,'a':f'{i+1}:{b["a"]}','b':f'{i+1}:{b["b"]}','kind':'component'})
        if i: bonds.append({'a':f'{i}:C','b':f'{i+1}:N','order':1,'aromatic':False,'kind':'peptide'})
        previous=(n,ca,c)
    return {'sequence':sequence,'atoms':atoms,'bonds':bonds,'method':'CCD ideal component coordinates, rigid residue alignment; extended backbone phi −135°, psi 135°, omega 180°; C–N 1.329 Å. Carbonyl oxygen placed in peptide plane. No energy minimization or folding prediction.','geometryStatus':'idealized_unrelaxed','confidenceKind':None}

def topology(sequence):
    model=construct(sequence); valences={a['id']:0 for a in model['atoms']}
    for b in model['bonds']:
        valences[b['a']]+=b['order'];valences[b['b']]+=b['order']
    # Compare each incorporated atom with its full, neutral CCD reference valence.
    errors=[]
    for a in model['atoms']:
        t=BY_ONE[sequence[a['residue']-1]]
        expected=sum(b['order'] for b in t['bonds'] if a['atomName'] in [b['a'],b['b']])
        if expected!=valences[a['id']]: errors.append('CCD valence mismatch: '+a['id'])
    return {'valid':not errors,'status':'validated_connectivity' if not errors else 'invalid','errors':errors,'atomCount':len(model['atoms']),'bondCount':len(model['bonds']),'peptideBonds':len(sequence)-1,'stereochemistry':'CCD stereochemical assignments inherited; residue rigid transforms preserve handedness. No independent conformational validation.','geometryStatus':'idealized_unrelaxed','limitations':['Standard linear peptides only; neutral CCD protonation, no pH model.','Topology validity does not establish biological folding, stability, activity or binding.'],'method':'Remove left OXT/HXT and right N leaving hydrogen per peptide link; add carbonyl C → next N single covalent bond; compare atom bond-order sums with CCD templates.'}

def state_validate(state):
    if not isinstance(state,dict) or state.get('schemaVersion')!=1: raise ValueError('Unsupported game state schema.')
    if len(json.dumps(state,allow_nan=False))>300000: raise ValueError('Game state too large.')
    blocks=state.get('blocks',[])
    if not isinstance(blocks,list) or len(blocks)>128: raise ValueError('At most 128 peptide blocks.')
    ids=[]
    for b in blocks:
        if not isinstance(b,dict) or b.get('one') not in BY_ONE or not isinstance(b.get('id'),str) or len(b['id'])>80: raise ValueError('Invalid building block.')
        ids.append(b['id'])
    if len(set(ids))!=len(ids): raise ValueError('Duplicate building block identity.')
    valid={(ids[i],ids[i+1]) for i in range(len(ids)-1)}
    links=state.get('links',[])
    if not isinstance(links,list) or len(links)>127: raise ValueError('Invalid connections.')
    pairs=[]
    for l in links:
        if not isinstance(l,dict) or (l.get('from'),l.get('to')) not in valid: raise ValueError('Only adjacent carbonyl C → next N peptide links are supported.')
        pairs.append((l['from'],l['to']))
    if len(set(pairs))!=len(pairs): raise ValueError('Duplicate peptide link.')
    return state

class Peptides:
    def __init__(self,service):
        self.s=service;self.db=service.db
        self.db.executescript('''CREATE TABLE IF NOT EXISTS peptide_versions(id TEXT PRIMARY KEY,record_id TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(record_id,revision));
        CREATE TABLE IF NOT EXISTS arcade_progress(project_id TEXT NOT NULL,workspace TEXT NOT NULL,revision INTEGER NOT NULL,state TEXT NOT NULL,updated TEXT NOT NULL,PRIMARY KEY(project_id,workspace));''')
    def dispatch(self,action,p): return getattr(self,action)(p)
    def amino_acids(self,p): return TEMPLATES
    def peptide_library(self,p):
        project=self.s.project(p['projectId']); records=[]
        for r in self.s.rows('SELECT * FROM records WHERE project_id=? ORDER BY created DESC',(project['id'],)):
            r['data']=json.loads(r['data']); seq=r['data'].get('sequence')
            if r['kind']=='structure':
                chains=r['data'].get('metadata',{}).get('provenance',{}).get('chains',[])
                if len(chains)==1 and isinstance(chains[0].get('sequence'),str):
                    seq=chains[0]['sequence'];r['data']['sequence']=seq
                    r['data']['origin']={'source':'Prediction input sequence; coordinate correspondence needs verification','sourceRecordId':r['id'],'asset':r['data']['asset']}
                    r['data']['sequenceStatus']='prediction_input_metadata'
            if isinstance(seq,str) and 0<len(seq)<=128 and not set(seq)-BY_ONE.keys() and r['kind'] in ['peptide','sequence','variant','structure']:
                r['data'].setdefault('revision',0);records.append(r)
        return records
    def record(self,id):
        r=self.db.execute("SELECT * FROM records WHERE id=? AND kind='peptide'",(id,)).fetchone()
        if not r: raise ValueError('Choose a saved peptide asset.')
        r=dict(r);r['data']=json.loads(r['data']);return r
    def peptide_save(self,p):
        project=self.s.project(p['projectId']); sequence=canonical(p['sequence']); validation=topology(sequence)
        if not validation['valid']: raise ValueError('Chemical topology did not validate.')
        if p.get('state') is not None:
            st=p['state']
            if st.get('schemaVersion')==2:
                from molecular_graph import validate
                validation=validate(st)
                if not validation['valid'] or validation['sequence']!=sequence: raise ValueError('Submitted atom/bond graph is incomplete or invalid: '+ '; '.join(validation['errors'][:3]))
            else:
                st=state_validate(st)
                if ''.join(b['one'] for b in st['blocks'])!=sequence or len(st['links'])!=len(sequence)-1: raise ValueError('Connect every adjacent C → N end before saving a scientific peptide.')
        name=str(p.get('name','')).strip()[:200]
        if not name: raise ValueError('Name the peptide before saving.')
        if p.get('parentId'):
            parent=self.db.execute('SELECT project_id FROM records WHERE id=?',(p['parentId'],)).fetchone()
            if not parent or parent[0]!=project['id']: raise ValueError('Source asset must exist in the same research project.')
        id=p.get('id'); old=self.record(id) if id else None
        if old and old['project_id']!=project['id']: raise ValueError('Peptide belongs to a different project.')
        revision=old['data']['revision']+1 if old else 1
        if old and p.get('revision')!=old['data']['revision']: raise ValueError('This peptide changed in another window. Reopen its latest version before saving.')
        id=id or str(uuid.uuid4()); date=now()
        data={'schemaVersion':1,'sequence':sequence,'length':len(sequence),'revision':revision,'notes':str(p.get('notes',''))[:100000],'origin':old['data']['origin'] if old else {'workspace':p.get('workspace','architect'),'created':date},'validation':validation,'templates':[{'code':BY_ONE[o]['code'],'sha256':BY_ONE[o]['sha256'],'source':BY_ONE[o]['source']} for o in sorted(set(sequence))],'modified':date,'geometryStatus':'not_a_prediction','parentId':p.get('parentId') or (old['data'].get('parentId') if old else None)}
        if (p.get('state') or {}).get('schemaVersion')==2:
            data['graph']=copy.deepcopy(p['state']);data['schemaVersion']=2
            data['graphSha256']=hashlib.sha256(json.dumps(data['graph'],sort_keys=True,allow_nan=False).encode()).hexdigest()
        # Serialize writers before checking revision again; fail without partial history.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if old:
                current=json.loads(self.db.execute('SELECT data FROM records WHERE id=?',(id,)).fetchone()[0])
                if current['revision']!=p.get('revision'): raise ValueError('Concurrent peptide edit; reopen the latest version.')
                self.db.execute('UPDATE records SET name=?,data=? WHERE id=?',(name,json.dumps(data),id))
            else: self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(id,project['id'],'peptide',name,json.dumps(data),date))
            self.db.execute('INSERT INTO peptide_versions VALUES(?,?,?,?,?)',(str(uuid.uuid4()),id,revision,json.dumps({'name':name,'data':data}),date))
            self.db.execute('UPDATE projects SET updated=? WHERE id=?',(date,project['id']))
        return self.record(id)
    def peptide_delete(self,p):
        if p.get('confirmed') is not True: raise ValueError('Confirm peptide deletion.')
        r=self.record(p['id'])
        if p.get('revision')!=r['data']['revision']: raise ValueError('The peptide changed. Reopen it before deleting.')
        with self.db:
            self.db.execute('DELETE FROM records WHERE id=?',(r['id'],))
        return {'deleted':r['id'],'versionHistoryRetained':True}
    def peptide_versions(self,p):
        return [{**r,'data':json.loads(r['data'])} for r in self.s.rows('SELECT * FROM peptide_versions WHERE record_id=? ORDER BY revision DESC',(p['id'],))]
    def peptide_geometry(self,p):
        model=construct(p['sequence']);model['validation']=topology(model['sequence']);return model
    def peptide_transfer(self,p):
        r=self.record(p['id'])
        if p.get('revision') is not None and p['revision']!=r['data']['revision']: raise ValueError('Peptide revision changed; reopen before transfer.')
        if r['data'].get('graph'):
            from molecular_graph import validate
            validation=validate(r['data']['graph'])
        else: validation=topology(r['data']['sequence'])
        if not validation['valid']: raise ValueError('Peptide topology failed validation.')
        return {'record':r,'sequence':r['data']['sequence'],'origin':{'source':'Validated canonical peptide sequence','peptideId':r['id'],'revision':r['data']['revision'],'workspace':r['data']['origin']['workspace'],'templates':r['data']['templates'],'validation':validation,'geometryTransfer':False,'graphSha256':r['data'].get('graphSha256')}}
    def peptide_structure(self,p):
        transfer=self.peptide_transfer(p)
        r=self.record(p['id']);model=construct(r['data']['sequence']);seq=model['sequence']; lines=['HEADER    IDEALIZED UNRELAXED PEPTIDE','REMARK   1 NOT A PREDICTION. NO CONFIDENCE VALUES.','REMARK   2 '+model['method']]
        ids={a['id']:i+1 for i,a in enumerate(model['atoms'])}
        for a in model['atoms']:
            x,y,z=a['xyz']; serial=ids[a['id']]
            lines.append(f"ATOM  {serial:5d} {a['atomName']:>4s} {a['code']:3s} A{a['residue']:4d}    {x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}          {a['element']:>2s}")
        for b in model['bonds']: lines.append(f"CONECT{ids[b['a']]:5d}"+f"{ids[b['b']]:5d}"*b['order'])
        lines+=['TER','END']; asset=self.s.root/'cache'/(str(uuid.uuid4())+'.pdb');asset.write_text('\n'.join(lines)+'\n')
        try:
            return self.s.import_structure({'projectId':r['project_id'],'path':str(asset),'name':r['name']+' · idealized, unrelaxed','source':'CCD peptide construction; not a predicted or experimental fold','metadata':{'peptideId':r['id'],'peptideRevision':r['data']['revision'],'graphSha256':r['data'].get('graphSha256'),'sourceGraphValidation':transfer['origin']['validation'],'method':model['method'],'validation':topology(seq),'geometryStatus':'idealized_unrelaxed','provenance':{'chains':[{'sequence':seq}],'origin':transfer['origin']}}})
        finally: asset.unlink(missing_ok=True)
    def workspace(self,p):
        self.s.project(p['projectId']);w=p.get('workspace','arcade')
        if w not in ['arcade','architect']: raise ValueError('Unknown construction workspace.')
        return w
    def arcade_load(self,p):
        w=self.workspace(p);r=self.db.execute('SELECT * FROM arcade_progress WHERE project_id=? AND workspace=?',(p['projectId'],w)).fetchone()
        return {**dict(r),'state':json.loads(r['state'])} if r else {'revision':0,'state':None}
    def arcade_save(self,p):
        w=self.workspace(p);st=state_validate(p['state'])
        with self.db:
            self.db.execute('BEGIN IMMEDIATE');old=self.arcade_load(p)
            if p.get('revision')!=old['revision']: raise ValueError('Progress changed in another window. Reopen this workspace to resume safely.')
            self.db.execute('INSERT OR REPLACE INTO arcade_progress VALUES(?,?,?,?,?)',(p['projectId'],w,old['revision']+1,json.dumps(st,allow_nan=False),now()))
        return self.arcade_load(p)
    def arcade_status(self,p):
        result=[]
        for j in self.s.rows("SELECT * FROM jobs WHERE engine='boltz2' ORDER BY created DESC LIMIT 10"):
            data=json.loads(j.pop('data'));j['outputs']=data.get('outputs',[]);j['elapsedSeconds']=max(0,int((datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(j['created'])).total_seconds())) if j['state'] in ['queued','running'] else None;result.append(j)
        return {'jobs':result}
