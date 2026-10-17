"""Bounded canonical CCD graph validator. Validates submitted atoms/bonds, never just a sequence.
Board positions are educational; template xyz/stereo are locked. No chemistry toolkit/engine imports.
"""
import copy, hashlib, json, math, pathlib
from functools import lru_cache
from peptides import BY_ONE, state_validate, now

MAX_BYTES = 1800000
MAX_ATOMS = 8000

def atom_id(residue, name): return residue + ':' + name

def expected(residues, links):
    removed = {r['id']: set() for r in residues}
    lookup = {r['id']: r for r in residues}
    for left, right in links:
        removed[left].update(['OXT', 'HXT'])
        t = BY_ONE[lookup[right]['one']]
        removed[right].update(a['id'] for a in t['atoms'] if a['element']=='H' and a['leaving'] and any({b['a'],b['b']}=={'N',a['id']} for b in t['bonds']))
    atoms, bonds = {}, {}
    for r in residues:
        t = BY_ONE[r['one']]
        for a in t['atoms']:
            if a['id'] not in removed[r['id']]: atoms[(r['id'],a['id'])]=a
        for b in t['bonds']:
            if b['a'] not in removed[r['id']] and b['b'] not in removed[r['id']]:
                bonds[frozenset([(r['id'],b['a']),(r['id'],b['b'])])] = (b['order'],b['aromatic'],'component')
    for left,right in links: bonds[frozenset([(left,'C'),(right,'N')])] = (1,False,'peptide')
    return atoms,bonds

def vector(value, size):
    return isinstance(value,list) and len(value)==size and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and abs(v)<=100000 for v in value)

def identity(value): return isinstance(value,str) and 0<len(value)<=120

def envelope(state):
    if not isinstance(state,dict) or state.get('schemaVersion')!=2: raise ValueError('Unsupported molecular draft schema.')
    if len(json.dumps(state,allow_nan=False).encode())>MAX_BYTES: raise ValueError('Molecular draft exceeds 1.8 MB.')
    residues,atoms,bonds=state.get('residues'),state.get('atoms'),state.get('bonds')
    if not isinstance(residues,list) or len(residues)>128 or not isinstance(atoms,list) or len(atoms)>MAX_ATOMS or not isinstance(bonds,list) or len(bonds)>12000: raise ValueError('Draft exceeds supported graph limits.')
    ids=[]
    for r in residues:
        if not isinstance(r,dict) or not identity(r.get('id')) or r.get('one') not in BY_ONE or not vector(r.get('position'),2) or not isinstance(r.get('rotation'),(int,float)) or not math.isfinite(r['rotation']): raise ValueError('Invalid residue or board orientation.')
        ids.append(r['id'])
    if len(set(ids))!=len(ids): raise ValueError('Duplicate residue identity.')
    aid=set();refs=set()
    for a in atoms:
        if not isinstance(a,dict) or not identity(a.get('id')) or a['id'] in aid or a.get('element') not in ['H','C','N','O','S'] or not vector(a.get('board'),2) or not vector(a.get('xyz'),3): raise ValueError('Invalid atom identity, element or coordinates.')
        aid.add(a['id'])
        if a.get('residueId') is not None:
            ref=(a['residueId'],a.get('templateAtom'))
            if a['residueId'] not in ids or not identity(a.get('templateAtom')) or ref in refs: raise ValueError('Invalid or duplicate template atom correspondence.')
            refs.add(ref)
        if not isinstance(a.get('charge'),int) or isinstance(a.get('charge'),bool) or abs(a['charge'])>4 or a.get('stereo') not in ['N','R','S','?']: raise ValueError('Invalid atom charge or stereo assignment.')
    pairs=set()
    for b in bonds:
        if not isinstance(b,dict) or b.get('a') not in aid or b.get('b') not in aid or b['a']==b['b'] or b.get('order') not in [1,2,3] or not isinstance(b.get('aromatic'),bool) or b.get('kind') not in ['component','peptide','free']: raise ValueError('Invalid bond endpoints or order.')
        pair=frozenset([b['a'],b['b']])
        if pair in pairs: raise ValueError('Duplicate covalent bond.')
        pairs.add(pair)
    for field,limit in [('name',200),('notes',100000)]:
        if not isinstance(state.get(field,''),str) or len(state.get(field,''))>limit: raise ValueError('Invalid '+field+'.')
    if state.get('mode') not in ['free','challenge','learn'] or not identity(state.get('challengeId')):raise ValueError('Invalid molecular challenge context.')
    if state.get('blueprintSequence') is not None and (not isinstance(state['blueprintSequence'],str) or not state['blueprintSequence'] or len(state['blueprintSequence'])>128 or set(state['blueprintSequence'])-BY_ONE.keys()):raise ValueError('Unsupported blueprint sequence.')
    if not isinstance(state.get('completed',[]),list) or len(state.get('completed',[]))>100: raise ValueError('Invalid challenge history.')
    return state

def validate(state):
    envelope(state)
    residues=state['residues'];atoms=state['atoms'];bonds=state['bonds'];lookup={a['id']:a for a in atoms};errors=[];links=[]
    ordered=[r['id'] for r in residues];adjacent={(ordered[i],ordered[i+1]) for i in range(len(ordered)-1)}
    for b in bonds:
        if b['kind']=='peptide':
            a,c=lookup[b['a']],lookup[b['b']];pair=(a.get('residueId'),c.get('residueId'))
            if a.get('templateAtom')!='C' or c.get('templateAtom')!='N' or pair not in adjacent or b['order']!=1 or b['aromatic']: errors.append('Unsupported peptide connection; use adjacent terminal C → N, single bond.')
            else: links.append(pair)
    if len(set(links))!=len(links): errors.append('Duplicate peptide attachment.')
    want_atoms,want_bonds=expected(residues,links)
    mapping={};unmapped=0
    for a in atoms:
        ref=(a.get('residueId'),a.get('templateAtom'));t=want_atoms.get(ref)
        if not t:
            if a.get('residueId') is None: unmapped+=1
            else: errors.append('Unexpected/leaving template atom: '+a['id'])
            continue
        mapping[a['id']]=ref
        if any(a.get(k)!=t[k] for k in ['element','charge','stereo']): errors.append('CCD element, neutral charge or locked stereo differs: '+a['id'])
        if any(abs(x-y)>1e-7 for x,y in zip(a['xyz'],t['xyz'])): errors.append('Template geometry is locked; mirror or atomic coordinate edits are unsupported: '+a['id'])
    found=set();valence={key:0 for key in want_atoms}
    for b in bonds:
        if b['a'] not in mapping or b['b'] not in mapping:
            if lookup[b['a']].get('residueId') is not None or lookup[b['b']].get('residueId') is not None: errors.append('Bond has unsupported template correspondence.')
            continue
        pair=frozenset([mapping[b['a']],mapping[b['b']]]);wanted=want_bonds.get(pair)
        if not wanted or (b['order'],b['aromatic'],b['kind'])!=wanted: errors.append('Bond connectivity/order/aromatic state differs from CCD: '+b['a']+' — '+b['b'])
        else: found.add(pair)
        valence[mapping[b['a']]]+=b['order'];valence[mapping[b['b']]]+=b['order']
    expected_valence={ref:0 for ref in want_atoms}
    for pair,value in want_bonds.items():
        for ref in pair: expected_valence[ref]+=value[0]
    for ref,total in valence.items():
        expected_total=expected_valence[ref]
        if total>expected_total: errors.append('Bond-order sum exceeds CCD reference: '+':'.join(ref))
    missing_atoms=len(want_atoms)-len(mapping);missing_bonds=len(want_bonds)-len(found)
    complete=bool(residues) and not errors and not unmapped and missing_atoms==0 and missing_bonds==0
    continuous=complete and len(links)==len(residues)-1
    status='invalid' if errors else 'valid_supported_topology' if continuous else 'incomplete'
    return {'valid':continuous,'status':status,'errors':errors[:100],'missingAtoms':max(0,missing_atoms),'missingBonds':max(0,missing_bonds),'unassignedAtoms':unmapped,'atomCount':len(atoms),'bondCount':len(bonds),'peptideBonds':len(links),'sequence':''.join(r['one'] for r in residues),'geometryStatus':'educational_board_template_locked','stereochemistry':'Pinned CCD template assignments and xyz are locked; board rotations do not mirror chemical geometry. No independent CIP assignment.','method':'Direct submitted graph correspondence to neutral CCD atoms/bonds, supported condensation and locked stereo; not sequence-only regeneration.'}

@lru_cache(maxsize=20)
def migration_layout(one):
    """Connectivity-aware educational layout, matching the new board's projection/relaxation.

    v1 had no atomic board coordinates. Keep its original tile state separately;
    never interpret decorative rotation as chemistry or edit the locked CCD xyz.
    """
    t=BY_ONE[one];atoms=t['atoms'];index={a['id']:i for i,a in enumerate(atoms)};n=len(atoms)
    best=None;best_score=-math.inf
    for k in range(18):
        ry=k*math.pi/9;rx=(k%3-1)*.7;projected=[]
        for a in atoms:
            x,y,z=a['xyz'];xx=x*math.cos(ry)+z*math.sin(ry);zz=-x*math.sin(ry)+z*math.cos(ry)
            projected.append([xx*30,(y*math.cos(rx)-zz*math.sin(rx))*30])
        score=sum(min(math.dist(projected[i],projected[j]),35) for i in range(n) for j in range(i+1,n))
        if score>best_score:best_score=score;best=projected
    p=best
    for _ in range(180):
        f=[[0.,0.] for _ in atoms]
        for i in range(n):
            for j in range(i+1,n):
                dx=p[i][0]-p[j][0];dy=p[i][1]-p[j][1];d=max(1,math.hypot(dx,dy))
                if d<1.01:dx=dy=.7
                force=min(2,280/(d*d))
                for axis,delta in enumerate((dx,dy)):f[i][axis]+=delta/d*force;f[j][axis]-=delta/d*force
        for b in t['bonds']:
            i=index[b['a']];j=index[b['b']];dx=p[j][0]-p[i][0];dy=p[j][1]-p[i][1];d=max(.1,math.hypot(dx,dy))
            target=32 if 'H' in (atoms[i]['element'],atoms[j]['element']) else 44;force=(d-target)*.065
            for axis,delta in enumerate((dx,dy)):f[i][axis]+=delta/d*force;f[j][axis]-=delta/d*force
        for i in range(n):
            for axis in (0,1):p[i][axis]+=max(-3,min(3,f[i][axis]))
    ca=p[index['CA']];nit=p[index['N']];car=p[index['C']];angle=math.atan2(car[1]-nit[1],car[0]-nit[0])
    return {a['id']:[(p[i][0]-ca[0])*math.cos(angle)+(p[i][1]-ca[1])*math.sin(angle),-(p[i][0]-ca[0])*math.sin(angle)+(p[i][1]-ca[1])*math.cos(angle)] for i,a in enumerate(atoms)}

def from_v1(state):
    state_validate(state);s={'schemaVersion':2,'residues':[],'atoms':[],'bonds':[],'challengeId':'free','mode':'free','completed':[],'legacyCompleted':copy.deepcopy(state.get('completed',[])),'name':state.get('name','Untitled peptide'),'notes':state.get('notes',''),'assisted':False,'legacy':copy.deepcopy(state)}
    legacy_ids=['v1-first-connection','v1-small-constellation','v1-sulfur-rings','v1-proline-turn','v1-repair-chain']
    s['legacyChallengeIds']=[legacy_ids[i] for i in state.get('completed',[]) if isinstance(i,int) and 0<=i<len(legacy_ids)]
    for key in ['savedId','savedRevision','sourceRecordId']:
        if key in state:s[key]=state[key]
    for i,r in enumerate(state['blocks']):s['residues'].append({'id':r['id'],'one':r['one'],'position':[i*280+160,220],'rotation':0})
    links=[(l['from'],l['to']) for l in state.get('links',[])];wanted,wb=expected(s['residues'],links);positions={r['id']:r['position'] for r in s['residues']}
    for (rid,name),a in wanted.items():
        pos=positions[rid];one=next(r['one'] for r in s['residues'] if r['id']==rid);xy=migration_layout(one)[name]
        s['atoms'].append({'id':atom_id(rid,name),'residueId':rid,'templateAtom':name,'element':a['element'],'charge':a['charge'],'stereo':a['stereo'],'xyz':copy.deepcopy(a['xyz']),'board':[pos[0]+xy[0],pos[1]+xy[1]]})
    for pair,(order,aromatic,kind) in wb.items():
        refs=sorted(pair,key=lambda r:(next(i for i,v in enumerate(s['residues']) if v['id']==r[0]),r[1]))
        if kind=='peptide': refs=[(next(l for l in links if frozenset([(l[0],'C'),(l[1],'N')])==pair)[0],'C'),(next(l for l in links if frozenset([(l[0],'C'),(l[1],'N')])==pair)[1],'N')]
        s['bonds'].append({'a':atom_id(*refs[0]),'b':atom_id(*refs[1]),'order':order,'aromatic':aromatic,'kind':kind})
    envelope(s);return s

class MolecularDrafts:
    def __init__(self, service):
        self.s=service;self.db=service.db
        from peptides import Peptides
        Peptides(service)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS molecular_drafts(context TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS molecular_migrations(context TEXT PRIMARY KEY,schema_version INTEGER NOT NULL,original TEXT NOT NULL,source_revision INTEGER NOT NULL,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY,applied TEXT NOT NULL);''')
        self.db.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?)',('arcade-graph-v2',now()));self.db.commit()
    def context(self,p):
        context=p.get('projectId') or 'local-practice'
        if context!='local-practice':self.s.project(context)
        return context
    def load(self,p):
        context=self.context(p)
        r=self.db.execute('SELECT * FROM molecular_drafts WHERE context=?',(context,)).fetchone()
        if r:
            state=json.loads(r['state']);envelope(state)
            return {**dict(r),'state':state}
        old=self.db.execute("SELECT * FROM arcade_progress WHERE project_id=? AND workspace='arcade'",(context,)).fetchone()
        if old:
            try: state=from_v1(json.loads(old['state']))
            except (ValueError,TypeError,KeyError) as e: return {'revision':0,'state':None,'migrationError':str(e),'originalRetained':True}
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('INSERT OR IGNORE INTO molecular_migrations VALUES(?,?,?,?,?)',(context,2,old['state'],old['revision'],now()))
                self.db.execute('INSERT OR IGNORE INTO molecular_drafts VALUES(?,?,?,?)',(context,1,json.dumps(state),now()))
            return self.load(p)
        return {'revision':0,'state':None}
    def save(self,p):
        context=self.context(p);envelope(p['state']);date=now()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE');old=self.db.execute('SELECT revision FROM molecular_drafts WHERE context=?',(context,)).fetchone();revision=old[0] if old else 0
            if p.get('revision')!=revision:raise ValueError('Draft changed in another window. Recover your local snapshot or reopen the latest draft; it was not overwritten.')
            self.db.execute('INSERT OR REPLACE INTO molecular_drafts VALUES(?,?,?,?)',(context,revision+1,json.dumps(p['state'],allow_nan=False),date))
        return {'revision':revision+1,'updated':date,'validation':validate(p['state'])}

ACTIONS={'molecular_draft_load','molecular_draft_save','molecular_graph_validate','molecular_draft_import'}
def dispatch(service,action,p):
    if action=='molecular_graph_validate':return validate(p['state'])
    if action=='molecular_draft_import':
        path=pathlib.Path(p['path'])
        if path.suffix.lower()!='.json' or path.stat().st_size>MAX_BYTES:raise ValueError('Choose a v2 molecular JSON draft of at most 1.8 MB.')
        state=json.loads(path.read_text());envelope(state)
        return {'state':state,'validation':validate(state)}
    drafts=MolecularDrafts(service)
    return drafts.load(p) if action=='molecular_draft_load' else drafts.save(p)
