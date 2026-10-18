"""Versioned protein-interface analysis, with optional native ChimeraX chemistry.
Coordinates are never modified. All cutoffs, assumptions and unavailable metrics are persisted.
"""
import collections, csv, datetime, hashlib, io, itertools, json, math, os, pathlib, random, re, subprocess, sys, uuid
from peptides import TEMPLATES, BY_ONE
from functools import lru_cache

VERSION='1.1.0'
_CHILDREN=[]
ACTIONS={'intelligence_inspect','intelligence_assign','intelligence_start','intelligence_tasks','intelligence_result','intelligence_cancel','intelligence_hotspots','intelligence_candidates','intelligence_candidate_save','intelligence_scramble','intelligence_compare','intelligence_export','intelligence_confidence_import','intelligence_screen','intelligence_resume','intelligence_evidence','intelligence_prioritize','intelligence_overlay','intelligence_auto','intelligence_register_chains','intelligence_prepare','intelligence_overlay_mix'}
CODES={c['code']:c['one'] for c in TEMPLATES['components']}
# Bondi (1964), elemental radii, Å. Unknown elements are refused for SASA/clashes.
RADII={'H':1.20,'D':1.20,'C':1.70,'N':1.55,'O':1.52,'F':1.47,'P':1.80,'S':1.80,'CL':1.75,'BR':1.85,'I':1.98,'SE':1.90}
DEFAULTS={'contact':4.0,'clash':0.6,'severe':1.0,'probe':1.4,'spherePoints':240,'hotspot':6.0,'salt':4.0,'hydrophobic':4.5,'hbondDA':3.5,'hbondHA':2.5,'hbondAngle':120.0,'clusterRmsd':5.0,'radiusMethod':'bondi','hbAllowance':0.0}
ROLES={'target','candidate','control','additional','other'}
LIMITATIONS=[
 'Measurements describe the supplied coordinate model, not experimentally demonstrated binding, inhibition or affinity.',
 'Default analysis uses one coordinate model and one residue-level alternate conformer (highest summed occupancy); zero-occupancy atoms and waters are omitted.',
 'Distances are in Å and areas in Å². Contacts include heavy atoms only; unique residue pairs are counted separately.',
 'Clash radii follow the saved radiusMethod: elemental Bondi, or source-specific ChimeraX default chemical radii. Native hydrogen-bond allowance follows the saved hbAllowance setting; offline Bondi mode uses zero. Cross-partner covalent links are not automatically excluded; native-default clash counts can differ.',
 'Standard-residue chemistry assumes neutral pH Lys/Arg positive and Asp/Glu negative. Histidine protonation is unspecified. No hydrogens are added during analysis; optional preparation creates a separate derived structure.',
 'Only explicit-hydrogen donor–H–acceptor geometry is called a potential hydrogen bond; missing-H approaches remain tentative. Electrostatic complementarity is unavailable without validated charge/protonation preparation.',
 'Shrake–Rupley SASA uses finite Fibonacci sphere sampling and heavy atoms; inspect convergence before using absolute areas. Interface area is half the total SASA loss.',
 'Observed sequence gaps do not establish missing biological residues. Full-length/mature identity requires a verified reference sequence and numbering metadata.'
]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def uid():return str(uuid.uuid4())
def sha(data):return hashlib.sha256(data).hexdigest()
def dist(a,b):return math.dist(a,b)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return [x-y for x,y in zip(a,b)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def angle(a,b,c):
 u,v=sub(a,b),sub(c,b);n=math.sqrt(dot(u,u)*dot(v,v))
 return math.degrees(math.acos(max(-1,min(1,dot(u,v)/n)))) if n>1e-12 else None

def cif_tokens(text):
 """CIF 1.1 lexical rules: quote ends only at whitespace; semicolon text at column 1."""
 i=0;n=len(text)
 while i<n:
  if text[i].isspace():i+=1;continue
  if text[i]=='#':
   end=text.find('\n',i);i=n if end<0 else end+1;continue
  if text[i]==';' and (i==0 or text[i-1]=='\n'):
   end=text.find('\n;',i+1)
   if end<0:raise ValueError('Unterminated CIF text field.')
   yield text[i+1:end];i=end+2;continue
  if text[i] in "'\"":
   q=text[i];start=i+1;i+=1
   while i<n and not(text[i]==q and (i+1==n or text[i+1].isspace())):i+=1
   if i==n:raise ValueError('Unterminated CIF quoted field.')
   yield text[start:i];i+=1;continue
  start=i
  while i<n and not text[i].isspace():i+=1
  yield text[start:i]

def atom_rows(text,fmt):
 if fmt=='pdb':
  model='1'
  for l in text.splitlines():
   if l.startswith('MODEL '):model=l[10:14].strip() or '1'
   if not l.startswith(('ATOM  ','HETATM')):continue
   if len(l)<54:raise ValueError('Truncated PDB atom row.')
   name=l[12:16].strip();element=l[76:78].strip().upper() if len(l)>=78 else ''
   if not element:
    element=re.sub('[^A-Za-z]','',name)[:1].upper() # protein ATOM convention; ambiguous hetero is refused
    if l.startswith('HETATM') and name not in ('O','H1','H2'):element='UNKNOWN'
   yield {'model':model,'chain':l[21:22].strip() or '_','labelChain':l[21:22].strip() or '_','num':int(l[22:26]),'label':None,'ins':l[26:27].strip(),'resname':l[17:20].strip(),'name':name,'alt':l[16:17].strip(),'xyz':[float(l[30:38]),float(l[38:46]),float(l[46:54])],'occupancy':float(l[54:60].strip() or 1),'bfactor':float(l[60:66].strip()) if l[60:66].strip() else None,'element':element,'group':l[:6].strip()}
 else:
  tokens=list(cif_tokens(text));i=0
  while i<len(tokens):
   if tokens[i]!='loop_':i+=1;continue
   i+=1;headers=[]
   while i<len(tokens) and tokens[i].startswith('_'):headers.append(tokens[i]);i+=1
   if not headers:raise ValueError('CIF loop has no columns.')
   rows=[]
   while i<len(tokens) and not(tokens[i].startswith(('_','data_','save_')) or tokens[i] in ('loop_','stop_','global_')):
    if i+len(headers)>len(tokens):raise ValueError('Truncated CIF loop.')
    rows.append(tokens[i:i+len(headers)]);i+=len(headers)
   if not headers[0].startswith('_atom_site.'):continue
   for row in rows:
    d={h.split('.',1)[1]:v for h,v in zip(headers,row)}
    def get(*keys,default=''):
     return next((d[k] for k in keys if k in d and d[k] not in ('.','?')),default)
    yield {'model':get('pdbx_PDB_model_num',default='1'),'chain':get('auth_asym_id','label_asym_id',default='_'),'labelChain':get('label_asym_id','auth_asym_id',default='_'),'num':int(get('auth_seq_id','label_seq_id',default='0')),'label':int(get('label_seq_id')) if get('label_seq_id') else None,'ins':get('pdbx_PDB_ins_code'),'resname':get('auth_comp_id','label_comp_id'),'name':get('auth_atom_id','label_atom_id'),'alt':get('label_alt_id'),'xyz':[float(get('Cartn_'+c)) for c in 'xyz'],'occupancy':float(get('occupancy',default='1')),'bfactor':float(get('B_iso_or_equiv')) if get('B_iso_or_equiv') else None,'element':get('type_symbol',default='UNKNOWN').upper(),'group':get('group_PDB',default='ATOM')}

def parse_structure(text,fmt,model=None):
 raw=list(atom_rows(text,fmt))
 if not raw:raise ValueError('No coordinate atoms found.')
 if len(raw)>200000:raise ValueError('Analysis is limited to 200,000 coordinate atoms.')
 models=list(dict.fromkeys(a['model'] for a in raw));model=str(model or models[0])
 if model not in models:raise ValueError('Requested coordinate model is missing.')
 raw=[a for a in raw if a['model']==model and a['occupancy']>0 and a['resname'] not in ('HOH','WAT','DOD')]
 if any(not all(math.isfinite(v) for v in a['xyz']+[a['occupancy']]+([] if a['bfactor'] is None else [a['bfactor']])) for a in raw):raise ValueError('Nonfinite coordinate or occupancy.')
 alternates=collections.defaultdict(collections.Counter)
 for a in raw:
  if a['alt']:alternates[(a['chain'],a['num'],a['ins'])][a['alt']]+=a['occupancy']
 chosen={k:sorted(v,key=lambda x:(-v[x],x))[0] for k,v in alternates.items()}
 atoms=[];residues={};seen=set()
 for a in raw:
  rk=(a['chain'],a['num'],a['ins'])
  if a['alt'] and a['alt']!=chosen[rk]:continue
  rid=json.dumps(list(rk),separators=(',',':'));a['residue']=rid;a['id']=len(atoms)
  ident=(rid,a['name'])
  if ident in seen:raise ValueError('Duplicate atom identity; split ambiguous chains/models before analysis.')
  seen.add(ident);atoms.append(a)
  r=residues.setdefault(rid,{'id':rid,'chain':a['chain'],'labelChain':a['labelChain'],'num':a['num'],'label':a['label'],'ins':a['ins'],'name':a['resname'],'one':CODES.get(a['resname'],'X'),'atoms':[]})
  if r['name']!=a['resname']:raise ValueError('Microheterogeneous residue identity requires explicit preparation.')
  r['atoms'].append(a['id'])
 chains=[];warnings=[]
 for r in residues.values():
  names={atoms[i]['name'] for i in r['atoms']};r['polymer']=r['one']!='X' or r['label'] is not None or {'N','CA','C'}.issubset(names)
 if any(r['polymer'] and r['one']=='X' for r in residues.values()):warnings.append('Unrecognized polymer residues are X in observed sequences. Automatic correspondence is unavailable until identities are resolved; chemistry screens cover supported standard residues only.')
 for chain in dict.fromkeys(a['chain'] for a in atoms):
  rs=[r for r in residues.values() if r['chain']==chain];protein=[r for r in rs if r['one']!='X'];missing=[];gaps=[];geometry=[];unusual=[]
  for r in protein:
   expected={a['id'] for a in BY_ONE[r['one']]['atoms'] if a['element']!='H' and not a['leaving'] and a['id']!='OXT'}
   absent=sorted(expected-{atoms[i]['name'] for i in r['atoms']})
   if absent:missing.append({'residue':r['id'],'atoms':absent})
   observed={atoms[i]['name']:atoms[i] for i in r['atoms']};template=BY_ONE[r['one']];ideal={a['id']:a for a in template['atoms']}
   for bond in template['bonds']:
    a,b=bond['a'],bond['b']
    if a not in observed or b not in observed or ideal[a]['element']=='H' or ideal[b]['element']=='H':continue
    measured=dist(observed[a]['xyz'],observed[b]['xyz']);expected_length=dist(ideal[a]['xyz'],ideal[b]['xyz'])
    if abs(measured-expected_length)>.20:unusual.append({'residue':r['id'],'a':a,'b':b,'distance':measured,'ccdIdeal':expected_length,'criterion':'heavy-atom component bond length deviates >0.20 Å from wwPDB CCD ideal geometry; no minimization performed'})
  for prev,r in zip(protein,protein[1:]):
   lookup=lambda rr,n:next((atoms[i] for i in rr['atoms'] if atoms[i]['name']==n),None)
   c,n=lookup(prev,'C'),lookup(r,'N')
   if r['num']>prev['num']+1:gaps.append({'from':prev['id'],'to':r['id'],'numberingGap':r['num']-prev['num']-1})
   if c and n and not 1.1<=dist(c['xyz'],n['xyz'])<=1.6:geometry.append({'from':prev['id'],'to':r['id'],'peptideCN':dist(c['xyz'],n['xyz']),'criterion':'C–N outside 1.1–1.6 Å; may be a genuine chain break'})
  chains.append({'id':chain,'labelIds':sorted({r['labelChain'] for r in rs}),'sequence':''.join(r['one'] for r in rs if r['polymer']),'residues':len(rs),'proteinResidues':sum(r['polymer'] for r in rs),'atoms':sum(len(r['atoms']) for r in rs),'missingAtoms':missing,'numberingGaps':gaps,'discontinuities':geometry,'unusualBonds':unusual,'composition':dict(collections.Counter(r['name'] for r in rs))})
 if chosen:warnings.append('Alternate conformers selected by residue summed occupancy; ties resolved lexicographically.')
 return {'atoms':atoms,'residues':list(residues.values()),'chains':chains,'models':models,'model':model,'warnings':warnings}

class Grid:
 def __init__(self,atoms,size):
  self.size=size;self.cells=collections.defaultdict(list)
  for a in atoms:self.cells[self.key(a['xyz'])].append(a)
 def key(self,p):return tuple(math.floor(v/self.size) for v in p)
 def near(self,p,r):
  key=self.key(p);n=math.ceil(r/self.size)
  for offset in itertools.product(range(-n,n+1),repeat=3):yield from self.cells.get(tuple(key[i]+offset[i] for i in range(3)),())

def settings(raw):
 s={**DEFAULTS,**raw}
 ranges={'contact':(1,20),'clash':(0,3),'severe':(0,4),'probe':(0.5,3),'spherePoints':(60,2000),'hotspot':(1,30),'salt':(2,6),'hydrophobic':(2,6),'hbondDA':(2,4),'hbondHA':(1,3),'hbondAngle':(90,180),'clusterRmsd':(0.1,30),'hbAllowance':(0,1)}
 for k,(low,high) in ranges.items():
  if type(s[k]) not in (float,int) or not math.isfinite(s[k]) or not low<=s[k]<=high:raise ValueError('Invalid analysis setting: '+k)
 if s['radiusMethod']=='bondi' and s['hbAllowance']!=0:raise ValueError('Hydrogen-bond allowance requires native chemical atom typing.')
 if s['radiusMethod'] not in ('bondi','chimerax-default'):raise ValueError('Unsupported van der Waals radius method.')
 if type(s['spherePoints']) is not int or s['severe']<s['clash']:raise ValueError('Sphere samples must be an integer; severe overlap must be ≥ clash cutoff.')
 return s

def map_sequence(reference,observed):
 """Exact fragment if unique; otherwise global NW with optimal-path ambiguity guard."""
 reference=re.sub(r'\s+','',reference).upper();observed=observed.upper()
 if not reference or set(reference)-set(CODES.values()) or not observed:raise ValueError('Supply canonical reference and observed protein sequences.')
 if 'X' in observed:return {'state':'unavailable','method':'unrecognized observed polymer identity; resolve modified/unknown residues before automatic correspondence','identity':None,'positions':{}}
 hits=[i for i in range(len(reference)-len(observed)+1) if reference[i:i+len(observed)]==observed]
 if len(hits)==1:return {'state':'verified','method':'unique exact fragment','identity':1.0,'positions':{i+1:hits[0]+i+1 for i in range(len(observed))}}
 if len(hits)>1:return {'state':'ambiguous','method':'repeated exact fragment','positions':{},'occurrences':[i+1 for i in hits]}
 n,m=len(reference),len(observed)
 if n*m>2000000:raise ValueError('Reference alignment exceeds bounded size; provide a verified fragment.')
 dp=[[0]*(m+1) for _ in range(n+1)];paths=[[0]*(m+1) for _ in range(n+1)];paths[0][0]=1
 for i in range(1,n+1):dp[i][0]=-2*i;paths[i][0]=1
 for j in range(1,m+1):dp[0][j]=-2*j;paths[0][j]=1
 for i in range(1,n+1):
  for j in range(1,m+1):
   opts=[dp[i-1][j-1]+(2 if reference[i-1]==observed[j-1] else -1),dp[i-1][j]-2,dp[i][j-1]-2];best=max(opts);dp[i][j]=best
   paths[i][j]=min(2,sum(p for p,v in zip([paths[i-1][j-1],paths[i-1][j],paths[i][j-1]],opts) if v==best))
 i,j=n,m;positions={};matches=0
 while i and j:
  if dp[i][j]==dp[i-1][j-1]+(2 if reference[i-1]==observed[j-1] else -1):
   if reference[i-1]==observed[j-1]:positions[j]=i;matches+=1
   i-=1;j-=1
  elif dp[i][j]==dp[i-1][j]-2:i-=1
  else:j-=1
 identity=matches/m
 return {'state':'verified' if paths[n][m]==1 and identity>=0.9 else 'ambiguous','method':'global Needleman–Wunsch +2/−1/−2; unique optimum, ≥90% observed identity','identity':identity,'positions':positions if paths[n][m]==1 and identity>=0.9 else {}}

def sasa(atoms,samples,probe,check=lambda:None):
 if not atoms:return 0.0
 grid=Grid(atoms,4);points=[];gold=math.pi*(3-math.sqrt(5))
 for i in range(samples):
  y=1-2*(i+0.5)/samples;r=math.sqrt(1-y*y);points.append((r*math.cos(i*gold),y,r*math.sin(i*gold)))
 area=0.;maximum=max(RADII[a['element']]+probe for a in atoms)
 for index,a in enumerate(atoms):
  if index%40==0:check()
  r=RADII[a['element']]+probe
  near=[(b['xyz'],(RADII[b['element']]+probe)**2) for b in grid.near(a['xyz'],r+maximum) if b['id']!=a['id'] and dist(a['xyz'],b['xyz'])<r+RADII[b['element']]+probe]
  count=0
  if any(b['id']<a['id'] and dist(a['xyz'],b['xyz'])<1e-10 and abs(RADII[b['element']]-RADII[a['element']])<1e-10 for b in grid.near(a['xyz'],0)):
   continue
  for p in points:
   q=[a['xyz'][i]+r*p[i] for i in range(3)]
   if not any(sum((q[i]-c[i])**2 for i in range(3))<rr-1e-10 for c,rr in near):count+=1
  area+=4*math.pi*r*r*count/samples
 return area

def chemistry(a):
 r,n=a['resname'],a['name'];donor=False;acceptor=False
 if r not in CODES:return False,False
 if n=='N':donor=r!='PRO'
 if n in ('O','OXT'):acceptor=True
 donors={'LYS':{'NZ'},'ARG':{'NE','NH1','NH2'},'ASN':{'ND2'},'GLN':{'NE2'},'TRP':{'NE1'},'SER':{'OG'},'THR':{'OG1'},'TYR':{'OH'}}
 acceptors={'ASP':{'OD1','OD2'},'GLU':{'OE1','OE2'},'ASN':{'OD1'},'GLN':{'OE1'},'SER':{'OG'},'THR':{'OG1'},'TYR':{'OH'}}
 return donor or n in donors.get(r,set()),acceptor or n in acceptors.get(r,set())

def interactions(a,b,d,structure,s):
 out=[]
 pos=lambda x:(x['resname']=='LYS' and x['name']=='NZ') or (x['resname']=='ARG' and x['name'] in ('NE','NH1','NH2'))
 neg=lambda x:(x['resname']=='ASP' and x['name'] in ('OD1','OD2')) or (x['resname']=='GLU' and x['name'] in ('OE1','OE2'))
 if d<=s['salt'] and ((pos(a) and neg(b)) or (pos(b) and neg(a))):out.append({'type':'salt bridge','status':'tentative','criterion':'Lys/Arg charged N to Asp/Glu carboxyl O; neutral-pH assumption'})
 if d<=s['hydrophobic'] and all(x['element']=='C' and x['name'] not in ('C','CA') and x['resname'] in ('ALA','VAL','ILE','LEU','MET','PHE','TRP','TYR','PRO') for x in (a,b)):out.append({'type':'hydrophobic contact','status':'geometric','criterion':'non-backbone carbon in nonpolar/aromatic side chains'})
 for donor,acceptor in ((a,b),(b,a)):
  if not(chemistry(donor)[0] and chemistry(acceptor)[1] and d<=s['hbondDA']):continue
  template=BY_ONE[CODES[donor['resname']]]
  names={bond['b'] if bond['a']==donor['name'] else bond['a'] for bond in template['bonds'] if donor['name'] in (bond['a'],bond['b'])}
  hydrogens=[h for h in structure['atoms'] if h['residue']==donor['residue'] and h['element'] in ('H','D') and h['name'] in names and dist(h['xyz'],donor['xyz'])<1.4]
  if not hydrogens:out.append({'type':'polar approach','status':'tentative','angle':None,'criterion':'recognized donor/acceptor, missing explicit bonded hydrogen; not an established H-bond'})
  else:
   for h in hydrogens:
    ang=angle(donor['xyz'],h['xyz'],acceptor['xyz']);ha=dist(h['xyz'],acceptor['xyz'])
    if ang is not None and ha<=s['hbondHA'] and ang>=s['hbondAngle']:out.append({'type':'potential hydrogen bond','status':'geometric','hydrogen':h['id'],'angle':ang,'hydrogenAcceptor':ha,'criterion':'explicit template-bonded H; D–A, H–A and D–H–A cutoffs'})
 return out

def aromatic(structure,left,right):
 rings={'PHE':['CG','CD1','CE1','CZ','CE2','CD2'],'TYR':['CG','CD1','CE1','CZ','CE2','CD2'],'TRP':['CD2','CE2','CZ2','CH2','CZ3','CE3'],'HIS':['CG','ND1','CE1','NE2','CD2']};out=[]
 def ring(r):
  names=rings.get(r['name']);lookup={structure['atoms'][i]['name']:structure['atoms'][i] for i in r['atoms']}
  if not names or not all(n in lookup for n in names):return None
  xyz=[lookup[n]['xyz'] for n in names];center=[sum(p[i] for p in xyz)/len(xyz) for i in range(3)];normal=cross(sub(xyz[1],xyz[0]),sub(xyz[2],xyz[0]));length=math.sqrt(dot(normal,normal))
  if length<1e-6:return None
  normal=[v/length for v in normal]
  if max(abs(dot(sub(p,center),normal)) for p in xyz)>0.2:return None
  return center,normal
 for a in structure['residues']:
  ra=ring(a)
  if not ra:continue
  for b in structure['residues']:
   if not((a['chain'] in left and b['chain'] in right) or (a['chain'] in right and b['chain'] in left)):continue
   rb=ring(b)
   if rb and a['id']<b['id']:
    d=dist(ra[0],rb[0]);ang=math.degrees(math.acos(min(1,abs(dot(ra[1],rb[1])))))
    if d<=6 and (ang<=30 or ang>=60):out.append({'type':'aromatic interaction','distanceType':'ring-centroid','status':'tentative','a':a['atoms'][0],'b':b['atoms'][0],'residueA':a['id'],'residueB':b['id'],'distance':d,'planeAngle':ang,'criterion':'complete planar rings; centroid ≤6 Å; normals ≤30° or ≥60°; geometric screen only'})
   for i in b['atoms']:
    atom=structure['atoms'][i]
    if (atom['resname']=='LYS' and atom['name']=='NZ') or (atom['resname']=='ARG' and atom['name']=='CZ'):
     v=sub(atom['xyz'],ra[0]);d=math.sqrt(dot(v,v));projection=abs(dot(v,ra[1]));lateral=math.sqrt(max(0,d*d-projection**2))
     if d<=6 and projection>=2 and lateral<=2:out.append({'type':'cation–π approach','distanceType':'cation-centroid','status':'tentative','a':a['atoms'][0],'b':i,'residueA':a['id'],'residueB':b['id'],'distance':d,'criterion':'cation centroid ≤6 Å, normal height ≥2 Å, lateral offset ≤2 Å'})
 return out

def analyze(structure,assignments,raw_settings,hotspots=None,check=lambda:None,progress=lambda x:None):
 s=settings(raw_settings);left={c for c,v in assignments.items() if v.get('role')=='target'};right={c for c,v in assignments.items() if v.get('role') in ('candidate','control')}
 if not left or not right or left&right:raise ValueError('Explicitly assign at least one target and one candidate/control chain.')
 if (left|right)-{c['id'] for c in structure['chains']}:raise ValueError('Assigned chain is not present.')
 heavy=[a for a in structure['atoms'] if a['element'] not in ('H','D')];a_atoms=[a for a in heavy if a['chain'] in left];b_atoms=[a for a in heavy if a['chain'] in right]
 if not a_atoms or not b_atoms:raise ValueError('Both partners need observed heavy atoms.')
 grid=Grid(b_atoms,4);cutoff=max(s['contact'],s['salt'],s['hydrophobic'],s['hbondDA'],4.5);contacts=[];clashes=[];chemical=[];pairs={};unknown=set()
 progress('Calculating heavy-atom contacts and interaction geometry')
 for i,a in enumerate(a_atoms):
  if i%100==0:check()
  for b in grid.near(a['xyz'],cutoff):
   d=dist(a['xyz'],b['xyz'])
   if d>cutoff:continue
   record={'a':a['id'],'b':b['id'],'residueA':a['residue'],'residueB':b['residue'],'distance':d}
   if d<=s['contact']:
    contacts.append(record);key=(a['residue'],b['residue']);entry=pairs.setdefault(key,{**record,'atomPairs':0});entry['atomPairs']+=1
    if d<entry['distance']:entry.update(record)
   if (a.get('vdw') is not None or a['element'] in RADII) and (b.get('vdw') is not None or b['element'] in RADII):
    overlap=a.get('vdw',RADII.get(a['element'],0))+b.get('vdw',RADII.get(b['element'],0))-d
    if overlap>=s['clash']:clashes.append({**record,'overlap':overlap,'severity':'severe' if overlap>=s['severe'] else 'moderate'})
   else:unknown.update(x['element'] for x in (a,b) if x['element'] not in RADII)
   chemical.extend({**record,**x} for x in interactions(a,b,d,structure,s))
   if len(contacts)+len(clashes)+len(chemical)>250000:raise ValueError('Over 250,000 cross-partner records; isolate partners or reduce the cutoffs.')
 chemical.extend(aromatic(structure,left,right));clashes.sort(key=lambda v:-v['overlap']);contacts.sort(key=lambda v:v['distance'])
 mappings={}
 for chain,v in assignments.items():
  if v.get('reference'):
   c=next(c for c in structure['chains'] if c['id']==chain);mapped=map_sequence(v['reference'],c['sequence']);rs=[r for r in structure['residues'] if r['chain']==chain and r.get('polymer',r['one']!='X')]
   mapped['residues']=[{'structure':r['id'],'observedPosition':i+1,'referencePosition':mapped['positions'].get(i+1),'originalNumber':mapped['positions'].get(i+1)+int(v.get('referenceStart',1))-1 if i+1 in mapped['positions'] else None} for i,r in enumerate(rs)];mappings[chain]=mapped
 progress('Calculating hotspot proximity and sampled accessible surface area')
 hotspot_results=[]
 for hot in hotspots or []:
  rid=hot.get('residueId')
  if hot.get('referenceNumber') is not None and not (hot.get('manualConfirmed') is True and rid):
   mapping=mappings.get(hot['chain'],{});matches=[r for r in mapping.get('residues',[]) if r['originalNumber']==int(hot['referenceNumber'])] if mapping.get('state')=='verified' else []
   rid=matches[0]['structure'] if len(matches)==1 else None
  residue=next((r for r in structure['residues'] if r['id']==rid),None)
  if not residue or residue['chain'] not in left or (hot.get('aminoAcid') and hot['aminoAcid'] not in (residue['one'],residue['name'])):
   hotspot_results.append({**hot,'state':'mapping requires confirmation','minimum':None,'atomPairs':None,'peptideResidues':[]});continue
  distances=[(dist(structure['atoms'][i]['xyz'],b['xyz']),b) for i in residue['atoms'] if structure['atoms'][i]['element'] not in ('H','D') for b in b_atoms];close=[b for d,b in distances if d<=s['hotspot']]
  hotspot_results.append({**hot,'residueId':rid,'state':'within threshold' if close else 'not within threshold','minimum':min((d for d,b in distances),default=None),'atomPairs':len(close),'peptideResidues':sorted({b['residue'] for b in close}),'interactions':[x for x in chemical if x['residueA']==rid or x['residueB']==rid]})
 unknown.update(a['element'] for a in a_atoms+b_atoms if a['element'] not in RADII)
 area={'state':'unavailable','reason':'Unsupported elemental radii: '+', '.join(sorted(unknown))} if unknown else None
 if area is None:
  sa=sasa(a_atoms,s['spherePoints'],s['probe'],check);sb=sasa(b_atoms,s['spherePoints'],s['probe'],check);sab=sasa(a_atoms+b_atoms,s['spherePoints'],s['probe'],check);loss=sa+sb-sab
  area={'state':'calculated','targetSasa':sa,'peptideSasa':sb,'complexSasa':sab,'totalLoss':loss,'interfaceArea':loss/2,'units':'Å²','radii':'Bondi elemental; independent of clash radiusMethod','method':'Shrake–Rupley; Fibonacci sphere points; isolated partner SASA sum minus partner-complex SASA; conventional interface value = loss/2'}
 interface_ids={x for p in pairs for x in p};polar=sum(1 for p in contacts if any(structure['atoms'][p[k]]['element'] in ('N','O','S') for k in ('a','b')))
 graph=collections.defaultdict(set)
 for interaction in chemical:
  if interaction['type']=='potential hydrogen bond':graph[interaction['residueA']].add(interaction['residueB']);graph[interaction['residueB']].add(interaction['residueA'])
 networks=[];seen=set()
 for node in sorted(graph):
  if node in seen:continue
  nodes=set();pending=[node]
  while pending:
   current=pending.pop()
   if current in nodes:continue
   nodes.add(current);seen.add(current);pending.extend(graph[current]-nodes)
  networks.append({'residues':sorted(nodes),'interactions':[x for x in chemical if x['type']=='potential hydrogen bond' and x['residueA'] in nodes and x['residueB'] in nodes],'criterion':'connected components of explicit-hydrogen geometric cross-partner H-bond residue graph; not an energetic network'})
 return {'version':VERSION,'hydrogenBondNetworks':networks,'structure':structure,'assignments':assignments,'settings':s,'contacts':contacts,'residuePairs':list(pairs.values()),'clashes':clashes,'interactions':chemical,'hotspots':hotspot_results,'mappings':mappings,'surface':area,'summary':{'atomicContacts':len(contacts),'uniqueResiduePairs':len(pairs),'interfaceResidues':len(interface_ids),'atomicClashes':len(clashes),'clashingResiduePairs':len({(c['residueA'],c['residueB']) for c in clashes}),'severeClashes':sum(c['severity']=='severe' for c in clashes),'polarAtomContacts':polar,'nonpolarAtomContacts':len(contacts)-polar,'interfaceComposition':dict(collections.Counter(r['name'] for r in structure['residues'] if r['id'] in interface_ids))},'limitations':LIMITATIONS,'unavailable':{'electrostaticComplementarity':'Requires validated charges, protonation and dielectric treatment','bindingAffinity':'No free-energy calculation performed'},'created':now()}

def fit(moving,fixed):
 """Horn quaternion least-squares rigid fit, symmetric Jacobi eigensolver (no reflection)."""
 if len(moving)!=len(fixed) or len(moving)<3:raise ValueError('Rigid alignment requires at least three corresponding atoms.')
 centers=lambda points:[sum(p[i] for p in points)/len(points) for i in range(3)]
 cm,cf=centers(moving),centers(fixed);m=[sub(p,cm) for p in moving];f=[sub(p,cf) for p in fixed]
 if max(math.sqrt(dot(cross(m[i],m[j]),cross(m[i],m[j]))) for i,j in itertools.combinations(range(min(30,len(m))),2))<1e-8:raise ValueError('Collinear alignment atoms do not determine orientation.')
 s=[[sum(a[i]*b[j] for a,b in zip(m,f)) for j in range(3)] for i in range(3)];xx,xy,xz=s[0];yx,yy,yz=s[1];zx,zy,zz=s[2]
 n=[[xx+yy+zz,yz-zy,zx-xz,xy-yx],[yz-zy,xx-yy-zz,xy+yx,zx+xz],[zx-xz,xy+yx,-xx+yy-zz,yz+zy],[xy-yx,zx+xz,yz+zy,-xx-yy+zz]];v=[[float(i==j) for j in range(4)] for i in range(4)]
 for _ in range(100):
  p,q=max(itertools.combinations(range(4),2),key=lambda ij:abs(n[ij[0]][ij[1]]))
  if abs(n[p][q])<1e-12:break
  phi=0.5*math.atan2(2*n[p][q],n[q][q]-n[p][p]);c=math.cos(phi);sn=math.sin(phi);ap,aq=n[p][p],n[q][q];off=n[p][q]
  n[p][p]=c*c*ap-2*sn*c*off+sn*sn*aq;n[q][q]=sn*sn*ap+2*sn*c*off+c*c*aq;n[p][q]=n[q][p]=0
  for k in range(4):
   if k not in (p,q):a,b=n[k][p],n[k][q];n[k][p]=n[p][k]=c*a-sn*b;n[k][q]=n[q][k]=sn*a+c*b
   a,b=v[k][p],v[k][q];v[k][p]=c*a-sn*b;v[k][q]=sn*a+c*b
 k=max(range(4),key=lambda i:n[i][i]);w,x,y,z=[v[i][k] for i in range(4)]
 r=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]];t=[cf[i]-dot(r[i],cm) for i in range(3)]
 transform={'rotation':r,'translation':t};value=math.sqrt(sum(dist(apply_fit(p,transform),q)**2 for p,q in zip(moving,fixed))/len(moving))
 return {**transform,'rmsd':value,'atoms':len(moving)}
def apply_fit(p,f):return [dot(row,p)+f['translation'][i] for i,row in enumerate(f['rotation'])]

@lru_cache(maxsize=128)
def sequence_pairs(reference,moving):
 if not reference or not moving or 'X' in reference+moving:return ()
 if reference==moving:return tuple((i+1,i+1) for i in range(len(reference)))
 mapping=map_sequence(reference,moving)
 if mapping['state']=='verified':return tuple(sorted((r,m) for m,r in mapping['positions'].items()))
 reverse=map_sequence(moving,reference)
 if reverse['state']=='verified':return tuple(sorted((r,m) for r,m in reverse['positions'].items()))
 return ()

def chain_permutations(reference,moving,roles):
 rc=[c for c in reference['structure']['chains'] if reference['assignments'].get(c['id'],{}).get('role') in roles];mc=[c for c in moving['structure']['chains'] if moving['assignments'].get(c['id'],{}).get('role') in roles]
 if len(rc)!=len(mc) or not rc:raise ValueError('Comparison partners must have the same chain composition.')
 options=[[c['id'] for c in mc if sequence_pairs(r['sequence'],c['sequence'])] for r in rc]
 count=math.prod(len(o) for o in options)
 if count>720:raise ValueError('More than 720 chain assignments; provide an explicit nonsymmetric subset.')
 maps=[dict(zip([r['id'] for r in rc],p)) for p in itertools.product(*options) if len(set(p))==len(p)]
 if not maps:raise ValueError('Partner sequences have no unambiguous high-identity correspondence. Confirm biological identities/numbering before quantitative comparison.')
 return maps

def correspondence(reference,moving,mapping,names,selected=None):
 fixed=[];mobile=[];ids=[]
 for rc,mc in mapping.items():
  rr=[r for r in reference['structure']['residues'] if r['chain']==rc and r['one']!='X'];mr=[r for r in moving['structure']['residues'] if r['chain']==mc and r['one']!='X']
  for ri,mi in sequence_pairs(''.join(r['one'] for r in rr),''.join(r['one'] for r in mr)):
   a,b=rr[ri-1],mr[mi-1]
   if selected and a['id'] not in selected:continue
   ra={reference['structure']['atoms'][i]['name']:reference['structure']['atoms'][i] for i in a['atoms']};ma={moving['structure']['atoms'][i]['name']:moving['structure']['atoms'][i] for i in b['atoms']}
   for n in sorted(names & ra.keys() & ma.keys()):fixed.append(ra[n]['xyz']);mobile.append(ma[n]['xyz']);ids.append((a['id'],b['id']))
 return mobile,fixed,ids

def compare_pair(reference,moving,method='ca',selected=None):
 names={'CA'} if method=='ca' else {'N','CA','C','O'}
 if method not in ('ca','backbone','interface','ranges'):raise ValueError('Unsupported alignment method.')
 if method=='interface':selected={p['residueA'] for p in reference['residuePairs']}
 if method=='ranges' and not selected:raise ValueError('Choose reference target residues for range alignment.')
 fits=[]
 for mapping in chain_permutations(reference,moving,{'target'}):
  mobile,fixed,ids=correspondence(reference,moving,mapping,names,selected);alignment=fit(mobile,fixed);fits.append((alignment['rmsd'],mapping,alignment))
 fits.sort(key=lambda x:(x[0],str(x[1])));best,mapping,alignment=fits[0];equivalent=[m for r,m,f in fits if abs(r-best)<0.01]
 # Target fit is selected solely by target geometry. Symmetric alternatives are reported explicitly.
 peptide_maps=chain_permutations(reference,moving,{'candidate','control'});pm=peptide_maps[0]
 if len(peptide_maps)>1:raise ValueError('Multiple identical peptide chains require an explicit correspondence before peptide RMSD.')
 metrics={}
 for label,n in [('ca',{'CA'}),('backbone',{'N','CA','C','O'})]:
  mp,fp,_=correspondence(reference,moving,pm,n)
  metrics[label+'PositionalRmsd']=math.sqrt(sum(dist(apply_fit(p,alignment),q)**2 for p,q in zip(mp,fp))/len(mp)) if mp else None
  metrics[label+'Atoms']=len(mp)
  try:metrics[label+'InternalRmsd']=fit(mp,fp)['rmsd']
  except ValueError:metrics[label+'InternalRmsd']=None
 mp,fp,_=correspondence(reference,moving,pm,{'CA'});metrics['centroidDisplacement']=dist([sum(apply_fit(p,alignment)[i] for p in mp)/len(mp) for i in range(3)],[sum(p[i] for p in fp)/len(fp) for i in range(3)]) if mp else None
 fullmap={**mapping,**pm};resmap={}
 for rc,mc in fullmap.items():
  rr=[r for r in reference['structure']['residues'] if r['chain']==rc and r['one']!='X'];mr=[r for r in moving['structure']['residues'] if r['chain']==mc and r['one']!='X']
  resmap.update({mr[mi-1]['id']:rr[ri-1]['id'] for ri,mi in sequence_pairs(''.join(r['one'] for r in rr),''.join(r['one'] for r in mr))})
 one={(x['residueA'],x['residueB']) for x in reference['residuePairs']};two={(resmap.get(x['residueA'],'unmapped:'+x['residueA']),resmap.get(x['residueB'],'unmapped:'+x['residueB'])) for x in moving['residuePairs']}
 interface_res={r for pair in one for r in pair};im,ip,_=correspondence(reference,moving,fullmap,{'CA'},interface_res)
 metrics['interfaceRmsd']=math.sqrt(sum(dist(apply_fit(p,alignment),q)**2 for p,q in zip(im,ip))/len(im)) if im else None
 return {'reference':reference['id'],'moving':moving['id'],'method':method,'chainMapping':fullmap,'residueCorrespondence':resmap,'correspondenceMethod':'Exact sequences or unique exact-fragment / ≥90% identical unique global alignment; only identity-matched residues fitted. Unmapped contacts remain explicit.','symmetryEquivalentTargetMappings':equivalent,'symmetryWarning':'Target orientation is ambiguous within 0.01 Å RMSD; peptide pose metrics depend on the chosen target mapping.' if len(equivalent)>1 else None,'alignment':alignment,'metrics':metrics,'contactJaccard':len(one&two)/len(one|two) if one|two else None,'recurringContacts':[list(x) for x in sorted(one&two)],'mappedMovingContacts':[list(x) for x in sorted(two)],'clashes':{'reference':reference['summary']['atomicClashes'],'moving':moving['summary']['atomicClashes']},'hotspots':{'reference':reference['hotspots'],'moving':moving['hotspots']},'clashCriteriaWarning':'Clash criteria differ; compare contacts/poses, but reanalyse at identical clash settings before interpreting clash-count changes.' if any(reference.get('settings',{}).get(k)!=moving.get('settings',{}).get(k) for k in ('radiusMethod','hbAllowance','clash','severe')) else None}

class Lab:
 def __init__(self,service):
  self.s=service;self.root=service.root/'intelligence';self.root.mkdir(exist_ok=True)
  service.db.executescript('''CREATE TABLE IF NOT EXISTS intelligence_assignments(structure_id TEXT PRIMARY KEY,project_id TEXT,data TEXT,updated TEXT);
  CREATE TABLE IF NOT EXISTS intelligence_tasks(id TEXT PRIMARY KEY,project_id TEXT,kind TEXT,state TEXT,data TEXT,result TEXT,created TEXT,updated TEXT);
  CREATE TABLE IF NOT EXISTS intelligence_candidates(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,data TEXT,created TEXT);
  CREATE TABLE IF NOT EXISTS intelligence_hotspots(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,data TEXT,created TEXT);
  CREATE TABLE IF NOT EXISTS intelligence_confidence(structure_id TEXT PRIMARY KEY,project_id TEXT,data TEXT,updated TEXT);''')
 def dispatch(self,action,p):return getattr(self,action)(p)
 def record(self,id):
  row=self.s.db.execute("SELECT * FROM records WHERE id=? AND kind='structure'",(id,)).fetchone()
  if not row or not any(r['id']==id for r in self.s.library({})['records']):raise ValueError('Choose an available library structure.')
  record=dict(row);record['data']=json.loads(record['data']);asset=record['data']['asset'];path=(self.s.root/'assets'/asset).resolve()
  if pathlib.Path(asset).name!=asset or not path.is_relative_to((self.s.root/'assets').resolve()) or not path.is_file():raise ValueError('Structure asset is missing.')
  if path.stat().st_size>100*1024**2 or sha(path.read_bytes())!=record['data']['sha256']:raise ValueError('Coordinate checksum changed. Reimport as a new structure.')
  return record,path
 def assigned(self,id):
  row=self.s.db.execute('SELECT data FROM intelligence_assignments WHERE structure_id=?',(id,)).fetchone();return json.loads(row[0]) if row else {}
 def intelligence_inspect(self,p):
  record,path=self.record(p['structureId']);st=parse_structure(path.read_text(),record['data']['format'],p.get('model'))
  # No peptide role is guessed from a filename or chain length.
  return {'structure':st,'record':record,'assignments':self.assigned(record['id']),'confidence':self.confidence(record,st),'autoAnalyze':self.s.setting('intelligenceAuto:'+record['project_id'],{}).get('enabled',False)}
 def intelligence_assign(self,p):
  record,path=self.record(p['structureId']);st=parse_structure(path.read_text(),record['data']['format']);chains={c['id'] for c in st['chains']};assignments=p['assignments']
  if not isinstance(assignments,dict) or set(assignments)-chains or any(v.get('role') not in ROLES for v in assignments.values()):raise ValueError('Invalid explicit chain assignments.')
  for v in assignments.values():
   if len(str(v.get('identity','')))>200:raise ValueError('Chain identity is too long.')
   if v.get('reference') and (len(v['reference'])>5000 or set(re.sub(r'\s+','',v['reference']).upper())-set(CODES.values())):raise ValueError('Reference must contain canonical amino acids.')
   if not 1<=int(v.get('referenceStart',1))<=100000:raise ValueError('Invalid reference numbering start.')
  self.s.db.execute('INSERT OR REPLACE INTO intelligence_assignments VALUES(?,?,?,?)',(record['id'],record['project_id'],json.dumps(assignments),now()));self.s.db.commit();return assignments
 def confidence(self,record,st):
  out={'plddt':None,'meanByChain':{},'pae':None,'directional':None,'ptm':None,'iptm':None,'sources':[],'warnings':[],'tokenMap':None}
  row=self.s.db.execute('SELECT data FROM intelligence_confidence WHERE structure_id=?',(record['id'],)).fetchone()
  if row:
   data=json.loads(row[0]);out.update(data)
  elif record['data'].get('confidenceKind') in ('Boltz-2 pLDDT','AlphaFold pLDDT','ColabFold pLDDT','BindCraft2 AlphaFold2 pLDDT'):
   residues=st['residues'];values=[]
   for r in residues:
    ca=next((st['atoms'][i] for i in r['atoms'] if st['atoms'][i]['name']=='CA'),None);values.append(ca['bfactor'] if ca else None)
   if all(v is None or 0<=v<=100 for v in values):out.update(plddt=values,tokenMap=[r['id'] for r in residues],sources=[{'type':'coordinate B_iso_or_equiv/CA','sha256':record['data']['sha256'],'semantics':record['data']['confidenceKind']}])
   else:out['warnings'].append('Confidence field has values outside 0–100; extraction refused.')
   if record['data'].get('confidenceKind')=='Boltz-2 pLDDT':
    try:
     job=self.s.job(record['data']['metadata']['jobId']);original=record['data']['metadata'].get('originalFilename');stem=pathlib.Path(original).stem if original else None
     if job['engine']=='boltz2' and job['state']=='completed' and job['project_id']==record['project_id'] and record['id'] in job['data'].get('outputs',[]) and stem:
      summaries=[x for x in job['data'].get('confidenceFiles',[]) if x.get('file')=='confidence_'+stem+'.json']
      if len(summaries)==1:
       for key in ('ptm','iptm'):
        v=summaries[0]['data'].get(key)
        if type(v) in (int,float) and math.isfinite(v) and 0<=v<=1:out[key]=v
       out['sources'].append({'type':'saved exact-output confidence summary','file':summaries[0]['file'],'sha256':sha(json.dumps(summaries[0]['data'],sort_keys=True).encode()),'hashScope':'canonical stored summary JSON'})
    except (KeyError,ValueError,TypeError):pass
    try:
     from confidence import local_confidence
     raw=local_confidence(self.s,record);chains=record['data']['metadata']['provenance']['chains'];expected={chr(65+i):c['sequence'] for i,c in enumerate(chains)}
     # Validate every token against actual protein residue labels and input order.
     protein=[r for r in residues if r['one']!='X'];ordered=[]
     for chain,seq in expected.items():
      rs=sorted([r for r in protein if r['labelChain']==chain],key=lambda r:r['label'] if r['label'] is not None else -1)
      if len(rs)!=len(seq) or [r['label'] for r in rs]!=list(range(1,len(seq)+1)) or ''.join(r['one'] for r in rs)!=seq:raise ValueError('Boltz token-to-residue order cannot be verified.')
      ordered.extend(rs)
     if len(ordered)!=len(residues) or len(ordered)!=len(raw['matrix']):raise ValueError('Unsupported nonprotein or missing confidence tokens.')
     out.update(pae=raw['matrix'],tokenMap=[r['id'] for r in ordered],plddt=[v*100 for v in raw['plddt']] if raw['plddt'] is not None else [next((st['atoms'][i]['bfactor'] for i in r['atoms'] if st['atoms'][i]['name']=='CA'),None) for r in ordered],ptm=(raw['metrics'] or {}).get('ptm',out['ptm']),iptm=(raw['metrics'] or {}).get('iptm',out['iptm']),sources=out['sources']+raw['files'])
    except (ValueError,KeyError,OSError) as e:out['warnings'].append(str(e))
  if out['plddt'] is not None and out['tokenMap']:
   lookup={r['id']:r for r in st['residues']}
   for c in st['chains']:
    values=[v for v,rid in zip(out['plddt'],out['tokenMap']) if v is not None and lookup[rid]['chain']==c['id']];out['meanByChain'][c['id']]=sum(values)/len(values) if values else None
  if out['pae'] is None:out['warnings'].append('PAE unavailable; no matrix is inferred from pLDDT.')
  return out
 def intelligence_confidence_import(self,p):
  record,path=self.record(p['structureId']);st=parse_structure(path.read_text(),record['data']['format']);file=pathlib.Path(p['path'])
  if file.suffix.lower()!='.json' or not file.is_file() or file.stat().st_size>32*1024**2:raise ValueError('Choose a confidence JSON file below 32 MB.')
  raw=file.read_bytes();data=json.loads(raw);data=data[0] if isinstance(data,list) and len(data)==1 else data
  if not isinstance(data,dict):raise ValueError('Confidence JSON must contain an object.')
  matrix=data.get('pae',data.get('predicted_aligned_error'));plddt=data.get('plddt');tokens=p.get('tokenMap') or data.get('tokenMap');ids={r['id'] for r in st['residues']}
  if not isinstance(tokens,list) or not tokens or len(tokens)!=len(set(tokens)) or set(tokens)-ids:raise ValueError('Supply an explicit, unique tokenMap of observed residue IDs; order will not be guessed.')
  n=len(tokens)
  if n>2000:raise ValueError('Confidence matrices are limited to 2,000 tokens.')
  if matrix is not None and (not isinstance(matrix,list) or len(matrix)!=n or any(not isinstance(row,list) or len(row)!=n or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1000 for v in row) for row in matrix)):raise ValueError('PAE dimensions/values disagree with the explicit token map.')
  if plddt is not None and (not isinstance(plddt,list) or len(plddt)!=n or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100 for v in plddt)):raise ValueError('pLDDT must contain one 0–100 value per mapped token.')
  if matrix is None and plddt is None and data.get('ptm') is None and data.get('iptm') is None:raise ValueError('No supported confidence array found.')
  out={'pae':matrix,'plddt':plddt,'tokenMap':tokens,'ptm':data.get('ptm'),'iptm':data.get('iptm'),'sources':[{'file':file.name,'sha256':sha(raw),'mapping':'user-confirmed explicit token map'}]}
  for k in ('ptm','iptm'):
   if out[k] is not None and (type(out[k]) not in (float,int) or not math.isfinite(out[k]) or not 0<=out[k]<=1):raise ValueError('Invalid '+k)
  # Keep every imported source as an immutable asset; analyses snapshot the source metadata.
  (self.root/('confidence-'+sha(raw)+'.json')).write_bytes(raw)
  self.s.db.execute('INSERT OR REPLACE INTO intelligence_confidence VALUES(?,?,?,?)',(record['id'],record['project_id'],json.dumps(out),now()));self.s.db.commit();return self.confidence(record,st)
 def task(self,id):
  row=self.s.db.execute('SELECT * FROM intelligence_tasks WHERE id=?',(id,)).fetchone()
  if not row:raise ValueError('Unknown intelligence task.')
  t=dict(row);t['data']=json.loads(t['data']);return t
 def update(self,id,state,extra=None,result=None):
  t=self.task(id);t['data'].update(extra or {})
  self.s.db.execute('UPDATE intelligence_tasks SET state=?,data=?,result=COALESCE(?,result),updated=? WHERE id=?',(state,json.dumps(t['data']),result,now(),id));self.s.db.commit()
 def new(self,project,kind,data,launch=True):
  self.s.project(project);id=uid();data=dict(data)
  for key in ('pid','workerCommandVerified','started','finished','resultSha256'):data.pop(key,None)
  self.s.db.execute('INSERT INTO intelligence_tasks VALUES(?,?,?,?,?,?,?,?)',(id,project,kind,'queued',json.dumps(data),None,now(),now()));self.s.db.commit()
  if launch:
   try:self.launch(id)
   except Exception as error:self.update(id,'failed',{'error':'Unable to launch background worker: '+str(error)});raise
  return self.task(id)
 def launch(self,id):
  with open(self.root/(id+'.log'),'ab',buffering=0) as log:
   proc=subprocess.Popen([sys.executable,'-B',str(pathlib.Path(__file__).with_name('worker.py')),'--root',str(self.s.root),'--intelligence-job',id],stdout=log,stderr=log,start_new_session=True,stdin=subprocess.DEVNULL)
  _CHILDREN[:]=[child for child in _CHILDREN if child.poll() is None];_CHILDREN.append(proc)
  self.s.db.execute('BEGIN IMMEDIATE');t=self.task(id);t['data']['pid']=proc.pid;t['data']['workerCommandVerified']=True;self.s.db.execute('UPDATE intelligence_tasks SET data=?,updated=? WHERE id=?',(json.dumps(t['data']),now(),id));self.s.db.commit()
 def intelligence_start(self,p):
  record,path=self.record(p['structureId']);assignments=self.assigned(record['id']);s=settings(p.get('settings',{}))
  if not any(a.get('role')=='target' for a in assignments.values()) or not any(a.get('role') in ('candidate','control') for a in assignments.values()):raise ValueError('Save explicit target and peptide chain assignments first.')
  h=self.intelligence_hotspots({'projectId':record['project_id']})
  chosen=next((x['data'] for x in h if x['id']==p.get('hotspotSet')),[])
  if p.get('hotspotSet') and not any(x['id']==p['hotspotSet'] for x in h):raise ValueError('The selected hotspot set belongs to another project or is missing.')
  return self.new(record['project_id'],'analysis',{'structureId':record['id'],'sourceSha256':record['data']['sha256'],'assignments':assignments,'settings':s,'hotspots':chosen,'model':p.get('model'),'version':VERSION})
 def intelligence_tasks(self,p):
  self.s.project(p['projectId']);rows=self.s.rows('SELECT * FROM intelligence_tasks WHERE project_id=? ORDER BY created DESC',(p['projectId'],))
  for row in rows:
   row['data']=json.loads(row['data'])
   if row['state'] in ('running','queued') and row['data'].get('pid'):
    try:
     os.kill(row['data']['pid'],0)
     if row['data'].get('workerCommandVerified'):
      status=subprocess.run(['/bin/ps','-p',str(row['data']['pid']),'-o','stat=','-o','command='],capture_output=True,text=True,timeout=2).stdout.strip()
      if not status or status.startswith('Z') or row['id'] not in status or 'worker.py' not in status:raise ProcessLookupError()
    except ProcessLookupError:self.update(row['id'],'interrupted',{'error':'Worker stopped. Resume to create a fresh attempt; raw files and prior results remain.'});row['state']='interrupted'
  return rows
 def intelligence_result(self,p):
  _CHILDREN[:]=[child for child in _CHILDREN if child.poll() is None]
  t=self.task(p['id'])
  if t['state']!='completed' or not t['result']:raise ValueError('This task has no completed result.')
  path=(self.root/t['result']).resolve()
  if not path.is_relative_to(self.root.resolve()):raise ValueError('Invalid saved result.')
  raw=path.read_bytes()
  if t['data'].get('resultSha256') and sha(raw)!=t['data']['resultSha256']:raise ValueError('Saved analysis checksum changed; result was refused.')
  return json.loads(raw)
 def intelligence_cancel(self,p):
  t=self.task(p['id'])
  if t['state'] in ('queued','running'):self.update(t['id'],'cancelled',{'cancelled':now()})
  return self.task(t['id'])
 def intelligence_resume(self,p):
  t=self.task(p['id'])
  if t['state'] not in ('failed','interrupted','cancelled'):raise ValueError('Only failed, interrupted or cancelled tasks can be retried.')
  if t['kind']=='screen' and t['data'].get('activeJob'):
   j=self.s.job(t['data']['activeJob'])
   if j['state'] in ('queued','running'):raise ValueError('The last prediction is still running; cancel it or wait before resuming.')
  return self.new(t['project_id'],t['kind'],{**t['data'],'previousAttempt':t['id'],'error':None,'cancelled':None})
 def intelligence_hotspots(self,p):
  self.s.project(p['projectId'])
  if 'hotspots' in p:
   h=p['hotspots']
   if not isinstance(h,list) or len(h)>200 or any(not isinstance(x,dict) or not x.get('chain') or not(x.get('residueId') or x.get('referenceNumber')) for x in h):raise ValueError('Define up to 200 hotspots with a chain and residue ID or biological reference number.')
   name=str(p.get('name','Hotspots')).strip()
   if not name:raise ValueError('Name the hotspot set.')
   self.s.db.execute('INSERT INTO intelligence_hotspots VALUES(?,?,?,?,?)',(uid(),p['projectId'],name[:200],json.dumps(h),now()));self.s.db.commit()
  rows=self.s.rows('SELECT * FROM intelligence_hotspots WHERE project_id=? ORDER BY created DESC',(p['projectId'],))
  for r in rows:r['data']=json.loads(r['data'])
  return rows
 def intelligence_candidates(self,p):
  self.s.project(p['projectId']);rows=self.s.rows('SELECT * FROM intelligence_candidates WHERE project_id=? ORDER BY created',(p['projectId'],))
  for r in rows:r['data']=json.loads(r['data'])
  return rows
 def intelligence_candidate_save(self,p):
  self.s.project(p['projectId']);seq=self.s.fasta_parse({'text':p['sequence']})
  if len(seq)!=1:raise ValueError('Register one candidate per entry.')
  name=str(p.get('name','')).strip()
  if not name:raise ValueError('Name the candidate.')
  sequence=seq[0]['sequence'];data={**p,'sequence':sequence,'length':len(sequence),'sequenceSha256':sha(sequence.encode()),'role':p.get('role','candidate')}
  if data['role'] not in ('candidate','control'):raise ValueError('Candidate role must be candidate or control.')
  if p.get('controlFor') and not any(c['id']==p['controlFor'] and c['data']['role']=='candidate' for c in self.intelligence_candidates(p)):raise ValueError('Matched candidate is missing from this project.')
  id=uid();self.s.db.execute('INSERT INTO intelligence_candidates VALUES(?,?,?,?,?)',(id,p['projectId'],name[:200],json.dumps(data),now()));self.s.db.commit();return next(c for c in self.intelligence_candidates(p) if c['id']==id)
 def intelligence_scramble(self,p):
  candidate=next((c for c in self.intelligence_candidates(p) if c['id']==p['candidateId']),None)
  if not candidate:raise ValueError('Choose an existing candidate.')
  seq=candidate['data']['sequence'];seed=int(p.get('seed',42));rng=random.Random(seed);arr=list(seq)
  if len(set(arr))<2:raise ValueError('A homopolymer has no distinct composition-matched permutation.')
  for attempt in range(1000):
   rng.shuffle(arr);scrambled=''.join(arr)
   if scrambled!=seq:break
  else:raise ValueError('Could not generate a distinct scramble.')
  return self.intelligence_candidate_save({'projectId':p['projectId'],'name':candidate['name']+' · scramble '+str(seed),'sequence':scrambled,'role':'control','controlFor':candidate['id'],'algorithm':'Python random.Random seeded Fisher–Yates shuffle; retry identity up to 1000','seed':seed,'attempt':attempt+1,'parentProtein':candidate['data'].get('parentProtein'),'sourceRange':candidate['data'].get('sourceRange')})
 def intelligence_compare(self,p):
  ids=p.get('analysisIds',[])
  if not 2<=len(ids)<=20 or len(set(ids))!=len(ids):raise ValueError('Choose 2–20 distinct completed analyses.')
  tasks=[self.task(i) for i in ids]
  if any(t['project_id']!=p['projectId'] or t['kind']!='analysis' or t['state']!='completed' for t in tasks):raise ValueError('Comparisons require completed analyses from the same project.')
  return self.new(p['projectId'],'comparison',{'analysisIds':ids,'method':p.get('method','ca'),'residueIds':p.get('residueIds'),'clusterRmsd':settings({'clusterRmsd':p.get('clusterRmsd',5)})['clusterRmsd']})
 def intelligence_screen(self,p):
  self.s.project(p['projectId']);candidates=self.intelligence_candidates(p);chosen=[c for c in candidates if c['id'] in p.get('candidateIds',[])]
  if not chosen:raise ValueError('Select candidates or permanently saved controls.')
  seeds=p.get('seeds',[])
  if not seeds or len(seeds)>50 or len(set(seeds))!=len(seeds) or any(type(s) is not int or not 0<=s<=2147483647 for s in seeds):raise ValueError('Use 1–50 distinct integer seeds.')
  targets=self.s.fasta_parse({'text':p['targetFasta']})
  if len(targets)>25 or any(sum(len(t['sequence']) for t in targets)+c['data']['length']>1500 for c in chosen):raise ValueError('Screening inputs exceed the existing local engine limits.')
  config={k:p.get(k,v) for k,v in {'recycles':3,'steps':200,'samples':1,'msa':'single'}.items()}
  for k,lo,hi in [('recycles',1,10),('steps',10,500),('samples',1,5)]:
   if type(config[k]) is not int or not lo<=config[k]<=hi:raise ValueError('Invalid screening '+k)
  if config['msa'] not in ('single','server'):raise ValueError('Invalid MSA mode.')
  specs=[{'candidate':c,'seed':seed,'targets':targets,'config':config} for c in chosen for seed in seeds]
  if len(specs)>500:raise ValueError('Limit one screening plan to 500 prediction jobs.')
  data={'specs':specs,'cursor':0,'jobs':[],'analyses':[],'autoAnalyze':bool(p.get('autoAnalyze',True)),'analysisSettings':settings(p.get('analysisSettings',{})),'hotspotSet':p.get('hotspotSet'),'workload':{'jobs':len(specs),'samples':len(specs)*config['samples'],'msa':config['msa']},'version':VERSION}
  if not p.get('start'):return {'plan':data,'note':'No computation started. Public MSA sends sequences to the existing ColabFold MSA server.'}
  if any(t['kind']=='screen' and t['state'] in ('running','queued') for t in self.intelligence_tasks(p)):raise ValueError('A screening plan is already active. Wait or cancel it before starting another.')
  return self.new(p['projectId'],'screen',data)
 def intelligence_export(self,p):
  kind=p.get('format','json')
  if kind in ('project-json','project-markdown','project-pdf'):
   project=self.s.project(p['projectId']);tasks=[t for t in self.intelligence_tasks(p) if t['state']=='completed'];analyses=[];comparisons=[]
   for task in tasks:
    if task['kind']=='analysis':
     r=self.intelligence_result({'id':task['id']});analyses.append({'id':r['id'],'source':r['source'],'settings':r['settings'],'summary':r['summary'],'surface':r['surface'],'hotspots':r['hotspots'],'confidenceSummary':{'meanByChain':r['confidence']['meanByChain'],'directional':r['confidence']['directional'],'ptm':r['confidence']['ptm'],'iptm':r['confidence']['iptm']}})
    elif task['kind']=='comparison':comparisons.append(self.intelligence_result({'id':task['id']}))
   result={'id':project['id'],'kind':'project-report','version':VERSION,'project':project,'analyses':analyses,'comparisons':comparisons,'evidence':self.intelligence_prioritize(p),'created':now()}
   if kind=='project-json':return {'name':'fold-project-report.json','text':json.dumps(result,indent=2,allow_nan=False)}
   if kind=='project-markdown':return {'name':'fold-project-report.md','text':report(result)}
   import base64
   return {'name':'fold-project-report.pdf','base64':base64.b64encode(pdf_report(result)).decode()}
  result=self.intelligence_result(p)
  if kind=='json':return {'name':'fold-analysis-'+p['id']+'.json','text':json.dumps(result,indent=2,allow_nan=False)}
  if kind=='csv':
   if result.get('kind')=='comparison':raise ValueError('Export comparison as JSON or report.')
   stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['type','chain_a','residue_a','insertion_a','resname_a','atom_a','chain_b','residue_b','insertion_b','resname_b','atom_b','distance_A','overlap_A','source_sha256','contact_cutoff_A','donor_atom_id','acceptor_atom_id','criterion']);atoms=result['structure']['atoms']
   for table in ('contacts','clashes','interactions','nativeHydrogenBonds'):
    for row in result.get(table,[]):
     a,b=atoms[row['a']],atoms[row['b']];writer.writerow([row.get('type',table),a['chain'],a['num'],a['ins'],a['resname'],a['name'],b['chain'],b['num'],b['ins'],b['resname'],b['name'],row['distance'],row.get('overlap',''),result['source']['sha256'],result['settings']['contact'],row.get('donor',''),row.get('acceptor',''),row.get('criterion','')])
   return {'name':'fold-contacts-'+p['id']+'.csv','text':stream.getvalue()}
  if kind=='pdf':
   import base64
   return {'name':'fold-report-'+p['id']+'.pdf','base64':base64.b64encode(pdf_report(result)).decode()}
  if kind=='markdown':return {'name':'fold-report-'+p['id']+'.md','text':report(result)}
  raise ValueError('Choose JSON, CSV or Markdown.')
 def intelligence_evidence(self,p):
  r=self.intelligence_result(p)
  if r.get('kind')=='comparison':return {'answer':f"Compared {len(r['analyses'])} saved analyses. Pose clusters use complete-linkage positional Cα RMSD ≤ {r['clusterRmsd']} Å. Target symmetry warnings must be reviewed.",'supportingData':r}
  s=r['summary'];clash=r['clashes'][0] if r['clashes'] else None
  return {'answer':f"This coordinate model has {s['atomicContacts']} heavy-atom contacts across {s['uniqueResiduePairs']} residue pairs at {r['settings']['contact']} Å, and {s['atomicClashes']} clashes across {s['clashingResiduePairs']} residue pairs. "+(f"Maximum overlap is {clash['overlap']:.3f} Å. " if clash else '')+"These measurements do not establish binding or sequence-specific activity. Compare independent seeds and permanently saved matched controls.",'supportingData':{'source':r['source'],'settings':r['settings'],'summary':s,'strongestClash':clash,'hotspots':r['hotspots']}}

 def intelligence_overlay(self,p):
  from observatory import Observatory,native_quote
  self.s.project(p['projectId']);obs=Observatory(self.s)
  code='''from chimerax.atomic import AtomicStructure
from chimerax.geometry import Place
previous = getattr(session, '_fold_intelligence_overlay', None)
if previous:
    session.models.close([m for m in previous['created'] if not m.deleted])
    for m, display in previous['visibility']:
        if not m.deleted: m.display = display
    session._fold_intelligence_overlay = None
'''
  if not p.get('clear'):
   comparison=self.intelligence_result({'id':p['comparisonId']})
   if comparison.get('projectId')!=p['projectId']:raise ValueError('Comparison belongs to another project.')
   pair=next((x for x in comparison['pairs'] if x['reference']==p['referenceAnalysis'] and x['moving']==p['movingAnalysis']),None)
   if not pair:raise ValueError('Choose a calculated comparison pair.')
   ref=self.intelligence_result({'id':pair['reference']});moving=self.intelligence_result({'id':pair['moving']})
   records=[self.record(x['source']['id']) for x in (ref,moving)]
   if any(record['project_id']!=p['projectId'] for record,path in records):raise ValueError('Overlay sources belong to another project.')
   for result,(record,path) in zip((ref,moving),records):
    if result['source']['sha256']!=record['data']['sha256']:raise ValueError('Overlay source fingerprint changed.')
   code+='''visibility = [(m, m.display) for m in session.models.list(type=AtomicStructure)]
created = []
try:
'''
   for i,(record,path) in enumerate(records):
    code+=f"    before = set(session.models.list())\n    run(session, {('open '+native_quote(path))!r})\n    fresh = [m for m in session.models.list(type=AtomicStructure) if m not in before]\n    created.extend(fresh)\n    if len(fresh) != 1: raise ValueError('Overlay requires one explicit coordinate model per source.')\n    model = fresh[0]\n"
    if i==1:
     f=pair['alignment'];matrix=[row+[f['translation'][j]] for j,row in enumerate(f['rotation'])];code+=f'    model.position = Place(matrix={matrix!r})\n'
    color='cyan' if i==0 else 'magenta';code+=f"    run(session, 'cartoon #' + model.id_string)\n    run(session, 'color #' + model.id_string + ' {color}')\n"
    peptide_chains=[chain for chain,a in (ref if i==0 else moving)['assignments'].items() if a.get('role') in ('candidate','control')]
    for chain in peptide_chains:
     if re.fullmatch('[A-Za-z0-9_]+',chain):code+=f"    run(session, 'show #' + model.id_string + '/{chain} atoms')\n"
   code+='''    for m, display in visibility: m.display = False
    session._fold_intelligence_overlay = {'created': created, 'visibility': visibility}
    run(session, 'view')
except Exception:
    session.models.close([m for m in created if not m.deleted])
    for m, display in visibility:
        if not m.deleted: m.display = display
    raise
'''
  result=obs.chimerax_python({'projectId':p['projectId'],'code':code,'confirmed':True})
  if result['state']!='completed':raise ValueError(str(result.get('error','Native overlay failed.')))
  if not p.get('clear'):
   current=obs.chimerax_scene({});current['models']=[m for m in current.get('models',[]) if m['display']];return {**result,'scene':current}
  return result
 def intelligence_overlay_mix(self,p):
  from observatory import Observatory
  self.s.project(p['projectId']);mix=p.get('mix',0)
  if type(mix) not in (float,int) or not math.isfinite(mix) or not 0<=mix<=1:raise ValueError('Overlay transition must be between zero and one.')
  values=[0,0] if p.get('reset') else [100*mix,100*(1-mix)]
  code=f"""overlay = getattr(session, '_fold_intelligence_overlay', None)
if not overlay or len(overlay['created']) != 2: raise ValueError('Open a calculated two-model overlay first.')
for model, transparency in zip(overlay['created'], {values!r}):
    if model.deleted: raise ValueError('The overlay model was closed.')
    run(session, 'transparency #' + model.id_string + ' ' + str(transparency) + ' target acsb')
"""
  result=Observatory(self.s).request('/fold/python',payload={'code':code},timeout=30)
  if result['state']!='completed':raise ValueError(str(result.get('error','Overlay transition failed.')))
  return {'state':'completed','mix':mix,'method':'Crossfade of fixed target-aligned coordinate models; no coordinate interpolation or molecular dynamics.'}
 def intelligence_prioritize(self,p):
  candidates=self.intelligence_candidates(p);tasks=[t for t in self.intelligence_tasks(p) if t['kind']=='analysis' and t['state']=='completed'];latest={}
  for t in tasks:
   key=t['data']['structureId']
   if key not in latest:latest[key]=t
  groups={c['id']:[] for c in candidates}
  for t in latest.values():
   r=self.intelligence_result({'id':t['id']});peptides=[c for c in r['structure']['chains'] if r['assignments'].get(c['id'],{}).get('role') in ('candidate','control')]
   if len(peptides)!=1:continue
   chain=peptides[0];identity=r['assignments'][chain['id']].get('identity');origin=r['source'].get('metadata',{}).get('provenance',{}).get('origin',{});candidate_id=origin.get('candidateId')
   matches=[c for c in candidates if c['data']['sequence']==chain['sequence'] and (c['id']==candidate_id or (candidate_id is None and c['name']==identity))]
   if len(matches)==1:groups[matches[0]['id']].append((r,chain['id']))
  summary=[];flags=[]
  def mean(values):
   values=[v for v in values if v is not None];return sum(values)/len(values) if values else None
  for c in candidates:
   unique={}
   for r,ch in groups[c['id']]:
    lineage=r['source'].get('metadata',{}).get('derivedFrom',{}).get('id',r['source']['id'])
    if lineage not in unique:unique[lineage]=(r,ch)
   runs=list(unique.values());row={'id':c['id'],'name':c['name'],'role':c['data']['role'],'controlFor':c['data'].get('controlFor'),'runs':len(runs),'plddt':mean([r['confidence']['meanByChain'].get(ch) for r,ch in runs]),'paeTargetToPeptide':mean([(r['confidence']['directional'] or {}).get('targetToPeptide') for r,ch in runs]),'paePeptideToTarget':mean([(r['confidence']['directional'] or {}).get('peptideToTarget') for r,ch in runs]),'contacts':mean([r['summary']['atomicContacts'] for r,ch in runs]),'clashes':mean([r['summary']['atomicClashes'] for r,ch in runs]),'interfaceArea':mean([r['surface'].get('interfaceArea') for r,ch in runs]),'sourceAnalyses':[r['id'] for r,ch in runs],'hotspotsWithin':sorted({str(h.get('chain'))+':'+str(h.get('referenceNumber',h.get('residueId'))) for r,ch in runs for h in r['hotspots'] if h['state']=='within threshold'}),'knownSeeds':sorted({r['source'].get('metadata',{}).get('provenance',{}).get('seed') for r,ch in runs if type(r['source'].get('metadata',{}).get('provenance',{}).get('seed')) is int}),'clashProfiles':sorted({json.dumps({k:r['settings'].get(k) for k in ('radiusMethod','hbAllowance','clash','severe')},sort_keys=True) for r,ch in runs}),'contactCutoffs':sorted({r['settings']['contact'] for r,ch in runs}),'reproducibility':'unavailable until a saved cross-seed comparison is examined'};summary.append(row)
   target_contacts=set()
   for r,ch in runs:
    sequence={c['id']:sha(c['sequence'].encode()) for c in r['structure']['chains']};positions={};counts=collections.Counter()
    for residue in r['structure']['residues']:
     if residue['one']=='X':continue
     counts[residue['chain']]+=1;positions[residue['id']]=(sequence[residue['chain']],counts[residue['chain']])
    target_contacts.update(positions[pair['residueA']] for pair in r['residuePairs'] if pair['residueA'] in positions)
   row['targetContactSignatures']=[list(x) for x in sorted(target_contacts)]
   if runs and any(r['summary']['severeClashes'] for r,ch in runs):flags.append(c['name']+': at least one supplied model has severe overlaps under its saved analysis criteria.')
   if runs and len(row['knownSeeds'])<3:flags.append(c['name']+': fewer than three distinct saved seeds are available. Unknown seeds and repeated diffusion samples do not establish independent-seed reproducibility.')
   if len(runs)<3:flags.append(c['name']+': fewer than three coordinate runs; independent-seed reproducibility is not established. Multiple diffusion samples from one seed are not independent seeds.')
  byid={c['id']:c for c in summary}
  for c in summary:
   parent=byid.get(c.get('controlFor'))
   if not parent or not c['runs'] or not parent['runs']:continue
   flags.append(parent['name']+' vs '+c['name']+': available computational results alone do not establish sequence-specific binding or an advantage over the matched control.')
   shared_hotspots=set(c['hotspotsWithin'])&set(parent['hotspotsWithin'])
   if shared_hotspots:flags.append('Both '+parent['name']+' and '+c['name']+' approach these mapped hotspots under their saved thresholds: '+', '.join(sorted(shared_hotspots))+'. Proximity alone does not establish sequence specificity.')
   left={tuple(x) for x in c['targetContactSignatures']};right={tuple(x) for x in parent['targetContactSignatures']};similarity=len(left&right)/len(left|right) if left|right else None
   if similarity is not None and similarity>=.5 and c['contactCutoffs']==parent['contactCutoffs']:flags.append('Target sequence-position contact Jaccard is '+format(similarity,'.3f')+' for '+parent['name']+' versus '+c['name']+' (descriptive flag threshold ≥0.5). Identical target copies are pooled; this is not an orientation or specificity test.')
   if c['plddt'] is not None and parent['plddt'] is not None and abs(c['plddt']-parent['plddt'])<=5:flags.append('Mean peptide pLDDT differs by ≤5 points for '+parent['name']+' and '+c['name']+'. This descriptive screening observation is not a significance test or affinity comparison.')
   if c['clashProfiles']!=parent['clashProfiles']:flags.append('Clash definitions differ between '+parent['name']+' and its control; reanalyse with identical settings before comparing clash counts.')
   if c['contactCutoffs']!=parent['contactCutoffs']:flags.append('Contact thresholds differ between '+parent['name']+' and its control; raw contact counts are not directly comparable.')
  comparison_tasks=[t for t in self.intelligence_tasks(p) if t['kind']=='comparison' and t['state']=='completed']
  for row in summary:
   row['poseComparisons']=[]
   for task in comparison_tasks:
    ids=set(task['data']['analysisIds'])
    if len(ids)<2 or not ids.issubset(set(row['sourceAnalyses'])):continue
    comparison=self.intelligence_result({'id':task['id']});values=[pair['metrics']['caPositionalRmsd'] for pair in comparison['pairs'] if pair['metrics']['caPositionalRmsd'] is not None];row['poseComparisons'].append({'id':task['id'],'clusters':comparison['clusters'],'maximumPositionalRmsd':max(values) if values else None})
    if len(comparison['clusters'])>1:flags.append(row['name']+': saved comparison '+task['id']+' separates these poses into '+str(len(comparison['clusters']))+' geometric clusters at '+str(comparison['clusterRmsd'])+' Å. Pose consistency is limited under that criterion.')
   if row['poseComparisons']:row['reproducibility']='See saved geometric comparisons; seed independence must be reviewed in prediction provenance.'
  return {'candidates':summary,'flags':flags,'method':'Separate descriptive dimensions, no composite binding score. Latest completed analysis per coordinate asset; exact stored candidate sequence and candidate ID/assigned identity required. A 5-point pLDDT similarity flag is descriptive, not statistical.','limitations':['No statistical uncertainty, energetic ranking or experimentally demonstrated specificity is computed.','Independent seeds and diffusion samples must be distinguished in saved prediction provenance.']}

 def intelligence_auto(self,p):
  record,path=self.record(p['structureId']);assign=self.assigned(record['id']);st=parse_structure(path.read_text(),record['data']['format'])
  if p.get('enabled') and (not any(v.get('role')=='target' for v in assign.values()) or not any(v.get('role') in ('candidate','control') for v in assign.values())):raise ValueError('Save explicit target and peptide chain roles before enabling automatic analysis.')
  entries=[{'sequence':c['sequence'],'assignment':assign[c['id']]} for c in st['chains'] if c['id'] in assign]
  self.s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('intelligenceAuto:'+record['project_id'],json.dumps({'enabled':bool(p.get('enabled')),'chains':entries,'settings':settings(p.get('settings',{})),'hotspotSet':p.get('hotspotSet')})));self.s.db.commit()
  return True
 def auto_prediction(self,job,outputs):
  config=self.s.setting('intelligenceAuto:'+job['project_id'],{})
  if not config.get('enabled') or job['data'].get('origin',{}).get('screenId'):return []
  chains=job['data'].get('chains',[]);assignments={}
  for i,chain in enumerate(chains):
   matches=[c['assignment'] for c in config.get('chains',[]) if c['sequence']==chain['sequence']]
   named=[a for a in matches if a.get('identity')==chain.get('name')]
   if len(named)==1:matches=named
   if not matches or any(any(a.get(k,1 if k=='referenceStart' else '')!=matches[0].get(k,1 if k=='referenceStart' else '') for k in ('role','reference','referenceStart')) for a in matches):raise ValueError('Automatic analysis paused: saved input sequences/chain roles are missing or ambiguous. Assign these new chains explicitly.')
   assignments[chr(65+i)]={**matches[0],'identity':chain.get('name',matches[0].get('identity',''))}
  tasks=[]
  for record in outputs:
   self.intelligence_assign({'structureId':record['id'],'assignments':assignments});tasks.append(self.intelligence_start({'structureId':record['id'],'settings':config.get('settings',{}),'hotspotSet':config.get('hotspotSet')})['id'])
  return tasks

 def native_radii(self,record,path,st,assignments=None,analysis_settings=None):
  from observatory import Observatory,native_quote
  obs=Observatory(self.s)
  code=f'''import json
from chimerax.atomic import AtomicStructure
before = set(session.models.list())
created = []
try:
    run(session, {('open '+native_quote(path))!r})
    created = [m for m in session.models.list(type=AtomicStructure) if m not in before]
    if len(created) != 1: raise ValueError('Native atom typing requires one explicit coordinate model.')
    model = created[0]
    rows = [[a.residue.chain_id, int(a.residue.number), a.residue.insertion_code or '', a.name, float(radius), a.idatm_type] for a, radius in zip(model.atoms, model.atoms.default_radii)]
    print('FOLD_RADII:' + json.dumps(rows))
finally:
    session.models.close(created)
'''
  if assignments is not None:
   opts=settings(analysis_settings or {});target=[c for c,a in assignments.items() if a.get('role')=='target'];peptide=[c for c,a in assignments.items() if a.get('role') in ('candidate','control')]
   selected_keys=[(a['chain'],a['num'],a['ins'],a['name']) for a in st['atoms']]
   extra=f'''    from chimerax.clashes import find_clashes
    from chimerax.atomic import Atoms
    def atom_key(a): return [a.residue.chain_id, int(a.residue.number), a.residue.insertion_code or '', a.name]
    selected_keys = set({selected_keys!r})
    selected_atoms = [a for a in model.atoms if tuple(atom_key(a)) in selected_keys and a.element.name not in ('H','D') and a.occupancy > 0]
    target_atoms = Atoms([a for a in selected_atoms if a.residue.chain_id in {target!r}])
    peptide_atoms = Atoms([a for a in selected_atoms if a.residue.chain_id in {peptide!r}])
    model.atoms.radii = model.atoms.default_radii
    clashes = find_clashes(session, target_atoms, restrict=peptide_atoms, clash_threshold={opts['clash']!r}, hbond_allowance={opts['hbAllowance']!r}, bond_separation=4, assumed_max_vdw=float(max(model.atoms.default_radii)))
    result_pairs = [[atom_key(a), atom_key(b), float(overlap)] for a, neighbors in clashes.items() if a in target_atoms for b, overlap in neighbors.items() if b in peptide_atoms]
    print('FOLD_CLASHES:' + json.dumps(result_pairs))
    from chimerax.hbonds import find_hbonds
    from chimerax.geometry import distance
    selected = Atoms(list(target_atoms) + list(peptide_atoms))
    target_set, peptide_set = set(target_atoms), set(peptide_atoms)
    hbonds = find_hbonds(session, [model], donors=selected, acceptors=selected, inter_model=False, dist_slop=0.0, angle_slop=0.0, cache_da=False, status=False)
    hbond_pairs = [[atom_key(d), atom_key(a), float(distance(d.scene_coord,a.scene_coord))] for d,a in hbonds if (d in target_set and a in peptide_set) or (d in peptide_set and a in target_set)]
    print('FOLD_HBONDS:' + json.dumps(hbond_pairs))
'''
   code=code.replace('finally:\n',extra+'finally:\n')
  result=obs.request('/fold/python',payload={'code':code},timeout=120)
  if result['state']!='completed':raise ValueError('Native atom typing failed: '+str(result.get('error')))
  line=next((line for line in result.get('stdout','').splitlines() if line.startswith('FOLD_RADII:')),None)
  if not line:raise ValueError('Native atom typing returned no radii.')
  rows=json.loads(line[len('FOLD_RADII:'):]);lookup={(r[0],r[1],r[2],r[3]):r[4:] for r in rows}
  for a in st['atoms']:
   key=(a['chain'],a['num'],a['ins'],a['name'])
   if key not in lookup or not 0.5<=lookup[key][0]<=4:raise ValueError('Native atom typing changed an observed atom identity.')
   a['vdw'],a['idatmType']=lookup[key]
  pairs=[];hbonds=[]
  if assignments is not None:
   line=next((line for line in result.get('stdout','').splitlines() if line.startswith('FOLD_CLASHES:')),None)
   if not line:raise ValueError('Native clash calculation returned no structured output.')
   ids={(a['chain'],a['num'],a['ins'],a['name']):a for a in st['atoms']}
   for a,b,overlap in json.loads(line[len('FOLD_CLASHES:'):]):
    if tuple(a) not in ids or tuple(b) not in ids:raise ValueError('Native clash calculation returned a nonselected alternate/atom.')
    aa,bb=ids[tuple(a)],ids[tuple(b)];pairs.append({'a':aa['id'],'b':bb['id'],'residueA':aa['residue'],'residueB':bb['residue'],'distance':dist(aa['xyz'],bb['xyz']),'overlap':overlap,'severity':'severe' if overlap>=opts['severe'] else 'moderate'})
   line=next((line for line in result.get('stdout','').splitlines() if line.startswith('FOLD_HBONDS:')),None)
   if not line:raise ValueError('Native hydrogen-bond calculation returned no structured output.')
   for donor,acceptor,distance in json.loads(line[len('FOLD_HBONDS:'):]):
    if tuple(donor) not in ids or tuple(acceptor) not in ids:raise ValueError('Native hydrogen bond returned a nonselected atom identity.')
    d,a=ids[tuple(donor)],ids[tuple(acceptor)]
    if not math.isfinite(distance) or abs(dist(d['xyz'],a['xyz'])-distance)>1e-4:raise ValueError('Native hydrogen-bond coordinates differ from the saved source.')
    aa,bb=(d,a) if assignments[d['chain']]['role']=='target' else (a,d)
    hbonds.append({'a':aa['id'],'b':bb['id'],'donor':d['id'],'acceptor':a['id'],'residueA':aa['residue'],'residueB':bb['residue'],'distance':distance,'distanceType':'donor–acceptor','directAtomPair':True,'type':'ChimeraX strict hydrogen bond','status':'native chemical geometry','criterion':'Original ChimeraX find_hbonds with zero distance/angle slop; no hydrogens added or protonation assigned.'})
  return {'method':'ChimeraX 1.12 Atoms.default_radii and clashes.find_clashes; fresh source model; four-bond exclusion; presentation radii ignored','sourceSha256':record['data']['sha256'],'hbondAllowance':(analysis_settings or {}).get('hbAllowance',0),'nativeClashes':pairs,'nativeHydrogenBonds':hbonds,'hydrogenBondMethod':{'engine':'ChimeraX 1.12 hbonds.find_hbonds','distanceSlopAngstrom':0.0,'angleSlopDegrees':0.0,'hydrogensAdded':False,'scope':'Cross-partner strict native chemical geometry; may infer donor geometry for missing H. Distinct from explicit-hydrogen screens; not energetic or experimental validation.'}}


 def intelligence_register_chains(self,p):
  record,path=self.record(p['structureId']);st=parse_structure(path.read_text(),record['data']['format']);assigned=self.assigned(record['id']);existing=self.intelligence_candidates({'projectId':record['project_id']});saved=[]
  for c in st['chains']:
   a=assigned.get(c['id'],{})
   if a.get('role') not in ('candidate','control'):continue
   if not c['sequence'] or 'X' in c['sequence']:raise ValueError('Resolve noncanonical sequence before registering a prediction candidate.')
   name=a.get('identity') or ('Chain '+c['id']);same=next((v for v in existing if v['name']==name and v['data']['sequence']==c['sequence'] and v['data']['role']==a['role']),None)
   if same:saved.append(same);continue
   saved.append(self.intelligence_candidate_save({'projectId':record['project_id'],'name':name,'sequence':c['sequence'],'role':a['role'],'controlFor':p.get('controlFor') if a['role']=='control' else None,'sourceStructure':record['id'],'sourceSha256':record['data']['sha256'],'sourceChain':c['id'],'sourceRange':'Observed coordinate chain; verify biological range separately'}))
  if not saved:raise ValueError('Assign a candidate or control chain before registering it.')
  return saved

 def intelligence_prepare(self,p):
  from observatory import Observatory,native_quote
  record,path=self.record(p['structureId']);original=parse_structure(path.read_text(),record['data']['format']);output=self.s.root/'assets'/('hydrogen-preparation-'+uid()+'.cif');obs=Observatory(self.s)
  code=f'''from chimerax.atomic import AtomicStructure
before = set(session.models.list())
created = []
try:
    run(session, {('open '+native_quote(path))!r})
    created = [m for m in session.models.list(type=AtomicStructure) if m not in before]
    if len(created) != 1: raise ValueError('Hydrogen preparation requires one explicit coordinate model.')
    model = created[0]
    run(session, 'addh #' + model.id_string)
    run(session, 'save ' + {native_quote(output)!r} + ' format mmcif models #' + model.id_string)
finally:
    session.models.close(created)
'''
  try:
   response=obs.request('/fold/python',payload={'code':code},timeout=120)
   if response['state']!='completed' or not output.is_file():raise ValueError('Hydrogen preparation failed: '+str(response.get('error')))
   prepared=parse_structure(output.read_text(),'mmcif');key=lambda a:(a['chain'],a['num'],a['ins'],a['name']);old={key(a):a for a in original['atoms'] if a['element'] not in ('H','D')};new={key(a):a for a in prepared['atoms'] if a['element'] not in ('H','D')}
   added=[k for k in new if k not in old]
   if not old.keys()<=new.keys() or any(dist(a['xyz'],new[k]['xyz'])>.0011 for k,a in old.items()):raise ValueError('Preparation changed original heavy-atom identities or coordinates; derived import refused.')
   if any(k[3]!='OXT' or (*k[:3],'C') not in old or not 1.0<=dist(new[k]['xyz'],old[(*k[:3],'C')]['xyz'])<=1.6 for k in added):raise ValueError('Preparation added an unexpected heavy atom; derived import refused.')
   metadata={**record['data'].get('metadata',{}),'derivedFrom':{'id':record['id'],'sha256':record['data']['sha256']},'preparation':{'engine':'ChimeraX 1.12 AddH','assumptions':'Installed AddH defaults; no explicit pH titration, charge assignment or tautomer optimization. Native AddH may complete missing terminal oxygens. Cropped fragments acquire artificial termini; review histidine, terminal protonation and full-protein context before interpreting hydrogen bonds.','sourceHeavyAtomsPreservedWithinAngstrom':.0011,'addedTerminalHeavyAtoms':[list(k) for k in added]}}
   imported=self.s.import_structure({'projectId':record['project_id'],'path':str(output),'name':record['name']+' · hydrogenated copy','source':'Derived ChimeraX AddH preparation','confidenceKind':record['data'].get('confidenceKind'),'metadata':metadata})
   assignments=self.assigned(record['id'])
   if assignments:self.intelligence_assign({'structureId':imported['id'],'assignments':assignments})
   cf=self.confidence(record,original)
   if cf['plddt'] is not None or cf['pae'] is not None or cf['ptm'] is not None or cf['iptm'] is not None:
    if set(cf['tokenMap'] or [])-{r['id'] for r in prepared['residues']}:raise ValueError('Prepared confidence residue map changed.')
    cf['sources'].append({'type':'heavy-atom-preserving derived preparation','sourceCoordinateSha256':record['data']['sha256'],'derivedCoordinateSha256':imported['data']['sha256']})
    self.s.db.execute('INSERT OR REPLACE INTO intelligence_confidence VALUES(?,?,?,?)',(imported['id'],record['project_id'],json.dumps(cf),now()));self.s.db.commit()
   return imported
  finally:
   if output.exists():output.unlink()

 def run(self,id):
  import time
  self.s.db.execute('BEGIN IMMEDIATE');t=self.task(id)
  if t['state']!='queued':self.s.db.rollback();return
  self.update(id,'running',{'progress':'Reading immutable inputs','started':now(),'pid':os.getpid()})
  def check():
   if self.task(id)['state']=='cancelled':raise InterruptedError('Cancelled by user.')
  def progress(message):
   check();self.update(id,'running',{'progress':message})
  try:
   p=t['data']
   if t['kind']=='analysis':
    record,path=self.record(p['structureId'])
    if record['data']['sha256']!=p['sourceSha256']:raise ValueError('Input fingerprint changed.')
    st=parse_structure(path.read_text(),record['data']['format'],p.get('model'));radii=None
    if p['settings'].get('radiusMethod')=='chimerax-default':
     progress('Obtaining source-specific ChimeraX chemical atom radii');radii=self.native_radii(record,path,st,p['assignments'],p['settings'])
    r=analyze(st,p['assignments'],p['settings'],p.get('hotspots'),check,progress);r['confidence']=self.confidence(record,st);r['radii']=radii or {'method':'Elemental Bondi radii','hbondAllowance':0}
    if radii is not None:
     r['clashes']=sorted(radii.pop('nativeClashes'),key=lambda x:-x['overlap']);r['summary'].update(atomicClashes=len(r['clashes']),clashingResiduePairs=len({(c['residueA'],c['residueB']) for c in r['clashes']}),severeClashes=sum(c['severity']=='severe' for c in r['clashes']))
     r['nativeHydrogenBonds']=radii.pop('nativeHydrogenBonds');r['summary']['nativeHydrogenBonds']=len(r['nativeHydrogenBonds']);r['limitations'].append(radii['hydrogenBondMethod']['scope'])
    cf=r['confidence']
    if cf['pae'] is not None and cf['tokenMap']:
     lookup={r['id']:r for r in st['residues']};target=[i for i,rid in enumerate(cf['tokenMap']) if p['assignments'].get(lookup[rid]['chain'],{}).get('role')=='target'];peptide=[i for i,rid in enumerate(cf['tokenMap']) if p['assignments'].get(lookup[rid]['chain'],{}).get('role') in ('candidate','control')]
     mean=lambda rows,cols:sum(cf['pae'][i][j] for i in rows for j in cols)/(len(rows)*len(cols)) if rows and cols else None
     cf['directional']={'targetToPeptide':mean(target,peptide),'peptideToTarget':mean(peptide,target),'convention':'source file row → column means; row/column order retained; do not assume a provider-independent alignment direction'}
    r.update(id=id,kind='analysis',source={'id':record['id'],'name':record['name'],'sha256':record['data']['sha256'],'format':record['data']['format'],'metadata':record['data'].get('metadata',{}),'confidenceKind':record['data'].get('confidenceKind')},projectId=t['project_id'])
   elif t['kind']=='comparison':
    analyses=[self.intelligence_result({'id':i}) for i in p['analysisIds']]
    if len({a['settings']['contact'] for a in analyses})!=1:raise ValueError('Contact cutoffs differ; reanalyse at one cutoff before comparison.')
    pairs=[]
    for a,b in itertools.combinations(analyses,2):progress('Aligning '+a['source']['name']+' ↔ '+b['source']['name']);pairs.append(compare_pair(a,b,p['method'],set(p['residueIds']) if p.get('residueIds') else None))
    # Complete linkage: every pair in a cluster must satisfy the cutoff. Deterministic greedy agglomeration.
    distances={frozenset([x['reference'],x['moving']]):x['metrics']['caPositionalRmsd'] for x in pairs};clusters=[[a['id']] for a in analyses]
    while True:
     options=[(max(distances[frozenset([a,b])] for a in ca for b in cb),i,j) for i,ca in enumerate(clusters) for j,cb in enumerate(clusters) if i<j and all(distances[frozenset([a,b])] is not None for a in ca for b in cb)]
     if not options:break
     d,i,j=min(options)
     if d>p['clusterRmsd']:break
     clusters[i]+=clusters.pop(j)
    counts=collections.Counter(tuple(c) for c in [(x['residueA'],x['residueB']) for x in analyses[0]['residuePairs']])
    for pair in pairs:
     if pair['reference']==analyses[0]['id']:counts.update(tuple(c) for c in pair['mappedMovingContacts'])
    r={'id':id,'kind':'comparison','version':VERSION,'projectId':t['project_id'],'analyses':[{'id':a['id'],'source':a['source'],'summary':a['summary'],'settings':a['settings'],'assignments':a['assignments'],'confidenceSummary':{'meanByChain':a['confidence']['meanByChain'],'directional':a['confidence']['directional'],'ptm':a['confidence']['ptm'],'iptm':a['confidence']['iptm']}} for a in analyses],'pairs':pairs,'clusters':[{'analyses':c,'occurrence':len(c),'total':len(analyses)} for c in clusters],'clusterRmsd':p['clusterRmsd'],'method':'complete-linkage agglomeration on target-aligned peptide positional Cα RMSD; deterministic tie order','contactFrequency':[{'pair':list(k),'count':v,'total':len(analyses)} for k,v in sorted(counts.items())],'limitations':LIMITATIONS+['Symmetric target alignments may have multiple valid poses; selected mappings and near-equivalent alternatives are retained. Ambiguous or low-identity cross-model residue correspondence is refused; partial observed sequences use only uniquely mapped identical residues. Unmapped contacts may reflect missing coordinates. Clustering is geometric and does not establish biological interfaces.'],'created':now()}
   elif t['kind']=='screen':
    self.run_screen(id,check,progress);return
   else:raise ValueError('Unsupported task kind.')
   check();name=id+'.json';temporary=self.root/(name+'.tmp');temporary.write_text(json.dumps(r,allow_nan=False));temporary.replace(self.root/name);check();self.update(id,'completed',{'progress':'Completed','finished':now(),'resultSha256':sha((self.root/name).read_bytes())},name)
  except InterruptedError:self.update(id,'cancelled',{'progress':'Cancelled at safe boundary','finished':now()})
  except Exception as e:self.update(id,'cancelled' if self.task(id)['state']=='cancelled' else 'failed',{'error':str(e),'finished':now()});print(str(e),flush=True)
 def run_screen(self,id,check,progress):
  import time
  task=self.task(id);p=task['data'];jobs=list(p.get('jobs',[]));analyses=list(p.get('analyses',[]));cursor=p.get('cursor',0)
  while cursor<len(p['specs']):
   check();spec=p['specs'][cursor];candidate=spec['candidate'];targets=spec['targets'];config=spec['config'];old=p.get('activeJob')
   if old:
    job=self.s.job(old)
    if job['state'] not in ('completed','running','queued'):old=None
   if not old:
    while self.s.active():progress('Waiting for the existing local engine process');time.sleep(2);check()
    fasta='\n'.join('>'+str(t['name'])+'\n'+t['sequence'] for t in targets)+'\n>'+candidate['name']+'\n'+candidate['data']['sequence']
    job=self.s.prediction_start({'projectId':task['project_id'],'name':candidate['name']+' · seed '+str(spec['seed']),'fasta':fasta,'seed':spec['seed'],**config,'origin':{'screenId':id,'candidateId':candidate['id'],'sequenceSha256':candidate['data']['sequenceSha256']}})
    if job['id'] not in jobs:jobs.append(job['id'])
    self.update(id,'running',{'jobs':jobs,'activeJob':job['id'],'cursor':cursor})
   while job['state'] in ('queued','running'):
    if self.task(id)['state']=='cancelled':self.s.job_cancel({'id':job['id']});raise InterruptedError()
    progress('Prediction '+str(cursor+1)+'/'+str(len(p['specs']))+' · '+candidate['name']);time.sleep(2);self.s.reconcile({});job=self.s.job(job['id'])
   if job['state']!='completed':raise ValueError('Prediction '+job['id']+' '+job['state']+': '+str(job['data'].get('error','Inspect saved prediction log.')))
   if p['autoAnalyze']:
    for output in job['data'].get('outputs',[]):
     assignment={chr(65+i):{'role':'target','identity':t['name'],'reference':t['sequence']} for i,t in enumerate(targets)};assignment[chr(65+len(targets))]={'role':candidate['data']['role'],'identity':candidate['name'],'reference':candidate['data']['sequence']}
     self.intelligence_assign({'structureId':output,'assignments':assignment});analysis=self.intelligence_start({'structureId':output,'settings':p.get('analysisSettings',{}),'hotspotSet':p.get('hotspotSet')});analyses.append(analysis['id'])
   cursor+=1;p['activeJob']=None;self.update(id,'running',{'cursor':cursor,'activeJob':None,'jobs':jobs,'analyses':analyses})
  comparisons=[];analysis_errors=[]
  if p['autoAnalyze']:
   progress('Waiting for queued analyses before reproducibility comparisons')
   while any(self.task(a)['state'] in ('running','queued') for a in analyses):
    check();self.intelligence_tasks({'projectId':task['project_id']});time.sleep(2)
   grouped=collections.defaultdict(list)
   for a in analyses:
    if self.task(a)['state']!='completed':analysis_errors.append({'analysisId':a,'state':self.task(a)['state'],'error':self.task(a)['data'].get('error')});continue
    result=self.intelligence_result({'id':a});candidate_id=result['source']['metadata'].get('provenance',{}).get('origin',{}).get('candidateId')
    if candidate_id:grouped[candidate_id].append(a)
   for candidate_id,ids in grouped.items():
    if len(ids)>=2:
     # Bound each reproducibility group to the supported 20-model comparison size.
     for chunk in range(0,len(ids),20):
      subset=ids[chunk:chunk+20]
      if len(subset)>=2:comparisons.append(self.intelligence_compare({'projectId':task['project_id'],'analysisIds':subset})['id'])
  check();name=id+'.json';(self.root/name).write_text(json.dumps({'id':id,'kind':'screen','jobs':jobs,'analyses':analyses,'comparisons':comparisons,'analysisErrors':analysis_errors,'workload':p['workload'],'note':'Prediction jobs, analyses and comparisons retain independent raw outputs and errors. Comparison groups are at most 20 coordinate runs.'}));self.update(id,'completed',{'finished':now(),'progress':'Screening complete; review saved analyses and queued comparisons.','comparisons':comparisons,'analysisErrors':analysis_errors},name)

def report(r):
 if r.get('kind')=='project-report':
  fmt=lambda v:f'{v:.3f}' if isinstance(v,(int,float)) else 'Unavailable'
  lines=['# FOLD STUDIO project research report','',r['project']['name'],f"Project: {r['id']} · engine {r['version']} · {r['created']}",'','## Candidate and matched-control measurements','',r['evidence']['method'],'']
  for c in r['evidence']['candidates']:
   lines += [f"### {c['name']} · {c['role']}",f"Latest coordinate models (derived copies deduplicated): {c['runs']}; known seeds: {c['knownSeeds'] or 'Unavailable'}.",f"Mean peptide pLDDT: {fmt(c['plddt'])}; target-row to peptide-column PAE: {fmt(c['paeTargetToPeptide'])} Å; peptide-row to target-column PAE: {fmt(c['paePeptideToTarget'])} Å.",f"Mean atomic contacts: {fmt(c['contacts'])}; mean atom clashes: {fmt(c['clashes'])}; mean conventional interface area: {fmt(c['interfaceArea'])} Å².",f"Matched candidate ID: {c['controlFor'] or 'None specified'}; contributing analyses: {', '.join(c['sourceAnalyses']) or 'None'}.",f"Mapped hotspots within threshold: {', '.join(c['hotspotsWithin']) or 'None measured'}.",c['reproducibility'],'']
  if not r['evidence']['candidates']:lines.append('No candidate/control sequences have been registered; no candidate identity was inferred from a filename.')
  lines+=['','## Control-aware observations','']+['- '+f for f in r['evidence']['flags']]+['','## Cross-seed structural comparisons','']
  for comparison in r['comparisons']:lines += [report(comparison),'']
  if not r['comparisons']:lines.append('No saved multi-model comparison was completed.')
  lines+=['','## Source models, versions and settings','']
  for a in r['analyses']:
   lines += [a['source']['name'],f"Analysis {a['id']} · coordinate SHA-256 {a['source']['sha256']}",f"Settings: {json.dumps(a['settings'],sort_keys=True)}",f"Atomic contacts {a['summary']['atomicContacts']}; unique residue pairs {a['summary']['uniqueResiduePairs']}; atom clashes {a['summary']['atomicClashes']}; clashing residue pairs {a['summary']['clashingResiduePairs']}.",'']
  lines+=['## Methods and provenance','','Candidate metrics are descriptive averages over the latest completed analysis per coordinate lineage, matched by exact saved sequence and candidate ID or assigned identity. Derived preparation copies do not add an independent prediction. Multiple diffusion samples from one seed are not independent seeds. Contact, clash and surface criteria are preserved per analysis. Separate single-structure reports document the actual algorithms and prediction provenance. No undocumented composite binding score is used.','','## Conclusions and limitations','','Available computational results do not by themselves establish an advantage over matched controls, sequence-specific binding, inhibition or therapeutic efficacy. Review replicate variability, target symmetry, hotspot numbering, preparation assumptions and missing confidence sources. Experimental validation is required for biological claims. Export the project archive, full analysis JSON/CSV and this project-report JSON together for reproducibility.']
  return '\n'.join(lines)
 if r.get('kind')=='comparison':
  lines=['# FOLD STUDIO reproducibility report','',f"Saved comparison: {r['id']}",'',r['method'],f"Clustering threshold: {r['clusterRmsd']} Å.",'']
  for pair in r['pairs']:
   lines += [f"## {pair['reference']} versus {pair['moving']}",'',f"Target RMSD: {pair['alignment']['rmsd']:.3f} Å over {pair['alignment']['atoms']} atoms.",f"Peptide positional Cα RMSD: {pair['metrics']['caPositionalRmsd']} Å; internal Cα RMSD: {pair['metrics']['caInternalRmsd']} Å.",f"Reference-interface Cα RMSD after target alignment: {pair['metrics']['interfaceRmsd']} Å.",f"Contact Jaccard: {pair['contactJaccard']}; selected chain mapping: {json.dumps(pair['chainMapping'])}.",pair.get('symmetryWarning') or '',pair.get('clashCriteriaWarning') or '','']
  lines+=['## Pose clusters','']+[f"Cluster {i+1}: {c['occurrence']}/{c['total']} coordinate runs." for i,c in enumerate(r['clusters'])]+['','## Interpretation','','Geometric reproducibility does not establish binding or specificity. Independent seeds must be distinguished from repeated diffusion samples. Review matched controls and experimental evidence.','','## Limitations','']+['- '+x for x in r['limitations']]
  return '\n'.join(lines)
 source=r['source'];s={**DEFAULTS,**r['settings']};summary=r['summary'];conf=r['confidence'];provenance=source.get('metadata',{}).get('provenance',{})
 fmt=lambda v,unit='':f'{v:.3f}{unit}' if isinstance(v,(int,float)) else 'Unavailable'
 atom=lambda i:f"{r['structure']['atoms'][i]['chain']} {r['structure']['atoms'][i]['resname']}{r['structure']['atoms'][i]['num']}{r['structure']['atoms'][i]['ins']} {r['structure']['atoms'][i]['name']}"
 lines=['# FOLD STUDIO molecular intelligence report','',f"Analysis: {r['id']} · calculation engine {r['version']}",f"Source: {source['name']}",f"Coordinate SHA-256: {source['sha256']}",f"Created: {r['created']}",'','## Experiment and structural characterization','']
 for c in r['structure']['chains']:
  a=r['assignments'].get(c['id'],{});lines += [f"Chain {c['id']}: {a.get('identity','unassigned')} · {a.get('role','unassigned')} · {c['proteinResidues']} protein residues · {c['atoms']} atoms.",f"Observed sequence: {c['sequence']}",f"Quality: {len(c['missingAtoms'])} residues with missing standard heavy atoms; {len(c['numberingGaps'])} numbering gaps; {len(c['discontinuities'])} unusual consecutive peptide C–N distances.",'']
 lines+=['Prediction metadata retained with the source:']
 if source.get('metadata',{}).get('preparation'):lines+=['Preparation: '+json.dumps(source['metadata']['preparation'],ensure_ascii=False)]
 for k,label in [('model','Prediction model'),('engineVersion','Software version'),('seed','Random seed'),('recycles','Recycles'),('steps','Diffusion steps'),('samples','Samples'),('msaSource','MSA source')]:lines.append(f"- {label}: {provenance.get(k,'Unavailable')}")
 lines+=['','## Calculated interface measurements','',f"Heavy-atom contacts at ≤{s['contact']} Å: {summary['atomicContacts']} atom pairs, {summary['uniqueResiduePairs']} unique residue pairs, {summary['interfaceResidues']} interface residues.",f"Steric clashes: {summary['atomicClashes']} atom pairs across {summary['clashingResiduePairs']} residue pairs; {summary['severeClashes']} severe atom overlaps.",f"Contact composition: {summary['polarAtomContacts']} atom pairs involving N/O/S and {summary['nonpolarAtomContacts']} other heavy-atom pairs. These descriptive atom categories are not an electrostatic-energy calculation.",'']
 area=r['surface']
 if area['state']=='calculated':lines += [f"Isolated target SASA: {fmt(area['targetSasa'],' Å²')}; isolated peptide SASA: {fmt(area['peptideSasa'],' Å²')}; complex SASA: {fmt(area['complexSasa'],' Å²')}.",f"Total solvent-accessible area loss: {fmt(area['totalLoss'],' Å²')}. Conventional per-interface area (half the total loss): {fmt(area['interfaceArea'],' Å²')}."]
 else:lines += ['Surface area unavailable: '+area['reason']]
 types=collections.Counter((x['type'],x['status']) for x in r['interactions']);lines+=['','Chemical interaction records (atom-level unless ring centroids are specified):']+([f'- {kind}: {count} ({status})' for (kind,status),count in sorted(types.items())] or ['- None detected under the stated chemical/geometric criteria.'])
 if 'nativeHydrogenBonds' in r:lines+=['',f"ChimeraX strict cross-partner hydrogen bonds: {len(r['nativeHydrogenBonds'])}. Original chemical geometry criteria, zero distance/angle slack; donor geometry may be inferred for missing H. Separate from explicit-hydrogen screens; no hydrogens or protonation were added. Full donor/acceptor identities and criteria are retained in JSON."]
 lines+=['','Closest measured contact atom pairs:']+[f"- {atom(x['a'])} ↔ {atom(x['b'])}: {x['distance']:.3f} Å" for x in r['contacts'][:10]]
 lines+=['','Largest steric overlaps:']+([f"- {atom(x['a'])} ↔ {atom(x['b'])}: distance {x['distance']:.3f} Å, overlap {x['overlap']:.3f} Å ({x['severity']})" for x in r['clashes'][:10]] or ['- No clashes under the saved criteria.'])
 lines+=['','## Prediction confidence','']
 for chain,v in conf['meanByChain'].items():lines.append(f'Chain {chain} mean pLDDT: {fmt(v)} / 100.')
 if not conf['meanByChain']:lines.append('Per-residue pLDDT: Unavailable.')
 direction=conf['directional'] or {};lines += [f"Target-row → peptide-column PAE: {fmt(direction.get('targetToPeptide'),' Å')}; peptide-row → target-column PAE: {fmt(direction.get('peptideToTarget'),' Å')}.",f"pTM: {fmt(conf['ptm'])}; ipTM: {fmt(conf['iptm'])}.",'PAE row/column orientation follows the source provider. No missing matrix was inferred from pLDDT.']+conf.get('warnings',[])
 lines+=['','## Hotspots and residue correspondence','']
 if not r['hotspots']:lines.append('No hotspot set was selected.')
 for h in r['hotspots']:lines += [f"- {h.get('name',h['chain'])} · reference {h.get('referenceNumber','not supplied')} → observed {h.get('residueId','unmapped')}: {h['state']}; minimum distance {fmt(h['minimum'],' Å')}; {h['atomPairs'] if h['atomPairs'] is not None else 'Unavailable'} atom pairs; {len(h['peptideResidues'])} distinct peptide residues."]+(['  Numbering correspondence was explicitly asserted by the user; observed amino-acid identity was checked.'] if h.get('manualConfirmed') else [])
 for chain,m in r['mappings'].items():lines.append(f"Chain {chain} mapping: {m['state']} · {m['method']} · observed identity {fmt(m.get('identity'))}. Full correspondence is included in the JSON export.")
 lines+=['','## Methods draft','',f"FOLD deterministic analysis engine {r['version']} analysed coordinate model {r['structure']['model']}. One residue-level alternate conformer was selected by highest summed occupancy; ties were resolved lexicographically. Zero-occupancy atoms and waters were omitted. Heavy-atom Euclidean contacts use distance ≤ {s['contact']} Å. Atom-pair and unique residue-pair counts were reported separately.",f"Clashes use {s['radiusMethod']} radii with overlap ≥ {s['clash']} Å (severe ≥ {s['severe']} Å), with hydrogen-bond allowance {s['hbAllowance']} Å. Native mode uses installed ChimeraX chemical atom typing and a four-bond exclusion; offline Bondi mode uses elemental radii without hydrogen-bond allowance. No source coordinates were relaxed or protonated.",f"Potential hydrogen bonds require explicit template-bonded hydrogens with donor–acceptor ≤ {s['hbondDA']} Å, H–acceptor ≤ {s['hbondHA']} Å and donor–H–acceptor ≥ {s['hbondAngle']}°. Missing-hydrogen donor/acceptor approaches remain tentative, rather than being called hydrogen bonds.",f"SASA uses elemental Bondi radii in both clash modes and Shrake–Rupley with {s['spherePoints']} deterministic Fibonacci sphere points per heavy atom and {s['probe']} Å probe. Both partners use the same point sampling. Conventional interface area is half the sum of isolated partner areas minus complex area. This is a geometric area, not an affinity measurement.",'Chemical screens, settings, mapped atom identities and source confidence hashes are included in the paired JSON export.','', '## Reproducibility and matched controls','','This single-coordinate report does not establish cross-seed reproducibility or an advantage over a control. Use saved multi-analysis comparisons and the candidate/control dashboard. Historical manually reported counts are not inputs to these calculations.','','## Evidence-calibrated interpretation','','The supplied model contains geometric contacts under the stated settings. These calculations do not establish sequence-specific binding, affinity, inhibition or therapeutic efficacy.','','## Limitations','']+['- '+l for l in r['limitations']]+['','## Scientific methods sources','','- Bondi A. van der Waals Volumes and Radii. J Phys Chem (1964), DOI: 10.1021/j100785a001.','- Shrake A, Rupley JA. Environment and exposure to solvent of protein atoms. J Mol Biol (1973), DOI: 10.1016/0022-2836(73)90011-9.','- Horn BKP. Closed-form solution of absolute orientation using unit quaternions. JOSA A (1987), DOI: 10.1364/JOSAA.4.000629.','','Export the JSON and CSV alongside this report to retain complete numerical tables and source provenance.']
 return '\n'.join(lines)


def pdf_report(r):
 """Portable PDF 1.4: paginated methods/results plus vector confidence/contact figures."""
 import textwrap
 text=report(r);replacements={'α':'alpha','π':'pi','→':'->','↔':'<->','≤':'<=','≥':'>=','–':'-','−':'-','·':' | ','°':' deg '}
 for a,b in replacements.items():text=text.replace(a,b)
 def width(value):
  return sum(10*(.92 if c in 'MW' else .74 if c.isupper() else .84 if c in 'mw' else .28 if c in ' il.,:;!|\'' else .57) for c in value)
 lines=[]
 for line in text.splitlines():
  if not line:lines.append('');continue
  current=''
  for word in line.split(' '):
   if width(word)>500:
    if current:lines.append(current);current=''
    for char in word:
     if width(current+char)>500:lines.append(current);current=''
     current+=char
   elif width(current+' '+word)>500:
    lines.append(current);current=word
   else:current+=((' ' if current else '')+word)
  if current:lines.append(current)
 streams=[]
 for start in range(0,len(lines),52):
  content='1 1 1 rg 0 0 595 842 re f 0.07 0.15 0.25 rg BT /F1 10 Tf 42 795 Td 14 TL\n'
  for line in lines[start:start+52]:
   heading=line.startswith('#');size=16 if line.startswith('# ') else 12 if heading else 10;line=line.lstrip('# ') if heading else line
   escaped=line.encode('latin1','replace').decode('latin1').replace('\\','\\\\').replace('(','\\(').replace(')','\\)');content+=('/F2 ' if heading else '/F1 ')+str(size)+' Tf ('+escaped+') Tj /F1 10 Tf T*\n'
  content+='ET\nBT /F1 8 Tf 42 25 Td (FOLD STUDIO | '+str(start//52+1)+' | '+r['id']+') Tj ET\n';streams.append(content)
 if r.get('kind')=='analysis':
  title='1 1 1 rg 0 0 595 842 re f 0.07 0.15 0.25 rg BT /F1 16 Tf 42 795 Td (Measured interface and prediction confidence) Tj ET\n'
  title+='BT /F1 8 Tf 42 774 Td ('+r['source']['sha256']+') Tj ET\n'
  target=[x for x in r['structure']['residues'] if r['assignments'].get(x['chain'],{}).get('role')=='target'];peptide=[x for x in r['structure']['residues'] if r['assignments'].get(x['chain'],{}).get('role') in ('candidate','control')];ti={x['id']:i for i,x in enumerate(target)};pi={x['id']:i for i,x in enumerate(peptide)}
  content=title+'BT /F1 10 Tf 42 748 Td (Contact map: target residue columns / peptide residue rows; observed order) Tj ET\n0.95 0.95 0.95 rg 42 500 510 230 re f\n0.65 0.2 0.6 rg\n'
  for p in r['residuePairs']:
   if p['residueA'] in ti and p['residueB'] in pi:content+=f"{42+ti[p['residueA']]*510/max(1,len(target)):.2f} {500+pi[p['residueB']]*230/max(1,len(peptide)):.2f} {max(1,510/max(1,len(target))):.2f} {max(1,230/max(1,len(peptide))):.2f} re f\n"
  content+='0 0 0 rg BT /F1 10 Tf 42 475 Td (Per-residue pLDDT: y = 0-100; x = confidence source token order) Tj ET\n'
  values=r['confidence']['plddt']
  if values:
   content+='0.1 0.4 0.7 RG 0.7 w\n'
   for i,v in enumerate(values):
    if v is not None:content+=f'{42+i*510/max(1,len(values)-1):.2f} 340 m {42+i*510/max(1,len(values)-1):.2f} {340+v:.2f} l S\n'
  else:content+='BT /F1 10 Tf 42 420 Td (pLDDT unavailable) Tj ET\n'
  matrix=r['confidence']['pae']
  content+='0 0 0 rg BT /F1 10 Tf 42 305 Td (PAE source rows/columns: dark blue 0 A to white 30+ A; asymmetric) Tj ET\n'
  if matrix:
   n=len(matrix);bins=min(n,60)
   for y in range(bins):
    for x in range(bins):
     v=min(30,matrix[int(y*n/bins)][int(x*n/bins)])/30;content+=f'{.1+.9*v:.3f} {.25+.75*v:.3f} {.5+.5*v:.3f} rg {42+x*240/bins:.2f} {40+(bins-1-y)*240/bins:.2f} {240/bins+.1:.2f} {240/bins+.1:.2f} re f\n'
  else:content+='BT /F1 10 Tf 42 270 Td (PAE unavailable; no matrix was synthesized.) Tj ET\n'
  streams.append(content)
 objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>'];kids=[]
 for stream in streams:
  page_id=len(objects)+1;content_id=page_id+1;kids.append(f'{page_id} 0 R');raw=stream.encode('latin1');objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>'.encode());objects.append(b'<< /Length '+str(len(raw)).encode()+b' >>\nstream\n'+raw+b'\nendstream')
 objects[1]=f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode();pdf=b'%PDF-1.4\n';offsets=[]
 for i,obj in enumerate(objects):offsets.append(len(pdf));pdf+=f'{i+1} 0 obj\n'.encode()+obj+b'\nendobj\n'
 xref=len(pdf);pdf+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets);pdf+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode();return pdf
