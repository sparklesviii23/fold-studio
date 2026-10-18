"""Explicit coordinate-preserving protein fragments for bounded design workflows.
No sequence completion, relaxation, capping or biological-numbering inference.
"""
import hashlib,json,pathlib,re,tempfile

def token(value):
 value=str(value)
 if not value or any(c.isspace() for c in value) or value[0] in '#_$;[]' or value in ('.','?') or any(c in value for c in "\"'"):
  if '\n' in value or '\r' in value or ('"' in value and "'" in value):raise ValueError('Unsupported coordinate identifier.')
  return ('"'+value+'"') if '"' not in value else ("'"+value+"'")
 return value

def create(engine,p):
 import fold_engine as fe
 mi=fe.mi
 if set(p)-{'projectId','structureId','residues','name'}:raise ValueError('Unsupported target-fragment field.')
 shared=engine.fold_structure(p);st=shared['structure'];record,path=engine.lab.record(p['structureId'])
 ids=p.get('residues')
 if not isinstance(ids,list) or not ids or len(ids)>600 or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):raise ValueError('Choose 1–600 distinct observed target residues.')
 selected=set(ids);by_id={r['id']:r for r in st['residues']}
 if selected-set(by_id):raise ValueError('Fragment residues must belong to the selected source structure.')
 residues=[r for r in st['residues'] if r['id'] in selected];chains={r['chain'] for r in residues}
 if len(st['models'])!=1:raise ValueError('Choose a source with one explicit coordinate model.')
 if any(not r['polymer'] or r['one']=='X' or r['ins'] or r['num']<1 or not re.fullmatch('[A-Za-z]',r['chain']) for r in residues):raise ValueError('Target fragments currently require canonical protein residues, positive author numbers, one-letter chains and no insertion codes.')
 for chain in chains:
  observed=[r for r in st['residues'] if r['chain']==chain];indices=[i for i,r in enumerate(observed) if r['id'] in selected]
  if indices!=list(range(indices[0],indices[-1]+1)):raise ValueError('Select one contiguous observed segment per chain; disjoint patches would introduce artificial sequence joins.')
  numbers=[r['num'] for r in residues if r['chain']==chain]
  if any(b!=a+1 for a,b in zip(numbers,numbers[1:])):raise ValueError('Selected residues contain an author-numbering gap. Prepare each continuous segment explicitly.')
 for r in residues:
  if not {'N','CA','C','O'}.issubset(st['atoms'][i]['name'] for i in r['atoms']):raise ValueError('Selected fragment residues need complete N, CA, C, O backbones.')
 raw_atoms=list(mi.atom_rows(path.read_text(),record['data']['format']));wanted={(r['chain'],r['num'],r['ins']) for r in residues}
 if any(a['alt'] or a['occupancy']<=0 for a in raw_atoms if (a['chain'],a['num'],a['ins']) in wanted):raise ValueError('Resolve alternate conformers and zero occupancies before extracting this segment.')
 atoms=[a for a in st['atoms'] if a['residue'] in selected]
 # Preserve author and label residue identities and full parsed coordinate precision.
 # This minimal transport intentionally carries no parent whole-complex metrics.
 columns=['group_PDB','id','type_symbol','label_atom_id','label_alt_id','label_comp_id','label_asym_id','label_entity_id','label_seq_id','pdbx_PDB_ins_code','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv','auth_seq_id','auth_comp_id','auth_asym_id','auth_atom_id','pdbx_PDB_model_num']
 chain_order=list(dict.fromkeys(a['chain'] for a in atoms));entity={c:i+1 for i,c in enumerate(chain_order)};labels={}
 for chain in chain_order:
  for i,r in enumerate((r for r in residues if r['chain']==chain),1):labels[r['id']]=r['label'] if r['label'] is not None else i
 lines=['data_fold_target_fragment','#','loop_']+['_atom_site.'+c for c in columns]
 for i,a in enumerate(atoms,1):
  values=[a['group'],i,a['element'],token(a['name']),'.',token(a['resname']),token(a['labelChain']),entity[a['chain']],labels[a['residue']],'?',*(repr(v) for v in a['xyz']),repr(a['occupancy']),repr(a['bfactor']) if a['bfactor'] is not None else '?',a['num'],token(a['resname']),token(a['chain']),token(a['name']),a['model']]
  lines.append(' '.join(map(str,values)))
 raw=('\n'.join(lines)+'\n#\n').encode();derived=mi.parse_structure(raw.decode(),'mmcif')
 signature=lambda a:(a['chain'],a['num'],a['ins'],a['resname'],a['name'],a['element'],a['xyz'],a['occupancy'],a['bfactor'])
 if [signature(a) for a in atoms]!=[signature(a) for a in derived['atoms']]:raise ValueError('Fragment serialization changed observed atom identities, coordinates or confidence fields.')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=record['data']['sha256']:raise ValueError('Source coordinate asset changed during extraction.')
 name=p.get('name',record['name']+' · target fragment')
 if not isinstance(name,str) or not name.strip() or len(name)>160:raise ValueError('Enter a fragment name of 1–160 characters.')
 ranges=[{'chain':chain,'start':min(r['num'] for r in residues if r['chain']==chain),'end':max(r['num'] for r in residues if r['chain']==chain)} for chain in chain_order]
 metadata={'derivedFrom':{'id':record['id'],'sha256':record['data']['sha256']},'fragment':{'schemaVersion':1,'residueIds':[r['id'] for r in residues],'ranges':ranges,'coordinatePreservation':'Exact parsed coordinate values and author residue identities retained.','sourceFormat':record['data']['format'],'parentConfidenceTransferred':'Per-atom field with its existing confidence interpretation only. Parent PAE, pTM, ipTM and interface metrics are not copied.','limitations':['Explicit geometric fragment; removed protein context can change folding, surface exposure and binding.','Artificial termini are not capped or protonated; no atoms, residues or sequence positions are invented.','This selection does not establish a biological domain or mature-protein numbering.']}}
 with tempfile.TemporaryDirectory(prefix='fragment-',dir=engine.s.root) as tmp:
  file=pathlib.Path(tmp)/'fragment.cif';file.write_bytes(raw)
  imported=engine.s.import_structure({'projectId':record['project_id'],'path':str(file),'name':name.strip(),'source':'Explicit observed target fragment','confidenceKind':record['data'].get('confidenceKind'),'metadata':metadata})
 assignments={chain:value for chain,value in engine.lab.assigned(record['id']).items() if chain in chains}
 if assignments:engine.lab.intelligence_assign({'structureId':imported['id'],'assignments':assignments})
 return imported
