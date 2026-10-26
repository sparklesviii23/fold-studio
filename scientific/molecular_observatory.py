"""Coordinate-preserving structural discovery and polymer inspection for the UI.
No structure prediction, experimental annotation inference or model calculation.
"""
import collections,hashlib,json,math,pathlib,re,tempfile,urllib.request
from intelligence import atom_rows,cif_tokens
from polymer_identity import chemical_identity
ACTIONS={'molecular_inspect','molecular_rcsb','molecular_rcsb_search'}

def cif_categories(text,wanted):
 # A quoted value such as '_database_2.pdbx_DOI' is data, not a new tag.
 tokens=iter(cif_tokens(text,typed=True));pending=None;tables=collections.defaultdict(list)
 def take():
  nonlocal pending
  if pending is not None:value=pending;pending=None;return value
  return next(tokens,None)
 def control(item):
  return item is not None and not item[1] and (item[0].startswith(('_','data_','save_')) or item[0] in ('loop_','stop_','global_'))
 while (item:=take()) is not None:
  token,quoted=item
  if token=='loop_' and not quoted:
   columns=[];item=take()
   while item is not None and not item[1] and item[0].startswith('_'):columns.append(item[0]);item=take()
   if not columns:raise ValueError('CIF loop has no columns.')
   values=[];category=columns[0].split('.')[0]
   while item is not None and not (not values and control(item)):
    values.append(item[0])
    if len(values)==len(columns):
     if category in wanted:tables[category].append(dict(zip((c.split('.',1)[1] for c in columns),values)))
     values=[]
    item=take()
   if values:raise ValueError('Incomplete CIF category row: '+category)
   pending=item
  elif token.startswith('_') and not quoted:
   item=take()
   if item is None or control(item):raise ValueError('Missing CIF field value: '+token)
   category=token.split('.')[0]
   if category in wanted:
    if not tables[category]:tables[category].append({})
    tables[category][0][token.split('.',1)[1]]=item[0]
 return dict(tables)

def inspect_bytes(raw,fmt):
 text=raw.decode('utf-8');tables=cif_categories(text,{'_chem_comp','_entity_poly','_struct_asym','_struct','_exptl','_refine','_pdbx_struct_mod_residue'}) if fmt=='mmcif' else {}
 components={r['id']:r for r in tables.get('_chem_comp',[]) if 'id' in r}
 modified={(r.get('label_asym_id'),r.get('label_seq_id'),r.get('label_comp_id')):r.get('parent_comp_id','') for r in tables.get('_pdbx_struct_mod_residue',[])}
 entity_types={r['entity_id']:r.get('type','') for r in tables.get('_entity_poly',[]) if 'entity_id' in r}
 entity_for_chain={r['id']:r.get('entity_id') for r in tables.get('_struct_asym',[]) if 'id' in r}
 if fmt=='pdb':
  for line in text.splitlines():
   if line.startswith('MODRES') and len(line)>=27:components[line[12:15].strip()]={'id':line[12:15].strip(),'mon_nstd_parent_comp_id':line[24:27].strip()}
 raw_atoms=list(atom_rows(text,fmt))
 if not raw_atoms or len(raw_atoms)>1000000:raise ValueError('Inspect 1–1,000,000 explicit atom records; source remains unchanged.')
 if any(not all(math.isfinite(v) for v in a['xyz']+[a['occupancy']]) for a in raw_atoms):raise ValueError('Nonfinite source atom coordinates cannot be mapped.')
 models=list(dict.fromkeys(a['model'] for a in raw_atoms));chains={};residues={}
 for atom in raw_atoms:
  key=(atom['model'],atom['chain'],atom['labelChain']);chain=chains.setdefault(key,{'id':json.dumps(key,separators=(',',':')),'model':atom['model'],'authorChain':atom['chain'],'labelChain':atom['labelChain'],'residues':[],'sourceAtomCount':0});chain['sourceAtomCount']+=1
  rid=(*key,atom['num'],atom['ins'],atom['resname'])
  residue=residues.get(rid)
  if residue is None:
   residue={'id':json.dumps(rid,separators=(',',':')),'authorNumber':atom['num'],'insertionCode':atom['ins'],'labelPosition':atom['label'],'component':atom['resname'],'atomNames':set(),'alternateLocations':set(),'sourceAtomCount':0};residues[rid]=residue;chain['residues'].append(residue)
  residue['atomNames'].add(atom['name']);residue['alternateLocations'].add(atom['alt']);residue['sourceAtomCount']+=1
 for chain in chains.values():
  kinds=set();entity=entity_types.get(entity_for_chain.get(chain['labelChain']), '')
  for index,r in enumerate(chain['residues'],1):
   component=components.get(r['component'],{});r.update(chemical_identity(r['component'],component.get('type',''),component.get('mon_nstd_parent_comp_id') or modified.get((chain['labelChain'],str(r['labelPosition']),r['component']),''),entity,r['atomNames']))
   r['atomNames']=sorted(r['atomNames']);r['alternateLocations']=sorted(r['alternateLocations']);r['observedPosition']=None
   if r['polymerType']!='Unclassified':kinds.add(r['polymerType'])
  chain['polymerType']=next(iter(kinds)) if len(kinds)==1 else 'DNA/RNA hybrid' if kinds and kinds<=set(('DNA','RNA','DNA/RNA hybrid')) else 'Mixed' if kinds else 'Unclassified'
  sequence_residues=[r for r in chain['residues'] if r['polymerType']!='Unclassified']
  positions=[r['labelPosition'] for r in sequence_residues]
  ordered=bool(positions) and all(type(x)is int and x>0 for x in positions) and len(set(positions))==len(positions)
  if ordered:sequence_residues.sort(key=lambda r:r['labelPosition'])
  chain['sequenceDirection']='5′ → 3′ · source label_seq_id order' if ordered and chain['polymerType'] in ('DNA','RNA','DNA/RNA hybrid') else 'Source coordinate record order; strand direction not established'
  for i,r in enumerate(sequence_residues,1):r['observedPosition']=i
  chain['observedSequence']=''.join(r['canonicalSymbol'] or ('X' if r['polymerType']=='Protein' else 'N') for r in sequence_residues)
  chain['mappingComplete']=bool(sequence_residues) and all(r['identityResolved'] for r in sequence_residues);chain['sequenceScope']='Observed coordinate residues only; gaps, missing residues and a full transcript are not inferred.'
 return {'schemaVersion':1,'format':fmt,'sourceSha256':hashlib.sha256(raw).hexdigest(),'sourceAtomCount':len(raw_atoms),'models':models,'chains':list(chains.values()),'title':next((r.get('title') for r in tables.get('_struct',[]) if r.get('title')),None),'experimentalMethods':[r['method'] for r in tables.get('_exptl',[]) if r.get('method')],'resolutionAngstrom':[r['ls_d_res_high'] for r in tables.get('_refine',[]) if r.get('ls_d_res_high') not in (None,'.','?')],'coordinatePolicy':'Source bytes, alternate locations, occupancy, residue identity and atom coordinates are preserved. This inspection does not create or repair 3D structure.'}

def get(s,p):
 s.project(p['projectId']);row=s.db.execute('SELECT * FROM records WHERE id=? AND project_id=? AND kind=?',(p['structureId'],p['projectId'],'structure')).fetchone()
 if not row:raise ValueError('Choose a coordinate structure in this research project.')
 data=json.loads(row['data']);name=data['asset']
 if pathlib.Path(name).name!=name:raise ValueError('Invalid coordinate asset.')
 raw=(s.root/'assets'/name).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=data['sha256']:raise ValueError('Source coordinates changed; reload a verified coordinate version.')
 return data,raw

def public_json(url,payload=None,limit=2*1024**2):
 request=urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'FoldStudio-MolecularObservatory/1.0'})
 with urllib.request.urlopen(request,timeout=30) as response:
  if response.status==204:return {}
  raw=response.read(limit+1)
 if len(raw)>limit:raise ValueError('Public structure metadata exceeds its bounded response size.')
 return json.loads(raw)

def dispatch(s,action,p):
 s.project(p['projectId'])
 if action=='molecular_inspect':
  data,raw=get(s,p);folder=s.root/'observatory/polymer-metadata';folder.mkdir(parents=True,exist_ok=True);cache=folder/(data['sha256']+'.json')
  if cache.is_file():result=json.loads(cache.read_text())
  else:
   result=inspect_bytes(raw,data['format']);pending=cache.with_suffix('.pending');pending.write_text(json.dumps(result,allow_nan=False));pending.replace(cache)
  metadata=data.get('metadata',{})
  origin='computational prediction · '+data['confidenceKind'] if data.get('confidenceKind') else metadata.get('structureOrigin')
  if not origin:origin='experimental structure · source annotations' if metadata.get('evidence')=='experimental_structure' else 'experimental method reported in source file' if any(m.upper() in ('X-RAY DIFFRACTION','ELECTRON MICROSCOPY','SOLUTION NMR','SOLID-STATE NMR','NEUTRON DIFFRACTION','ELECTRON CRYSTALLOGRAPHY','FIBER DIFFRACTION') for m in result['experimentalMethods']) else 'user-supplied; experimental status not established'
  return {**result,'structureId':p['structureId'],'origin':origin,'source':data.get('source'),'sourceMetadata':metadata}
 if action=='molecular_rcsb_search':
  term=str(p.get('query','')).strip()
  if not 2<=len(term)<=160:raise ValueError('Use a 2–160 character public structure search term; no private sequence is sent.')
  query={'query':{'type':'terminal','service':'full_text','parameters':{'value':term}},'return_type':'entry','request_options':{'paginate':{'start':0,'rows':12}}}
  result=public_json('https://search.rcsb.org/rcsbsearch/v2/query',query)
  return {'source':'https://search.rcsb.org','query':term,'total':result.get('total_count',0),'structures':[r['identifier'] for r in result.get('result_set',[])]}
 if action=='molecular_rcsb':
  id=str(p.get('pdbId','')).strip().upper()
  if not re.fullmatch('[0-9][A-Z0-9]{3}',id):raise ValueError('Enter a four-character RCSB PDB structure identifier.')
  metadata=public_json('https://data.rcsb.org/rest/v1/core/entry/'+id);url='https://files.rcsb.org/download/'+id+'.cif'
  with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(100*1024**2+1)
  if len(raw)>100*1024**2 or b'_atom_site.' not in raw:raise ValueError('Coordinate file is unavailable or exceeds the bounded 100 MiB import.')
  checksum=hashlib.sha256(raw).hexdigest()
  for row in s.rows('SELECT * FROM records WHERE project_id=? AND kind=?',(p['projectId'],'structure')):
   if json.loads(row['data']).get('sha256')==checksum:return {**dict(row),'data':json.loads(row['data']),'reused':True}
  methods=[r.get('method') for r in metadata.get('exptl',[])];origin='experimental' if methods else 'unspecified'
  with tempfile.TemporaryDirectory(prefix='fold-public-structure-') as tmp:
   path=pathlib.Path(tmp)/(id+'.cif');path.write_bytes(raw)
   return s.import_structure({'projectId':p['projectId'],'path':str(path),'name':id+' · '+metadata.get('struct',{}).get('title','RCSB PDB'),'source':url,'metadata':{'pdbId':id,'structureOrigin':origin,'rcsb':metadata,'metadataSource':'https://data.rcsb.org/rest/v1/core/entry/'+id}})
 raise ValueError('Unsupported molecular observatory operation.')
